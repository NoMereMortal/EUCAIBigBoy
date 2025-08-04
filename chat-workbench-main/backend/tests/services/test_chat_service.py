# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for ChatService - core chat management functionality."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from app.models import (
    CitationPart,
    ImagePart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from app.repositories.chat import ChatRepository
from app.repositories.message import MessageRepository
from app.services.chat import (
    ChatNotFoundError,
    ChatService,
    ChatServiceError,
    MessageNotFoundError,
)


class TestChatService:
    """Tests for ChatService - chat management and orchestration."""

    @pytest.fixture
    def mock_message_repo(self):
        """Mock MessageRepository."""
        return AsyncMock(spec=MessageRepository)

    @pytest.fixture
    def mock_chat_repo(self):
        """Mock ChatRepository."""
        return AsyncMock(spec=ChatRepository)

    @pytest.fixture
    def chat_service(self, mock_message_repo, mock_chat_repo):
        """Create ChatService with mocked dependencies."""
        return ChatService(message_repo=mock_message_repo, chat_repo=mock_chat_repo)

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_initialization(
        self, chat_service, mock_message_repo, mock_chat_repo
    ):
        """Test ChatService initializes correctly."""
        assert chat_service.message_repo == mock_message_repo
        assert chat_service.chat_repo == mock_chat_repo
        assert chat_service.monitor is not None

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_validate_and_convert_parts_text_part(self, chat_service):
        """Test part validation with TextPart."""
        # Test with valid TextPart
        text_part = TextPart(content='Hello world')
        parts = [text_part]

        validated = chat_service._validate_and_convert_parts(parts)

        assert len(validated) == 1
        assert isinstance(validated[0], TextPart)
        assert validated[0].content == 'Hello world'

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_validate_and_convert_parts_multiple_types(self, chat_service):
        """Test part validation with multiple part types."""
        parts = [
            TextPart(content='Text content'),
            ToolCallPart(
                tool_name='calculator',
                tool_args={'expression': '2+2'},
                tool_id='calc_123',
            ),
            ToolReturnPart(
                tool_name='calculator', tool_id='calc_123', result={'answer': 4}
            ),
            CitationPart(
                document_id='doc_123', text='Citation text', page=5, section='Results'
            ),
        ]

        validated = chat_service._validate_and_convert_parts(parts)

        assert len(validated) == 4
        assert isinstance(validated[0], TextPart)
        assert isinstance(validated[1], ToolCallPart)
        assert isinstance(validated[2], ToolReturnPart)
        assert isinstance(validated[3], CitationPart)

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_validate_and_convert_parts_skip_none(self, chat_service):
        """Test part validation skips None values."""
        parts = [
            TextPart(content='Valid part'),
            None,  # Should be skipped
            TextPart(content='Another valid part'),
        ]

        validated = chat_service._validate_and_convert_parts(parts)

        assert len(validated) == 2
        assert validated[0].content == 'Valid part'
        assert validated[1].content == 'Another valid part'

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_validate_and_convert_parts_with_dict(self, chat_service):
        """Test part validation with dictionary input."""
        # Test with dict that should be converted to TextPart
        parts = [
            {
                'part_kind': 'text',
                'content': 'Text from dict',
                'metadata': {},
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
        ]

        validated = chat_service._validate_and_convert_parts(parts)

        assert len(validated) == 1
        assert isinstance(validated[0], TextPart)
        assert validated[0].content == 'Text from dict'

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_error_exceptions(self):
        """Test ChatService custom exceptions."""
        # Test base exception
        base_error = ChatServiceError('Base error')
        assert str(base_error) == 'Base error'
        assert isinstance(base_error, Exception)

        # Test ChatNotFoundError
        chat_error = ChatNotFoundError('Chat not found')
        assert str(chat_error) == 'Chat not found'
        assert isinstance(chat_error, ChatServiceError)

        # Test MessageNotFoundError
        msg_error = MessageNotFoundError('Message not found')
        assert str(msg_error) == 'Message not found'
        assert isinstance(msg_error, ChatServiceError)

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_with_image_parts(self, chat_service):
        """Test ChatService handles ImagePart correctly."""
        image_part = ImagePart(
            file_id='img_123',
            user_id='user_456',
            mime_type='image/png',
            width=800,
            height=600,
            content='[Image: img_123]',
        )

        parts = [image_part]
        validated = chat_service._validate_and_convert_parts(parts)

        assert len(validated) == 1
        assert isinstance(validated[0], ImagePart)
        assert validated[0].file_id == 'img_123'
        assert validated[0].mime_type == 'image/png'

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_part_validation_error_handling(self, chat_service):
        """Test ChatService handles validation errors gracefully."""
        # Test with malformed part dict
        parts = [
            {
                'part_kind': 'invalid_type',  # Invalid part kind
                'content': 'Should fail validation',
            }
        ]

        # Should handle validation errors gracefully
        try:
            validated = chat_service._validate_and_convert_parts(parts)
            # If it doesn't raise an error, it should filter out invalid parts
            assert len(validated) == 0 or all(
                hasattr(p, 'part_kind') for p in validated
            )
        except Exception as e:
            # If it does raise an error, make sure it's appropriate
            assert 'validation' in str(e).lower() or 'invalid' in str(e).lower()

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_monitoring_integration(self, chat_service):
        """Test ChatService has monitoring integration."""
        # Check that monitor is properly initialized
        assert hasattr(chat_service, 'monitor')
        assert chat_service.monitor is not None

        # Check that monitor has expected attributes for operation tracking
        assert hasattr(chat_service.monitor, '_operation_name')
        assert 'chat_service' in chat_service.monitor._operation_name

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_complex_message_parts(self, chat_service):
        """Test ChatService with complex multi-part messages."""
        # Create a complex message with multiple part types
        complex_parts = [
            TextPart(content='Let me help you with that calculation.'),
            ToolCallPart(
                tool_name='advanced_calculator',
                tool_args={'expression': 'sqrt(25) + log(100)', 'precision': 4},
                tool_id='calc_advanced_789',
            ),
            ToolReturnPart(
                tool_name='advanced_calculator',
                tool_id='calc_advanced_789',
                result={
                    'answer': 5.0 + 2.0,  # sqrt(25) + log10(100)
                    'steps': ['sqrt(25) = 5', 'log(100) = 2', '5 + 2 = 7'],
                    'precision': 4,
                },
            ),
            CitationPart(
                document_id='math_reference_456',
                text='Mathematical operations follow standard order of precedence.',
                page=12,
                section='Basic Operations',
                citation_id='cite_math_001',
            ),
            TextPart(content=' The final result is 7.0.'),
        ]

        validated = chat_service._validate_and_convert_parts(complex_parts)

        # Verify all parts are properly validated
        assert len(validated) == 5

        # Check specific part types and content
        assert isinstance(validated[0], TextPart)
        assert 'calculation' in validated[0].content

        assert isinstance(validated[1], ToolCallPart)
        assert validated[1].tool_name == 'advanced_calculator'
        assert 'sqrt' in validated[1].tool_args['expression']

        assert isinstance(validated[2], ToolReturnPart)
        assert validated[2].result['answer'] == 7.0
        assert 'steps' in validated[2].result

        assert isinstance(validated[3], CitationPart)
        assert validated[3].document_id == 'math_reference_456'
        assert validated[3].page == 12

        assert isinstance(validated[4], TextPart)
        assert '7.0' in validated[4].content

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_empty_parts_list(self, chat_service):
        """Test ChatService handles empty parts list."""
        parts = []
        validated = chat_service._validate_and_convert_parts(parts)

        assert validated == []
        assert len(validated) == 0

    @pytest.mark.asyncio
    @pytest.mark.service
    async def test_chat_service_mixed_valid_invalid_parts(self, chat_service):
        """Test ChatService filters invalid parts while keeping valid ones."""
        parts = [
            TextPart(content='Valid text part'),
            None,  # Invalid - None
            TextPart(content='Another valid part'),
            # Could add more invalid cases here depending on implementation
        ]

        validated = chat_service._validate_and_convert_parts(parts)

        # Should have filtered out None and kept valid parts
        assert len(validated) == 2
        assert all(isinstance(p, TextPart) for p in validated)
        assert validated[0].content == 'Valid text part'
        assert validated[1].content == 'Another valid part'
