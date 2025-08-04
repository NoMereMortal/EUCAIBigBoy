# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Request context middleware."""

import uuid
from collections.abc import Callable

from fastapi import Request, Response  # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

# Use relative import since context.py is in the same package
from .context import RequestContext


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set request context for clients."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and set context variables."""
        # Generate request ID if not provided
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

        # Extract chat ID from path or query params if available
        chat_id = None
        path_params = request.path_params
        if 'chat_id' in path_params:
            chat_id = path_params['chat_id']
        elif 'chat_id' in request.query_params:
            chat_id = request.query_params['chat_id']

        # Extract user ID from auth token or headers
        user_id = request.headers.get('X-User-ID')

        # Get a proper context manager using the factory method
        context_manager = RequestContext.get_context_manager()
        response = None

        # Use the context manager with async context manager protocol
        async with context_manager():
            # Set context values
            RequestContext.update_state(
                request_id=request_id, chat_id=chat_id, user_id=user_id
            )

            # Process the request and get response
            response = await call_next(request)

            # Add request ID to response headers
            response.headers['X-Request-ID'] = request_id

        # Always return the response
        assert response is not None, 'Response should never be None'
        return response
