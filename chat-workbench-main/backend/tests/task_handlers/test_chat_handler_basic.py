# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Basic tests for ChatHandler initialization and properties."""

from unittest.mock import AsyncMock

import pytest
from app.clients.bedrock_runtime.client import BedrockRuntimeClient
from app.clients.opensearch.client import OpenSearchClient
from app.task_handlers.chat.handler import ChatHandler
from botocore.config import Config


class TestChatHandlerBasics:
    """Basic tests for ChatHandler that don't require complex mocking."""

    @pytest.fixture
    def mock_opensearch_client(self):
        """Mock OpenSearch client."""
        return AsyncMock(spec=OpenSearchClient)

    @pytest.fixture
    def mock_bedrock_runtime_client(self):
        """Mock Bedrock Runtime client."""
        return AsyncMock(spec=BedrockRuntimeClient)

    @pytest.fixture
    def mock_botocore_config(self):
        """Mock Botocore config."""
        return Config(region_name='us-east-1')

    @pytest.mark.unit
    def test_chat_handler_initialization(
        self, mock_opensearch_client, mock_bedrock_runtime_client, mock_botocore_config
    ):
        """Test ChatHandler can be initialized with required dependencies."""
        # Act
        handler = ChatHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
            botocore_config=mock_botocore_config,
        )

        # Assert
        assert handler is not None
        assert handler.name == 'chat'
        assert 'Strands Agent' in handler.description
        assert isinstance(handler.tools, list)
        assert len(handler.tools) > 0

    @pytest.mark.unit
    def test_chat_handler_properties(
        self, mock_opensearch_client, mock_bedrock_runtime_client, mock_botocore_config
    ):
        """Test ChatHandler properties return expected values."""
        # Arrange
        handler = ChatHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
            botocore_config=mock_botocore_config,
        )

        # Act & Assert
        assert handler.name == 'chat'
        assert isinstance(handler.description, str)
        assert len(handler.description) > 0

        # Check tools list
        tools = handler.tools
        assert isinstance(tools, list)
        expected_tools = [
            'calculator',
            'http_request',
            'current_time',
            'knowledge_base_search',
        ]
        for tool in expected_tools:
            assert tool in tools

    @pytest.mark.unit
    def test_chat_handler_block_context_management(
        self, mock_opensearch_client, mock_bedrock_runtime_client, mock_botocore_config
    ):
        """Test ChatHandler internal context management."""
        # Arrange
        handler = ChatHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
            botocore_config=mock_botocore_config,
        )

        # Act - Test private methods that manage content blocks
        context1 = handler._get_or_create_block_context(0)
        context2 = handler._get_or_create_block_context(0)  # Same index
        context3 = handler._get_or_create_block_context(1)  # Different index

        # Assert
        assert context1 is context2  # Same object for same index
        assert context1 is not context3  # Different object for different index
        assert len(handler._content_blocks) == 2  # Two contexts created

        # Test cleanup
        handler._cleanup_block_context(0)
        assert 0 not in handler._content_blocks
        assert 1 in handler._content_blocks  # Other context still exists

    @pytest.mark.unit
    def test_chat_handler_tool_mapping(
        self, mock_opensearch_client, mock_bedrock_runtime_client, mock_botocore_config
    ):
        """Test ChatHandler tool ID mapping functionality."""
        # Arrange
        handler = ChatHandler(
            opensearch_client=mock_opensearch_client,
            bedrock_runtime_client=mock_bedrock_runtime_client,
            botocore_config=mock_botocore_config,
        )

        # Act - Test tool ID mapping (internal state)
        assert hasattr(handler, '_tool_id_mapping')
        assert isinstance(handler._tool_id_mapping, dict)
        assert len(handler._tool_id_mapping) == 0  # Initially empty
