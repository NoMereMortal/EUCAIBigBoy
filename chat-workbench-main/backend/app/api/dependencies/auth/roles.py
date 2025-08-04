# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Role-based authentication utilities."""

from typing import Any

from loguru import logger

from app.api.dependencies.auth.validation import extract_groups

__all__ = [
    'check_if_user_is_admin',
    'get_required_roles_for_endpoint',
    'get_user_roles_list',
]


def check_if_user_is_admin(user: dict[str, Any]) -> bool:
    """Check if user has admin privileges based on their groups/roles.

    Args:
        user: User object from auth

    Returns:
        Boolean indicating if user is an admin
    """
    # Extract all groups/roles from various locations
    groups = extract_groups(user)

    if not groups:
        # Fallback to username check if no groups found
        username = user.get('preferred_username', '') or user.get('username', '')
        if username and username.lower() == 'admin':
            logger.info(f'Admin access granted based on admin username: {username}')
            return True
        return False

    # Convert to lowercase for case-insensitive matching
    lowercase_groups = [group.lower() for group in groups]

    # Check for common admin patterns
    for group in lowercase_groups:
        if (
            group == 'admin'  # Exact match
            or 'admin' in group  # Contains 'admin'
            or group == 'administrator'  # Common alternative
            or 'administrator' in group
            or group.startswith('app-admin')  # Common prefix patterns
            or group.startswith('system-admin')
            or group.endswith('-admin')  # Common suffix patterns
            or 'superuser' in group
        ):  # Other admin terms
            return True

    return False


def get_user_roles_list(user: dict[str, Any]) -> list[str]:
    """
    Get a comprehensive list of all roles for a user.
    This is a convenience method that calls extract_groups.

    Args:
        user: User object from auth

    Returns:
        List of all roles the user has
    """
    return extract_groups(user)


def get_required_roles_for_endpoint(
    endpoint_name: str, default_roles: list[str] | None = None
) -> list[str]:
    """
    Get required roles for a specific endpoint based on configuration.

    Args:
        endpoint_name: Name of the endpoint to check
        default_roles: Default required roles if not configured

    Returns:
        List of required role names
    """
    # For now, this is a placeholder. Would typically check against
    # a configuration store of endpoint-specific role requirements

    # Return the default roles
    if default_roles is None:
        default_roles = ['admin']
    return default_roles
