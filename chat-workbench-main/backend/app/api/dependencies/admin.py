# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Admin authorization dependencies."""

from typing import Any

from fastapi import Depends, HTTPException
from loguru import logger
from starlette.status import HTTP_403_FORBIDDEN

from app.api.dependencies.auth import check_if_user_is_admin, require_auth


async def admin_required(
    user: dict[str, Any] = Depends(require_auth()),
) -> dict[str, Any]:
    """Check if user is an admin.

    Args:
        user: User object from require_auth dependency

    Returns:
        User object if admin access is granted

    Raises:
        HTTPException: If user is not an admin
    """
    # User is already authenticated at this point due to require_auth dependency

    # Debug output
    logger.debug(
        f'Checking admin access for user: {user.get("preferred_username", "Unknown")}'
    )
    logger.debug(f'User object: {user}')

    # Check if user is admin using our consolidated function
    if not check_if_user_is_admin(user):
        logger.error(
            f'Admin check failed for user: {user.get("preferred_username", "Unknown")}'
        )
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail='Admin access required'
        )

    logger.info(
        f'Admin access granted for user: {user.get("preferred_username", "Unknown")}'
    )
    return user


def get_admin_dependency() -> list:
    """Get admin authorization dependency.

    Returns:
        List of dependencies to apply to routes
    """
    return [Depends(admin_required)]
