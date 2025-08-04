# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Request context management for middleware."""

import contextlib
import contextvars
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional, TypeVar

from loguru import logger


@dataclass
class RequestState:
    """Request state for the current context."""

    request_id: Optional[str] = None
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Define TypeVar for RequestState
T = TypeVar('T', bound=Optional['RequestState'])

# Define a context variable for request state
# This needs to be a module-level variable, accessible by all instances
_state_var: contextvars.ContextVar[Optional[RequestState]] = contextvars.ContextVar(
    'request_state', default=None
)


class RequestContext:
    """
    Context manager for request state.
    Redesigned to avoid singleton pattern issues with context variables.
    """

    @classmethod
    def get_state(cls) -> RequestState:
        """Get the current request state."""
        state = _state_var.get()
        if state is None:
            # Create a default state if none exists
            state = RequestState(request_id=str(uuid.uuid4()))
            _state_var.set(state)
        return state

    @classmethod
    def update_state(cls, **kwargs: Any) -> None:
        """Update the current request state."""
        state = cls.get_state()
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
            else:
                state.metadata[key] = value
        _state_var.set(state)

    @classmethod
    def get_context_manager(cls):
        """Return a context manager for the request context."""
        return _RequestContextManager()


class _RequestContextManager:
    """Helper class for context management."""

    @contextlib.asynccontextmanager
    async def __call__(self) -> AsyncGenerator[None, None]:
        """Context manager for request context."""
        # Create a new token for this specific async context
        token = _state_var.set(RequestState())
        try:
            yield
        except Exception as exc:
            logger.exception(f'Exception in RequestContext: {exc}')
            raise
        finally:
            try:
                # Reset the context var to its previous state
                _state_var.reset(token)
            except ValueError as e:
                # This should happen much less frequently now, but still handle it gracefully
                logger.warning(f'Context variable reset error: {e}')
                # Try to set a fresh state instead of resetting
                try:
                    _state_var.set(None)
                except Exception as inner_e:
                    # In case even setting a fresh state fails
                    logger.error(
                        f'Failed to set fresh state after context reset error: {inner_e}'
                    )
