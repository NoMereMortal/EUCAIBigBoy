# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for models module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from app.models import (
    ChatSession,
    CitationPart,
    DocumentPart,
    ImagePart,
    ListChatSessions,
    Message,
    MessagePart,
    ModelRequest,
    ModelResponse,
    ReasoningPart,
    StreamedPartUpdate,
    StreamEvent,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    get_part_kind,
    validate_content,
)


class TestValidateContent:
    """Test validate_content function."""

    def test_validate_content_valid_string(self):
        """Test validation with valid string content."""
        result = validate_content('Valid content')
        assert result == 'Valid content'

    def test_validate_content_valid_dict_with_text(self):
        """Test validation with valid dict containing text."""
        content = {'text': 'Valid text content'}
        result = validate_content(content)
        assert result == content

    def test_validate_content_none_raises_error(self):
        """Test validation with None raises error."""
        with pytest.raises(ValueError, match='Content field must not be empty'):
            validate_content(None)

    def test_validate_content_empty_string_raises_error(self):
        """Test validation with empty string raises error."""
        with pytest.raises(ValueError, match='Content field must not be empty string'):
            validate_content('')

    def test_validate_content_whitespace_string_raises_error(self):
        """Test validation with whitespace-only string raises error."""
        with pytest.raises(ValueError, match='Content field must not be empty string'):
            validate_content('   ')

    def test_validate_content_dict_empty_text_raises_error(self):
        """Test validation with dict containing empty text raises error."""
        with pytest.raises(ValueError, match='Content.text field must not be empty'):
            validate_content({'text': ''})

    def test_validate_content_dict_none_text_raises_error(self):
        """Test validation with dict containing None text raises error."""
        with pytest.raises(ValueError, match='Content.text field must not be empty'):
            validate_content({'text': None})


class TestGetPartKind:
    """Test get_part_kind function."""

    def test_get_part_kind_from_dict(self):
        """Test getting part_kind from dictionary."""
        result = get_part_kind({'part_kind': 'text'})
        assert result == 'text'

    def test_get_part_kind_from_object(self):
        """Test getting part_kind from object."""
        obj = MagicMock()
        obj.part_kind = 'image'
        result = get_part_kind(obj)
        assert result == 'image'

    def test_get_part_kind_missing_returns_none(self):
        """Test getting part_kind when missing returns None."""
        result = get_part_kind({})
        assert result is None

        obj = MagicMock()
        del obj.part_kind
        result = get_part_kind(obj)
        assert result is None


class TestMessagePart:
    """Test MessagePart base class."""

    @pytest.mark.asyncio
    async def test_message_part_not_implemented_error(self):
        """Test that MessagePart raises NotImplementedError for to_bedrock."""
        from typing import Literal

        class TestPart(MessagePart):
            # Use one of the allowed values from the parent class
            part_kind: Literal[
                'text',
                'image',
                'document',
                'tool-call',
                'tool-return',
                'reasoning',
                'citation',
            ] = 'text'

        part = TestPart(content='test content')
        # This should work without error
        assert part.content == 'test content'
        assert part.part_kind == 'text'

        # This should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            await part.to_bedrock()


class TestTextPart:
    """Test TextPart model."""

    def test_text_part_creation(self):
        """Test creating a TextPart."""
        part = TextPart(content='Hello, world!')
        assert part.part_kind == 'text'
        assert part.content == 'Hello, world!'
        assert isinstance(part.timestamp, datetime)

    def test_text_part_with_metadata(self):
        """Test TextPart with metadata."""
        metadata = {'source': 'user_input'}
        part = TextPart(content='Hello', metadata=metadata)
        assert part.metadata == metadata

    @pytest.mark.asyncio
    async def test_text_part_to_bedrock(self):
        """Test TextPart conversion to Bedrock format."""
        part = TextPart(content='Hello, world!')
        result = await part.to_bedrock()
        assert result == {'text': 'Hello, world!'}


