# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Knowledge base retrieval functionality for chat."""

import json
import os
import time
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field
from strands import tool

from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.opensearch.client import OpenSearchClient
from app.utils import generate_nanoid

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'amazon.titan-embed-text-v2:0')
OPENSEARCH_INDEX = os.getenv('OPENSEARCH_INDEX', 'documents')

# Module-level client registry for tools
_clients_registry = None


def set_clients(opensearch_client, bedrock_client):
    """Set clients for tools to use - called by handler during initialization"""
    global _clients_registry
    _clients_registry = {'opensearch': opensearch_client, 'bedrock': bedrock_client}
    logger.debug('Knowledge base tool clients initialized')


def get_clients():
    """Get clients for tool use"""
    if not _clients_registry:
        raise RuntimeError('Clients not initialized for knowledge base tools')
    return _clients_registry['opensearch'], _clients_registry['bedrock']


class DocumentResult(BaseModel):
    """Document search result model."""

    document_id: str
    score: float
    title: str
    source: dict[str, Any]


class ChunkResult(BaseModel):
    """Document chunk search result model."""

    chunk_id: str
    document_id: str
    content: str
    section_title: Optional[str] = None
    page_num: Optional[int] = None
    additional_fields: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Search request parameters."""

    keyword_queries: list[str] = Field(default_factory=list)
    semantic_query: Optional[str] = None
    max_results: int = 3


class SearchResponse(BaseModel):
    """Combined search response with documents and chunks."""

    documents: list[DocumentResult] = Field(default_factory=list)
    chunks: list[ChunkResult] = Field(default_factory=list)


async def generate_embedding(
    bedrock_client: BedrockRuntimeClient, model_id: str, text: str
) -> list[float]:
    """
    Generate embeddings for text using Bedrock embeddings.

    Args:
        bedrock_client: Initialized Bedrock client
        model_id: Embedding model ID
        text: Text to embed

    Returns:
        List of embedding values
    """
    if not text or text.strip() == '':
        return [0.0] * 1024  # Return zero vector

    # Truncate text if too long
    if len(text) > 8000:
        text = text[:8000]

    try:
        # Get sync client for synchronous operations
        client = await bedrock_client.get_sync_client()

        request_body = json.dumps(
            {
                'inputText': text,
            }
        )

        response = client.invoke_model(modelId=model_id, body=request_body)

        response_body = json.loads(response.get('body').read())
        embedding = response_body.get('embedding')
        return embedding
    except Exception as e:
        logger.error('Error generating embedding: {error}', error=str(e))
        # Return zero vector in case of error
        return [0.0] * 1024


async def search_knowledge_base(
    opensearch_client: OpenSearchClient,
    bedrock_client: BedrockRuntimeClient,
    search_request: SearchRequest,
) -> SearchResponse:
    """
    Search for documents and chunks in the knowledge base.

    Args:
        opensearch_client: Initialized OpenSearch client
        bedrock_client: Initialized Bedrock client
        search_request: Search parameters

    Returns:
        Combined search results with documents and chunks
    """
    results = SearchResponse()

    try:
        # Check if OpenSearch client is available
        os_client = opensearch_client.get_client()

        # Generate embedding for semantic search if requested
        semantic_vector = None
        if search_request.semantic_query:
            semantic_vector = await generate_embedding(
                bedrock_client, EMBEDDING_MODEL, search_request.semantic_query
            )

        # Search the unified index for chunks with embeddings
        search_queries: list[dict[str, Any]] = []

        # Add vector search if available
        if semantic_vector:
            search_queries.append(
                {
                    'knn': {
                        'embedding': {
                            'vector': semantic_vector,
                            'k': search_request.max_results * 2,
                        }
                    }
                }
            )

        # Add keyword queries for text content
        for keyword_query in search_request.keyword_queries:
            if keyword_query:
                search_queries.append(
                    {'match': {'text': {'query': keyword_query, 'fuzziness': 'AUTO'}}}
                )

        # Only search if we have queries
        if search_queries:
            # Build the search query
            search_body = {
                'size': search_request.max_results,
                'query': {
                    'bool': {
                        'should': search_queries,
                        'minimum_should_match': 1,
                    }
                },
                '_source': True,
            }

            # Execute search
            try:
                response = os_client.search(body=search_body, index=OPENSEARCH_INDEX)

                # Process results as chunks
                for hit in response.get('hits', {}).get('hits', []):
                    source = hit.get('_source', {})
                    metadata = source.get('metadata', {})

                    # Extract and explicitly type each field
                    # Get chunk_id from metadata.chunk_index or fall back to _id
                    chunk_id = str(metadata.get('chunk_index', hit.get('_id', '')))

                    # Get document_id from metadata.document_name or fall back to unknown
                    document_id = str(metadata.get('document_name', 'unknown'))

                    # Get content from text field
                    content = str(source.get('text', ''))

                    # Handle optional fields with proper typing
                    section_title: Optional[str] = None
                    if metadata.get('title') is not None:
                        section_title = str(metadata.get('title'))

                    page_num: Optional[int] = None
                    if metadata.get('page_numbers') is not None:
                        try:
                            page_num = int(metadata.get('page_numbers'))
                        except (ValueError, TypeError):
                            logger.debug(
                                'Invalid page number: {page_num}',
                                page_num=metadata.get('page_numbers'),
                            )
                            pass

                    # Build additional fields dictionary
                    additional_fields: dict[str, Any] = {}

                    # Add model_id and created_at from top level
                    if source.get('model_id'):
                        additional_fields['model_id'] = source.get('model_id')
                    if source.get('created_at'):
                        additional_fields['created_at'] = source.get('created_at')

                    # Add any remaining metadata fields
                    for k, v in metadata.items():
                        if k not in [
                            'chunk_index',
                            'document_name',
                            'title',
                            'page_numbers',
                        ]:
                            additional_fields[k] = v

                    # Create ChunkResult with explicit parameters
                    chunk_result = ChunkResult(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        content=content,
                        section_title=section_title,
                        page_num=page_num,
                        additional_fields=additional_fields,
                    )
                    results.chunks.append(chunk_result)

                logger.info(f'Found {len(results.chunks)} chunks')
            except Exception as e:
                logger.error('Error searching index: {error}', error=str(e))

        return results

    except Exception as e:
        logger.error('Error in knowledge base search: {error}', error=str(e))
        return results


async def get_document_by_id(
    opensearch_client: OpenSearchClient, document_id: str
) -> Optional[dict[str, Any]]:
    """
    Retrieve a specific document by ID.

    Args:
        opensearch_client: Initialized OpenSearch client
        document_id: Document ID to retrieve

    Returns:
        Document data if found, None otherwise
    """
    try:
        os_client = opensearch_client.get_client()

        # Search for the document by ID using the metadata.document_name field
        response = os_client.search(
            index=OPENSEARCH_INDEX,
            body={'query': {'term': {'metadata.document_name': document_id}}},
        )

        # Check if document was found
        if response['hits']['total']['value'] == 0:
            # Try fallback to old schema if not found
            response = os_client.search(
                index=OPENSEARCH_INDEX,
                body={'query': {'term': {'document_id': document_id}}},
            )

            if response['hits']['total']['value'] == 0:
                return None

        # Return the document
        return response['hits']['hits'][0]['_source']
    except Exception as e:
        logger.error('Error retrieving document: {error}', error=str(e))
        return None


# Status update tool function
@tool
def status_update(status: str) -> str:
    """
    A progress update on how the research plan is going

    Args:
        status (str): The status update to report

    Returns:
        The status content
    """
    # Check if the status is already a JSON string
    if status.strip().startswith('{') and status.strip().endswith('}'):
        try:
            # Try to parse and enhance the JSON
            status_obj = json.loads(status)

            # Ensure it has a title field
            if 'title' not in status_obj:
                # Generate a title from the text if available
                if 'text' in status_obj:
                    status_obj['title'] = status_obj['text'][:50] + (
                        '...' if len(status_obj['text']) > 50 else ''
                    )
                else:
                    status_obj['title'] = 'Processing research'

            # Return the enhanced JSON
            return json.dumps(status_obj)
        except json.JSONDecodeError:
            # If it looks like JSON but isn't valid, wrap it in a proper structure
            logger.warning(f'Invalid JSON in status_update: {status}')
            return json.dumps({'text': status, 'title': 'Processing research'})

    # For simple string status, create a proper JSON structure
    return json.dumps(
        {
            'text': status,
            'title': status[:50] + ('...' if len(status) > 50 else ''),
            'phase': 'progress',
        }
    )


@tool
def add_document(title: str, source: str, document_id: str, summary: str = '') -> str:
    """
    Add a document to the research context and notify the UI.

    Use this tool when you have found specific documents during your research
    that should be displayed in the status panel's "Reading sources" section.

    Args:
        title: Document title
        source: Document source/URL or identifier
        document_id: Unique document identifier
        summary: Optional document summary or description

    Returns:
        Success message (DocumentEvent will be generated on tool completion)
    """
    try:
        tool_id = generate_nanoid()
    except Exception as e:
        logger.debug(f'Error generating nanoid: {e}')
        tool_id = 'add_doc_' + str(int(time.time()))

    logger.info(f'[TOOL:ADD_DOCUMENT:{tool_id}] Adding document: {title}')
    logger.debug(
        f'[TOOL:ADD_DOCUMENT:{tool_id}] Document details: id={document_id}, source={source}'
    )

    return f"Document '{title}' added to reading sources"


# Citation tool for emitting citation events
@tool
def add_citation(
    document_id: str,
    text: str,
    page: Optional[int] = None,
    section: Optional[str] = None,
    document_title: Optional[str] = None,
) -> str:
    """
    Add a citation reference for specific research content.

    Args:
        document_id: The ID of the source document
        text: The text content being cited
        page: Page number where the content appears
        section: Section or chapter name
        document_title: Title of the source document

    Returns:
        Confirmation message
    """
    logger.info(f'Citation added for document {document_id}')
    return f'Citation added for document {document_id}'


@tool
def knowledge_base_search(
    keyword_queries: Optional[list[str]] = None,
    semantic_query: Optional[str] = None,
    max_results: int = 3,
) -> str:
    """
    Search the knowledge base for relevant documents and passages.

    Args:
        keyword_queries: List of keyword queries to search for
        semantic_query: Natural language query for semantic search
        max_results: Maximum number of results to return

    Returns:
        Formatted search results with documents and relevant passages
    """
    if keyword_queries is None:
        keyword_queries = []
    opensearch_client, bedrock_runtime_client = get_clients()

    logger.info(
        f'Searching knowledge base with query: {semantic_query or keyword_queries}'
    )

    # Convert max_results to int to handle Decimal types from Strands
    max_results = int(max_results) if max_results is not None else 3

    # Create search request
    request = SearchRequest(
        keyword_queries=keyword_queries if keyword_queries else [],
        semantic_query=semantic_query,
        max_results=max_results,
    )

    # Execute async search within sync tool context
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        # Define async search coroutine
        async def perform_async_search():
            return await search_knowledge_base(
                opensearch_client, bedrock_runtime_client, request
            )

        # Try to handle async call from sync context
        try:
            # Check if we're in an async context already
            asyncio.get_running_loop()
            # We're in an async context, need to be careful
            # Use run_in_executor to avoid blocking the current loop
            with ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(perform_async_search()))
                search_results = future.result(timeout=30)  # 30 second timeout
        except RuntimeError:
            # No running loop, safe to use asyncio.run directly
            search_results = asyncio.run(perform_async_search())

    except Exception as e:
        logger.error(f'Error in search execution: {e}', exc_info=True)
        # Return empty results on error
        search_results = SearchResponse()

    # Format results for display
    formatted_results = format_search_results(search_results)
    return formatted_results


def format_search_results(search_results: SearchResponse) -> str:
    """
    Format search results for display in chat.

    Args:
        search_results: Search response with documents and chunks

    Returns:
        Formatted string for display
    """
    output = []

    if not search_results.documents and not search_results.chunks:
        return 'No relevant documents or information found.'

    # Format documents
    if search_results.documents:
        output.append('## Documents')
        for i, doc in enumerate(search_results.documents, 1):
            output.append(f'### {i}. {doc.title}')

            # Add document metadata
            metadata = doc.source.get('metadata', {})

            # Document name
            if metadata.get('document_name'):
                output.append(f'**Document Name:** {metadata.get("document_name")}')

            # Quality score if available
            if metadata.get('quality_score') is not None:
                output.append(f'**Quality Score:** {metadata.get("quality_score")}')

            # Token count if available
            if metadata.get('token_count') is not None:
                output.append(f'**Token Count:** {metadata.get("token_count")}')

            output.append(f'**Document ID:** {doc.document_id}')
            output.append('')  # Add space between documents

    # Format chunks
    if search_results.chunks:
        output.append('## Relevant Passages')
        for i, chunk in enumerate(search_results.chunks, 1):
            # Use section_title if available, otherwise use a generic title
            if chunk.section_title:
                output.append(f'### {i}. {chunk.section_title}')
            else:
                output.append(f'### {i}. Passage from document {chunk.document_id}')

            # Display page number if available
            if chunk.page_num:
                output.append(f'**Page:** {chunk.page_num}')

            # Display quality score if available in additional_fields
            if chunk.additional_fields.get('quality_score') is not None:
                output.append(
                    f'**Quality Score:** {chunk.additional_fields.get("quality_score")}'
                )

            # Display token count if available
            if chunk.additional_fields.get('token_count') is not None:
                output.append(
                    f'**Token Count:** {chunk.additional_fields.get("token_count")}'
                )

            # Add content with context
            output.append(f'\n{chunk.content}\n')

            # Add source reference
            output.append(f'**Source:** Document {chunk.document_id}')

            # Add model ID if available
            if chunk.additional_fields.get('model_id'):
                output.append(f'**Model:** {chunk.additional_fields.get("model_id")}')

            output.append('')  # Add space between chunks

    return '\n'.join(output)
