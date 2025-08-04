# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for app/api/dependencies/auth/bearer.py - OIDC bearer token authentication."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.dependencies.auth.bearer import OIDCHTTPBearer, token_cache
from cachetools import TTLCache
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.status import HTTP_401_UNAUTHORIZED


class TestOIDCHTTPBearer:
    """Tests for OIDCHTTPBearer class in app/api/dependencies/auth/bearer.py."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with authentication configuration."""
        from app.config import AuthConfig

        mock_settings = MagicMock()
        mock_settings.auth = AuthConfig(
            authority='https://login.microsoftonline.com/tenant-id',
            client_id='test-client-id',
        )
        return mock_settings

    @pytest.fixture
    def valid_token_payload(self):
        """Valid JWT token payload for testing."""
        return {
            'iss': 'https://login.microsoftonline.com/tenant-id/v2.0',
            'aud': 'test-client-id',
            'sub': 'user-12345',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
            'preferred_username': 'testuser@company.com',
            'name': 'Test User',
        }

    @pytest.fixture
    def oidc_bearer(self, mock_settings):
        """Create OIDCHTTPBearer instance with mocked settings."""
        with patch(
            'app.api.dependencies.auth.bearer.get_settings', return_value=mock_settings
        ):
            return OIDCHTTPBearer()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_get_token_from_credentials_valid(self, oidc_bearer):
        """Test _get_token_from_credentials with valid credentials."""
        creds = HTTPAuthorizationCredentials(
            scheme='Bearer', credentials='valid.jwt.token'
        )
        token = oidc_bearer._get_token_from_credentials(creds)
        assert token == 'valid.jwt.token'

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_get_token_from_credentials_none(self, oidc_bearer):
        """Test _get_token_from_credentials with None credentials."""
        token = oidc_bearer._get_token_from_credentials(None)
        assert token == ''

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_initialization_success(self, oidc_bearer):
        """Test successful OIDC bearer initialization."""
        mock_metadata = {
            'issuer': 'https://login.microsoftonline.com/tenant-id/v2.0',
            'jwks_uri': 'https://login.microsoftonline.com/tenant-id/discovery/v2.0/keys',
        }

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_metadata
        ) and patch('jwt.PyJWKClient') as mock_jwks_client:
            mock_jwks_client.return_value = MagicMock()

            await oidc_bearer.initialize()

            assert oidc_bearer.jwks_client is not None
            mock_jwks_client.assert_called_once_with(
                mock_metadata['jwks_uri'], cache_jwk_set=True, lifespan=360
            )

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_initialization_no_authority(self):
        """Test initialization failure when authority is not configured."""
        mock_settings = MagicMock()
        mock_settings.auth = MagicMock()
        mock_settings.auth.authority = ''
        mock_settings.auth.client_id = 'test-client-id'

        with patch(
            'app.api.dependencies.auth.bearer.get_settings', return_value=mock_settings
        ):
            bearer = OIDCHTTPBearer()

            with pytest.raises(RuntimeError, match='Auth authority not configured'):
                await bearer.initialize()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_token_cache_behavior(self, oidc_bearer):
        """Test token caching functionality."""
        # Test cache properties
        assert isinstance(token_cache, TTLCache)
        assert token_cache.maxsize == 1000
        assert token_cache.ttl == 300

        # Test caching operations
        test_token = 'test.jwt.token'
        test_payload = {'sub': 'user-123'}

        token_cache[test_token] = test_payload
        assert token_cache.get(test_token) == test_payload

        # Clear for other tests
        token_cache.clear()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_crypto_support_detection(self):
        """Test cryptography support detection."""
        from app.api.dependencies.auth.bearer import HAS_CRYPTO

        assert isinstance(HAS_CRYPTO, bool)


class TestOIDCHTTPBearerTokenValidation:
    """Tests for token validation logic in OIDCHTTPBearer."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for token validation tests."""
        from app.config import AuthConfig

        mock_settings = MagicMock()
        mock_settings.auth = AuthConfig(
            authority='https://test-authority.com', client_id='test-client'
        )
        return mock_settings

    @pytest.fixture
    def oidc_bearer(self, mock_settings):
        """Create OIDCHTTPBearer for token validation tests."""
        with patch(
            'app.api.dependencies.auth.bearer.get_settings', return_value=mock_settings
        ):
            return OIDCHTTPBearer()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_call_method_no_jwks_client_initializes(self, oidc_bearer):
        """Test that __call__ initializes jwks_client if not present."""
        mock_request = MagicMock(spec=Request)
        mock_creds = HTTPAuthorizationCredentials(
            scheme='Bearer', credentials='test.token'
        )

        mock_metadata = {'jwks_uri': 'https://test.com/keys'}

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_metadata
        ) and patch('jwt.PyJWKClient') as mock_jwks:
            mock_jwks.return_value = MagicMock()
            with (
                patch('fastapi.security.HTTPBearer.__call__', return_value=mock_creds),
                patch('jwt.get_unverified_header', return_value={'alg': 'RS256'}),
                patch('jwt.decode', return_value={'aud': 'test-client'}),
            ):
                result = await oidc_bearer(mock_request)

                assert oidc_bearer.jwks_client is not None
                assert result == mock_creds

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_call_method_http_exception_handling(self, oidc_bearer):
        """Test __call__ method handles HTTPException from parent class."""
        mock_request = MagicMock(spec=Request)

        with (
            patch.object(oidc_bearer, 'initialize', new_callable=AsyncMock),
            patch('fastapi.security.HTTPBearer.__call__') as mock_parent,
        ):
            # Mock initialization to avoid HTTP calls
            oidc_bearer.jwks_client = (
                MagicMock()
            )  # Set jwks_client so initialize won't be called

            mock_parent.side_effect = HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail='Not authenticated'
            )

            with pytest.raises(HTTPException) as exc_info:
                await oidc_bearer(mock_request)

            assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED
            assert 'Bearer token required' in exc_info.value.detail

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_call_method_unexpected_exception_handling(self, oidc_bearer):
        """Test __call__ method handles unexpected exceptions."""
        mock_request = MagicMock(spec=Request)

        with (
            patch.object(oidc_bearer, 'initialize', new_callable=AsyncMock),
            patch('fastapi.security.HTTPBearer.__call__') as mock_parent,
        ):
            # Mock initialization to avoid HTTP calls
            oidc_bearer.jwks_client = (
                MagicMock()
            )  # Set jwks_client so initialize won't be called

            mock_parent.side_effect = ValueError('Unexpected error')

            with pytest.raises(HTTPException) as exc_info:
                await oidc_bearer(mock_request)

            assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED
            assert 'Authorization error' in exc_info.value.detail
