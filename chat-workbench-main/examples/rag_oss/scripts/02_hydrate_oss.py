# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Hydrate OpenSearch Serverless with embeddings from 01_prepare_data.py"""

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from opensearchpy import (
    AsyncHttpConnection,
    AsyncOpenSearch,
    AWSV4SignerAsyncAuth,
    helpers,
)
from opensearchpy.exceptions import AuthorizationException

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve()
DATA_DIR = HERE.parents[1] / 'data'
EMBEDDINGS_FILE = DATA_DIR / 'embeddings.jsonl'

INDEX_MAPPING = {
    'settings': {
        'knn': True,
        'knn.algo_param.ef_search': 512,
    },
    'mappings': {
        'properties': {
            'text': {'type': 'text'},
            'embedding': {
                'type': 'knn_vector',
                'dimension': 1024,
                'method': {
                    'name': 'hnsw',
                    'space_type': 'l2',
                    'engine': 'faiss',
                    'parameters': {
                        'ef_construction': 512,
                        'm': 16,
                    },
                },
            },
            'model_id': {'type': 'keyword'},
            'metadata': {
                'type': 'object',
                'properties': {
                    'document_name': {'type': 'keyword'},
                    'page_numbers': {'type': 'integer'},
                    'quality_score': {'type': 'float'},
                    'token_count': {'type': 'integer'},
                    'chunk_index': {'type': 'integer'},
                },
            },
            'created_at': {'type': 'date'},
        },
    },
}


