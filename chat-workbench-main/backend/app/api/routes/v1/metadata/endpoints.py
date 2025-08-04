# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Metadata API endpoints."""

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix='/metadata', tags=['metadata'])


@router.get('/')
async def get_metadata() -> dict[str, Any]:
    """Get metadata about the API."""
    return {
        'name': 'Chat Workbench API',
        'description': 'API for managing chat interactions with LLMs',
        'version': '0.1.0',
    }
