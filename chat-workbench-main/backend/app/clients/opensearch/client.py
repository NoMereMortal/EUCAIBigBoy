# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""OpenSearch client implementation."""

from typing import Any, Callable, Optional

import boto3
from loguru import logger
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from app.clients.base import BaseClient, CircuitOpenError
from app.config import get_settings


class OpenSearchClient(BaseClient):
    """OpenSearch client with AWS authentication."""

    _client: Any = None
    _session: Any = None
    _region: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize OpenSearch client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation('initialize'):
            try:
                # Extract hostname from URL if it contains protocol
                host = self._extract_hostname(self.settings.opensearch.host)

                # Log the endpoint_url for debugging
                logger.info(
                    f'Initializing OpenSearch client with original endpoint: {self.settings.opensearch.host}'
                )
                logger.info(
                    f'Extracted hostname: {host}, port: {self.settings.opensearch.port}'
                )
                awsauth = self._get_aws_auth()
                self._client = OpenSearch(
                    hosts=[
                        {
                            'host': self.settings.opensearch.host,
                            'port': self.settings.opensearch.port,
                        }
                    ],
                    http_auth=awsauth,
                    use_ssl=False,
                    verify_certs=False,
                    connection_class=RequestsHttpConnection,
                    timeout=60,
                )
                logger.info('OpenSearch client initialized successfully')
            except Exception as e:
                logger.error(f'Failed to initialize OpenSearch client: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def cleanup(self) -> None:
        """Clean up OpenSearch client."""
        if self._client:
            with self.monitor_operation('cleanup'):
                try:
                    # OpenSearch client doesn't have a close method like aioboto3, so we'll just set it to None
                    self._client = None
                    logger.info('OpenSearch client closed')
                except Exception as e:
                    logger.error(f'Failed to cleanup OpenSearch client: {e}')
                    self.circuit_breaker.record_failure()
                    raise

    def _extract_hostname(self, host_url: str) -> str:
        """
        Extract hostname from URL, removing protocol if present.

        Args:
            host_url: Host URL which may include protocol

        Returns:
            Just the hostname part
        """
        if '://' in host_url:
            # Remove protocol part
            hostname = host_url.split('://', 1)[1]
            logger.debug(f'Extracted hostname {hostname} from URL {host_url}')
            return hostname
        return host_url

    def _get_aws_auth(self) -> Any:
        """
        Get AWS authentication for OpenSearch.

        Returns:
            AWS4Auth object for authentication
        """
        try:
            settings = get_settings()
            profile_name = settings.aws_profile_name
            region = settings.aws_region
            service = 'aoss'

            # Store session and region for refresh operations
            self._session = boto3.Session(profile_name=profile_name)
            self._region = region

            credentials = self._session.get_credentials()
            return AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                service,
                session_token=credentials.token,
            )
        except Exception as e:
            logger.error(f'Failed to get AWS authentication: {e}')
            self.circuit_breaker.record_failure()
            raise

    def refresh_auth(self) -> bool:
        """
        Refresh AWS credentials and update the OpenSearch client with new auth.

        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            if not self._session or not self._region:
                logger.error('Session or region not available for auth refresh')
                return False

            # Get fresh credentials
            credentials = self._session.get_credentials()
            new_auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                self._region,
                'aoss',
                session_token=credentials.token,
            )

            # Update the client's connection pool with new auth
            if self._client:
                for conn in self._client.transport.connection_pool.connections:
                    conn.session.auth = new_auth

                logger.info('OpenSearch authentication refreshed')
                return True
            else:
                logger.error('OpenSearch client not available for auth refresh')
                return False
        except Exception as e:
            logger.error(f'Failed to refresh OpenSearch authentication: {e!s}')
            return False

    def with_auth_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute OpenSearch operation with automatic auth refresh on 403 errors.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        try:
            # Try the operation
            return func(*args, **kwargs)
        except Exception as e:
            # Check if it's an auth error (403 Forbidden)
            if 'Forbidden' in str(e) or '403' in str(e):
                logger.warning(f'Auth error detected: {e!s}. Refreshing credentials...')

                # Refresh the auth token
                if self.refresh_auth():
                    # Retry the operation
                    return func(*args, **kwargs)
                else:
                    logger.error('Failed to refresh auth, re-raising original error')
                    raise
            else:
                # Not an auth error, re-raise
                raise

    def get_client(self) -> Any:
        """
        Get the OpenSearch client instance.

        Returns:
            OpenSearch client instance

        Raises:
            ValueError: If the client is not initialized
        """
        if not self._client:
            raise ValueError('OpenSearch client not initialized')
        return self._client
