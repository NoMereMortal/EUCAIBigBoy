# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
import mimetypes
import os
import tempfile
import zlib
from typing import Any, BinaryIO, Literal, Union

import aiofiles  # type: ignore
import botocore.exceptions
from loguru import logger

from app.clients.s3.client import S3Client
from app.config import Settings
from app.models import generate_nanoid


class ContentPointer:
    """Tracks content location and metadata."""

    def __init__(
        self,
        uri: str,  # s3://bucket/key or file:///path/to/file
        file_id: str,  # A unique identifier for the file
        mime_type: str,
        storage_type: Literal['s3', 'local'],
        metadata: dict[str, Any] | None = None,
    ):
        self.uri = uri
        self.file_id = file_id
        self.mime_type = mime_type
        self.storage_type = storage_type
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            'uri': self.uri,
            'file_id': self.file_id,
            'mime_type': self.mime_type,
            'storage_type': self.storage_type,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ContentPointer':
        return cls(
            uri=data['uri'],
            file_id=data['file_id'],
            mime_type=data['mime_type'],
            storage_type=data['storage_type'],
            metadata=data.get('metadata', {}),
        )


class ContentStorageService:
    """Service for storing and retrieving content."""

    # Constants for compression
    COMPRESSION_THRESHOLD: int = 100 * 1024  # 100KB - compress files larger than this
    COMPRESSION_LEVEL = (
        6  # Medium compression level (range is 0-9, where 9 is max compression)
    )

    def __init__(
        self,
        settings: Settings,
        s3_client: S3Client,
        valkey_client=None,
    ) -> None:
        """Initialize content storage service."""
        self.settings = settings
        self.s3_client = s3_client
        self.valkey_client = valkey_client

        # Get settings from the content storage config (default TTL is now 60 days)
        self.content_ttl_days = 60  # Hard-coded to 60 days per requirements
        self.base_bucket = settings.content_storage.base_bucket

        # Check if we should force local storage from environment variables
        self.force_local_storage = settings.content_storage.force_local_storage

        # Cache size management
        self.max_cache_size_bytes = (
            settings.content_storage.max_cache_size_mb * 1024 * 1024
        )
        self._current_cache_size_bytes = 0  # Track current cache usage

        # Cache metrics
        self.cache_hits = 0
        self.cache_misses = 0

        # Set file size limit to 4MB
        self.max_file_size_bytes = 4 * 1024 * 1024  # 4MB

        # For local storage - use configured path or env var if set, otherwise fallback to temp dir
        self.local_storage_path = (
            settings.content_storage.local_storage_path
            or os.environ.get('CONTENT_STORAGE_LOCAL_PATH')
            or os.path.join(tempfile.gettempdir(), 'chat-workbench', 'content-storage')
        )

        # Log storage configuration with detailed information
        logger.info('Content storage configuration:')
        logger.info(f'  Base bucket: {self.base_bucket}')
        logger.info(f'  Force local storage: {self.force_local_storage}')
        logger.info(f'  Local storage path: {self.local_storage_path}')
        logger.info(f'  S3 client available: {self.s3_client is not None}')
        logger.info('  Maximum file size: 4MB')
        logger.info('  Content TTL: 60 days')

        # Add more detailed S3 client diagnostics
        if self.s3_client is not None:
            logger.info(f'  S3 client type: {type(self.s3_client).__name__}')
            logger.info(
                f'  S3 client initialized: {hasattr(self.s3_client, "_client") and self.s3_client._client is not None}'
            )
        else:
            logger.warning(
                '  S3 client is None - document retrieval from S3 will not work'
            )

        # Ensure local storage path exists
        os.makedirs(self.local_storage_path, exist_ok=True)

    def get_extension_for_mime(self, mime_type: str) -> str:
        """Get file extension for mime type."""
        ext = mimetypes.guess_extension(mime_type)
        return ext if ext else ''

    def parse_pointer(self, pointer: str) -> tuple[str, str]:
        """Parse S3 pointer to get bucket and key."""
        # Format: s3://<bucket>/<key>
        if not pointer.startswith('s3://'):
            raise ValueError(f'Invalid S3 pointer: {pointer}')

        parts = pointer[5:].split('/', 1)
        if len(parts) != 2:
            raise ValueError(f'Invalid S3 pointer: {pointer}')

        return parts[0], parts[1]

    def get_cache_key(self, uri: str) -> str:
        """Generate cache key for content URI."""
        return f'content:{uri}'

    async def store_content(
        self,
        user_id: str,
        content: Union[bytes, BinaryIO],
        mime_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> ContentPointer:
        """Store content and return pointer with file ID."""
        # Convert BinaryIO to bytes if needed
        if not isinstance(content, bytes):
            content = content.read()

        # Check file size limits - hard limit of 4MB
        content_size_bytes = len(content)

        if content_size_bytes > self.max_file_size_bytes:
            raise ValueError(
                f'Content exceeds maximum size limit of 4MB '
                f'(actual size: {content_size_bytes / (1024 * 1024):.2f}MB)'
            )

        # Validate MIME type if allowed types are specified
        allowed_mime_types = self.settings.content_storage.allowed_mime_types
        if (
            allowed_mime_types
            and mime_type not in allowed_mime_types
            and not (
                mime_type.startswith('text/') and 'text/plain' in allowed_mime_types
            )
        ):
            raise ValueError(f'Unsupported content type: {mime_type}')

        # Generate a unique file ID
        file_id = generate_nanoid()

        # Initialize storage variables with default values
        uri = None
        storage_type: Literal['s3', 'local'] = 'local'  # Default to local storage

        # Choose storage method:
        # 1. Use S3 if client is available and local storage is not forced
        # 2. Fall back to local storage if S3 fails or isn't available
        use_s3 = self.s3_client is not None and not self.force_local_storage

        # S3 storage implementation using user_id in path for isolation
        bucket = self.base_bucket

        if use_s3:
            try:
                file_extension = self.get_extension_for_mime(mime_type)

                # Use user_id as part of the key path for isolation
                key = f'{user_id}/{file_id}{file_extension}'

                # Ensure metadata is a dict
                meta: dict[str, Any] = metadata.copy() if metadata else {}
                # Add content type and file ID
                meta['ContentType'] = mime_type
                meta['file_id'] = file_id
                meta['user_id'] = user_id  # Store user ID in metadata for validation

                # Set expiration using S3 lifecycle policies - no need to store in metadata

                logger.info(f'Attempting to store content in S3 bucket: {bucket}')
                await self.s3_client.put_object(bucket, key, content, meta)
                uri = f's3://{bucket}/{key}'
                storage_type = 's3'
                logger.info(f'Successfully stored content in S3: {uri}')
            except botocore.exceptions.ClientError as e:
                # Handle specific S3 errors
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == 'NoSuchBucket':
                    logger.warning(
                        f'S3 bucket does not exist: {bucket}. Falling back to local storage.'
                    )
                else:
                    logger.error(f'S3 error: {e}. Falling back to local storage.')
                # Fall back to local storage
                uri = None  # Reset to force local storage path
            except Exception as e:
                # Handle any other errors
                logger.error(
                    f'Unexpected error storing to S3: {e}. Falling back to local storage.'
                )
                uri = None  # Reset to force local storage path
        else:
            logger.info('Using local storage for content')

        # If S3 storage failed or wasn't attempted, use local storage
        if uri is None:
            # Local storage implementation
            filename = f'{file_id}{self.get_extension_for_mime(mime_type)}'
            # Use user_id in the path for isolation
            user_dir = os.path.join(self.local_storage_path, user_id)
            os.makedirs(user_dir, exist_ok=True)

            file_path = os.path.join(user_dir, filename)
            # Use async context manager properly
            f = await aiofiles.open(file_path, 'wb')
            try:
                await f.write(content)
            finally:
                await f.close()

            uri = f'file://{file_path}'
            storage_type = 'local'
            logger.info(f'Successfully stored content locally: {uri}')

        # Create content pointer
        pointer = ContentPointer(
            uri=uri,
            file_id=file_id,
            mime_type=mime_type,
            storage_type=storage_type,
            metadata=metadata,
        )

        # Cache the content if we have a cache client
        if self.valkey_client:
            content_size = len(content)
            cache_key = self.get_cache_key(uri)
            # Initialize cache metadata with important pointer information
            cache_metadata: dict[str, Any] = {
                'mime_type': mime_type,  # Store original mime type
                'storage_type': storage_type,
                'uri': uri,
            }

            # Add any additional metadata from the pointer
            if metadata:
                cache_metadata['pointer_metadata'] = metadata

            cached_content = content

            # Compress large content to save cache space
            if content_size > self.COMPRESSION_THRESHOLD:
                try:
                    # Compress the content
                    compressed_content = zlib.compress(
                        content, level=self.COMPRESSION_LEVEL
                    )
                    compressed_size = len(compressed_content)

                    # Only use compression if it actually saves space
                    if compressed_size < content_size:
                        logger.debug(
                            f'Compressed content from {content_size / 1024:.2f}KB to {compressed_size / 1024:.2f}KB '
                            f'({(compressed_size / content_size) * 100:.1f}%)'
                        )
                        cached_content = compressed_content
                        content_size = compressed_size
                        cache_metadata['compressed'] = 'zlib'
                        cache_metadata['original_size'] = len(content)
                except Exception as e:
                    # If compression fails, just use the original content
                    logger.warning(f'Compression failed: {e}')

            # Check if adding this content would exceed our cache size limit
            if (
                self._current_cache_size_bytes + content_size
                <= self.max_cache_size_bytes
            ):
                try:
                    # Set the cache metadata
                    meta_key = f'{cache_key}:meta'
                    if cache_metadata:
                        await self.valkey_client.set(
                            meta_key,
                            json.dumps(cache_metadata),
                            ex=self.content_ttl_days * 24 * 60 * 60,
                        )

                    # Set the actual content - use binary method if available
                    if hasattr(self.valkey_client, 'set_binary'):
                        await self.valkey_client.set_binary(
                            cache_key,
                            cached_content,
                            ex=self.content_ttl_days * 24 * 60 * 60,  # TTL in seconds
                        )
                    else:
                        # Fallback to regular set (may cause issues with binary data)
                        await self.valkey_client.set(
                            cache_key,
                            cached_content,
                            ex=self.content_ttl_days * 24 * 60 * 60,  # TTL in seconds
                        )

                    # Update our tracking of cache size
                    self._current_cache_size_bytes += content_size

                    # Update cache hit/miss metrics
                    self.cache_hits += 0  # Just tracking, not an actual hit

                    logger.debug(
                        f'Content cached with key: {cache_key}, size: {content_size / 1024:.2f}KB'
                        f'{" (compressed)" if "compressed" in cache_metadata else ""}'
                    )
                except Exception as e:
                    # Don't fail if caching fails - it's optional
                    logger.warning(f'Failed to cache content: {e}')
            else:
                logger.info(
                    f'Skipping cache for content: {content_size / 1024:.2f}KB would exceed cache size limit of {self.max_cache_size_bytes / 1024 / 1024:.2f}MB'
                )

        return pointer

    async def get_content(
        self, pointer: Union[ContentPointer, str]
    ) -> tuple[bytes | None, str | None]:
        """Retrieve content and mime type from pointer.

        Returns (None, None) if content is not found.
        """
        # Convert string URI to ContentPointer if needed
        if isinstance(pointer, str):
            if pointer.startswith('s3://'):
                # Extract metadata from S3 object if available
                bucket, key = self.parse_pointer(pointer)
                if self.s3_client:
                    try:
                        metadata = await self.s3_client.head_object(bucket, key)
                        mime_type = metadata.get(
                            'ContentType', 'application/octet-stream'
                        )
                        file_id = metadata.get('file_id', 'unknown')

                        pointer = ContentPointer(
                            uri=pointer,
                            file_id=file_id,
                            mime_type=mime_type,
                            storage_type='s3',
                            metadata=metadata,
                        )
                    except Exception as e:
                        logger.error(f'Error retrieving S3 metadata: {e}')
                        return None, None
                else:
                    # Can't process S3 URIs without client
                    logger.warning('S3 client not available to retrieve content')
                    return None, None
            elif pointer.startswith('file://'):
                # Local file
                file_path = pointer[7:]  # Remove file:// prefix
                if not os.path.exists(file_path):
                    logger.warning(f'Local file not found: {file_path}')
                    return None, None

                # Try to guess mime type
                mime_type = (
                    mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                )

                # Extract file_id from path
                filename = os.path.basename(file_path)
                file_id = os.path.splitext(filename)[
                    0
                ]  # Use filename without extension as ID

                pointer = ContentPointer(
                    uri=pointer,
                    file_id=file_id,
                    mime_type=mime_type,
                    storage_type='local',
                    metadata={},
                )
            else:
                # Unknown URI scheme
                logger.warning(f'Unknown URI scheme: {pointer}')
                return None, None

        # Try to get content from cache first
        content = None
        if self.valkey_client:
            cache_key = self.get_cache_key(pointer.uri)
            meta_key = f'{cache_key}:meta'

            # First try to get metadata to check for compression
            try:
                meta_str = await self.valkey_client.get(meta_key)
                cache_metadata: dict[str, Any] = {}
                if meta_str:
                    # Convert string representation of dict to actual dict
                    meta_str = (
                        meta_str.decode('utf-8')
                        if isinstance(meta_str, bytes)
                        else meta_str
                    )
                    if '{' in meta_str:
                        # Parse the string as JSON
                        cache_metadata = json.loads(meta_str)
            except Exception as e:
                logger.warning(f'Failed to get cache metadata: {e}')
                cache_metadata = {}

            # Then get the actual content using binary client to avoid UTF-8 decoding errors
            try:
                # Use binary-specific get method if available
                if hasattr(self.valkey_client, 'get_binary'):
                    cached_content = await self.valkey_client.get_binary(cache_key)
                else:
                    # Fallback to regular get (might cause issues with binary data)
                    cached_content = await self.valkey_client.get(cache_key)

                if cached_content:
                    # Update cache hit metrics
                    self.cache_hits += 1

                    # Check if content was compressed
                    if cache_metadata.get('compressed') == 'zlib':
                        try:
                            # Decompress the content
                            cache_metadata.get('original_size', 0)
                            content = zlib.decompress(cached_content)
                            logger.debug(
                                f'Decompressed content from {len(cached_content) / 1024:.2f}KB to {len(content) / 1024:.2f}KB'
                            )
                        except Exception as e:
                            logger.error(f'Failed to decompress content: {e}')
                            # Fall back to storage if decompression fails
                            content = None

                    # Use the mime_type from cache metadata if available
                    cached_mime_type = cache_metadata.get('mime_type')
                    if cached_mime_type:
                        logger.info(
                            f'Using mime_type from cache metadata: {cached_mime_type}'
                        )
                        # Update the pointer's mime_type with the cached value
                        pointer.mime_type = cached_mime_type
            except UnicodeDecodeError as e:
                # This should no longer happen with get_binary, but handle it just in case
                logger.error(f'Unicode decode error retrieving from cache: {e}')
                content = None
            except Exception as e:
                logger.error(f'Error retrieving from cache: {e}')
                content = None

        # If not in cache, fetch from storage
        if content is None:
            if pointer.storage_type == 's3':
                # S3 storage
                bucket, key = self.parse_pointer(pointer.uri)
                if not self.s3_client:
                    logger.warning('S3 client not available to retrieve content')
                    # Log more detailed information for debugging
                    logger.error(f'S3 client details: None type={type(None)}')
                    logger.error(
                        'This suggests the S3 client was never passed to ContentStorageService or was not initialized'
                    )
                    return None, None

                # Log S3 client state
                logger.info(
                    f'S3 client exists: {self.s3_client is not None}, '
                    f'initialized: {hasattr(self.s3_client, "_client") and self.s3_client._client is not None}'
                )
                try:
                    logger.info(
                        f'Retrieving object from S3: bucket={bucket}, key={key}'
                    )
                    content = await self.s3_client.get_object(bucket, key)

                    # Cache the content only if content exists and we have a cache client
                    if self.valkey_client and content is not None:
                        content_size = len(content)  # type: ignore[arg-type]
                        # Check cache size limits
                        if (
                            self._current_cache_size_bytes + content_size
                            <= self.max_cache_size_bytes
                        ):
                            try:
                                cache_key = self.get_cache_key(pointer.uri)
                                # Use binary method if available
                                if hasattr(self.valkey_client, 'set_binary'):
                                    await self.valkey_client.set_binary(
                                        cache_key,
                                        content,
                                        ex=self.content_ttl_days
                                        * 24
                                        * 60
                                        * 60,  # TTL in seconds
                                    )
                                else:
                                    # Fallback to regular set
                                    await self.valkey_client.set(
                                        cache_key,
                                        content,
                                        ex=self.content_ttl_days
                                        * 24
                                        * 60
                                        * 60,  # TTL in seconds
                                    )
                                # Update cache size tracking
                                self._current_cache_size_bytes += content_size
                                logger.debug(
                                    f'Content cached with key: {cache_key} after S3 retrieval. Size: {content_size / 1024:.2f}KB'
                                )
                            except Exception as e:
                                # Don't fail if caching fails - it's optional
                                logger.warning(f'Failed to cache content from S3: {e}')
                        else:
                            logger.info(
                                f'Skipping cache for S3 content: {content_size / 1024:.2f}KB would exceed cache limit'
                            )
                except Exception as e:
                    logger.error(f'Error retrieving S3 content: {e}')
                    return None, None
            elif pointer.storage_type == 'local':
                # Local storage
                file_path = pointer.uri[7:]  # Remove file:// prefix
                if not os.path.exists(file_path):
                    logger.warning(f'Local file not found: {file_path}')
                    return None, None

                try:
                    # Use async file operations properly with try/finally
                    f = await aiofiles.open(file_path, 'rb')
                    try:
                        content = await f.read()
                    finally:
                        await f.close()

                    # Cache the content
                    if content and self.valkey_client:
                        content_size = len(content)
                        # Check cache size limits
                        if (
                            self._current_cache_size_bytes + content_size
                            <= self.max_cache_size_bytes
                        ):
                            try:
                                cache_key = self.get_cache_key(pointer.uri)
                                # Use binary method if available
                                if hasattr(self.valkey_client, 'set_binary'):
                                    await self.valkey_client.set_binary(
                                        cache_key,
                                        content,
                                        ex=self.content_ttl_days
                                        * 24
                                        * 60
                                        * 60,  # TTL in seconds
                                    )
                                else:
                                    # Fallback to regular set
                                    await self.valkey_client.set(
                                        cache_key,
                                        content,
                                        ex=self.content_ttl_days
                                        * 24
                                        * 60
                                        * 60,  # TTL in seconds
                                    )
                                # Update cache size tracking
                                self._current_cache_size_bytes += content_size
                                logger.debug(
                                    f'Content cached with key: {cache_key} after local retrieval. Size: {content_size / 1024:.2f}KB'
                                )
                            except Exception as e:
                                # Don't fail if caching fails - it's optional
                                logger.warning(
                                    f'Failed to cache content from local file: {e}'
                                )
                        else:
                            logger.info(
                                f'Skipping cache for local file content: {content_size / 1024:.2f}KB would exceed cache limit'
                            )
                except Exception as e:
                    logger.error(f'Error reading local file: {e}')
                    return None, None
            else:
                # Unknown storage type
                logger.warning(f'Unknown storage type: {pointer.storage_type}')
                return None, None

        return content, pointer.mime_type

    async def cache_multiple_contents(
        self, contents_dict: dict[str, bytes], ttl_seconds: int | None = None
    ) -> bool:
        """
        Cache multiple contents in a single pipeline operation.

        Args:
            contents_dict: Dict mapping cache keys to content bytes
            ttl_seconds: Optional override for TTL in seconds

        Returns:
            True if caching was successful, False otherwise
        """
        if not self.valkey_client or not contents_dict:
            return False

        # Default TTL to the standard content TTL
        if ttl_seconds is None:
            ttl_seconds = self.content_ttl_days * 24 * 60 * 60

        try:
            # Check if Valkey client supports pipelining
            if hasattr(self.valkey_client, 'pipeline'):
                # Use pipeline for more efficient batch operation
                pipeline = self.valkey_client.pipeline()
                for key, content in contents_dict.items():
                    pipeline.set(key, content, ex=ttl_seconds)
                await pipeline.execute()
            else:
                # Fall back to individual operations if pipelining not supported
                for key, content in contents_dict.items():
                    await self.valkey_client.set(key, content, ex=ttl_seconds)

            # Update cache size tracking with total size of cached content
            total_size = sum(len(content) for content in contents_dict.values())
            self._current_cache_size_bytes += total_size

            logger.debug(
                f'Batch cached {len(contents_dict)} items, total size: {total_size / 1024:.2f}KB'
            )
            return True
        except Exception as e:
            logger.warning(f'Failed to perform batch caching: {e}')
            return False

    async def get_content_from_id(
        self, file_id: str, user_id: str
    ) -> tuple[bytes | None, str | None]:
        """
        Retrieve content by file ID and user ID.

        This validates that the user has access to the file before returning it.

        Args:
            file_id: The unique file identifier
            user_id: The requesting user's ID

        Returns:
            Tuple of (content_bytes, mime_type) or (None, None) if not found
        """
        # Try to find file in S3 storage first
        if self.s3_client:
            try:
                # Check for file in user's directory
                bucket = self.base_bucket

                # Try to find the object by listing objects with the prefix
                response = await self.s3_client.list_objects(
                    bucket, prefix=f'{user_id}/{file_id}'
                )

                # Extract key if found
                key = None
                if response and isinstance(response, dict) and 'Contents' in response:
                    contents_list = response['Contents']
                    for obj in contents_list:
                        if obj['Key'].startswith(f'{user_id}/{file_id}'):
                            key = obj['Key']
                            break

                if key:
                    # Get object metadata to verify ownership
                    metadata = await self.s3_client.head_object(bucket, key)
                    stored_user_id = metadata.get('user_id')

                    # Verify user has access
                    if stored_user_id and stored_user_id != user_id:
                        logger.warning(
                            f'Access denied: User {user_id} attempted to access file {file_id} owned by {stored_user_id}'
                        )
                        return None, None

                    # Get the actual content
                    content = await self.s3_client.get_object(bucket, key)
                    mime_type = metadata.get('ContentType', 'application/octet-stream')
                    return content, mime_type
            except Exception as e:
                logger.error(f'Error retrieving file {file_id} from S3: {e}')

        # Fall back to local storage
        try:
            # Check local storage - we need to find the file within the user's directory
            user_dir = os.path.join(self.local_storage_path, user_id)
            if not os.path.exists(user_dir):
                logger.warning(f"User directory doesn't exist: {user_dir}")
                return None, None

            # Look for files with the matching ID
            matching_files: list[str] = []  # Explicitly annotate as list of strings
            for filename in os.listdir(user_dir):
                if filename.startswith(file_id):
                    matching_files.append(filename)  # type: ignore  # Safe to ignore - filename is always a string

            if not matching_files:
                logger.warning(f'No matching files found for file_id: {file_id}')
                return None, None

            # Use the first matching file
            file_path = os.path.join(user_dir, matching_files[0])

            # Read the file content
            f = await aiofiles.open(file_path, 'rb')
            try:
                content = await f.read()
            finally:
                await f.close()

            # Determine mime type
            mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

            return content, mime_type
        except Exception as e:
            logger.error(f'Error retrieving file {file_id} from local storage: {e}')
            return None, None

    async def get_pointer_from_id(self, file_id: str, user_id: str) -> str | None:
        """
        Get the full URI pointer for a file ID.

        This is used to resolve file IDs to pointers for the Bedrock API.

        Args:
            file_id: The unique file identifier
            user_id: The requesting user's ID

        Returns:
            The full URI pointer (s3://bucket/user_id/file_id...) or None if not found
        """
        # Try S3 first if available
        if self.s3_client:
            try:
                bucket = self.base_bucket

                # Try to find the object by listing objects with the prefix
                response = await self.s3_client.list_objects(
                    bucket, prefix=f'{user_id}/{file_id}'
                )

                # Extract key if found
                if response and isinstance(response, dict) and 'Contents' in response:
                    contents_list = response['Contents']
                    for obj in contents_list:
                        if obj['Key'].startswith(f'{user_id}/{file_id}'):
                            # Verify it's the user's file (extra security check)
                            metadata = await self.s3_client.head_object(
                                bucket, obj['Key']
                            )
                            stored_user_id = metadata.get('user_id')

                            if not stored_user_id or stored_user_id == user_id:
                                # Return full S3 URI
                                return f's3://{bucket}/{obj["Key"]}'
            except Exception as e:
                logger.error(f'Error looking up S3 pointer for file {file_id}: {e}')

        # Fall back to local storage
        try:
            user_dir = os.path.join(self.local_storage_path, user_id)
            if not os.path.exists(user_dir):
                return None

            # Look for files with the matching ID
            for filename in os.listdir(user_dir):
                if filename.startswith(file_id):
                    file_path = os.path.join(user_dir, filename)
                    return f'file://{file_path}'
        except Exception as e:
            logger.error(f'Error looking up local pointer for file {file_id}: {e}')

        # File not found
        return None
