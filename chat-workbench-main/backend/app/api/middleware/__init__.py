# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Middleware package."""

from app.api.middleware.setup import setup_basic_middleware  # type: ignore

__all__ = ['setup_basic_middleware']
