# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for app.utils module."""

import uuid
from datetime import date, datetime, timezone

import pytest
from app.utils import (
    generate_nanoid,
    make_json_serializable,
    mime_type_to_bedrock_format,
)
from pydantic import BaseModel


class TestMakeJsonSerializable:
    """Tests for make_json_serializable function."""

    @pytest.mark.unit
    def test_primitive_types(self):
        """Test serialization of primitive types."""
        assert make_json_serializable('string') == 'string'
        assert make_json_serializable(42) == 42
        assert make_json_serializable(3.14) == 3.14
        assert make_json_serializable(True) is True
        assert make_json_serializable(False) is False
        assert make_json_serializable(None) is None

    @pytest.mark.unit
    def test_datetime_serialization(self):
        """Test datetime and date serialization."""
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        result = make_json_serializable(dt)
        assert result == '2024-01-15T10:30:45+00:00'

        d = date(2024, 1, 15)
        result = make_json_serializable(d)
        assert result == '2024-01-15'

    @pytest.mark.unit
    def test_uuid_serialization(self):
        """Test UUID serialization."""
        test_uuid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        result = make_json_serializable(test_uuid)
        assert result == '12345678-1234-5678-1234-567812345678'

    @pytest.mark.unit
    def test_dict_serialization(self):
        """Test dictionary serialization."""
        test_dict = {
            'string': 'value',
            'number': 42,
            'datetime': datetime(2024, 1, 15, tzinfo=timezone.utc),
            'nested': {'inner': 'value'},
        }
        result = make_json_serializable(test_dict)
        expected = {
            'string': 'value',
            'number': 42,
            'datetime': '2024-01-15T00:00:00+00:00',
            'nested': {'inner': 'value'},
        }
        assert result == expected

    @pytest.mark.unit
    def test_list_serialization(self):
        """Test list and tuple serialization."""
        test_list = [
            'string',
            42,
            datetime(2024, 1, 15, tzinfo=timezone.utc),
            {'nested': 'dict'},
        ]
        result = make_json_serializable(test_list)
        expected = ['string', 42, '2024-01-15T00:00:00+00:00', {'nested': 'dict'}]
        assert result == expected

        # Test tuple
        test_tuple = ('a', 1, datetime(2024, 1, 15, tzinfo=timezone.utc))
        result = make_json_serializable(test_tuple)
        expected = ['a', 1, '2024-01-15T00:00:00+00:00']
        assert result == expected

    @pytest.mark.unit
    def test_pydantic_model_serialization(self):
        """Test Pydantic model serialization."""

        class TestModel(BaseModel):
            name: str
            value: int
            created_at: datetime

        model = TestModel(
            name='test', value=42, created_at=datetime(2024, 1, 15, tzinfo=timezone.utc)
        )
        result = make_json_serializable(model)
        expected = {
            'name': 'test',
            'value': 42,
            'created_at': '2024-01-15T00:00:00+00:00',
        }
        assert result == expected

    @pytest.mark.unit
    def test_object_with_dict_serialization(self):
        """Test object with __dict__ serialization."""

        class TestObject:
            def __init__(self):
                self.name = 'test'
                self.value = 42
                self.created_at = datetime(2024, 1, 15, tzinfo=timezone.utc)

        obj = TestObject()
        result = make_json_serializable(obj)
        expected = {
            'name': 'test',
            'value': 42,
            'created_at': '2024-01-15T00:00:00+00:00',
        }
        assert result == expected

    @pytest.mark.unit
    def test_fallback_to_string(self):
        """Test fallback to string representation."""

        class CustomObject:
            # Remove __dict__ to force fallback to string
            __slots__ = []

            def __str__(self):
                return 'custom_object_string'

        obj = CustomObject()
        result = make_json_serializable(obj)
        assert result == 'custom_object_string'


class TestGenerateNanoid:
    """Tests for generate_nanoid function."""

    @pytest.mark.unit
    def test_default_size(self):
        """Test nanoid generation with default size."""
        nanoid = generate_nanoid()
        assert isinstance(nanoid, str)
        assert len(nanoid) == 21
        # Check it contains only allowed characters
        allowed_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        assert all(c in allowed_chars for c in nanoid)

    @pytest.mark.unit
    def test_custom_size(self):
        """Test nanoid generation with custom size."""
        for size in [10, 15, 30]:
            nanoid = generate_nanoid(size=size)
            assert isinstance(nanoid, str)
            assert len(nanoid) == size

    @pytest.mark.unit
    def test_uniqueness(self):
        """Test that generated nanoids are unique."""
        ids = [generate_nanoid() for _ in range(100)]
        assert len(set(ids)) == 100  # All should be unique

    @pytest.mark.unit
    def test_consistent_alphabet(self):
        """Test that nanoid uses consistent alphabet."""
        nanoid = generate_nanoid()
        allowed_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        assert all(c in allowed_chars for c in nanoid)


