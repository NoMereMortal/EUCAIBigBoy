# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import get_user_id_from_header
from app.api.routes.v1.models.models import ListModelsResponse, Model

router = APIRouter(tags=['models'], prefix='/models')


def _load_models_from_json() -> list[Model]:
    """
    Load models from the JSON file co-located with this module.
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'models.json')

        print(f'Loading models from: {file_path}')

        if not os.path.exists(file_path):
            raise FileNotFoundError(f'Models JSON file not found at {file_path}')

        with open(file_path) as f:
            models_data = json.load(f)
            return [Model.model_validate(model) for model in models_data]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error loading models: {e!s}'
        ) from e


@router.get('/')
async def list_models(
    user_id: Annotated[str, Depends(get_user_id_from_header)],
    provider: Annotated[
        str | None, Query(description='Filter models by provider')
    ] = None,
    limit: Annotated[
        int, Query(description='Maximum number of models to return')
    ] = 100,
) -> ListModelsResponse:
    """
    List available language models with optional filtering.

    Models are sorted by their "order" field (lowest first).
    """
    try:
        models = _load_models_from_json()

        # Apply provider filter if provided
        if provider:
            models = [m for m in models if m.provider.lower() == provider.lower()]

        # Sort by order field (lowest first)
        models.sort(key=lambda x: x.order)

        # Apply limit
        models = models[:limit]

        return ListModelsResponse(models=models)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error listing models: {e!s}'
        ) from e


@router.get('/{model_id}')
async def get_model(
    model_id: str, user_id: Annotated[str, Depends(get_user_id_from_header)]
) -> Model:
    """
    Get detailed information about a specific model.
    """
    try:
        models = _load_models_from_json()
        for model in models:
            if model.id == model_id:
                return model

        raise HTTPException(
            status_code=404, detail=f"Model with ID '{model_id}' not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error retrieving model: {e!s}'
        ) from e
