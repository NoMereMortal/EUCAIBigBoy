# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

import json
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for updating runtime configuration and Cognito client settings.

    Args:
        event: Lambda event containing ResourceProperties with configuration data
        context: Lambda context object

    Returns:
        Dict containing PhysicalResourceId and success data
    """
    logger.info('Processing configuration update request')
    logger.debug(f'Event: {json.dumps(event, default=str)}')

    try:
        # Extract and validate properties from event
        props = event.get('ResourceProperties', {})
        required_props = [
            'applicationUri',
            'apiVersion',
            'userPoolDomainUrl',
            'clientId',
            'parameterName',
        ]

        for prop in required_props:
            if prop not in props:
                raise ValueError(f'Missing required property: {prop}')

        application_uri = props['applicationUri']
        api_version = props['apiVersion']
        user_pool_domain_url = props['userPoolDomainUrl']
        client_id = props['clientId']
        parameter_name = props['parameterName']
        user_pool_id = props.get('userPoolId')
        ui_title = props.get('uiTitle', '')

        logger.info(f'Updating configuration for application: {application_uri}')

        # Create the runtime configuration
        runtime_config = _create_runtime_config(
            application_uri=application_uri,
            api_version=api_version,
            ui_title=ui_title,
            user_pool_domain_url=user_pool_domain_url,
            client_id=client_id,
        )

        # Update SSM parameter
        _update_ssm_parameter(parameter_name, runtime_config)

        # Update Cognito client if user_pool_id is provided
        if user_pool_id:
            _update_cognito_client(user_pool_id, client_id, application_uri)

        logger.info('Configuration update completed successfully')
        return {
            'PhysicalResourceId': f'config-update-{int(time.time())}',
            'Data': {'success': True, 'parameterName': parameter_name},
        }

    except Exception as e:
        logger.error(f'Configuration update failed: {e!s}')
        raise


def _create_runtime_config(
    *,
    application_uri: str,
    api_version: str,
    ui_title: str,
    user_pool_domain_url: str,
    client_id: str,
) -> dict[str, Any]:
    """Create the runtime configuration object."""
    return {
        'API_URI': application_uri,
        'API_VERSION': api_version,
        'UI_TITLE': ui_title,
        'COGNITO': {
            'authority': user_pool_domain_url,
            'client_id': client_id,
            'redirect_uri': application_uri,
            'post_logout_redirect_uri': application_uri,
            'scope': 'openid',
            'response_type': 'code',
            'loadUserInfo': True,
            'metadata': {
                'authorization_endpoint': f'{user_pool_domain_url}/oauth2/authorize',
                'token_endpoint': f'{user_pool_domain_url}/oauth2/token',
                'userinfo_endpoint': f'{user_pool_domain_url}/oauth2/userInfo',
                'end_session_endpoint': f'{user_pool_domain_url}/logout',
            },
        },
    }


def _update_ssm_parameter(parameter_name: str, runtime_config: dict[str, Any]) -> None:
    """Update SSM parameter with runtime configuration."""
    try:
        ssm = boto3.client('ssm')
        ssm.put_parameter(
            Name=parameter_name,
            Value=json.dumps(runtime_config),
            Type='String',
            Overwrite=True,
        )
        logger.info(f'Successfully updated SSM parameter: {parameter_name}')
    except ClientError as e:
        logger.error(f'Failed to update SSM parameter {parameter_name}: {e!s}')
        raise


def _update_cognito_client(
    user_pool_id: str, client_id: str, application_uri: str
) -> None:
    """Update Cognito user pool client with callback and logout URLs."""
    try:
        callback_urls = [application_uri, 'http://localhost:3000']
        logout_urls = [application_uri, 'http://localhost:3000']

        logger.info(f'Updating Cognito client {client_id} in user pool {user_pool_id}')
        logger.info(f'Setting callback URLs: {callback_urls}')
        logger.info(f'Setting logout URLs: {logout_urls}')

        cognito = boto3.client('cognito-idp')

        # Get existing client configuration
        response = cognito.describe_user_pool_client(
            UserPoolId=user_pool_id, ClientId=client_id
        )
        client = response['UserPoolClient']

        # Update the client with new URLs while preserving existing settings
        update_response = cognito.update_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            ClientName=client['ClientName'],
            RefreshTokenValidity=client.get('RefreshTokenValidity', 30),
            AccessTokenValidity=client.get('AccessTokenValidity', 1),
            IdTokenValidity=client.get('IdTokenValidity', 1),
            TokenValidityUnits=client.get(
                'TokenValidityUnits',
                {
                    'AccessToken': 'hours',
                    'IdToken': 'hours',
                    'RefreshToken': 'days',
                },
            ),
            ReadAttributes=client.get('ReadAttributes', []),
            WriteAttributes=client.get('WriteAttributes', []),
            ExplicitAuthFlows=client.get('ExplicitAuthFlows', []),
            SupportedIdentityProviders=client.get('SupportedIdentityProviders', []),
            CallbackURLs=callback_urls,
            LogoutURLs=logout_urls,
            AllowedOAuthFlows=client.get('AllowedOAuthFlows', []),
            AllowedOAuthScopes=client.get('AllowedOAuthScopes', []),
            AllowedOAuthFlowsUserPoolClient=client.get(
                'AllowedOAuthFlowsUserPoolClient', True
            ),
            PreventUserExistenceErrors=client.get(
                'PreventUserExistenceErrors', 'ENABLED'
            ),
        )

        logger.info('Successfully updated Cognito client configuration')
        logger.debug(f'Update response: {json.dumps(update_response, default=str)}')

    except ClientError as e:
        logger.error(f'Failed to update Cognito client {client_id}: {e!s}')
        raise
