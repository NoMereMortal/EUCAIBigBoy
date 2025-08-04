# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Public interface for API dependencies."""

from app.api.dependencies.admin import (
    get_admin_dependency,
)
from app.api.dependencies.auth import (
    CachedOIDCHTTPBearer,
    OIDCHTTPBearer,
    OptionalOIDCHTTPBearer,
    check_if_user_is_admin,
    check_user_has_role,
    extract_groups,
    get_auth_dependency,
    get_auth_scheme,
    get_current_user,
    get_standard_public_routes,
    optional_auth,
    public_route,
    require_auth,
)
from app.api.dependencies.chat import (
    get_chat_service,
    get_chat_service_ws,
    get_task_handler_registry,
    get_task_handler_registry_ws,
    get_websocket_manager,
    get_websocket_manager_ws,
)
from app.api.dependencies.clients import (
    get_bedrock_client,
    get_bedrock_runtime_client,
    # get_opensearch_client,
    # get_bedrock_kb_client,
    get_client,
    get_client_registry,
    get_client_registry_ws,
    get_dynamodb_client,
    get_s3_client,
    get_typed_client,
    get_valkey_client,
)
from app.api.dependencies.context import (
    RequestContext,
    get_request_context,
)
from app.api.dependencies.rate_limit import (
    check_rate_limit,
    get_rate_limiter,
)

__all__ = [
    'CachedOIDCHTTPBearer',
    # Auth handlers and dependencies
    'OIDCHTTPBearer',
    'OptionalOIDCHTTPBearer',
    # Context and request handling
    'RequestContext',
    'check_if_user_is_admin',
    # Rate limiting
    'check_rate_limit',
    'check_user_has_role',
    'extract_groups',
    # Admin access
    'get_admin_dependency',
    'get_auth_dependency',
    'get_auth_scheme',
    'get_bedrock_client',
    'get_bedrock_runtime_client',
    # Chat and task handlers
    'get_chat_service',
    'get_chat_service_ws',
    # Clients
    'get_client',
    'get_client_registry',
    'get_client_registry_ws',
    'get_current_user',
    'get_dynamodb_client',
    'get_rate_limiter',
    'get_request_context',
    'get_s3_client',
    'get_standard_public_routes',
    'get_task_handler_registry',
    'get_task_handler_registry_ws',
    'get_typed_client',
    'get_valkey_client',
    'get_websocket_manager',
    'get_websocket_manager_ws',
    'optional_auth',
    'public_route',
    'require_auth',
]
