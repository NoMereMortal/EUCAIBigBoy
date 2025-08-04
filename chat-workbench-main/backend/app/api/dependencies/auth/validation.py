# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Common authentication validation utilities."""

from typing import Any

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED


class AuthError(Exception):
    """Base exception for authentication errors."""

    def __init__(self, message: str, status_code: int = HTTP_401_UNAUTHORIZED):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def extract_token_from_request(request: Request) -> str:
    """
    Extract token from various places in a request.

    Args:
        request: The FastAPI request

    Returns:
        The extracted token

    Raises:
        HTTPException: If token not found
    """
    # Try to get from Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.replace('Bearer ', '')

    # Try to get from cookie
    token = request.cookies.get('access_token')
    if token:
        return token

    # Try to get from query parameter
    token = request.query_params.get('access_token')
    if token:
        return token

    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def extract_groups(user: dict[str, Any]) -> list[str]:
    """
    Extract groups from various locations in the user object.

    Args:
        user: User object from auth

    Returns:
        List of group/role names
    """
    groups = []

    # Standard groups
    if isinstance(user.get('groups'), list):
        groups.extend(user.get('groups', []))

    # Cognito groups
    if isinstance(user.get('cognito:groups'), list):
        groups.extend(user.get('cognito:groups', []))

    # Standard roles
    if isinstance(user.get('roles'), list):
        groups.extend(user.get('roles', []))

    # Keycloak realm_access.roles
    realm_access = user.get('realm_access', {})
    if isinstance(realm_access, dict) and isinstance(realm_access.get('roles'), list):
        groups.extend(realm_access.get('roles', []))

    # Keycloak client roles (resource_access)
    resource_access = user.get('resource_access', {})
    if isinstance(resource_access, dict):
        for _client_name, client_data in resource_access.items():
            if isinstance(client_data, dict) and isinstance(
                client_data.get('roles'), list
            ):
                groups.extend(client_data.get('roles', []))

    return groups


def check_user_has_role(user_roles: list[str], required_roles: list[str]) -> bool:
    """
    Check if user has any of the required roles.

    Args:
        user_roles: The roles the user has
        required_roles: The roles required for access

    Returns:
        True if user has any required role, False otherwise
    """
    if not required_roles or not user_roles:
        return False

    # Case insensitive check for role match
    lowercase_user_roles = [role.lower() for role in user_roles]
    lowercase_required_roles = [role.lower() for role in required_roles]

    return any(role in lowercase_user_roles for role in lowercase_required_roles)


def check_user_has_permission(
    user_permissions: list[str], required_permissions: list[str]
) -> bool:
    """
    Check if user has any of the required permissions.

    Args:
        user_permissions: The permissions the user has
        required_permissions: The permissions required for access

    Returns:
        True if user has any required permission, False otherwise
    """
    if not required_permissions or not user_permissions:
        return False

    return any(perm in user_permissions for perm in required_permissions)


def validate_api_key(api_key: str, valid_keys: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate API key against a dictionary of valid keys.

    Args:
        api_key: API key to validate
        valid_keys: Dictionary mapping API keys to metadata

    Returns:
        API key metadata if valid, None otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return None

    # Direct lookup in the valid keys
    return valid_keys.get(api_key)


def validate_auth_header(auth_header: str, auth_type: str = 'Bearer') -> str:
    """
    Validate Authorization header format and extract token.

    Args:
        auth_header: The Authorization header value
        auth_type: The expected auth type (e.g., 'Bearer', 'ApiKey')

    Returns:
        The extracted token

    Raises:
        AuthError: If header format is invalid
    """
    if not auth_header:
        raise AuthError('Missing Authorization header')

    parts = auth_header.split()

    if len(parts) != 2:
        raise AuthError(
            f"Invalid Authorization header format. Expected: '{auth_type} token'"
        )

    if parts[0] != auth_type:
        raise AuthError(f"Invalid authentication type. Expected: '{auth_type}'")

    return parts[1]


def get_current_user(request: Request) -> dict[str, Any] | None:
    """Get the current authenticated user if available."""
    return getattr(request.state, 'user', None)
