# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.


from pydantic import BaseModel


class ModelFeature(BaseModel):
    """
    Represents a specific capability or feature of an AI model.
    """

    name: str
    description: str


class Model(BaseModel):
    """
    Represents a language model with its metadata and capabilities.
    """

    id: str
    name: str
    provider: str
    description: str
    features: list[ModelFeature]
    provider_link: str
    order: int = 0
    is_available: bool = True


class ListModelsResponse(BaseModel):
    """
    Response model for listing models.
    """

    models: list[Model]
