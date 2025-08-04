# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Admin API routes."""

from fastapi import APIRouter

from app.api.dependencies import get_admin_dependency
from app.api.routes.v1.admin.guardrail import router as guardrail_router
from app.api.routes.v1.admin.task import router as task_router

# Create router with admin dependencies
router = APIRouter(dependencies=get_admin_dependency())
router.include_router(guardrail_router, prefix='/guardrail')
router.include_router(task_router, prefix='/task')

__all__ = ['get_client_registry', 'router']
