# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for content storage service."""

import json
import os
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.clients.s3.client import S3Client
from app.config import Settings
from app.services.content_storage import ContentPointer, ContentStorageService


class TestContentPointer:
    """Test cases for ContentPointer class."""

    def test_content_pointer_creation(self):
        """Test creating a ContentPointer instance."""
        pointer = ContentPointer(
            uri='s3://bucket/key',
            file_id='test-id',
            mime_type='text/plain',
            storage_type='s3',
            metadata={'test': 'data'},
        )

        assert pointer.uri == 's3://bucket/key'
        assert pointer.file_id == 'test-id'
        assert pointer.mime_type == 'text/plain'
        assert pointer.storage_type == 's3'
        assert pointer.metadata == {'test': 'data'}

    def test_content_pointer_to_dict(self):
        """Test converting ContentPointer to dictionary."""
        pointer = ContentPointer(
            uri='s3://bucket/key',
            file_id='test-id',
            mime_type='text/plain',
            storage_type='s3',
            metadata={'test': 'data'},
        )

        result = pointer.to_dict()
        expected = {
            'uri': 's3://bucket/key',
            'file_id': 'test-id',
            'mime_type': 'text/plain',
            'storage_type': 's3',
            'metadata': {'test': 'data'},
        }

        assert result == expected

    def test_content_pointer_from_dict(self):
        """Test creating ContentPointer from dictionary."""
        data = {
            'uri': 's3://bucket/key',
            'file_id': 'test-id',
            'mime_type': 'text/plain',
            'storage_type': 's3',
            'metadata': {'test': 'data'},
        }

        pointer = ContentPointer.from_dict(data)

        assert pointer.uri == 's3://bucket/key'
        assert pointer.file_id == 'test-id'
        assert pointer.mime_type == 'text/plain'
        assert pointer.storage_type == 's3'
        assert pointer.metadata == {'test': 'data'}

    def test_content_pointer_from_dict_no_metadata(self):
        """Test creating ContentPointer from dictionary without metadata."""
        data = {
            'uri': 's3://bucket/key',
            'file_id': 'test-id',
            'mime_type': 'text/plain',
            'storage_type': 's3',
        }

        pointer = ContentPointer.from_dict(data)

        assert pointer.metadata == {}


