# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Authentication dependencies module."""

# Re-export all public functions and classes for backward compatibility

# Core bearer token classes
from app.api.dependencies.auth.bearer import (
    CachedOIDCHTTPBearer,
    OIDCHTTPBearer,
)

# Authentication dependencies and utilities
from app.api.dependencies.auth.dependencies import (
    OptionalOIDCHTTPBearer,
    get_auth_dependency,
    get_auth_scheme,
    get_current_user,
    get_standard_public_routes,
    optional_auth,
    public_route,
    require_auth,
)

# Header-based authentication
from app.api.dependencies.auth.headers import get_user_id_from_header

# Role verification
from app.api.dependencies.auth.roles import (
    check_if_user_is_admin,
    get_required_roles_for_endpoint,
    get_user_roles_list,
)

# User validation
from app.api.dependencies.auth.validation import (
    check_user_has_role,
    extract_groups,
)

__all__ = [
    'CachedOIDCHTTPBearer',
    # Bearer token classes
    'OIDCHTTPBearer',
    'OptionalOIDCHTTPBearer',
    # Role verification
    'check_if_user_is_admin',
    # User validation
    'check_user_has_role',
    'extract_groups',
    # Dependencies
    'get_auth_dependency',
    'get_auth_scheme',
    'get_current_user',
    'get_required_roles_for_endpoint',
    # Route utilities
    'get_standard_public_routes',
    'get_user_id_from_header',
    'get_user_roles_list',
    'optional_auth',
    'public_route',
    'require_auth',
]
