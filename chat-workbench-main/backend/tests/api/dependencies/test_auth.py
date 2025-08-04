# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for authentication dependencies - critical security module testing."""

import time
from unittest.mock import MagicMock, patch

import httpx
import jwt
import pytest
from app.api.dependencies.auth import OIDCHTTPBearer
from app.config import AuthConfig
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from starlette.status import HTTP_401_UNAUTHORIZED


class TestOIDCHTTPBearer:
    """Tests for OIDC HTTP Bearer authentication - security critical."""

    @pytest.fixture
    def mock_settings(self):
        """Mock application settings with auth configuration."""
        mock_settings = MagicMock()
        mock_settings.auth = AuthConfig(
            authority='https://login.microsoftonline.com/test-tenant',
            client_id='test-client-id',
        )
        return mock_settings

    @pytest.fixture
    def valid_jwt_token(self):
        """Create a valid JWT token for testing."""
        payload = {
            'iss': 'https://login.microsoftonline.com/test-tenant/v2.0',
            'aud': 'test-client-id',
            'sub': 'user-123',
            'exp': int(time.time()) + 3600,  # 1 hour from now
            'iat': int(time.time()),
            'preferred_username': 'test@example.com',
            'name': 'Test User',
            'roles': ['user'],
        }
        # Use a test secret (in real tests, would use proper key)
        token = jwt.encode(payload, 'test-secret', algorithm='HS256')
        # Ensure token is a string (PyJWT < 2.0 returns bytes, >= 2.0 returns str)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        return token

    @pytest.fixture
    def expired_jwt_token(self):
        """Create an expired JWT token for testing."""
        payload = {
            'iss': 'https://login.microsoftonline.com/test-tenant/v2.0',
            'aud': 'test-client-id',
            'sub': 'user-123',
            'exp': int(time.time()) - 3600,  # 1 hour ago (expired)
            'iat': int(time.time()) - 7200,  # 2 hours ago
            'preferred_username': 'test@example.com',
        }
        token = jwt.encode(payload, 'test-secret', algorithm='HS256')
        # Ensure token is a string (PyJWT < 2.0 returns bytes, >= 2.0 returns str)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        return token

    @pytest.fixture
    def malformed_jwt_token(self):
        """Create a malformed JWT token for testing."""
        return 'not.a.valid.jwt.token.structure'

    @pytest.fixture
    def mock_oidc_metadata(self):
        """Mock OIDC metadata response."""
        return {
            'issuer': 'https://login.microsoftonline.com/test-tenant/v2.0',
            'authorization_endpoint': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/authorize',
            'token_endpoint': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/token',
            'jwks_uri': 'https://login.microsoftonline.com/test-tenant/discovery/v2.0/keys',
            'response_types_supported': ['code', 'token'],
            'subject_types_supported': ['pairwise'],
            'id_token_signing_alg_values_supported': ['RS256'],
        }

    @pytest.fixture
    def mock_jwks_response(self):
        """Mock JWKS (JSON Web Key Set) response."""
        return {
            'keys': [
                {
                    'kty': 'RSA',
                    'use': 'sig',
                    'kid': 'test-key-id',
                    'x5t': 'test-thumbprint',
                    'n': 'test-modulus',
                    'e': 'AQAB',
                    'x5c': ['test-cert'],
                }
            ]
        }

    @pytest.fixture
    def oidc_bearer(self, mock_settings):
        """Create OIDCHTTPBearer instance with mocked settings."""
        with patch(
            'app.api.dependencies.auth.get_settings', return_value=mock_settings
        ):
            return OIDCHTTPBearer()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_initialization_success(
        self, oidc_bearer, mock_oidc_metadata, mock_jwks_response
    ):
        """Test successful OIDC bearer initialization."""
        # Mock HTTP responses for OIDC metadata and JWKS
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_oidc_metadata
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            with patch('jwt.PyJWKClient') as mock_jwks_client:
                mock_jwks_client.return_value = MagicMock()

                # Act
                await oidc_bearer.initialize()

                # Assert
                assert oidc_bearer.jwks_client is not None
                mock_jwks_client.assert_called_once_with(
                    mock_oidc_metadata['jwks_uri'], cache_jwk_set=True, lifespan=360
                )

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_initialization_no_authority(self):
        """Test OIDC bearer initialization fails without authority."""
        # Create bearer with no authority
        mock_settings = MagicMock()
        mock_settings.auth = AuthConfig(
            authority='',  # Empty authority
            client_id='test-client-id',
        )

        with patch(
            'app.api.dependencies.auth.get_settings', return_value=mock_settings
        ):
            bearer = OIDCHTTPBearer()

            # Act & Assert
            with pytest.raises(RuntimeError, match='Auth authority not configured'):
                await bearer.initialize()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_valid_token_verification(
        self, oidc_bearer, valid_jwt_token, mock_oidc_metadata
    ):
        """Test successful verification of valid JWT token."""
        # Mock the request with valid authorization header
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {'authorization': f'Bearer {valid_jwt_token}'}

        # Mock OIDC metadata and JWKS client
        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
        ):
            mock_jwks_client = MagicMock()
            mock_signing_key = MagicMock()
            mock_signing_key.key = 'test-key'
            mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch('jwt.PyJWKClient', return_value=mock_jwks_client) and patch(
                'jwt.decode'
            ) as mock_jwt_decode:
                # Mock successful JWT decode
                mock_jwt_decode.return_value = {
                    'sub': 'user-123',
                    'preferred_username': 'test@example.com',
                    'aud': 'test-client-id',
                }

                # Mock parent __call__ to return credentials
                with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
                    mock_parent_call.return_value = HTTPAuthorizationCredentials(
                        scheme='Bearer', credentials=valid_jwt_token
                    )

                    # Act
                    result = await oidc_bearer(mock_request)

                    # Assert
                    assert result is not None
                    assert result.credentials == valid_jwt_token
                    mock_jwt_decode.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_expired_token_rejection(
        self, oidc_bearer, expired_jwt_token, mock_oidc_metadata
    ):
        """Test rejection of expired JWT token."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {'authorization': f'Bearer {expired_jwt_token}'}

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
        ):
            mock_jwks_client = MagicMock()
            mock_signing_key = MagicMock()
            mock_signing_key.key = 'test-key'
            mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch('jwt.PyJWKClient', return_value=mock_jwks_client) and patch(
                'jwt.decode'
            ) as mock_jwt_decode:
                # Mock JWT decode raising ExpiredSignatureError
                mock_jwt_decode.side_effect = jwt.ExpiredSignatureError(
                    'Token has expired'
                )

                with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
                    mock_parent_call.return_value = HTTPAuthorizationCredentials(
                        scheme='Bearer', credentials=expired_jwt_token
                    )

                    # Act & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await oidc_bearer(mock_request)

                    assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED
                    assert 'expired' in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_malformed_token_rejection(
        self, oidc_bearer, malformed_jwt_token
    ):
        """Test rejection of malformed JWT token."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {'authorization': f'Bearer {malformed_jwt_token}'}

        with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
            mock_parent_call.return_value = HTTPAuthorizationCredentials(
                scheme='Bearer', credentials=malformed_jwt_token
            )

            with patch('jwt.get_unverified_header') as mock_header:
                # Mock JWT decode raising DecodeError for malformed token
                mock_header.side_effect = jwt.DecodeError('Invalid token format')

                # Act & Assert
                with pytest.raises(HTTPException) as exc_info:
                    await oidc_bearer(mock_request)

                assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_missing_authorization_header(self, oidc_bearer):
        """Test rejection when no authorization header is provided."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}  # No authorization header

        with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
            # Mock parent call raising HTTPException for missing header
            mock_parent_call.side_effect = HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail='Not authenticated'
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await oidc_bearer(mock_request)

            assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED
            assert 'Bearer token required' in exc_info.value.detail

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_invalid_audience(self, oidc_bearer, mock_oidc_metadata):
        """Test rejection of token with invalid audience."""
        # Create token with wrong audience
        payload = {
            'iss': 'https://login.microsoftonline.com/test-tenant/v2.0',
            'aud': 'wrong-client-id',  # Wrong audience
            'sub': 'user-123',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
        }
        invalid_aud_token = jwt.encode(payload, 'test-secret', algorithm='HS256')
        # Ensure token is a string (PyJWT < 2.0 returns bytes, >= 2.0 returns str)
        if isinstance(invalid_aud_token, bytes):
            invalid_aud_token = invalid_aud_token.decode('utf-8')

        mock_request = MagicMock(spec=Request)
        # Ensure the token in headers is always a string
        token_str = (
            invalid_aud_token
            if isinstance(invalid_aud_token, str)
            else invalid_aud_token.decode('utf-8')
        )
        mock_request.headers = {'authorization': f'Bearer {token_str}'}

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
        ):
            mock_jwks_client = MagicMock()
            mock_signing_key = MagicMock()
            mock_signing_key.key = 'test-key'
            mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch('jwt.PyJWKClient', return_value=mock_jwks_client) and patch(
                'jwt.decode'
            ) as mock_jwt_decode:
                # Mock JWT decode raising InvalidAudienceError
                mock_jwt_decode.side_effect = jwt.InvalidAudienceError(
                    'Invalid audience'
                )

                with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
                    # Ensure credentials in HTTPAuthorizationCredentials is a string
                    token_str = (
                        invalid_aud_token
                        if isinstance(invalid_aud_token, str)
                        else invalid_aud_token.decode('utf-8')
                    )
                    mock_parent_call.return_value = HTTPAuthorizationCredentials(
                        scheme='Bearer', credentials=token_str
                    )

                    # Act & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await oidc_bearer(mock_request)

                    assert exc_info.value.status_code == HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_network_error_during_init(self, oidc_bearer):
        """Test handling of network errors during OIDC metadata retrieval."""
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock network error
            mock_get.side_effect = httpx.ConnectError('Connection failed')

            # Act & Assert
            with pytest.raises(httpx.ConnectError):
                await oidc_bearer.initialize()

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_auto_initialization_on_first_call(
        self, oidc_bearer, valid_jwt_token, mock_oidc_metadata
    ):
        """Test that OIDC bearer auto-initializes on first token verification call."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {'authorization': f'Bearer {valid_jwt_token}'}

        # Ensure not initialized
        assert oidc_bearer.jwks_client is None

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
        ):
            mock_jwks_client = MagicMock()
            mock_signing_key = MagicMock()
            mock_signing_key.key = 'test-key'
            mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

            with (
                patch(
                    'jwt.PyJWKClient', return_value=mock_jwks_client
                ) as mock_jwks_constructor,
                patch(
                    'jwt.decode',
                    return_value={'sub': 'user-123', 'aud': 'test-client-id'},
                ),
                patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call,
            ):
                mock_parent_call.return_value = HTTPAuthorizationCredentials(
                    scheme='Bearer', credentials=valid_jwt_token
                )

                # Act
                result = await oidc_bearer(mock_request)

                # Assert - should have auto-initialized
                assert oidc_bearer.jwks_client is not None
                mock_jwks_constructor.assert_called_once()
                assert result is not None

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_concurrent_initialization(
        self, oidc_bearer, mock_oidc_metadata
    ):
        """Test that concurrent initialization calls are handled safely."""
        import asyncio

        with (
            patch.object(
                oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
            ),
            patch('jwt.PyJWKClient') as mock_jwks_client,
        ):
            mock_jwks_client.return_value = MagicMock()

            # Act - simulate concurrent initialization
            tasks = [oidc_bearer.initialize() for _ in range(5)]
            await asyncio.gather(*tasks)

            # Assert - should have initialized successfully without errors
            assert oidc_bearer.jwks_client is not None

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_token_caching_behavior(
        self, oidc_bearer, valid_jwt_token, mock_oidc_metadata
    ):
        """Test token validation caching for performance."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {'authorization': f'Bearer {valid_jwt_token}'}

        with patch.object(
            oidc_bearer, 'get_oidc_metadata', return_value=mock_oidc_metadata
        ):
            mock_jwks_client = MagicMock()
            mock_signing_key = MagicMock()
            mock_signing_key.key = 'test-key'
            mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

            with patch('jwt.PyJWKClient', return_value=mock_jwks_client) and patch(  # noqa: SIM117
                'jwt.decode',
                return_value={'sub': 'user-123', 'aud': 'test-client-id'},
            ) as mock_decode:
                with patch('fastapi.security.HTTPBearer.__call__') as mock_parent_call:
                    mock_parent_call.return_value = HTTPAuthorizationCredentials(
                        scheme='Bearer', credentials=valid_jwt_token
                    )

                    # Act - call multiple times with same token
                    for _ in range(3):
                        result = await oidc_bearer(mock_request)
                        assert result is not None

                    # Assert - JWT decode should be called multiple times (no caching in this simple version)
                    # In a production system, you might want to implement token caching
                    assert mock_decode.call_count >= 3

    @pytest.mark.asyncio
    @pytest.mark.auth
    async def test_oidc_bearer_configuration_validation(self):
        """Test OIDC bearer configuration validation."""
        # Test with missing authority
        mock_settings_no_auth = MagicMock()
        mock_settings_no_auth.auth = AuthConfig(
            authority='', client_id='test-client-id'
        )

        with patch(
            'app.api.dependencies.auth.get_settings', return_value=mock_settings_no_auth
        ):
            bearer = OIDCHTTPBearer()
            # Should log warning but not fail construction
            assert bearer.authority == ''
            assert bearer.client_id == 'test-client-id'

        # Test with missing client_id
        mock_settings_no_client = MagicMock()
        mock_settings_no_client.auth = AuthConfig(
            authority='https://test.com', client_id=''
        )

        with patch(
            'app.api.dependencies.auth.get_settings',
            return_value=mock_settings_no_client,
        ):
            bearer = OIDCHTTPBearer()
            assert bearer.authority == 'https://test.com'
            assert bearer.client_id == ''
