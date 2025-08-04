# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Header-based authentication dependencies."""

from typing import Annotated

from fastapi import Header, HTTPException
from loguru import logger


async def get_user_id_from_header(
    x_user_id: Annotated[str | None, Header()] = None,
) -> str:
    """Extract and validate the user ID from the X-User-ID header.

    This dependency is meant for endpoints that need user identification
    but not full JWT validation. Used particularly for internal API calls
    where the user ID is passed through the X-User-ID header.

    Args:
        x_user_id: The user ID from the X-User-ID header

    Returns:
        str: The validated user ID

    Raises:
        HTTPException: If the X-User-ID header is missing or invalid
    """
    if not x_user_id:
        logger.error('Missing X-User-ID header')
        raise HTTPException(
            status_code=422,  # Unprocessable Entity
            detail='X-User-ID header is required for this endpoint',
        )

    # Basic validation
    if len(x_user_id) < 3:  # Assuming user IDs should be at least 3 characters
        logger.error(f'Invalid user ID format in X-User-ID header: {x_user_id}')
        raise HTTPException(
            status_code=422, detail='Invalid user ID format in X-User-ID header'
        )

    logger.debug(f'Using user ID from X-User-ID header: {x_user_id}')
    return x_user_id
