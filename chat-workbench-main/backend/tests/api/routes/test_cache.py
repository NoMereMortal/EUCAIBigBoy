# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for cache management routes."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.app import create_app
from app.api.dependencies import check_rate_limit, get_valkey_client
from app.clients.valkey.client import ValkeyClient
from fastapi.testclient import TestClient


class TestCacheStatsEndpoint:
    """Test cases for cache stats endpoint."""

    @pytest.fixture
    def app(self):
        """Create test app instance."""
        return create_app()

    def test_cache_stats_available(self, app):
        """Test cache stats returns statistics when cache is available."""
        # Mock Valkey client
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_redis_client = AsyncMock()
        mock_redis_client.info.return_value = {
            'used_memory': '1048576',
            'connected_clients': '5',
            'uptime_in_seconds': '3600',
        }
        mock_valkey._client = mock_redis_client

        # Override dependencies
        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.get('/cache/stats')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'available'
            assert data['used_memory'] == '1048576'
            assert data['connected_clients'] == '5'
            assert data['uptime_in_seconds'] == '3600'
        finally:
            app.dependency_overrides.clear()

    def test_cache_stats_unavailable_no_client(self):
        """Test cache stats returns unavailable when client is None."""
        # Create test app instance
        app = create_app()

        # Mock no Valkey client
        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: None,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.get('/cache/stats')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'unavailable'
        finally:
            app.dependency_overrides.clear()

    def test_cache_stats_unavailable_no_redis_client(self):
        """Test cache stats returns unavailable when Redis client is None."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client without Redis client
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_valkey._client = None

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.get('/cache/stats')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'unavailable'
        finally:
            app.dependency_overrides.clear()

    def test_cache_stats_error(self):
        """Test cache stats returns error when info() raises exception."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client that raises exception
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_redis_client = AsyncMock()
        mock_redis_client.info.side_effect = Exception('Connection error')
        mock_valkey._client = mock_redis_client

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.get('/cache/stats')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'error'
            assert data['message'] == 'Connection error'
        finally:
            app.dependency_overrides.clear()

    def test_cache_stats_partial_info(self):
        """Test cache stats handles missing information gracefully."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client with partial info
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_redis_client = AsyncMock()
        mock_redis_client.info.return_value = {
            'used_memory': '1048576'
            # Missing other fields
        }
        mock_valkey._client = mock_redis_client

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.get('/cache/stats')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'available'
            assert data['used_memory'] == '1048576'
            assert data['connected_clients'] == 'unknown'
            assert data['uptime_in_seconds'] == 'unknown'
        finally:
            app.dependency_overrides.clear()


class TestCacheFlushEndpoint:
    """Test cases for cache flush endpoint."""

    def test_flush_cache_success(self):
        """Test cache flush succeeds when cache is available."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_redis_client = AsyncMock()
        mock_redis_client.flushdb = AsyncMock()
        mock_valkey._client = mock_redis_client

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.post('/cache/flush')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'success'
            mock_redis_client.flushdb.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    def test_flush_cache_unavailable_no_client(self):
        """Test cache flush returns 503 when client is None."""
        # Create test app instance
        app = create_app()

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: None,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.post('/cache/flush')

            assert response.status_code == 503
            data = response.json()
            assert 'Cache service unavailable' in data['detail']
        finally:
            app.dependency_overrides.clear()

    def test_flush_cache_unavailable_no_redis_client(self):
        """Test cache flush returns 503 when Redis client is None."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client without Redis client
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_valkey._client = None

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.post('/cache/flush')

            assert response.status_code == 503
            data = response.json()
            assert 'Cache service unavailable' in data['detail']
        finally:
            app.dependency_overrides.clear()

    def test_flush_cache_error(self):
        """Test cache flush returns 500 when flushdb() raises exception."""
        # Create test app instance
        app = create_app()

        # Mock Valkey client that raises exception
        mock_valkey = MagicMock(spec=ValkeyClient)
        mock_redis_client = AsyncMock()
        mock_redis_client.flushdb.side_effect = Exception('Flush failed')
        mock_valkey._client = mock_redis_client

        app.dependency_overrides = {
            get_valkey_client: lambda: lambda: mock_valkey,
            check_rate_limit: lambda: None,
        }

        try:
            with TestClient(app) as client:
                response = client.post('/cache/flush')

            assert response.status_code == 500
            data = response.json()
            assert 'Failed to flush cache: Flush failed' in data['detail']
        finally:
            app.dependency_overrides.clear()
