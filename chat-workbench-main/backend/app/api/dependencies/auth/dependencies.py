# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Authentication FastAPI dependencies."""

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

from app.api.dependencies.auth.bearer import CachedOIDCHTTPBearer
from app.config import get_settings


# Token cache and standard public routes
def get_standard_public_routes() -> list[str]:
    """Get list of standard routes that don't require authentication."""
    # With root_path, these paths are relative to the application
    return [
        '/api/health',
        '/api/metrics',
        '/api/docs',
        '/api/openapi.json',
        '/api/redoc',
    ]


def public_route():
    """Mark a route as publicly accessible without authentication."""

    def decorator(func):
        func.is_public = True
        return func

    return decorator


# Enhanced bearer token class with optional authentication support
class OptionalOIDCHTTPBearer(CachedOIDCHTTPBearer):
    """OIDC bearer that can be marked as optional for specific routes."""

    def _is_public_route(self, request: Request) -> bool:
        """Check if the current route is public."""
        # Check standard public routes
        if any(
            request.url.path.startswith(path) for path in get_standard_public_routes()
        ):
            return True

        # Check if route is explicitly marked as public
        route = request.scope.get('route')
        return bool(route and getattr(route.endpoint, 'is_public', False))

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Verify the provided bearer token if present.

        For routes marked as optional_auth=True, this won't raise an exception
        if no token is provided.

        Args:
            request: FastAPI request object

        Returns:
            HTTPAuthorizationCredentials: The validated credentials or None

        Raises:
            HTTPException: If authentication fails and it's required
        """
        # Check if route is public
        if self._is_public_route(request):
            return None

        # Get context from request for optional auth routes
        # Use type ignore since we're using a dynamic attribute
        optional_auth = getattr(request.state, 'optional_auth', False)  # type: ignore

        try:
            return await super().__call__(request)
        except HTTPException as e:
            if optional_auth:
                # For optional auth routes, proceed without authentication
                logger.debug('Optional auth route - proceeding without valid token')
                return None
            # For required auth routes, propagate the exception
            raise e


# Singleton instance of the auth scheme
_AUTH_SCHEME_INSTANCE: OptionalOIDCHTTPBearer | None = None


def get_auth_scheme() -> OptionalOIDCHTTPBearer:
    """Get the authentication scheme singleton."""
    global _AUTH_SCHEME_INSTANCE
    if _AUTH_SCHEME_INSTANCE is None:
        _AUTH_SCHEME_INSTANCE = OptionalOIDCHTTPBearer()
    return _AUTH_SCHEME_INSTANCE


def require_auth() -> Callable:
    """Dependency for routes that require authentication."""
    auth_scheme = get_auth_scheme()

    async def auth_dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Security(auth_scheme),
    ) -> dict[str, Any]:
        """Validate authentication and return user info."""
        if not credentials or not hasattr(request.state, 'user_id'):
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail='Authentication required',
                headers={'WWW-Authenticate': 'Bearer'},
            )
        return request.state.user

    return auth_dependency


def optional_auth() -> Callable:
    """Dependency for routes where authentication is optional."""
    auth_scheme = get_auth_scheme()

    async def auth_dependency(request: Request) -> dict[str, Any] | None:
        """Attempt authentication but don't require it."""
        # Mark this as an optional auth route
        request.state.optional_auth = True  # type: ignore

        try:
            # Attempt authentication but don't fail if it's not available
            credentials = await auth_scheme(request)
            if credentials:
                # If we got valid credentials, authentication succeeded
                logger.debug('Optional auth succeeded')
        except HTTPException:
            logger.debug('Authentication failed but not required for this route')

        return get_current_user(request)

    return auth_dependency


def get_current_user(request: Request) -> dict[str, Any] | None:
    """Get the current authenticated user if available."""
    return getattr(request.state, 'user', None)


def get_auth_dependency() -> list:
    """Get authentication dependency based on configuration.

    Returns:
        List: list of dependencies to apply to routes
    """
    settings = get_settings()

    if not settings.auth.enabled:
        logger.info('Authentication is disabled')
        return []

    if not settings.auth.authority or not settings.auth.client_id:
        logger.warning(
            'Auth authority or client_id not configured, continuing without authentication'
        )
        return []

    logger.info('Authentication is enabled')
    return [Depends(require_auth())]
