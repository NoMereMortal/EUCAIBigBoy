# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""S3 client implementation."""

from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name


class S3Client(BaseClient):
    """S3 client with async operations."""

    _client: Any | None = None

    @staticmethod
    def _safe_extract_error_code(exception: Exception) -> tuple[str, dict]:
        """
        Safely extract error code and details from various exception types.
        Returns a tuple of (error_code, error_details)
        """
        error_code = 'Unknown'
        error_details = {}

        # Try to extract standard botocore error code
        if hasattr(exception, 'code'):
            error_code = str(getattr(exception, 'code', 'Unknown'))

        # Try to extract from ClientError-like structures
        try:
            if hasattr(exception, 'response'):
                # Don't access response directly as it might not exist
                response_dict = getattr(exception, 'response', {})
                if isinstance(response_dict, dict):
                    error_details = response_dict
                    if 'Error' in response_dict and isinstance(
                        response_dict['Error'], dict
                    ):
                        error_code = str(response_dict['Error'].get('Code', 'Unknown'))
        except (AttributeError, TypeError, ValueError):
            pass  # If any error occurs during extraction, just use the defaults

        return error_code, error_details

    async def initialize(self) -> None:
        """Initialize S3 client."""
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            logger.error('Cannot initialize S3 client: Circuit breaker is open')
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            try:
                # Log detailed AWS configuration for debugging
                aws_config = self.settings.get_aws_config()
                logger.info(f'Initializing S3 client with region: {aws_config.region}')
                logger.info(
                    f'S3 endpoint URL: {aws_config.endpoint_url or "default AWS endpoint"}'
                )

                # Create the session
                session = AioSession()

                # Log any boto configuration settings
                boto_config = aws_config.get_boto_config('s3')
                if boto_config:
                    logger.info(f'Using boto config: {boto_config}')

                # Create the client
                self._client = await session.create_client(
                    's3',
                    region_name=aws_config.region,
                    endpoint_url=aws_config.endpoint_url,
                    config=boto_config,
                ).__aenter__()

                # Log successful initialization
                logger.info('S3 client successfully initialized')
            except Exception as e:
                # Log the specific error in detail
                logger.error(
                    f'Failed to initialize S3 client: {e.__class__.__name__}: {e}'
                )

                error_code, error_details = self._safe_extract_error_code(e)
                logger.error(f'Error code: {error_code}')
                logger.error(f'Error details: {error_details}')
                logger.exception('Full stack trace for S3 client initialization error:')
                self.circuit_breaker.record_failure()
                raise

    async def cleanup(self) -> None:
        """Cleanup S3 client."""
        if self._client:
            with self.monitor_operation(get_function_name()):
                await self._client.__aexit__(None, None, None)
                logger.info('S3 client closed')

    async def get_object(self, bucket: str, key: str) -> bytes | None:
        """Get an object from S3."""
        if not self._client:
            logger.error('Cannot get S3 object: S3 client not initialized')
            raise ValueError('S3 client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                logger.info(f'S3 get_object: bucket={bucket}, key={key}')
                response = await self._client.get_object(
                    Bucket=bucket,
                    Key=key,
                )

                # Log the response metadata
                if response and isinstance(response, dict):
                    content_length = response.get('ContentLength', 'unknown')
                    content_type = response.get('ContentType', 'unknown')
                    logger.info(
                        f'S3 object found: size={content_length}, type={content_type}'
                    )

                # Read the object data
                body = response.get('Body')
                if not body:
                    logger.error('S3 response missing Body')
                    return None

                # For S3 objects, the body should be a streamable object with a read method
                data = None

                try:
                    # First, handle string or bytes directly to avoid attribute checks on them
                    if isinstance(body, str):
                        data = body.encode('utf-8')
                    elif isinstance(body, bytes):
                        data = body
                    # Handle StreamingBody from aiobotocore
                    elif hasattr(body, 'read') and callable(body.read):
                        # Type-safe approach: use the body's methods based on what's available
                        # For aiobotocore >= 2.0.0, .read() should return bytes
                        try:
                            # First try the synchronous read
                            data = body.read()
                        except Exception as e:
                            logger.warning(f'Synchronous read failed: {e}')
                            # Try alternate approaches for different aiobotocore versions
                            try:
                                # For aiobotocore < 2.0.0, we might need an async read
                                # But we don't directly await to avoid type errors
                                if hasattr(body, '_raw_stream') and hasattr(
                                    body._raw_stream, 'read'
                                ):
                                    # Access the underlying stream directly
                                    data = body._raw_stream.read()
                                else:
                                    # Last resort: just read whatever we can
                                    data = b''
                            except Exception as e2:
                                logger.error(f'All read methods failed: {e2}')
                                data = b''
                    else:
                        # We can't handle this body type
                        logger.warning(f'Unsupported body type: {type(body)}')
                        data = b''

                    # Ensure we have bytes or return empty
                    if data is None:
                        logger.warning(
                            f'Could not read data from body type: {type(body)}'
                        )
                        data = b''
                    elif not isinstance(data, bytes):
                        # Convert to bytes if needed
                        if isinstance(data, str):
                            data = data.encode('utf-8')
                        else:
                            data = str(data).encode('utf-8')

                finally:
                    # Try to close the body if it has a close method
                    # Extra type checking to ensure it's not a string or bytes
                    if (
                        body is not None
                        and not isinstance(body, str)
                        and not isinstance(body, bytes)
                        and hasattr(body, 'close')
                        and callable(body.close)
                    ):
                        try:
                            body.close()
                        except Exception as e:
                            # Just log the error but don't raise
                            logger.warning(f'Error closing S3 response body: {e}')

                logger.info(
                    f'Successfully retrieved S3 object {bucket}/{key}: {len(data)} bytes'
                )
                return data

            except Exception as e:
                error_code, error_details = self._safe_extract_error_code(e)

                logger.error(
                    f'Failed to get S3 object {bucket}/{key}: {e.__class__.__name__}: {e}'
                )
                logger.error(f'S3 error code: {error_code}')
                logger.error(f'S3 error details: {error_details}')

                if error_code == 'AccessDenied':
                    logger.error(
                        'S3 access denied error! Check IAM permissions for this bucket/object.'
                    )
                elif error_code == 'NoSuchKey':
                    logger.error(f'S3 object not found: {bucket}/{key}')

                self.circuit_breaker.record_failure()
                raise

    async def put_object(
        self, bucket: str, key: str, data: bytes, metadata: dict[str, str] | None = None
    ) -> None:
        """Put an object in S3."""
        if not self._client:
            logger.error('Cannot put S3 object: S3 client not initialized')
            raise ValueError('S3 client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # Log the request details
                logger.info(
                    f'S3 put_object: bucket={bucket}, key={key}, size={len(data)} bytes'
                )
                if metadata:
                    logger.info(f'S3 put_object metadata: {metadata}')

                params = {
                    'Bucket': bucket,
                    'Key': key,
                    'Body': data,
                }

                if metadata:
                    # Type ignore because mypy doesn't understand that dict(metadata) is valid here
                    params['Metadata'] = dict(metadata)  # type: ignore

                result = await self._client.put_object(**params)

                # Log success information
                logger.info(f'Successfully uploaded object to S3: {bucket}/{key}')
                if result:
                    etag = result.get('ETag', 'unknown')
                    logger.info(f'S3 put_object response: ETag={etag}')
            except Exception as e:
                error_code, error_details = self._safe_extract_error_code(e)

                logger.error(
                    f'Failed to put S3 object {bucket}/{key}: {e.__class__.__name__}: {e}'
                )
                logger.error(f'S3 error code: {error_code}')
                logger.error(f'S3 error details: {error_details}')

                if error_code == 'AccessDenied':
                    logger.error(
                        'S3 access denied error! Check IAM permissions for this bucket.'
                    )
                elif error_code == 'NoSuchBucket':
                    logger.error(f'S3 bucket not found: {bucket}')

                self.circuit_breaker.record_failure()
                raise

    async def list_objects(
        self, bucket: str, prefix: str | None = None
    ) -> list[dict[str, Any]]:
        """List objects in an S3 bucket."""
        if not self._client:
            raise ValueError('S3 client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                params = {
                    'Bucket': bucket,
                }

                if prefix:
                    params['Prefix'] = prefix

                response = await self._client.list_objects_v2(**params)

                # Extract object information
                objects = []
                for obj in response.get('Contents', []):
                    objects.append(
                        {
                            'key': obj.get('Key'),
                            'size': obj.get('Size'),
                            'last_modified': obj.get('LastModified'),
                            'etag': obj.get('ETag'),
                        }
                    )

                return objects
            except Exception as e:
                logger.error(f'Failed to list objects in {bucket}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def head_object(self, bucket: str, key: str) -> dict[str, Any]:
        """Get object metadata from S3."""
        if not self._client:
            raise ValueError('S3 client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                response = await self._client.head_object(
                    Bucket=bucket,
                    Key=key,
                )
                return dict(response)
            except Exception as e:
                logger.error(f'Failed to get object metadata {bucket}/{key}: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object from S3."""
        if not self._client:
            raise ValueError('S3 client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                await self._client.delete_object(
                    Bucket=bucket,
                    Key=key,
                )
            except Exception as e:
                logger.error(f'Failed to delete object {bucket}/{key}: {e}')
                self.circuit_breaker.record_failure()
                raise

    # We're not using this method anymore, removed for simplicity
