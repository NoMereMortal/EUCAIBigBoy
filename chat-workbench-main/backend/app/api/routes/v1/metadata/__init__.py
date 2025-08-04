# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Metadata API package."""

# Import the router directly from the endpoints module
from app.api.routes.v1.metadata.endpoints import router

__all__ = ['router']
