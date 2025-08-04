# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Handlers for guardrail API."""

from datetime import datetime
from typing import Any

from loguru import logger

from app.api.routes.v1.admin.guardrail.models import (
    GuardrailContentFilter,
    GuardrailCreate,
    GuardrailDeniedTopic,
    GuardrailDetail,
    GuardrailInfo,
    GuardrailPiiEntity,
    GuardrailUpdate,
    GuardrailVersion,
    GuardrailWordFilter,
)
from app.clients.bedrock.client import BedrockClient


async def list_guardrails(
    client: BedrockClient,
) -> list[GuardrailInfo]:
    """List all guardrails.

    Args:
        client: The Bedrock guardrails client.

    Returns:
        List of guardrail information.
    """
    try:
        guardrails = await client.list_guardrails()

        result = []
        for guardrail in guardrails:
            # Get versions for each guardrail
            # According to AWS docs, the field is 'id' not 'guardrailId'
            versions = await client.list_guardrail_versions(guardrail['id'])

            # Convert to our model
            guardrail_info = GuardrailInfo(
                id=guardrail['id'],
                name=guardrail['name'],
                description=guardrail.get('description', ''),
                created_at=guardrail['createdAt'],
                versions=[
                    GuardrailVersion(
                        version=version['version'], created_at=version['createdAt']
                    )
                    for version in versions
                ],
                current_version=versions[0]['version'] if versions else None,
            )
            result.append(guardrail_info)

        return result
    except Exception as e:
        logger.error(f'Error listing guardrails: {e}')
        raise


async def get_guardrail(
    client: BedrockClient,
    guardrail_id: str,
    guardrail_version: str | None = None,
) -> GuardrailDetail:
    """Get guardrail details.

    Args:
        client: The Bedrock guardrails client.
        guardrail_id: The ID of the guardrail to retrieve.
        guardrail_version: Optional version of the guardrail to retrieve.
                          If not specified, returns DRAFT version.

    Returns:
        Guardrail details.
    """
    try:
        # Get guardrail details
        guardrail = await client.get_guardrail(guardrail_id, guardrail_version)

        # Get versions
        versions = await client.list_guardrail_versions(guardrail_id)

        # Convert to our model - using the correct field names from AWS API docs
        # Parse content filters
        content_filter_models = []

        # Check both old and new field name formats for compatibility
        if 'contentPolicy' in guardrail and 'filters' in guardrail['contentPolicy']:
            for filter_config in guardrail['contentPolicy']['filters']:
                content_filter_models.append(
                    GuardrailContentFilter.from_dict(filter_config)
                )
        elif (
            'contentPolicyConfig' in guardrail
            and 'filtersConfig' in guardrail['contentPolicyConfig']
        ):
            for filter_config in guardrail['contentPolicyConfig']['filtersConfig']:
                content_filter_models.append(
                    GuardrailContentFilter.from_dict(filter_config)
                )

        # Parse denied topics
        denied_topic_models = []
        if 'topicPolicy' in guardrail and 'topics' in guardrail['topicPolicy']:
            for topic_config in guardrail['topicPolicy']['topics']:
                denied_topic_models.append(GuardrailDeniedTopic.from_dict(topic_config))
        elif (
            'topicPolicyConfig' in guardrail
            and 'topicsConfig' in guardrail['topicPolicyConfig']
        ):
            for topic_config in guardrail['topicPolicyConfig']['topicsConfig']:
                denied_topic_models.append(GuardrailDeniedTopic.from_dict(topic_config))

        # Parse word filters
        word_filter_models = []
        if 'wordPolicy' in guardrail and 'words' in guardrail['wordPolicy']:
            for word_config in guardrail['wordPolicy']['words']:
                word_filter_models.append(GuardrailWordFilter.from_dict(word_config))
        elif (
            'wordPolicyConfig' in guardrail
            and 'wordsConfig' in guardrail['wordPolicyConfig']
        ):
            for word_config in guardrail['wordPolicyConfig']['wordsConfig']:
                word_filter_models.append(GuardrailWordFilter.from_dict(word_config))

        # Parse PII entities
        pii_entity_models = []
        if (
            'sensitiveInformationPolicy' in guardrail
            and 'piiEntities' in guardrail['sensitiveInformationPolicy']
        ):
            for pii_config in guardrail['sensitiveInformationPolicy']['piiEntities']:
                pii_entity_models.append(GuardrailPiiEntity.from_dict(pii_config))
        elif (
            'sensitiveInformationPolicyConfig' in guardrail
            and 'piiEntitiesConfig' in guardrail['sensitiveInformationPolicyConfig']
        ):
            for pii_config in guardrail['sensitiveInformationPolicyConfig'][
                'piiEntitiesConfig'
            ]:
                pii_entity_models.append(GuardrailPiiEntity.from_dict(pii_config))

        return GuardrailDetail(
            id=guardrail.get('guardrailId') or guardrail.get('id', ''),
            name=guardrail['name'],
            description=guardrail.get('description', ''),
            created_at=guardrail['createdAt'],
            versions=[
                GuardrailVersion(
                    version=version['version'], created_at=version['createdAt']
                )
                for version in versions
            ],
            current_version=versions[0]['version'] if versions else None,
            content_filters=content_filter_models,
            denied_topics=denied_topic_models,
            word_filters=word_filter_models,
            pii_entities=pii_entity_models,
            blocked_input_messaging=guardrail.get(
                'blockedInputMessaging',
                'Your request was blocked by content filtering.',
            ),
            blocked_output_messaging=guardrail.get(
                'blockedOutputsMessaging',
                'The response was blocked by content filtering.',
            ),
        )
    except Exception as e:
        logger.error(f'Error getting guardrail {guardrail_id}: {e}')
        raise


