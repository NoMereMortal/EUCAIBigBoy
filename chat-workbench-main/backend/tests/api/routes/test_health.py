# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.app import create_app
from app.clients.dynamodb.client import DynamoDBClient
from app.clients.registry import ClientRegistry
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test cases for health check endpoint."""

    @pytest.fixture
    def app(self):
        """Create test app instance."""
        return create_app()

    def test_health_check_healthy(self, app):
        """Test health check returns healthy status when all services are available."""
        # Mock client registry
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.client_info.return_value = [
            {'name': 'dynamodb', 'initialized': True},
            {'name': 'valkey', 'initialized': True},
        ]

        # Mock DynamoDB client
        mock_dynamodb = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb.table_exists.return_value = True
        mock_registry.get_typed_client.return_value = mock_dynamodb

        # Override dependency
        app.dependency_overrides = {
            'app.api.dependencies.get_client_registry': lambda: mock_registry
        }

        try:
            with TestClient(app) as client:
                response = client.get('/health')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'
            assert data['details']['api'] == 'ok'
            assert data['details']['dynamodb'] == 'ok'
            assert data['details']['valkey'] == 'ok'
        finally:
            app.dependency_overrides.clear()

    def test_health_check_unhealthy_missing_dynamodb_client(self, app):
        """Test health check returns unhealthy when DynamoDB client is missing."""
        # Mock client registry without DynamoDB
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.client_info.return_value = [
            {'name': 'valkey', 'initialized': True},
        ]
        mock_registry.get_typed_client.return_value = None

        # Override dependency
        app.dependency_overrides = {
            'app.api.dependencies.get_client_registry': lambda: mock_registry
        }

        try:
            with TestClient(app) as client:
                response = client.get('/health')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'unhealthy'
            assert data['details']['api'] == 'ok'
            assert data['details']['valkey'] == 'ok'
        finally:
            app.dependency_overrides.clear()

    def test_health_check_unhealthy_missing_table(self, app):
        """Test health check returns unhealthy when DynamoDB table is missing."""
        # Mock client registry
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.client_info.return_value = [
            {'name': 'dynamodb', 'initialized': True},
        ]

        # Mock DynamoDB client with missing table
        mock_dynamodb = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb.table_exists.return_value = False
        mock_registry.get_typed_client.return_value = mock_dynamodb

        # Override dependency
        app.dependency_overrides = {
            'app.api.dependencies.get_client_registry': lambda: mock_registry
        }

        try:
            with TestClient(app) as client:
                response = client.get('/health')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'unhealthy'
            assert 'missing table:' in data['details']['dynamodb']
        finally:
            app.dependency_overrides.clear()

    def test_health_check_unhealthy_table_check_exception(self, app):
        """Test health check returns unhealthy when table check raises exception."""
        # Mock client registry
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.client_info.return_value = [
            {'name': 'dynamodb', 'initialized': True},
        ]

        # Mock DynamoDB client that raises exception
        mock_dynamodb = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb.table_exists.side_effect = Exception('Connection failed')
        mock_registry.get_typed_client.return_value = mock_dynamodb

        # Override dependency
        app.dependency_overrides = {
            'app.api.dependencies.get_client_registry': lambda: mock_registry
        }

        try:
            with TestClient(app) as client:
                response = client.get('/health')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'unhealthy'
            assert 'table check failed:' in data['details']['dynamodb']
            assert 'Connection failed' in data['details']['dynamodb']
        finally:
            app.dependency_overrides.clear()

    def test_health_check_uninitialized_clients(self, app):
        """Test health check shows unavailable status for uninitialized clients."""
        # Mock client registry with uninitialized clients
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.client_info.return_value = [
            {'name': 'dynamodb', 'initialized': False},
            {'name': 'valkey', 'initialized': True},
        ]

        # Mock DynamoDB client
        mock_dynamodb = AsyncMock(spec=DynamoDBClient)
        mock_dynamodb.table_exists.return_value = True
        mock_registry.get_typed_client.return_value = mock_dynamodb

        # Override dependency
        app.dependency_overrides = {
            'app.api.dependencies.get_client_registry': lambda: mock_registry
        }

        try:
            with TestClient(app) as client:
                response = client.get('/health')

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'  # Still healthy if DynamoDB works
            assert data['details']['api'] == 'ok'
            assert (
                data['details']['dynamodb'] == 'unavailable'
            )  # Shows as unavailable initially
            assert data['details']['valkey'] == 'ok'
        finally:
            app.dependency_overrides.clear()
