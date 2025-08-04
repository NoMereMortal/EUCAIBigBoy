# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Error handling middleware."""

from collections.abc import Callable
from typing import Any

from fastapi import Request, Response  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from loguru import logger  # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore

from .context import RequestContext


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and handle errors."""
        try:
            return await call_next(request)
        except Exception as e:
            # Log the error
            state = RequestContext.get_state()
            request_id = state.request_id or 'unknown'
            logger.exception(f'Unhandled exception: {e!s} [request_id={request_id}]')

            # Create a safe error response
            error_details: dict[str, Any] = {
                'detail': 'Internal server error',
                'request_id': request_id,
            }

            # Add error type and message in development mode
            if logger.level == 'DEBUG':
                error_details['error_type'] = type(e).__name__
                error_details['error_message'] = str(e)

            # Return a consistent error response
            return JSONResponse(
                status_code=500,
                content=error_details,
            )
