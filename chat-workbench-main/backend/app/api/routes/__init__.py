# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""API routes."""

from fastapi import APIRouter

from app.api.routes.v1 import router as v1_router

router = APIRouter()
# Only include v1 router - health, metrics, and cache are handled separately in app.py
router.include_router(v1_router)
