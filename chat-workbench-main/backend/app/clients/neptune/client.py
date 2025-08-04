# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Neptune client implementation."""

import asyncio
import json
import time
from typing import Any

from aiobotocore.session import AioSession
from loguru import logger

from app.clients.base import BaseClient, CircuitOpenError
from app.utils import get_function_name


class NeptuneClient(BaseClient):
    """Neptune client with async operations."""

    _client: Any | None = None
    _iam_role_arn: str = ''
    _endpoint_url: str = ''

    async def initialize(self) -> None:
        """Initialize Neptune client."""

        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        with self.monitor_operation(get_function_name()):
            session = AioSession()

            iam_role_arn = (
                self.settings.aws.neptune.iam_role_arn or self.settings.aws.iam_role_arn
            )
            if iam_role_arn is None:
                raise ValueError('IAM role ARN not set')
            # Ensure the iam_role_arn is not None before assignment
            self._iam_role_arn = str(iam_role_arn)

            endpoint_url = (
                self.settings.aws.neptune.endpoint_url or self.settings.aws.endpoint_url
            )
            if not endpoint_url:
                raise ValueError('Neptune endpoint URL not set')

            # Ensure the endpoint_url is not None
            endpoint_url = str(endpoint_url)

            # must start with "wss://" and end with ":8182"
            if not endpoint_url.startswith('wss://'):
                raise ValueError("Neptune endpoint URL must start with 'wss://'")
            if not endpoint_url.endswith(':8182'):
                raise ValueError("Neptune endpoint URL must end with ':8182'")

            logger.info(f'Initializing Neptune with endpoint: {endpoint_url}')

            self._endpoint_url = endpoint_url
            self._client = await session.create_client(
                'neptunedata',
                region_name=self.settings.aws.region,
                endpoint_url=self._endpoint_url,
                config=self.settings.aws.get_boto_config('neptune'),
            ).__aenter__()

            logger.info('Neptune client initialized')

    async def cleanup(self) -> None:
        """Cleanup Neptune client."""
        if self._client:
            with self.monitor_operation(get_function_name()):
                await self._client.__aexit__(None, None, None)
                logger.info('Neptune client closed')

    async def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute OpenCypher query."""
        logger.info('Executing query')
        if not self._client:
            raise ValueError('Neptune client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                payload = {'openCypherQuery': query}
                if parameters:
                    payload['parameters'] = json.dumps(parameters)

                response = await self._client.execute_open_cypher_query(**payload)
                self.circuit_breaker.record_success()
                return response['results']
            except Exception as e:
                logger.error(f'Failed to execute query: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def get_node_by_id(self, label: str, node_id: str) -> dict[str, Any] | None:
        """Get node by ID and label."""
        # In openCypher you can't parameterize the node label so it must be added here, before the query executes
        query = f"""MATCH (n:{label}) WHERE id(n) = $node_id RETURN n"""

        with self.monitor_operation(get_function_name()):
            try:
                parameters = {'node_id': node_id}
                results = await self.execute_query(query, parameters)
                print(results)
                return results[0] if results else None
            except Exception as e:
                logger.error(f'Failed to get {label} node: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def create_node(
        self, label: str, properties: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Create a new node."""
        # The structure of properties must be {"properties": {"prop1": "value1"...}}
        if 'properties' not in properties:
            properties = {'properties': properties}

        # In openCypher you can't parameterize the node label so it must be added here, before the query executes
        query = f"""CREATE (n:{label} $properties) RETURN n"""

        with self.monitor_operation(get_function_name()):
            try:
                results = await self.execute_query(query, properties)
                return results[0] if results else None
            except Exception as e:
                logger.error(f'Failed to insert {label} node: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def create_edge(
        self, source_id: str, target_id: str, label: str, properties: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Create a new edge."""

        # In openCypher you can't parameterize the node label so it must be added here, before the query executes
        query = f"""MATCH (source), (target) WHERE id(source) = $source_id AND id(target) = $target_id CREATE (source)-[r:{label} $properties]->(target) RETURN r"""

        with self.monitor_operation(get_function_name()):
            try:
                parameters = {
                    'source_id': source_id,
                    'target_id': target_id,
                    'properties': properties,
                }
                results = await self.execute_query(query, parameters)
                return results[0] if results else None
            except Exception as e:
                logger.error(f'Failed to insert {label} edge: {e}')
                self.circuit_breaker.record_failure()
                raise

    async def bulk_load_csv(
        self,
        s3_path: str,
        iam_role_arn: str | None = None,
        mode: str = 'AUTO',
        parallelism: str = 'HIGH',
        fail_on_error: bool = True,
        user_provided_edge_ids: bool = True,
        wait_for_completion: bool = True,
        timeout: int = 3600,
        refresh_graph: bool = False,
    ) -> dict[str, Any]:
        """Bulk load CSV data from S3 into Neptune using openCypher format.

        Args:
            s3_path: Full S3 path to CSV file(s) to load
            iam_role_arn: Name of role with correct permissions to bulk load from S3 to Netpune
            mode: RESUME, NEW, AUTO. In RESUME mode, the loader looks for a previous load from this source, and if it finds one, resumes that load job. If no previous load job is found, the loader stops. In NEW mode, the creates a new load request regardless of any previous loads. You can use this mode to reload all the data from a source after dropping previously loaded data from your Neptune cluster, or to load new data available at the same source.  In AUTO mode, the loader looks for a previous load job from the same source, and if it finds one, resumes that job, just as in RESUME mode. If the loader doesn't find a previous load job from the same source, it loads all data from the source, just as in NEW mode.
            parallelism: Loading parallelism (LOW, MEDIUM, HIGH, OVERSUBSCRIBE)
            fail_on_error: Whether to fail on first error
            user_provided_edge_ids: Whether relationship CSV files contain IDs
            wait_for_completion: Whether to wait for load to complete
            timeout: Timeout in seconds to wait for completion
            refresh_graph: Whether to remove all of the data in the graph and create it from scratch

        Returns:
            Dict containing load results and status

        Raises:
            ValueError: If CSV files are not in valid format
            CircuitOpenError: If circuit breaker is open
        """
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        # Validate S3 path
        if not s3_path.startswith('s3://'):
            raise ValueError('S3 path must start with s3://')

        # Use the class's _iam_role_arn if none is provided
        if not iam_role_arn:
            iam_role_arn = self._iam_role_arn

        # Ensure it's a string
        iam_role_arn = str(iam_role_arn)

        endpoint_url = self._endpoint_url
        # must start with https NOT wss
        endpoint_url = endpoint_url.replace('wss://', 'https://')

        if refresh_graph:
            logger.info('Refreshing graph')
            await self.execute_query('MATCH (n) DETACH DELETE n')

        with self.monitor_operation(get_function_name()):
            try:
                if not self._client:
                    raise ValueError('Neptune client not initialized')

                response = await self._client.start_loader_job(
                    source=s3_path,
                    format='opencypher',
                    iamRoleArn=iam_role_arn,
                    s3BucketRegion=self.settings.aws.region,
                    mode=mode,
                    userProvidedEdgeIds=user_provided_edge_ids,
                    failOnError=fail_on_error,
                    parallelism=parallelism,
                    queueRequest=True,
                )

                load_id = response['payload']['loadId']
                logger.info(f'Started bulk load job {load_id}')

                if not wait_for_completion:
                    return {'loadId': load_id, 'status': 'LOAD_IN_QUEUE'}

                # Monitor load status until complete or timeout
                start_time = time.time()
                while True:
                    status = await self._get_load_status(load_id)
                    logger.debug(status)

                    if status['overallStatus']['status'] in ['LOAD_COMPLETED']:
                        self.circuit_breaker.record_success()
                        return status

                    if status['overallStatus']['status'] in [
                        'LOAD_FAILED',
                        'LOAD_CANCELLED',
                    ]:
                        error_msg = f'Load failed with status {status["overallStatus"]["status"]}'
                        if 'errorLogs' in status:
                            error_msg += f': {status["errorLogs"]}'
                        self.circuit_breaker.record_failure()
                        raise ValueError(error_msg)

                    # Check for timeout
                    if time.time() - start_time > timeout:
                        raise TimeoutError(
                            f'Load job {load_id} timed out after {timeout} seconds'
                        )

                    await asyncio.sleep(10)  # Poll every 10 seconds

            except Exception as e:
                logger.error(f'Failed to load CSV data: {e!s}')
                self.circuit_breaker.record_failure()
                raise

        # This should never be reached due to the conditions in the loop
        # But adding explicit return to satisfy type checker
        return {
            'loadId': load_id,
            'status': 'UNKNOWN',
            'details': {'message': 'Loop exited unexpectedly'},
        }

    async def _get_load_status(self, load_id: str) -> dict[str, Any]:
        """Get status of a bulk load job."""
        if not self._client:
            raise ValueError('Neptune client not initialized')

        response = await self._client.get_loader_job_status(loadId=load_id)
        return response['payload']

    async def delete_all_data(self) -> None:
        """Delete all nodes and relationships in the Neptune graph.

        This operation will permanently remove all data from the graph database.
        Use with caution as this cannot be undone.

        Returns:
            None

        Raises:
            CircuitOpenError: If circuit breaker is open
            Exception: If deletion fails
        """
        if not self.circuit_breaker.can_execute():
            self.circuit_breaker.record_failure()
            raise CircuitOpenError('Circuit breaker is open')

        if not self._client:
            raise ValueError('Neptune client not initialized')

        with self.monitor_operation(get_function_name()):
            try:
                # This OpenCypher query matches all nodes and deletes them along with their relationships
                query = 'MATCH (n) DETACH DELETE n'
                await self.execute_query(query)
                logger.info('Successfully deleted all data from Neptune graph')
                self.circuit_breaker.record_success()
            except Exception as e:
                logger.error(f'Failed to delete all data from graph: {e}')
                self.circuit_breaker.record_failure()
                raise