class TestImagePart:
    """Test ImagePart model."""

    def test_image_part_creation(self):
        """Test creating an ImagePart."""
        part = ImagePart(
            file_id='test-file-id', user_id='test-user', mime_type='image/jpeg'
        )
        assert part.part_kind == 'image'
        assert part.file_id == 'test-file-id'
        assert part.user_id == 'test-user'
        assert part.mime_type == 'image/jpeg'
        assert part.content == '[Image: test-file-id]'

    def test_image_part_with_content(self):
        """Test ImagePart with explicit content."""
        part = ImagePart(
            file_id='test-file-id',
            user_id='test-user',
            mime_type='image/jpeg',
            content='Custom image description',
        )
        assert part.content == 'Custom image description'

    def test_image_part_with_dimensions(self):
        """Test ImagePart with width and height."""
        part = ImagePart(
            file_id='test-file-id',
            user_id='test-user',
            mime_type='image/jpeg',
            width=800,
            height=600,
        )
        assert part.width == 800
        assert part.height == 600

    @pytest.mark.asyncio
    async def test_image_part_to_bedrock_without_service(self):
        """Test ImagePart conversion to Bedrock without content service."""
        part = ImagePart(
            file_id='test-file-id', user_id='test-user', mime_type='image/jpeg'
        )
        result = await part.to_bedrock()
        assert result == {
            'text': '[Image test-file-id - pointer resolution unavailable]'
        }

    @pytest.mark.asyncio
    async def test_image_part_to_bedrock_with_service_no_pointer(
        self, mock_content_storage_service
    ):
        """Test ImagePart conversion when service returns no pointer."""
        part = ImagePart(
            file_id='test-file-id', user_id='test-user', mime_type='image/jpeg'
        )

        # Configure the mock to return None for this test
        mock_content_storage_service.get_pointer_from_id.return_value = None

        result = await part.to_bedrock(mock_content_storage_service)
        assert result == {'text': '[Image test-file-id not found]'}

    @pytest.mark.asyncio
    async def test_image_part_to_bedrock_with_service_and_pointer(
        self, mock_content_storage_service
    ):
        """Test ImagePart conversion with service returning pointer."""
        part = ImagePart(
            file_id='test-file-id', user_id='test-user', mime_type='image/jpeg'
        )

        # Configure the mock to return a specific pointer
        mock_content_storage_service.get_pointer_from_id.return_value = (
            's3://bucket/path/image.jpg'
        )

        with patch('app.models.mime_type_to_bedrock_format', return_value='jpeg'):
            result = await part.to_bedrock(mock_content_storage_service)

        expected = {
            'image': {
                'format': 'jpeg',
                'source': {'s3Location': {'uri': 's3://bucket/path/image.jpg'}},
            }
        }
        assert result == expected


class TestDocumentPart:
    """Test DocumentPart model."""

    def test_document_part_creation(self):
        """Test creating a DocumentPart."""
        part = DocumentPart(file_id='doc-123', mime_type='application/pdf')
        assert part.part_kind == 'document'
        assert part.file_id == 'doc-123'
        assert part.mime_type == 'application/pdf'
        assert part.content == '[Document: doc-123]'

    def test_document_part_with_title(self):
        """Test DocumentPart with title."""
        part = DocumentPart(
            file_id='doc-123', mime_type='application/pdf', title='My Document'
        )
        assert part.content == '[Document: My Document]'

    def test_document_part_with_metadata(self):
        """Test DocumentPart with page and word count."""
        part = DocumentPart(
            file_id='doc-123',
            mime_type='application/pdf',
            page_count=10,
            word_count=1000,
        )
        assert part.page_count == 10
        assert part.word_count == 1000

    @pytest.mark.asyncio
    async def test_document_part_to_bedrock_without_service(self):
        """Test DocumentPart conversion without content service."""
        part = DocumentPart(file_id='doc-123', mime_type='application/pdf')
        result = await part.to_bedrock()
        assert result == {'text': '[Document doc-123 - pointer resolution unavailable]'}

    @pytest.mark.asyncio
    async def test_document_part_to_bedrock_with_service_and_pointer(
        self, mock_content_storage_service
    ):
        """Test DocumentPart conversion with service and pointer."""
        part = DocumentPart(
            file_id='doc-123', mime_type='application/pdf', title='My Document'
        )

        # Configure the mock to return a specific pointer
        mock_content_storage_service.get_pointer_from_id.return_value = (
            's3://bucket/path/doc.pdf'
        )

        with patch('app.models.mime_type_to_bedrock_format', return_value='pdf'):
            result = await part.to_bedrock(mock_content_storage_service)

        expected = {
            'document': {
                'format': 'pdf',
                'name': 'My Document',
                'source': {'s3Location': {'uri': 's3://bucket/path/doc.pdf'}},
            }
        }
        assert result == expected


