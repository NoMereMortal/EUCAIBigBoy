# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""OIDC bearer token authentication."""

from typing import Any

import httpx
import jwt
from cachetools import TTLCache
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

from app.config import get_settings

try:
    from cryptography.hazmat.backends import default_backend

    HAS_CRYPTO = default_backend() is not None
except ImportError:
    HAS_CRYPTO = False
    logger.error('No crypto support for JWT.')

token_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1000, ttl=300)


class OIDCHTTPBearer(HTTPBearer):
    """OIDC based bearer token authenticator."""

    def _get_token_from_credentials(
        self, creds: HTTPAuthorizationCredentials | None
    ) -> str:
        """Extract token from credentials, handling None case.

        Args:
            creds: The HTTP authorization credentials

        Returns:
            str: The token string or empty string if credentials are None
        """
        return creds.credentials if creds else ''

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the OIDC authenticator.

        Args:
            **kwargs: Additional arguments for HTTPBearer
        """
        super().__init__(**kwargs)
        self.jwks_client = None
        self.settings = get_settings()
        self.authority = self.settings.auth.authority
        self.client_id = self.settings.auth.client_id

        if not self.authority or not self.client_id:
            logger.warning('Auth authority or client_id not configured')
        else:
            logger.debug(
                f'OIDC authenticator configured with authority={self.authority}'
            )

    async def initialize(self) -> None:
        """Initialize the OIDC authenticator by fetching OIDC metadata."""
        if not self.authority:
            raise RuntimeError('Auth authority not configured')

        # Get OIDC metadata and initialize JWKS client
        oidc_metadata = await self.get_oidc_metadata()
        self.jwks_client = jwt.PyJWKClient(  # type: ignore
            oidc_metadata['jwks_uri'], cache_jwk_set=True, lifespan=360
        )

        logger.info('OIDC authenticator initialized')

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Verify the provided bearer token.

        Args:
            request: FastAPI request object

        Returns:
            HTTPAuthorizationCredentials: The validated credentials

        Raises:
            HTTPException: If authentication fails
        """
        # Initialize if not already initialized
        if not self.jwks_client:
            await self.initialize()

        # Get the authorization header
        try:
            http_auth_creds = await super().__call__(request)
            if http_auth_creds and hasattr(http_auth_creds, 'credentials'):
                logger.debug(f'Received token: {http_auth_creds.credentials[:10]}...')
        except HTTPException as e:
            logger.debug(f'No bearer token in request: {e}')
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail='Bearer token required'
            ) from e
        except Exception as e:
            logger.exception(f'Unexpected error getting authorization header: {e}')
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail='Authorization error'
            ) from e

        # Try to decode and verify the token
        try:
            token = self._get_token_from_credentials(http_auth_creds)

            # For debugging, try to decode the token without validation first
            try:
                header = jwt.get_unverified_header(token)  # type: ignore
                logger.debug(f'Token header: {header}')
                payload = jwt.decode(  # type: ignore
                    token, options={'verify_signature': False}
                )
                logger.debug(
                    f'Token claims (unverified): sub={payload.get("sub")}, iss={payload.get("iss")}, exp={payload.get("exp")}'
                )
            except Exception as e:
                logger.warning(f'Could not decode token for debug info: {e}')

            # Now do the real verification
            decoded_jwt = await self.decode_jwt(id_token=token)

            # Log the full JWT payload for debugging
            logger.debug(f'Full JWT payload: {decoded_jwt}')

            # Extract user identity with support for both Keycloak and Cognito
            # Prioritize sub claim (standard OIDC user identifier)
            user_id = None

            # Check for the 'sub' claim first (standard OIDC)
            if 'sub' in decoded_jwt:
                user_id = decoded_jwt.get('sub')
                logger.debug(f"Using 'sub' claim as user ID: {user_id}")
            # Fall back to other identifiers if needed
            else:
                user_id = (
                    decoded_jwt.get('cognito:username')
                    or decoded_jwt.get('preferred_username')
                    or decoded_jwt.get('email')
                    or f'unknown-{hash(token)}'
                )
                logger.debug(f'Using fallback identifier as user ID: {user_id}')

            logger.debug(f'JWT verification successful for user: {user_id}')

            # Extract groups/roles with provider-specific paths
            groups = []
            if 'cognito:groups' in decoded_jwt:
                groups = decoded_jwt['cognito:groups']
            elif 'groups' in decoded_jwt:
                groups = decoded_jwt['groups']
            elif 'realm_access' in decoded_jwt and isinstance(
                decoded_jwt.get('realm_access'), dict
            ):
                roles = decoded_jwt['realm_access'].get('roles', [])
                if roles:
                    groups = roles

            # Add user ID to request
            request.state.user_id = user_id  # type: ignore

            # Add normalized user info to request state
            request.state.user = {  # type: ignore
                'id': user_id,
                'email': decoded_jwt.get('email', ''),
                'name': decoded_jwt.get('name', '')
                or decoded_jwt.get('given_name', ''),
                'preferred_username': decoded_jwt.get('preferred_username', '')
                or decoded_jwt.get('cognito:username', ''),
                'groups': groups,
            }

            return http_auth_creds
        except Exception as e:
            # Special handling for expiration errors
            error_str = str(e).lower()
            if 'expired' in error_str:
                logger.warning(f'Token has expired: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail='Authentication token has expired',
                ) from e
            elif (
                'invalid' in error_str or 'signature' in error_str or 'jwt' in error_str
            ):
                logger.warning(f'Invalid token: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail='Invalid authentication token',
                ) from e
            else:
                logger.exception(f'Authentication failed: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED, detail='Authentication error'
                ) from e

    async def get_oidc_metadata(self) -> dict[str, Any]:
        """Get OIDC endpoints and metadata from authority.

        Returns:
            dict[str, Any]: OIDC metadata

        Raises:
            RuntimeError: If the request fails
        """
        try:
            async with httpx.AsyncClient() as client:
                logger.debug(
                    f'Fetching OIDC config from {self.authority}/.well-known/openid-configuration'
                )
                response = await client.get(
                    f'{self.authority}/.well-known/openid-configuration', timeout=30.0
                )
                response.raise_for_status()

                json_response: dict[str, Any] = response.json()
                return json_response

        except httpx.RequestError as e:
            logger.exception(f'Failed to retrieve OIDC metadata: {e}')
            raise RuntimeError(f'Failed to retrieve OIDC metadata: {e}') from e

    async def decode_jwt(self, id_token: str) -> Any:
        """Decode JWT.

        Args:
            id_token: The JWT token to decode

        Returns:
            Any: The decoded JWT payload

        Raises:
            jwt.PyJWTError: If token validation fails
        """
        if not self.jwks_client:
            raise RuntimeError('JWKS client not initialized')

        signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)

        # Get the token's issuer without verification
        try:
            unverified_payload = jwt.decode(  # type: ignore
                id_token, options={'verify_signature': False}
            )
            actual_issuer = unverified_payload.get('iss')
            logger.debug(f'Token has issuer: {actual_issuer}')
        except Exception as e:
            logger.warning(f'Could not extract issuer from token: {e}')
            actual_issuer = None

        # Define valid issuers - support both container hostname and localhost
        valid_issuers = [self.authority]

        # Add localhost variant if we're using the keycloak hostname
        if self.authority and 'keycloak:8080' in self.authority:
            localhost_issuer = self.authority.replace('keycloak:8080', 'localhost:8080')
            valid_issuers.append(localhost_issuer)

        # Add keycloak variant if we're using the localhost
        if self.authority and 'localhost:8080' in self.authority:
            keycloak_issuer = self.authority.replace('localhost:8080', 'keycloak:8080')
            valid_issuers.append(keycloak_issuer)

        logger.debug(f'Valid issuers: {valid_issuers}')

        # Use the actual token issuer if it's in our valid list
        issuer_to_use = (
            actual_issuer if actual_issuer in valid_issuers else self.authority
        )

        # Check if the token has an audience claim
        has_aud_claim = False
        if unverified_payload and 'aud' in unverified_payload:
            has_aud_claim = True
            logger.debug(f'Token has audience claim: {unverified_payload.get("aud")}')
        else:
            logger.warning(
                "Token is missing the 'aud' claim, making audience validation optional"
            )

        return jwt.decode(  # type: ignore
            id_token,
            signing_key.key,
            algorithms=['RS256'],
            issuer=issuer_to_use,  # Use the issuer from the token if it's valid
            audience=self.client_id if has_aud_claim else None,
            options={
                'verify_signature': True,
                'verify_exp': True,
                'verify_nbf': True,
                'verify_iat': True,
                'verify_aud': has_aud_claim,  # Only verify audience if the claim exists
                'verify_iss': True,
            },
        )


