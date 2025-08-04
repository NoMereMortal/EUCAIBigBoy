# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""API v1 routes."""

from fastapi import APIRouter

from app.api.routes.v1.admin import router as admin_router
from app.api.routes.v1.chat import router as chat_router
from app.api.routes.v1.files import router as files_router
from app.api.routes.v1.generate import router as generate_router
from app.api.routes.v1.models import router as models_router
from app.api.routes.v1.personas import router as personas_router
from app.api.routes.v1.prompt_library import router as prompt_library_router
from app.api.routes.v1.task_handlers import router as task_handlers_router

# from app.api.routes.v1.metadata import router as metadata_router


router = APIRouter()
router.include_router(generate_router)
router.include_router(chat_router)
router.include_router(
    files_router, prefix='/files'
)  # Add the new files router with prefix
router.include_router(models_router)
router.include_router(personas_router)
router.include_router(prompt_library_router)
router.include_router(task_handlers_router)
router.include_router(admin_router, prefix='/admin')
# router.include_router(metadata_router)