class TestMimeTypeToBedockFormat:
    """Tests for mime_type_to_bedrock_format function."""

    @pytest.mark.unit
    def test_image_mime_types(self):
        """Test image MIME type conversions."""
        assert mime_type_to_bedrock_format('image/png', content_type='image') == 'png'
        assert mime_type_to_bedrock_format('image/jpeg', content_type='image') == 'jpeg'
        assert mime_type_to_bedrock_format('image/jpg', content_type='image') == 'jpeg'
        assert mime_type_to_bedrock_format('image/gif', content_type='image') == 'gif'
        assert mime_type_to_bedrock_format('image/webp', content_type='image') == 'webp'

    @pytest.mark.unit
    def test_document_mime_types(self):
        """Test document MIME type conversions."""
        assert (
            mime_type_to_bedrock_format('application/pdf', content_type='document')
            == 'pdf'
        )
        assert mime_type_to_bedrock_format('text/csv', content_type='document') == 'csv'
        assert (
            mime_type_to_bedrock_format('application/msword', content_type='document')
            == 'doc'
        )
        assert (
            mime_type_to_bedrock_format(
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                content_type='document',
            )
            == 'docx'
        )
        assert (
            mime_type_to_bedrock_format('text/plain', content_type='document') == 'txt'
        )
        assert (
            mime_type_to_bedrock_format('text/markdown', content_type='document')
            == 'md'
        )

    @pytest.mark.unit
    def test_file_path_fallback_images(self):
        """Test file path fallback for images."""
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='image.png', content_type='image'
            )
            == 'png'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='photo.jpg', content_type='image'
            )
            == 'jpeg'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='animation.gif', content_type='image'
            )
            == 'gif'
        )

    @pytest.mark.unit
    def test_file_path_fallback_documents(self):
        """Test file path fallback for documents."""
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='document.pdf', content_type='document'
            )
            == 'pdf'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='data.csv', content_type='document'
            )
            == 'csv'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='report.docx', content_type='document'
            )
            == 'docx'
        )

    @pytest.mark.unit
    def test_case_insensitive_file_paths(self):
        """Test that file path detection is case insensitive."""
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='IMAGE.PNG', content_type='image'
            )
            == 'png'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='DOCUMENT.PDF', content_type='document'
            )
            == 'pdf'
        )

    @pytest.mark.unit
    def test_s3_uri_paths(self):
        """Test handling of S3 URI paths."""
        assert (
            mime_type_to_bedrock_format(
                mime_type=None,
                file_path='s3://bucket/path/image.jpg',
                content_type='image',
            )
            == 'jpeg'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None,
                file_path='s3://bucket/documents/report.pdf',
                content_type='document',
            )
            == 'pdf'
        )

    @pytest.mark.unit
    def test_default_fallbacks(self):
        """Test default fallback behavior."""
        # No mime type or file path provided
        assert mime_type_to_bedrock_format(content_type='image') == 'png'
        assert mime_type_to_bedrock_format(content_type='document') == 'txt'

        # Unknown mime type and no file path
        assert (
            mime_type_to_bedrock_format('unknown/type', content_type='image') == 'png'
        )
        assert (
            mime_type_to_bedrock_format('unknown/type', content_type='document')
            == 'txt'
        )

        # Unknown file extension
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='file.unknown', content_type='image'
            )
            == 'png'
        )
        assert (
            mime_type_to_bedrock_format(
                mime_type=None, file_path='file.unknown', content_type='document'
            )
            == 'txt'
        )

    @pytest.mark.unit
    def test_mime_type_precedence(self):
        """Test that mime_type takes precedence over file_path."""
        # When both are provided, mime_type should be used first
        assert (
            mime_type_to_bedrock_format(
                mime_type='image/png',
                file_path='image.jpg',  # Different extension
                content_type='image',
            )
            == 'png'
        )  # Should use mime_type result

        assert (
            mime_type_to_bedrock_format(
                mime_type='application/pdf',
                file_path='document.docx',  # Different extension
                content_type='document',
            )
            == 'pdf'
        )  # Should use mime_type result