class OpenSearchManager:
    """OpenSearch connection manager (local or AWS Serverless)."""

    def __init__(
        self,
        host: str,
        port: int | None = None,
        region: str = 'us-west-2',
        batch_size: int = 100,
        max_retries: int = 5,
    ) -> None:
        self.host = host
        self.region = region
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.cached_client = None
        self.client_creation_time = 0.0
        self.client_ttl = 1800  # 30 minutes

        # Detect if this is local or AWS based on hostname
        self.is_local = host in ['localhost', '127.0.0.1'] or host.startswith(
            'localhost:'
        )

        if self.is_local:
            self.port = port or 9200
            self.service = None
            logger.info(f'Configured for local OpenSearch: {host}:{self.port}')
        else:
            self.port = port or 443
            self.service = 'aoss'
            logger.info(f'Configured for AWS OpenSearch Serverless: {host}:{self.port}')

    @property
    def client(self) -> AsyncOpenSearch:
        """Create OpenSearch client with appropriate auth."""
        if not self.cached_client or (
            (time.time() - self.client_creation_time) > self.client_ttl
        ):
            logger.info('Creating new OpenSearch client connection')

            if self.is_local:
                # Local OpenSearch - no auth needed
                self.cached_client = AsyncOpenSearch(
                    hosts=[{'host': self.host, 'port': self.port}],
                    use_ssl=False,
                    verify_certs=False,
                    timeout=60,
                    max_retries=self.max_retries,
                )
            else:
                # AWS OpenSearch Serverless - needs AWS auth
                credentials = boto3.Session().get_credentials().get_frozen_credentials()
                awsauth = AWSV4SignerAsyncAuth(
                    credentials,
                    self.region,
                    self.service,
                )

                self.cached_client = AsyncOpenSearch(
                    hosts=[{'host': self.host, 'port': self.port}],
                    http_auth=awsauth,
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=AsyncHttpConnection,
                    timeout=60,
                    max_retries=self.max_retries,
                )

            self.client_creation_time = time.time()
        return self.cached_client

    async def delete_index(self, index: str) -> dict[str, Any]:
        """Delete an OpenSearch index."""
        try:
            result = await self.client.indices.delete(
                index=index, ignore_unavailable=True
            )
            logger.info(f"Successfully deleted index '{index}'")
            return {'deleted': True, 'result': result}
        except AuthorizationException as e:
            logger.warning(
                f"No permissions to delete index '{index}' - will skip deletion: {e}"
            )
            return {'deleted': False, 'reason': 'no_permissions'}
        except Exception as e:
            logger.error("Failed to delete index '%s': %s", index, e)
            return {'deleted': False, 'reason': 'error', 'error': str(e)}

    async def create_index_if_not_exists(
        self, index: str, index_mapping: dict[str, Any]
    ) -> dict[str, Any]:
        """Ensure that an OpenSearch index exists, create if it does not."""
        try:
            exists = await self.client.indices.exists(index=index)
            if not exists:
                # Create index with proper error handling
                create_response = await self.client.indices.create(
                    index=index, body=index_mapping
                )
                logger.info(
                    f"Created new index '{index}' - Response: {create_response}"
                )
                await asyncio.sleep(5)  # Give index time to initialize
                return {
                    'exists': False,
                    'created': True,
                    'index': index,
                }

            logger.info(f"Index '{index}' already exists")
            return {
                'exists': True,
                'created': False,
                'index': index,
            }

        except Exception as e:
            logger.error("Error creating index '%s': %s", index, e)
            return {
                'exists': False,
                'created': False,
                'index': index,
                'error': str(e),
                'error_type': type(e).__name__,
            }

    async def bulk_upload(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk upload documents to OpenSearch."""
        if not data:
            return {
                'total_success': 0,
                'total_failed': 0,
                'failed_items': [],
            }

        total_success = 0
        failed_items = []

        try:
            # Process in batches
            for i in range(0, len(data), self.batch_size):
                batch = data[i : i + self.batch_size]

                try:
                    success, failed = await helpers.async_bulk(
                        self.client,
                        batch,
                        request_timeout=60,
                        raise_on_error=False,
                        stats_only=False,
                    )
                    total_success += success
                    if failed:
                        failed_items.extend(failed)
                except Exception as e:
                    logger.error('Batch upload failed: %s', e)
                    failed_items.extend(
                        [
                            {'index': item.get('_index'), 'error': str(e)}
                            for item in batch
                        ]
                    )

            return {
                'total_success': total_success,
                'total_failed': len(failed_items),
                'failed_items': failed_items,
            }

        except Exception as e:
            logger.error('Bulk upload failed completely: %s', e)
            return {
                'total_success': total_success,
                'total_failed': len(data) - total_success,
                'failed_items': [{'error': str(e)}],
            }

    async def close(self):
        """Close the OpenSearch client."""
        if self.cached_client:
            await self.cached_client.close()


def load_embeddings_data(file_path: Path, index_name: str) -> list[dict[str, Any]]:
    """Load all embeddings data from JSONL file."""
    documents = []

    if not file_path.exists():
        logger.error(f'Embeddings file not found: {file_path}')
        return documents

    try:
        with open(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())

                    # Skip records without embeddings
                    if not record.get('embedding'):
                        logger.warning(
                            f'Skipping record without embedding on line {line_num}'
                        )
                        continue

                    # Prepare document for OpenSearch
                    doc = {
                        '_op_type': 'index',
                        '_index': index_name,
                        '_source': {
                            'text': record['text'],
                            'embedding': record['embedding'],
                            'model_id': record['model_id'],
                            'metadata': record['metadata'],
                            'created_at': datetime.now().isoformat(),
                        },
                    }
                    documents.append(doc)

                except json.JSONDecodeError as e:
                    logger.warning(f'Skipping invalid JSON on line {line_num}: {e}')
                    continue
                except Exception as e:
                    logger.warning(f'Skipping record on line {line_num}: {e}')
                    continue

        logger.info(f'Loaded {len(documents)} documents from {file_path}')

    except Exception as e:
        logger.error('Failed to load embeddings data: %s', e)

    return documents


def cli() -> argparse.Namespace:
    """Command-line interface."""
    parser = argparse.ArgumentParser(description='Hydrate OpenSearch with embeddings')

    parser.add_argument(
        '--host',
        type=str,
        required=True,
        help='OpenSearch host (localhost for local or your-endpoint.aoss.amazonaws.com for AWS)',
    )
    parser.add_argument(
        '--port',
        type=int,
        help='OpenSearch port (defaults: 9200 for local, 443 for AWS)',
    )
    parser.add_argument(
        '--region-name', type=str, default='us-west-2', help='AWS region'
    )
    parser.add_argument(
        '--index',
        type=str,
        default='documents',
        help='OpenSearch index name',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for bulk uploads',
    )

    return parser.parse_args()


async def main() -> None:
    """Main entrypoint."""
    start_time = time.time()
    logger.info('Starting OpenSearch hydration script...')

    args = cli()

    # Load embeddings data
    logger.info(f'Loading embeddings from {EMBEDDINGS_FILE}')
    documents = load_embeddings_data(EMBEDDINGS_FILE, args.index)

    if not documents:
        logger.error('No documents found to index')
        return

    logger.info(f'Found {len(documents)} documents to index')

    # Initialize OpenSearch manager
    manager = OpenSearchManager(
        host=args.host,
        port=args.port,
        region=args.region_name,
        batch_size=args.batch_size,
    )

    try:
        # Always delete existing index and recreate with fresh data
        logger.info(f"Deleting existing index '{args.index}' if it exists...")
        delete_result = await manager.delete_index(args.index)

        if delete_result['deleted']:
            # Wait a bit for deletion to propagate
            logger.info('Waiting 10 seconds for index deletion to complete...')
            await asyncio.sleep(10)
        else:
            logger.info(
                f'Index deletion skipped: {delete_result.get("reason", "unknown")}'
            )

        # Create fresh index
        logger.info(f"Creating index '{args.index}'")
        index_result = await manager.create_index_if_not_exists(
            args.index, INDEX_MAPPING
        )
        logger.info(f'Index status: {json.dumps(index_result, indent=2)}')

        if not index_result.get('exists') and not index_result.get('created'):
            logger.error('Failed to create index. Exiting.')
            return

        # Upload all documents
        logger.info(f'Starting bulk upload of {len(documents)} documents...')
        upload_start = time.time()

        result = await manager.bulk_upload(documents)

        upload_time = time.time() - upload_start

        # Log results
        logger.info(f'Upload completed in {upload_time:.2f} seconds')
        logger.info(f'Successfully indexed: {result["total_success"]:,} documents')
        logger.info(f'Failed to index: {result["total_failed"]:,} documents')

        if result['failed_items']:
            logger.warning('Some failures occurred:')
            for item in result['failed_items'][:5]:  # Show first 5 failures
                logger.warning(f'  {item}')

        # Final stats
        total_time = time.time() - start_time
        throughput = result['total_success'] / upload_time if upload_time > 0 else 0

        logger.info(
            f'Total script runtime: {total_time:.2f} seconds ({total_time / 60:.1f} minutes)'
        )
        logger.info(f'Average throughput: {throughput:.1f} documents/second')
        logger.info(
            f"Index '{args.index}' is ready for search with {result['total_success']} documents"
        )

    except Exception as e:
        logger.error('Script failed: %s', e)
        raise
    finally:
        await manager.close()


if __name__ == '__main__':
    asyncio.run(main())