class TestContentStorageService:
    """Test cases for ContentStorageService class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.content_storage.base_bucket = 'test-bucket'
        settings.content_storage.force_local_storage = False
        settings.content_storage.max_cache_size_mb = 100
        settings.content_storage.local_storage_path = None
        settings.content_storage.allowed_mime_types = None
        return settings

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return AsyncMock(spec=S3Client)

    @pytest.fixture
    def mock_valkey_client(self):
        """Create mock Valkey client."""
        return AsyncMock()

    @pytest.fixture
    def storage_service(self, mock_settings, mock_s3_client, mock_valkey_client):
        """Create ContentStorageService instance."""
        with patch('os.makedirs'):
            return ContentStorageService(
                settings=mock_settings,
                s3_client=mock_s3_client,
                valkey_client=mock_valkey_client,
            )

    def test_get_extension_for_mime(self, storage_service):
        """Test getting file extension from MIME type."""
        assert storage_service.get_extension_for_mime('text/plain') == '.txt'
        assert storage_service.get_extension_for_mime('image/jpeg') == '.jpg'
        assert storage_service.get_extension_for_mime('unknown/type') == ''

    def test_parse_pointer_valid(self, storage_service):
        """Test parsing valid S3 pointer."""
        bucket, key = storage_service.parse_pointer('s3://bucket/path/to/file')
        assert bucket == 'bucket'
        assert key == 'path/to/file'

    def test_parse_pointer_invalid(self, storage_service):
        """Test parsing invalid S3 pointer."""
        with pytest.raises(ValueError, match='Invalid S3 pointer'):
            storage_service.parse_pointer('invalid://pointer')

        with pytest.raises(ValueError, match='Invalid S3 pointer'):
            storage_service.parse_pointer('s3://bucket-only')

    def test_get_cache_key(self, storage_service):
        """Test generating cache key."""
        uri = 's3://bucket/key'
        cache_key = storage_service.get_cache_key(uri)
        assert cache_key == 'content:s3://bucket/key'

    @pytest.mark.asyncio
    async def test_store_content_s3_success(self, storage_service, mock_s3_client):
        """Test storing content to S3 successfully."""
        content = b'test content'
        mock_s3_client.put_object = AsyncMock()

        with patch('app.models.generate_nanoid', return_value='test-id'):
            pointer = await storage_service.store_content(
                user_id='user123', content=content, mime_type='text/plain'
            )

        assert pointer.storage_type == 's3'
        assert pointer.file_id == 'test-id'
        assert pointer.mime_type == 'text/plain'
        assert pointer.uri == 's3://test-bucket/user123/test-id.txt'

        mock_s3_client.put_object.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_content_size_limit_exceeded(self, storage_service):
        """Test storing content that exceeds size limit."""
        large_content = b'x' * (5 * 1024 * 1024)  # 5MB

        with pytest.raises(ValueError, match='Content exceeds maximum size limit'):
            await storage_service.store_content(
                user_id='user123', content=large_content, mime_type='text/plain'
            )

    @pytest.mark.asyncio
    async def test_store_content_invalid_mime_type(
        self, storage_service, mock_settings
    ):
        """Test storing content with invalid MIME type."""
        mock_settings.content_storage.allowed_mime_types = ['text/plain']
        storage_service.settings = mock_settings

        with pytest.raises(ValueError, match='Unsupported content type'):
            await storage_service.store_content(
                user_id='user123', content=b'test', mime_type='application/exe'
            )

    @pytest.mark.asyncio
    async def test_store_content_s3_fallback_to_local(
        self, storage_service, mock_s3_client
    ):
        """Test S3 storage falling back to local storage on error."""
        content = b'test content'
        mock_s3_client.put_object = AsyncMock(side_effect=Exception('S3 error'))

        with (
            patch('app.models.generate_nanoid', return_value='test-id'),
            patch('aiofiles.open') as mock_open,
            patch('os.makedirs'),
        ):
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            pointer = await storage_service.store_content(
                user_id='user123', content=content, mime_type='text/plain'
            )

        assert pointer.storage_type == 'local'
        assert pointer.file_id == 'test-id'
        mock_file.write.assert_awaited_once_with(content)

    @pytest.mark.asyncio
    async def test_store_content_with_caching(
        self, storage_service, mock_valkey_client
    ):
        """Test storing content with caching enabled."""
        content = b'test content'
        mock_valkey_client.set = AsyncMock()
        mock_valkey_client.set_binary = AsyncMock()

        with (
            patch('app.models.generate_nanoid', return_value='test-id'),
            patch('aiofiles.open') as mock_open,
            patch('os.makedirs'),
        ):
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            await storage_service.store_content(
                user_id='user123', content=content, mime_type='text/plain'
            )

        # Verify caching was attempted
        mock_valkey_client.set.assert_awaited()
        mock_valkey_client.set_binary.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_content_from_cache(self, storage_service, mock_valkey_client):
        """Test retrieving content from cache."""
        content = b'cached content'
        cache_metadata = {
            'mime_type': 'text/plain',
            'storage_type': 's3',
            'uri': 's3://bucket/key',
        }

        mock_valkey_client.get.return_value = json.dumps(cache_metadata).encode()
        mock_valkey_client.get_binary = AsyncMock(return_value=content)

        pointer = ContentPointer(
            uri='s3://bucket/key',
            file_id='test-id',
            mime_type='text/plain',
            storage_type='s3',
        )

        result_content, result_mime = await storage_service.get_content(pointer)

        assert result_content == content
        assert result_mime == 'text/plain'
        assert storage_service.cache_hits == 1

    @pytest.mark.asyncio
    async def test_get_content_from_s3(
        self, storage_service, mock_s3_client, mock_valkey_client
    ):
        """Test retrieving content from S3 when not in cache."""
        content = b's3 content'
        mock_valkey_client.get_binary = AsyncMock(return_value=None)
        mock_s3_client.get_object = AsyncMock(return_value=content)

        pointer = ContentPointer(
            uri='s3://bucket/key',
            file_id='test-id',
            mime_type='text/plain',
            storage_type='s3',
        )

        result_content, result_mime = await storage_service.get_content(pointer)

        assert result_content == content
        assert result_mime == 'text/plain'
        mock_s3_client.get_object.assert_awaited_once_with('bucket', 'key')

    @pytest.mark.asyncio
    async def test_get_content_from_local_file(
        self, storage_service, mock_valkey_client
    ):
        """Test retrieving content from local file."""
        content = b'local content'
        mock_valkey_client.get_binary = AsyncMock(return_value=None)

        with (
            patch('aiofiles.open') as mock_open,
            patch('os.path.exists', return_value=True),
        ):
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=content)
            mock_open.return_value.__aenter__.return_value = mock_file

            pointer = ContentPointer(
                uri='file:///path/to/file',
                file_id='test-id',
                mime_type='text/plain',
                storage_type='local',
            )

            result_content, result_mime = await storage_service.get_content(pointer)

        assert result_content == content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_get_content_compressed(self, storage_service, mock_valkey_client):
        """Test retrieving and decompressing cached content."""
        original_content = b'original content'
        compressed_content = zlib.compress(original_content)

        cache_metadata = {
            'mime_type': 'text/plain',
            'compressed': 'zlib',
            'original_size': len(original_content),
        }

        mock_valkey_client.get.return_value = json.dumps(cache_metadata).encode()
        mock_valkey_client.get_binary = AsyncMock(return_value=compressed_content)

        pointer = ContentPointer(
            uri='s3://bucket/key',
            file_id='test-id',
            mime_type='text/plain',
            storage_type='s3',
        )

        result_content, result_mime = await storage_service.get_content(pointer)

        assert result_content == original_content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_get_content_not_found(self, storage_service, mock_valkey_client):
        """Test retrieving non-existent content."""
        mock_valkey_client.get_binary = AsyncMock(return_value=None)

        with patch('os.path.exists', return_value=False):
            pointer = ContentPointer(
                uri='file:///nonexistent/file',
                file_id='test-id',
                mime_type='text/plain',
                storage_type='local',
            )

            result_content, result_mime = await storage_service.get_content(pointer)

        assert result_content is None
        assert result_mime is None

    @pytest.mark.asyncio
    async def test_get_content_from_string_uri_s3(
        self, storage_service, mock_s3_client
    ):
        """Test retrieving content using string URI for S3."""
        content = b's3 content'
        metadata = {'ContentType': 'text/plain', 'file_id': 'test-id'}

        mock_s3_client.head_object = AsyncMock(return_value=metadata)
        mock_s3_client.get_object = AsyncMock(return_value=content)

        result_content, result_mime = await storage_service.get_content(
            's3://bucket/key'
        )

        assert result_content == content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_get_content_from_string_uri_local(self, storage_service):
        """Test retrieving content using string URI for local file."""
        content = b'local content'

        with (
            patch('aiofiles.open') as mock_open,
            patch('os.path.exists', return_value=True),
            patch('mimetypes.guess_type', return_value=('text/plain', None)),
        ):
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=content)
            mock_open.return_value.__aenter__.return_value = mock_file

            result_content, result_mime = await storage_service.get_content(
                'file:///path/to/file.txt'
            )

        assert result_content == content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_cache_multiple_contents(self, storage_service, mock_valkey_client):
        """Test caching multiple contents at once."""
        contents_dict = {'key1': b'content1', 'key2': b'content2'}

        mock_pipeline = AsyncMock()
        mock_valkey_client.pipeline = MagicMock(return_value=mock_pipeline)

        result = await storage_service.cache_multiple_contents(contents_dict, 3600)

        assert result is True
        mock_valkey_client.pipeline.assert_called_once()
        mock_pipeline.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_content_from_id_s3(self, storage_service, mock_s3_client):
        """Test retrieving content by file ID from S3."""
        content = b'test content'
        list_response = {'Contents': [{'Key': 'user123/test-id.txt'}]}
        metadata = {'user_id': 'user123', 'ContentType': 'text/plain'}

        mock_s3_client.list_objects = AsyncMock(return_value=list_response)
        mock_s3_client.head_object = AsyncMock(return_value=metadata)
        mock_s3_client.get_object = AsyncMock(return_value=content)

        result_content, result_mime = await storage_service.get_content_from_id(
            'test-id', 'user123'
        )

        assert result_content == content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_get_content_from_id_access_denied(
        self, storage_service, mock_s3_client
    ):
        """Test access denied when user tries to access another user's file."""
        list_response = {'Contents': [{'Key': 'user123/test-id.txt'}]}
        metadata = {'user_id': 'other-user', 'ContentType': 'text/plain'}

        mock_s3_client.list_objects = AsyncMock(return_value=list_response)
        mock_s3_client.head_object = AsyncMock(return_value=metadata)

        result_content, result_mime = await storage_service.get_content_from_id(
            'test-id', 'user123'
        )

        assert result_content is None
        assert result_mime is None

    @pytest.mark.asyncio
    async def test_get_content_from_id_local(self, storage_service):
        """Test retrieving content by file ID from local storage."""
        content = b'local content'

        with (
            patch('os.path.exists', return_value=True),
            patch('os.listdir', return_value=['test-id.txt']),
            patch('aiofiles.open') as mock_open,
            patch('mimetypes.guess_type', return_value=('text/plain', None)),
        ):
            mock_file = AsyncMock()
            mock_file.read = AsyncMock(return_value=content)
            mock_open.return_value.__aenter__.return_value = mock_file

            result_content, result_mime = await storage_service.get_content_from_id(
                'test-id', 'user123'
            )

        assert result_content == content
        assert result_mime == 'text/plain'

    @pytest.mark.asyncio
    async def test_get_pointer_from_id_s3(self, storage_service, mock_s3_client):
        """Test getting pointer from file ID in S3."""
        list_response = {'Contents': [{'Key': 'user123/test-id.txt'}]}
        metadata = {'user_id': 'user123'}

        mock_s3_client.list_objects = AsyncMock(return_value=list_response)
        mock_s3_client.head_object = AsyncMock(return_value=metadata)

        pointer = await storage_service.get_pointer_from_id('test-id', 'user123')

        assert pointer == 's3://test-bucket/user123/test-id.txt'

    @pytest.mark.asyncio
    async def test_get_pointer_from_id_local(self, storage_service):
        """Test getting pointer from file ID in local storage."""
        with (
            patch('os.path.exists', return_value=True),
            patch('os.listdir', return_value=['test-id.txt']),
        ):
            pointer = await storage_service.get_pointer_from_id('test-id', 'user123')

        expected_path = os.path.join(
            storage_service.local_storage_path, 'user123', 'test-id.txt'
        )
        assert pointer == f'file://{expected_path}'

    @pytest.mark.asyncio
    async def test_get_pointer_from_id_not_found(self, storage_service):
        """Test getting pointer for non-existent file ID."""
        with patch('os.path.exists', return_value=False):
            pointer = await storage_service.get_pointer_from_id(
                'nonexistent', 'user123'
            )

        assert pointer is None