class CachedOIDCHTTPBearer(OIDCHTTPBearer):
    """OIDC authenticator with token caching for performance."""

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Verify the provided bearer token with caching support.

        Args:
            request: FastAPI request object

        Returns:
            HTTPAuthorizationCredentials: The validated credentials

        Raises:
            HTTPException: If authentication fails
        """
        # Initialize if not already initialized
        if not self.jwks_client:
            await self.initialize()

        # Get the authorization header
        try:
            http_auth_creds = await super(HTTPBearer, self).__call__(request)
            if http_auth_creds and hasattr(http_auth_creds, 'credentials'):
                logger.debug(f'Received token: {http_auth_creds.credentials[:10]}...')
        except HTTPException as e:
            logger.debug(f'No bearer token in request: {e}')
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail='Bearer token required',
                headers={'WWW-Authenticate': 'Bearer'},
            ) from e
        except Exception as e:
            logger.exception(f'Unexpected error getting authorization header: {e}')
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail='Authorization error',
                headers={'WWW-Authenticate': 'Bearer'},
            ) from e

        # Try to decode and verify the token
        try:
            token = self._get_token_from_credentials(http_auth_creds)

            # Check cache first
            cached_result = token_cache.get(token)
            if cached_result:
                # Set user info from cached result
                request.state.user_id = cached_result.get('user_id')  # type: ignore
                request.state.user = cached_result.get('user')  # type: ignore
                logger.debug('Using cached authentication')
                return http_auth_creds

            # For debugging, try to decode the token without validation first
            try:
                header = jwt.get_unverified_header(token)  # type: ignore
                logger.debug(f'Token header: {header}')
                payload = jwt.decode(  # type: ignore
                    token, options={'verify_signature': False}
                )
                logger.debug(
                    f'Token claims (unverified): sub={payload.get("sub")}, iss={payload.get("iss")}, exp={payload.get("exp")}'
                )
            except Exception as e:
                logger.warning(f'Could not decode token for debug info: {e}')

            # Now do the real verification
            decoded_jwt = await self.decode_jwt(id_token=token)

            # Log the full JWT payload for debugging
            logger.debug(f'Full JWT payload: {decoded_jwt}')

            # Extract user identity with support for both Keycloak and Cognito
            # Prioritize sub claim (standard OIDC user identifier)
            user_id = None

            # Check for the 'sub' claim first (standard OIDC)
            if 'sub' in decoded_jwt:
                user_id = decoded_jwt.get('sub')
                logger.debug(f"Using 'sub' claim as user ID: {user_id}")
            # Fall back to other identifiers if needed
            else:
                user_id = (
                    decoded_jwt.get('cognito:username')
                    or decoded_jwt.get('preferred_username')
                    or decoded_jwt.get('email')
                    or f'unknown-{hash(token)}'
                )
                logger.debug(f'Using fallback identifier as user ID: {user_id}')

            logger.debug(f'JWT verification successful for user: {user_id}')

            # Extract groups/roles with provider-specific paths
            groups = []
            if 'cognito:groups' in decoded_jwt:
                groups = decoded_jwt['cognito:groups']
            elif 'groups' in decoded_jwt:
                groups = decoded_jwt['groups']
            elif 'realm_access' in decoded_jwt and isinstance(
                decoded_jwt.get('realm_access'), dict
            ):
                roles = decoded_jwt['realm_access'].get('roles', [])
                if roles:
                    groups = roles

            # Add user ID to request
            request.state.user_id = user_id  # type: ignore

            # Add normalized user info to request state
            user_info = {
                'id': user_id,
                'email': decoded_jwt.get('email', ''),
                'name': decoded_jwt.get('name', '')
                or decoded_jwt.get('given_name', ''),
                'preferred_username': decoded_jwt.get('preferred_username', '')
                or decoded_jwt.get('cognito:username', ''),
                'groups': groups,
            }

            request.state.user = user_info  # type: ignore

            # Cache the successful result with user info
            token_cache[token] = {'user_id': user_id, 'user': user_info}

            return http_auth_creds
        except Exception as e:
            # Special handling for expiration errors
            error_str = str(e).lower()
            if 'expired' in error_str:
                logger.warning(f'Token has expired: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail='Authentication token has expired',
                    headers={'WWW-Authenticate': 'Bearer error="invalid_token"'},
                ) from e
            elif (
                'invalid' in error_str or 'signature' in error_str or 'jwt' in error_str
            ):
                logger.warning(f'Invalid token: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail='Invalid authentication token',
                    headers={'WWW-Authenticate': 'Bearer error="invalid_token"'},
                ) from e
            else:
                logger.exception(f'Authentication failed: {e}')
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail='Authentication error',
                    headers={'WWW-Authenticate': 'Bearer'},
                ) from e