class TestToolCallPart:
    """Test ToolCallPart model."""

    def test_tool_call_part_creation(self):
        """Test creating a ToolCallPart."""
        part = ToolCallPart(
            tool_name='calculator', tool_args={'operation': 'add', 'a': 1, 'b': 2}
        )
        assert part.part_kind == 'tool-call'
        assert part.tool_name == 'calculator'
        assert part.tool_args == {'operation': 'add', 'a': 1, 'b': 2}
        assert part.tool_id is not None

    def test_tool_call_part_with_custom_id(self):
        """Test ToolCallPart with custom tool_id."""
        part = ToolCallPart(
            tool_name='calculator', tool_args={'operation': 'add'}, tool_id='custom-id'
        )
        assert part.tool_id == 'custom-id'

    @pytest.mark.asyncio
    async def test_tool_call_part_to_bedrock(self):
        """Test ToolCallPart conversion to Bedrock format."""
        part = ToolCallPart(
            tool_name='calculator',
            tool_args={'operation': 'add', 'a': 1, 'b': 2},
            tool_id='test-id',
        )
        result = await part.to_bedrock()
        expected = {
            'toolUse': {
                'toolUseId': 'test-id',
                'name': 'calculator',
                'input': {'operation': 'add', 'a': 1, 'b': 2},
            }
        }
        assert result == expected


