# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Models for guardrail API."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContentFilterType(str, Enum):
    """Content filter types."""

    SEXUAL = 'SEXUAL'
    VIOLENCE = 'VIOLENCE'
    HATE = 'HATE'
    INSULTS = 'INSULTS'
    MISCONDUCT = 'MISCONDUCT'
    PROMPT_ATTACK = 'PROMPT_ATTACK'


class FilterStrength(str, Enum):
    """Filter strength levels."""

    NONE = 'NONE'
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'


class FilterAction(str, Enum):
    """Filter action types."""

    BLOCK = 'BLOCK'
    NONE = 'NONE'


class PiiAction(str, Enum):
    """PII action types."""

    BLOCK = 'BLOCK'
    ANONYMIZE = 'ANONYMIZE'
    NONE = 'NONE'


class PiiEntityType(str, Enum):
    """PII entity types."""

    EMAIL = 'EMAIL'
    PHONE = 'PHONE'
    ADDRESS = 'ADDRESS'
    NAME = 'NAME'
    AGE = 'AGE'
    SSN = 'US_SOCIAL_SECURITY_NUMBER'
    CREDIT_CARD = 'CREDIT_DEBIT_CARD_NUMBER'
    CREDIT_CARD_CVV = 'CREDIT_DEBIT_CARD_CVV'
    CREDIT_CARD_EXPIRY = 'CREDIT_DEBIT_CARD_EXPIRY'
    BANK_ACCOUNT = 'US_BANK_ACCOUNT_NUMBER'
    BANK_ROUTING = 'US_BANK_ROUTING_NUMBER'
    IP_ADDRESS = 'IP_ADDRESS'
    PASSPORT = 'US_PASSPORT_NUMBER'
    DRIVER_ID = 'DRIVER_ID'
    LICENSE_PLATE = 'LICENSE_PLATE'
    VIN = 'VEHICLE_IDENTIFICATION_NUMBER'
    MAC_ADDRESS = 'MAC_ADDRESS'
    URL = 'URL'
    USERNAME = 'USERNAME'
    PASSWORD = 'PASSWORD'  # noqa: S105 # pragma: allowlist secret
    PIN = 'PIN'
    AWS_ACCESS_KEY = 'AWS_ACCESS_KEY'
    AWS_SECRET_KEY = 'AWS_SECRET_KEY'  # noqa: S105 # pragma: allowlist secret


class GuardrailContentFilter(BaseModel):
    """Content filter configuration for guardrails."""

    type: ContentFilterType
    input_strength: FilterStrength
    output_strength: FilterStrength

    def __init__(self, **data):
        super().__init__(**data)
        if (
            self.input_strength == FilterStrength.NONE
            and self.output_strength == FilterStrength.NONE
        ):
            raise ValueError(
                'At least one filter strength (input_strength or output_strength) must not be NONE. Valid Values are NONE, LOW, MEDIUM, HIGH'
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuardrailContentFilter':
        """Create a GuardrailContentFilter from a dictionary."""
        return cls(
            type=data['type'],
            input_strength=data['inputStrength'],
            output_strength=data['outputStrength'],
        )


class GuardrailDeniedTopic(BaseModel):
    """Denied topic configuration for guardrails."""

    name: str
    definition: str
    examples: list[str] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuardrailDeniedTopic':
        """Create a GuardrailDeniedTopic from a dictionary."""
        return cls(
            name=data['name'],
            definition=data['definition'],
            examples=data.get('examples', []),
        )


class GuardrailWordFilter(BaseModel):
    """Word filter configuration for guardrails."""

    text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuardrailWordFilter':
        """Create a GuardrailWordFilter from a dictionary."""
        return cls(text=data['text'])


class GuardrailPiiEntity(BaseModel):
    """PII entity configuration for guardrails."""

    type: PiiEntityType
    action: PiiAction = PiiAction.ANONYMIZE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuardrailPiiEntity':
        """Create a GuardrailPiiEntity from a dictionary."""
        return cls(
            type=data['type'],
            action=data.get('action', PiiAction.ANONYMIZE),
        )


class GuardrailCreate(BaseModel):
    """Request model for creating a guardrail."""

    name: str
    description: str = ''
    content_filters: list[GuardrailContentFilter] = Field(
        default_factory=lambda: [
            GuardrailContentFilter(
                type=ContentFilterType.SEXUAL,
                input_strength=FilterStrength.MEDIUM,
                output_strength=FilterStrength.MEDIUM,
            )
        ]
    )
    denied_topics: list[GuardrailDeniedTopic] = Field(default_factory=list)
    word_filters: list[GuardrailWordFilter] = Field(default_factory=list)
    pii_entities: list[GuardrailPiiEntity] = Field(default_factory=list)
    blocked_input_messaging: str = 'Your request was blocked by content filtering.'
    blocked_output_messaging: str = 'The response was blocked by content filtering.'


class GuardrailUpdate(BaseModel):
    """Request model for updating a guardrail."""

    name: str | None = None
    description: str | None = None
    content_filters: list[GuardrailContentFilter] | None = None
    denied_topics: list[GuardrailDeniedTopic] | None = None
    word_filters: list[GuardrailWordFilter] | None = None
    pii_entities: list[GuardrailPiiEntity] | None = None
    blocked_input_messaging: str | None = None
    blocked_output_messaging: str | None = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.content_filters is not None and len(self.content_filters) == 0:
            # Set default content filter if empty list provided
            self.content_filters = [
                GuardrailContentFilter(
                    type=ContentFilterType.SEXUAL,
                    input_strength=FilterStrength.MEDIUM,
                    output_strength=FilterStrength.MEDIUM,
                )
            ]


class GuardrailVersion(BaseModel):
    """Guardrail version information."""

    version: str
    created_at: datetime


class GuardrailInfo(BaseModel):
    """Response model for guardrail information."""

    id: str
    name: str
    description: str
    created_at: datetime
    versions: list[GuardrailVersion] = Field(default_factory=list)
    current_version: str | None = None


class GuardrailDetail(GuardrailInfo):
    """Detailed guardrail information including configuration."""

    content_filters: list[GuardrailContentFilter] = Field(default_factory=list)
    denied_topics: list[GuardrailDeniedTopic] = Field(default_factory=list)
    word_filters: list[GuardrailWordFilter] = Field(default_factory=list)
    pii_entities: list[GuardrailPiiEntity] = Field(default_factory=list)
    blocked_input_messaging: str
    blocked_output_messaging: str
