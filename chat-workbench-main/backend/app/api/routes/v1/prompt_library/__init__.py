# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Prompt Library API."""

from app.api.routes.v1.prompt_library import handlers
from app.api.routes.v1.prompt_library.endpoints import router

__all__ = ['handlers', 'router']
