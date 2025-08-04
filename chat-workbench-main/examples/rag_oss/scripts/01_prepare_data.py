# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Prepare textract-extracted data for RAG processing."""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter

# Removed pdfplumber since we're processing textract .txt files
from langchain_aws import BedrockEmbeddings

HERE = Path(__file__).resolve()
DATA_DIR = HERE.parents[1] / 'data'
OUTPUT_DIR = DATA_DIR
EMBEDDINGS_FILE = OUTPUT_DIR / 'embeddings.jsonl'

# Setup logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)


def load_documents() -> dict[str, list[dict[str, Any]]]:
    """Load textract-extracted documents from .txt files."""
    paths = list(DATA_DIR.glob('*.txt'))
    logging.info(f'Found {len(paths)} textract .txt documents to process')

    documents: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        logging.info(f'Loading document: {path.name}')
        try:
            with open(path, encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                logging.warning(f'Empty document: {path.name}')
                continue

            # Store the full text content for processing
            documents[path.stem] = content

            logging.info(f'Loaded {len(content)} characters from {path.name}')

        except Exception as e:
            logging.error(f'Failed to load {path.name}: {e}')
            continue

    return documents


def split_document(
    *,
    text: str,
    document_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    """Splits document using LangChain RecursiveCharacterTextSplitter."""
    if not text or not text.strip():
        return []

    # Initialize the text splitter with character-based chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,  # Use character count instead of token count
        separators=[
            '\n\n',
            '\n',
            '. ',
            ' ',
            '',
        ],  # Split on paragraphs, lines, sentences, words
        is_separator_regex=False,
    )

    # Split the text into chunks
    text_chunks = text_splitter.split_text(text)

    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        if chunk_text.strip():  # Only include non-empty chunks
            chunks.append(
                {
                    'text': chunk_text.strip(),
                    'page_numbers': [1],  # Default to page 1 for textract files
                    'quality_score': 1.0,  # Default quality score
                    'document_name': document_name,
                    'chunk_index': i,
                }
            )

    return chunks


def cli() -> argparse.Namespace:
    """Command-line interface (CLI)."""
    parser = argparse.ArgumentParser(description='Prepare RAG data with embeddings')

    parser.add_argument(
        '--model',
        type=str,
        default='amazon.titan-embed-text-v2:0',
        choices=['amazon.titan-embed-text-v2:0'],
        help='Embedding model to use',
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Maximum characters per chunk',
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=200,
        help='Character overlap between chunks',
    )
    parser.add_argument(
        '--maximum-concurrency',
        type=int,
        default=25,
        help='Maximum concurrency for async processing',
    )

    args = parser.parse_known_args()[0]

    return args


def load_existing_embeddings(model_id: str) -> dict:
    """Load existing embeddings from JSONL file for specific model."""
    cache = {}
    if EMBEDDINGS_FILE.exists():
        try:
            with open(EMBEDDINGS_FILE) as f:
                for line in f:
                    record = json.loads(line.strip())
                    # Only load if embedding exists AND matches current model
                    if (
                        record.get('embedding') is not None
                        and record.get('model_id') == model_id
                    ):
                        cache[record['id']] = record
            logging.info(
                f'Loaded {len(cache)} existing embeddings for model {model_id}'
            )
        except Exception as e:
            logging.warning('Failed to load existing embeddings: %s', e)
    return cache


async def process_chunk_with_semaphore(
    semaphore: asyncio.Semaphore, embeddings: BedrockEmbeddings, chunk: dict
) -> dict:
    """Process a single chunk with rate limiting."""
    async with semaphore:
        try:
            # Generate embedding using async method
            embedding = await embeddings.aembed_query(chunk['text'])
            chunk['embedding'] = embedding
            logging.debug(f'Generated embedding for chunk {chunk["id"]}')
            return chunk
        except Exception as e:
            logging.error(
                'Failed to generate embedding for chunk %s: %s', chunk['id'], e
            )
            raise


def build_output_record(chunk: dict, model_id: str) -> dict:
    """Build standardized output record for a chunk."""
    return {
        'id': chunk['id'],
        'text': chunk['text'],
        'embedding': chunk.get('embedding'),
        'model_id': model_id,
        'metadata': {
            'document_name': chunk['document_name'],
            'page_numbers': chunk['page_numbers'],
            'quality_score': chunk['quality_score'],
            'token_count': len(chunk['text'].split()),
            'chunk_index': int(chunk['id'].split('_')[-1]),
        },
    }


def write_complete_embeddings_file(
    cache: dict, all_chunks: list, model_id: str
) -> None:
    """Write complete JSONL file with all chunks (replaces any existing file)."""
    try:
        with open(EMBEDDINGS_FILE, 'w') as f:
            for chunk in all_chunks:
                # Use cached version if available (has embedding), otherwise original chunk
                output_chunk = cache.get(chunk['id'], chunk)

                output_record = build_output_record(output_chunk, model_id)
                f.write(json.dumps(output_record) + '\n')

        embedded_count = sum(1 for chunk in all_chunks if chunk['id'] in cache)
        logging.info(
            f'Written {len(all_chunks)} total chunks ({embedded_count} with embeddings) to {EMBEDDINGS_FILE}'
        )
    except Exception as e:
        logging.error('Failed to write embeddings file: %s', e)


async def main() -> None:
    """Entrypoint."""
    start_time = time.time()
    logging.info('Starting data preparation script...')

    args = cli()

    documents = load_documents()

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Load existing embeddings for this specific model
    cache = load_existing_embeddings(args.model)

    # Initialize embeddings model
    embeddings = BedrockEmbeddings(
        model_id=args.model,
        region_name='us-east-1',
    )

    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(args.maximum_concurrency)

    # Collect all chunks with unique IDs
    all_chunks = []
    for document_name, text_content in documents.items():
        chunks = split_document(
            text=text_content,
            document_name=document_name,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        for chunk in chunks:
            chunk_id = f'{document_name}_{chunk["chunk_index"]}'
            chunk['id'] = chunk_id
            all_chunks.append(chunk)

    logging.info(f'Processing {len(all_chunks)} chunks')

    # Process chunks with embeddings
    tasks = []
    for chunk in all_chunks:
        if chunk['id'] not in cache:
            task = process_chunk_with_semaphore(semaphore, embeddings, chunk)
            tasks.append(task)
        else:
            logging.info(f'Using cached embedding for chunk {chunk["id"]}')

    # Process in batches with asyncio.as_completed
    if tasks:
        results = []
        completed_count = 0
        for coro in asyncio.as_completed(tasks):
            try:
                processed_chunk = await coro
                results.append(processed_chunk)
                cache[processed_chunk['id']] = processed_chunk

                completed_count += 1
                if completed_count % 10 == 0:
                    logging.info(f'Processed {completed_count}/{len(tasks)} chunks')

                # Write to disk after processing at least max_concurrency chunks
                if completed_count % args.maximum_concurrency == 0:
                    logging.info(f'Saving progress after {completed_count} chunks...')
                    write_complete_embeddings_file(cache, all_chunks, args.model)
            except Exception as e:
                logging.error('Error processing chunk: %s', e)

    # Ensure any remaining chunks are written to disk
    logging.info('Writing final embeddings file...')
    write_complete_embeddings_file(cache, all_chunks, args.model)

    end_time = time.time()
    total_time = end_time - start_time
    logging.info(
        f'Data preparation completed successfully in {total_time:.2f} seconds ({total_time / 60:.1f} minutes)'
    )


if __name__ == '__main__':
    asyncio.run(main())