async def create_guardrail(
    client: BedrockClient,
    guardrail: GuardrailCreate,
) -> GuardrailInfo:
    """Create a new guardrail.

    Args:
        client: The Bedrock guardrails client.
        guardrail: The guardrail configuration.

    Returns:
        Created guardrail information.
    """
    try:
        # Convert our model to Bedrock API format matching AWS documentation
        config: dict[str, Any] = {
            'name': guardrail.name,
            'blockedInputMessaging': guardrail.blocked_input_messaging,
            'blockedOutputsMessaging': guardrail.blocked_output_messaging,
        }

        # Add description if provided (optional in AWS API)
        if guardrail.description:
            config['description'] = guardrail.description

        # Add content filters using correct AWS parameter names
        if guardrail.content_filters:
            filters_list = [
                {
                    'type': filter.type,
                    'inputStrength': filter.input_strength,
                    'outputStrength': filter.output_strength,
                }
                for filter in guardrail.content_filters
            ]
            config['contentPolicyConfig'] = {'filtersConfig': filters_list}

        # Add denied topics using correct AWS parameter names
        if guardrail.denied_topics:
            topics_list = [
                {
                    'name': topic.name,
                    'definition': topic.definition,
                    'examples': topic.examples,
                    'type': 'DENY',
                }
                for topic in guardrail.denied_topics
            ]
            config['topicPolicyConfig'] = {'topicsConfig': topics_list}

        # Add word filters using correct AWS parameter names
        if guardrail.word_filters:
            words_list = [{'text': word.text} for word in guardrail.word_filters]
            config['wordPolicyConfig'] = {'wordsConfig': words_list}

        # Add PII entities using correct AWS parameter names
        if guardrail.pii_entities:
            pii_list = [
                {'type': pii.type, 'action': pii.action}
                for pii in guardrail.pii_entities
            ]
            config['sensitiveInformationPolicyConfig'] = {'piiEntitiesConfig': pii_list}

        # Create the guardrail
        result = await client.create_guardrail(config)

        # Return the created guardrail info
        return GuardrailInfo(
            id=result.get('guardrailId') or result.get('id', ''),
            name=guardrail.name,
            description=guardrail.description,
            created_at=result['createdAt'],
            versions=[
                GuardrailVersion(
                    version=result['version'], created_at=result['createdAt']
                )
            ],
            current_version=result['version'],
        )
    except Exception as e:
        logger.error(f'Error creating guardrail: {e}')
        raise