class TestToolReturnPart:
    """Test ToolReturnPart model."""

    def test_tool_return_part_creation(self):
        """Test creating a ToolReturnPart."""
        part = ToolReturnPart(
            tool_name='calculator', tool_id='test-id', result={'result': 3}
        )
        assert part.part_kind == 'tool-return'
        assert part.tool_name == 'calculator'
        assert part.tool_id == 'test-id'
        assert part.result == {'result': 3}

    @pytest.mark.asyncio
    async def test_tool_return_part_to_bedrock_string_result(self):
        """Test ToolReturnPart conversion with string result."""
        part = ToolReturnPart(
            tool_name='calculator', tool_id='test-id', result='The answer is 3'
        )
        result = await part.to_bedrock()
        expected = {
            'toolResult': {
                'toolUseId': 'test-id',
                'content': [{'text': 'The answer is 3'}],
                'status': 'success',
            }
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_tool_return_part_to_bedrock_dict_result(self):
        """Test ToolReturnPart conversion with dict result."""
        part = ToolReturnPart(
            tool_name='calculator',
            tool_id='test-id',
            result={'text': 'Result is 3', 'json': {'value': 3}},
        )
        result = await part.to_bedrock()
        expected = {
            'toolResult': {
                'toolUseId': 'test-id',
                'content': [{'json': {'value': 3}}, {'text': 'Result is 3'}],
                'status': 'success',
            }
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_tool_return_part_to_bedrock_non_string_non_dict_result(self):
        """Test ToolReturnPart conversion with non-string, non-dict result."""
        # Test with integer
        part = ToolReturnPart(tool_name='calculator', tool_id='test-id', result=42)
        result = await part.to_bedrock()
        expected = {
            'toolResult': {
                'toolUseId': 'test-id',
                'content': [{'text': '42'}],
                'status': 'success',
            }
        }
        assert result == expected

        # Test with list
        part = ToolReturnPart(
            tool_name='list_tool', tool_id='test-id-2', result=[1, 2, 3]
        )
        result = await part.to_bedrock()
        expected = {
            'toolResult': {
                'toolUseId': 'test-id-2',
                'content': [{'text': '[1, 2, 3]'}],
                'status': 'success',
            }
        }
        assert result == expected


class TestReasoningPart:
    """Test ReasoningPart model."""

    def test_reasoning_part_creation(self):
        """Test creating a ReasoningPart."""
        part = ReasoningPart(content='This is my reasoning...')
        assert part.part_kind == 'reasoning'
        assert part.content == 'This is my reasoning...'
        assert part.signature is None
        assert part.redacted_content == b''

    def test_reasoning_part_with_signature(self):
        """Test ReasoningPart with signature."""
        part = ReasoningPart(content='Reasoning content', signature='sha256:abcd1234')
        assert part.signature == 'sha256:abcd1234'

    @pytest.mark.asyncio
    async def test_reasoning_part_to_bedrock(self):
        """Test ReasoningPart conversion to Bedrock format."""
        part = ReasoningPart(content='This is my reasoning', signature='sha256:test')
        result = await part.to_bedrock()
        expected = {
            'reasoningContent': {
                'reasoningText': {
                    'text': 'This is my reasoning',
                    'signature': 'sha256:test',
                },
                'redactedContent': b'',
            }
        }
        assert result == expected


class TestCitationPart:
    """Test CitationPart model."""

    def test_citation_part_creation_with_text(self):
        """Test creating CitationPart with text."""
        part = CitationPart(document_id='doc-123', text='This is cited text')
        assert part.part_kind == 'citation'
        assert part.document_id == 'doc-123'
        assert part.text == 'This is cited text'
        assert '[Citation from doc-123]: This is cited text' in part.content

    def test_citation_part_creation_with_content(self):
        """Test creating CitationPart with content."""
        part = CitationPart(
            document_id='doc-123', content='[Citation from doc-123]: This is cited text'
        )
        assert part.text == 'This is cited text'

    def test_citation_part_creation_content_only(self):
        """Test creating CitationPart with only content (no text)."""
        part = CitationPart(
            document_id='doc-123',
            content='[Citation from doc-123]: Extracted text content',
        )
        # Text should be extracted from content
        assert part.text == 'Extracted text content'
        assert part.content == '[Citation from doc-123]: Extracted text content'

    def test_citation_part_creation_both_provided(self):
        """Test creating CitationPart when both text and content are provided."""
        part = CitationPart(
            document_id='doc-123',
            text='Original text',
            content='[Citation from doc-123]: Different content',
        )
        # Both should remain as provided (no synchronization when both exist)
        assert part.text == 'Original text'
        assert part.content == '[Citation from doc-123]: Different content'

    def test_citation_part_creation_neither_provided(self):
        """Test creating CitationPart when neither text nor content are provided."""
        part = CitationPart(document_id='doc-123')
        # Should set defaults
        assert part.text == 'No citation content available'
        assert part.content == '[Citation: No content available]'

    def test_citation_part_with_page(self):
        """Test CitationPart with page number."""
        part = CitationPart(document_id='doc-123', text='Cited text', page=5)
        assert part.page == 5
        assert '(page 5)' in part.content

    def test_citation_part_text_setter(self):
        """Test CitationPart text property setter."""
        part = CitationPart(document_id='doc-123', text='Original text')
        # Check that the text getter works correctly
        assert part.text == 'Original text'

        # Try setting a new text value
        part.text = 'Updated text'
        assert part.text == 'Updated text'

        # Note: The content may not update automatically depending on implementation
        # This test verifies the text property behavior works correctly

    @pytest.mark.asyncio
    async def test_citation_part_to_bedrock(self):
        """Test CitationPart conversion to Bedrock format."""
        part = CitationPart(
            document_id='doc-123',
            text='This is cited text',
            page=5,
            citation_id='cite-123',
        )
        result = await part.to_bedrock()
        expected_text = '[Citation from doc-123 (page 5)]: This is cited text. Citation ID: cite-123'
        assert result == {'text': expected_text}


class TestMessage:
    """Test Message model."""

    def test_message_creation(self):
        """Test creating a Message."""
        message = Message(message_id='msg-123', chat_id='chat-123', kind='request')
        assert message.message_id == 'msg-123'
        assert message.chat_id == 'chat-123'
        assert message.kind == 'request'
        assert message.parent_id == 'chat-123'  # Defaults to chat_id
        assert message.parts == []
        assert message.status == 'complete'

    def test_message_with_parts(self):
        """Test Message with parts."""
        text_part = TextPart(content='Hello')
        message = Message(
            message_id='msg-123', chat_id='chat-123', kind='request', parts=[text_part]
        )
        assert len(message.parts) == 1
        assert message.parts[0].content == 'Hello'

    def test_message_with_parent_id(self):
        """Test Message with explicit parent_id."""
        message = Message(
            message_id='msg-123',
            chat_id='chat-123',
            parent_id='parent-123',
            kind='request',
        )
        assert message.parent_id == 'parent-123'

    @pytest.mark.asyncio
    async def test_message_to_bedrock_request(self):
        """Test Message conversion to Bedrock format for request."""
        text_part = TextPart(content='Hello, world!')
        message = Message(
            message_id='msg-123', chat_id='chat-123', kind='request', parts=[text_part]
        )
        result = await message.to_bedrock()
        expected = {'role': 'user', 'content': [{'text': 'Hello, world!'}]}
        assert result == expected

    @pytest.mark.asyncio
    async def test_message_to_bedrock_response(self):
        """Test Message conversion to Bedrock format for response."""
        text_part = TextPart(content='Hello back!')
        message = Message(
            message_id='msg-123', chat_id='chat-123', kind='response', parts=[text_part]
        )
        result = await message.to_bedrock()
        expected = {'role': 'assistant', 'content': [{'text': 'Hello back!'}]}
        assert result == expected

    @pytest.mark.asyncio
    async def test_message_to_bedrock_multiple_parts(self):
        """Test Message conversion with multiple parts."""
        text_part = TextPart(content='Text content')
        citation_part = CitationPart(document_id='doc-123', text='Cited text')

        message = Message(
            message_id='msg-123',
            chat_id='chat-123',
            kind='request',
            parts=[text_part, citation_part],
        )
        result = await message.to_bedrock()

        assert result['role'] == 'user'
        assert len(result['content']) == 2
        assert result['content'][0] == {'text': 'Text content'}
        assert 'Citation from doc-123' in result['content'][1]['text']

    @pytest.mark.asyncio
    async def test_message_to_bedrock_messages_static_method(self):
        """Test Message.to_bedrock_messages static method."""
        message1 = Message(
            message_id='msg-1',
            chat_id='chat-123',
            kind='request',
            parts=[TextPart(content='Hello')],
        )
        message2 = Message(
            message_id='msg-2',
            chat_id='chat-123',
            kind='response',
            parts=[TextPart(content='Hi there')],
        )

        messages = [message1, message2]
        result = await Message.to_bedrock_messages(messages)

        assert len(result) == 2
        assert result[0]['role'] == 'user'
        assert result[0]['content'] == [{'text': 'Hello'}]
        assert result[1]['role'] == 'assistant'
        assert result[1]['content'] == [{'text': 'Hi there'}]


class TestModelRequest:
    """Test ModelRequest model."""

    def test_model_request_creation(self):
        """Test creating a ModelRequest."""
        request = ModelRequest(message_id='req-123', chat_id='chat-123')
        assert request.kind == 'request'
        assert request.message_id == 'req-123'


class TestModelResponse:
    """Test ModelResponse model."""

    def test_model_response_creation(self):
        """Test creating a ModelResponse."""
        response = ModelResponse(
            message_id='resp-123', chat_id='chat-123', model_name='claude-3-sonnet'
        )
        assert response.kind == 'response'
        assert response.model_name == 'claude-3-sonnet'
        assert response.usage == {}

    def test_model_response_with_usage(self):
        """Test ModelResponse with usage data."""
        usage = {'input_tokens': 100, 'output_tokens': 50}
        response = ModelResponse(
            message_id='resp-123',
            chat_id='chat-123',
            model_name='claude-3-sonnet',
            usage=usage,
        )
        assert response.usage == usage


class TestChatSession:
    """Test ChatSession model."""

    def test_chat_session_creation(self):
        """Test creating a ChatSession."""
        session = ChatSession(user_id='user-123', title='Test Chat')
        assert session.user_id == 'user-123'
        assert session.title == 'Test Chat'
        assert session.chat_id is not None
        assert session.status == 'active'
        assert session.messages == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)

    def test_chat_session_with_messages(self):
        """Test ChatSession with messages."""
        message = Message(message_id='msg-123', chat_id='chat-123', kind='request')
        session = ChatSession(user_id='user-123', title='Test Chat', messages=[message])
        assert len(session.messages) == 1


class TestStreamEvent:
    """Test StreamEvent model."""

    def test_stream_event_creation(self):
        """Test creating a StreamEvent."""
        event = StreamEvent(type='content', data={'text': 'Hello'}, sequence=1)
        assert event.type == 'content'
        assert event.data == {'text': 'Hello'}
        assert event.sequence == 1
        assert isinstance(event.timestamp, datetime)


class TestStreamedPartUpdate:
    """Test StreamedPartUpdate model."""

    def test_streamed_part_update_creation(self):
        """Test creating a StreamedPartUpdate."""
        update = StreamedPartUpdate(part_index=0, content_delta='Hello')
        assert update.part_index == 0
        assert update.content_delta == 'Hello'
        assert update.content_complete is False
        assert update.metadata == {}

    def test_streamed_part_update_complete(self):
        """Test StreamedPartUpdate with completion flag."""
        update = StreamedPartUpdate(
            part_index=0, content_delta='', content_complete=True
        )
        assert update.content_complete is True


class TestListChatSessions:
    """Test ListChatSessions model."""

    def test_list_chat_sessions_creation(self):
        """Test creating a ListChatSessions."""
        session = ChatSession(user_id='user-123', title='Test')
        response = ListChatSessions(chats=[session])
        assert len(response.chats) == 1
        assert response.last_evaluated_key is None

    def test_list_chat_sessions_with_pagination(self):
        """Test ListChatSessions with pagination key."""
        session = ChatSession(user_id='user-123', title='Test')
        response = ListChatSessions(
            chats=[session], last_evaluated_key={'pk': 'user-123', 'sk': 'chat-123'}
        )
        assert response.last_evaluated_key == {'pk': 'user-123', 'sk': 'chat-123'}