async def update_guardrail(
    client: BedrockClient,
    guardrail_id: str,
    guardrail: GuardrailUpdate,
) -> GuardrailInfo:
    """Update an existing guardrail.

    Args:
        client: The Bedrock guardrails client.
        guardrail_id: The ID of the guardrail to update.
        guardrail: The updated guardrail configuration.

    Returns:
        Updated guardrail information.
    """
    try:
        # Get current guardrail to merge with updates
        current = await get_guardrail(client, guardrail_id)

        # Convert our model to Bedrock API format
        # According to AWS docs, name is required
        config: dict[str, Any] = {
            'name': guardrail.name if guardrail.name is not None else current.name,
            # These are required according to AWS documentation
            'blockedInputMessaging': guardrail.blocked_input_messaging
            if guardrail.blocked_input_messaging is not None
            else current.blocked_input_messaging,
            'blockedOutputsMessaging': guardrail.blocked_output_messaging
            if guardrail.blocked_output_messaging is not None
            else current.blocked_output_messaging,
        }

        # Add description if it's being updated (optional in AWS API)
        if guardrail.description is not None:
            config['description'] = guardrail.description

        # Add content filters using correct AWS parameter names
        if guardrail.content_filters is not None:
            filters_list = [
                {
                    'type': filter.type,
                    'inputStrength': filter.input_strength,
                    'outputStrength': filter.output_strength,
                }
                for filter in guardrail.content_filters
            ]
            config['contentPolicyConfig'] = {'filtersConfig': filters_list}

        # Add denied topics using correct AWS parameter names
        if guardrail.denied_topics is not None:
            topics_list = [
                {
                    'name': topic.name,
                    'definition': topic.definition,
                    'examples': topic.examples,
                    'type': 'DENY',
                }
                for topic in guardrail.denied_topics
            ]
            config['topicPolicyConfig'] = {'topicsConfig': topics_list}

        # Add word filters using correct AWS parameter names
        if guardrail.word_filters is not None:
            words_list = [{'text': word.text} for word in guardrail.word_filters]
            config['wordPolicyConfig'] = {'wordsConfig': words_list}

        # Add PII entities using correct AWS parameter names
        if guardrail.pii_entities is not None:
            pii_list = [
                {'type': pii.type, 'action': pii.action}
                for pii in guardrail.pii_entities
            ]
            config['sensitiveInformationPolicyConfig'] = {'piiEntitiesConfig': pii_list}

        # Update the guardrail
        result = await client.update_guardrail(guardrail_id, config)

        # Get versions
        versions = await client.list_guardrail_versions(guardrail_id)

        # Return the updated guardrail info
        return GuardrailInfo(
            id=result.get('guardrailId') or result.get('id', ''),
            name=config['name'],
            description=config.get('description', current.description),
            created_at=current.created_at,  # Keep original creation time
            versions=[
                GuardrailVersion(
                    version=version['version'], created_at=version['createdAt']
                )
                for version in versions
            ],
            current_version=versions[0]['version'] if versions else None,
        )
    except Exception as e:
        logger.error(f'Error updating guardrail {guardrail_id}: {e}')
        raise


async def delete_guardrail(
    client: BedrockClient,
    guardrail_id: str,
) -> None:
    """Delete a guardrail.

    Args:
        client: The Bedrock guardrails client.
        guardrail_id: The ID of the guardrail to delete.
    """
    try:
        await client.delete_guardrail(guardrail_id)
    except Exception as e:
        logger.error(f'Error deleting guardrail {guardrail_id}: {e}')
        raise


async def create_guardrail_version(
    client: BedrockClient,
    guardrail_id: str,
    description: str | None = None,
) -> GuardrailVersion:
    """Create a new version of a guardrail (publish the draft).

    Args:
        client: The Bedrock guardrails client.
        guardrail_id: The ID of the guardrail to create a version for.
        description: Optional description for the version.

    Returns:
        Created guardrail version information.
    """
    try:
        result = await client.publish_guardrail(guardrail_id, description)

        # Get the version info now that it's been created
        # Since publish_guardrail only returns guardrailId and version
        # but we need createdAt for our model
        guardrail_versions = await client.list_guardrail_versions(guardrail_id)

        # Find the version that was just created
        created_version = None
        for version in guardrail_versions:
            if version.get('version') == result['version']:
                created_version = version
                break

        if not created_version:
            # If we can't find the version, return with basic info
            return GuardrailVersion(
                version=result['version'], created_at=datetime.now()
            )

        return GuardrailVersion(
            version=created_version['version'], created_at=created_version['createdAt']
        )
    except Exception as e:
        logger.error(f'Error publishing guardrail {guardrail_id}: {e}')
        raise
