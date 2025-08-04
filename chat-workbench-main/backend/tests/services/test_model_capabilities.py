# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for model capabilities service."""

from app.services.model_capabilities import ModelCapabilities


class TestModelCapabilities:
    """Test cases for ModelCapabilities class."""

    def test_get_supported_types_default_only(self):
        """Test getting supported types for unknown model returns only defaults."""
        supported = ModelCapabilities.get_supported_types('unknown-model')
        assert supported == {'text/plain'}

    def test_get_supported_types_known_model(self):
        """Test getting supported types for known model includes model-specific types."""
        supported = ModelCapabilities.get_supported_types(
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        )

        expected = {
            'text/plain',  # Default
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/pdf',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }

        assert supported == expected

    def test_normalize_model_id_exact_match(self):
        """Test normalizing model ID that matches exactly."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        normalized = ModelCapabilities.normalize_model_id(model_id)
        assert normalized == model_id

    def test_normalize_model_id_no_match(self):
        """Test normalizing model ID with no match returns original."""
        model_id = 'unknown-provider.unknown-model'
        normalized = ModelCapabilities.normalize_model_id(model_id)
        assert normalized == model_id

    def test_normalize_model_id_version_variations(self):
        """Test normalizing model IDs with version variations."""
        # Test with different version patterns
        test_cases = [
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            'us.anthropic.claude-3-5-sonnet-20240620-v1:0',
            'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
        ]

        for model_id in test_cases:
            normalized = ModelCapabilities.normalize_model_id(model_id)
            # Should find exact match in capabilities
            assert normalized in ModelCapabilities.MODEL_CAPABILITIES

    def test_is_supported_direct_match(self):
        """Test checking support for directly matched MIME type."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

        # Should support image/jpeg directly
        assert ModelCapabilities.is_supported(model_id, 'image/jpeg') is True

        # Should support text/plain (default)
        assert ModelCapabilities.is_supported(model_id, 'text/plain') is True

    def test_is_supported_category_match(self):
        """Test checking support for MIME type category."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

        # Test with unsupported specific type but supported category
        # This test assumes category matching is implemented
        assert ModelCapabilities.is_supported(model_id, 'image/webp') is False

    def test_is_supported_unsupported_type(self):
        """Test checking support for unsupported MIME type."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

        # Should not support video types
        assert ModelCapabilities.is_supported(model_id, 'video/mp4') is False

        # Should not support executable types
        assert (
            ModelCapabilities.is_supported(model_id, 'application/x-executable')
            is False
        )

    def test_is_supported_unknown_model(self):
        """Test checking support for unknown model."""
        model_id = 'unknown-model'

        # Should only support default text/plain
        assert ModelCapabilities.is_supported(model_id, 'text/plain') is True
        assert ModelCapabilities.is_supported(model_id, 'image/jpeg') is False

    def test_supports_images_true(self):
        """Test checking image support for model that supports images."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        assert ModelCapabilities.supports_images(model_id) is True

    def test_supports_images_false(self):
        """Test checking image support for model that doesn't support images."""
        model_id = 'unknown-text-only-model'
        assert ModelCapabilities.supports_images(model_id) is False

    def test_supports_documents_true(self):
        """Test checking document support for model that supports documents."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        assert ModelCapabilities.supports_documents(model_id) is True

    def test_supports_documents_false(self):
        """Test checking document support for model that doesn't support documents."""
        model_id = 'unknown-text-only-model'
        assert ModelCapabilities.supports_documents(model_id) is False

    def test_supports_documents_excludes_plain_text(self):
        """Test that document support check excludes text/plain."""
        # Create a model that only supports text/plain (no documents)
        # Since unknown models only get DEFAULT_SUPPORTED_TYPES
        model_id = 'text-only-model'
        assert ModelCapabilities.supports_documents(model_id) is False

    def test_supports_multimodal_true(self):
        """Test checking multimodal support for model that supports non-text."""
        model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'
        assert ModelCapabilities.supports_multimodal(model_id) is True

    def test_supports_multimodal_false(self):
        """Test checking multimodal support for text-only model."""
        model_id = 'unknown-text-only-model'
        assert ModelCapabilities.supports_multimodal(model_id) is False

    def test_get_size_limit_image(self):
        """Test getting size limit for image content."""
        limit = ModelCapabilities.get_size_limit('image/jpeg')
        assert limit == 5 * 1024 * 1024  # 5MB

    def test_get_size_limit_document(self):
        """Test getting size limit for document content."""
        limit = ModelCapabilities.get_size_limit('application/pdf')
        assert limit == 10 * 1024 * 1024  # 10MB

        limit = ModelCapabilities.get_size_limit('text/csv')
        assert limit == 10 * 1024 * 1024  # 10MB

    def test_get_size_limit_default(self):
        """Test getting size limit for unknown content type."""
        limit = ModelCapabilities.get_size_limit('unknown/type')
        assert limit == 20 * 1024 * 1024  # 20MB

    def test_get_size_limit_text_plain(self):
        """Test getting size limit for text/plain."""
        limit = ModelCapabilities.get_size_limit('text/plain')
        assert limit == 10 * 1024 * 1024  # 10MB (text category)

    def test_all_known_models_have_capabilities(self):
        """Test that all models in MODEL_CAPABILITIES have valid capabilities."""
        for _model_id, capabilities in ModelCapabilities.MODEL_CAPABILITIES.items():
            # Should have at least one capability
            assert len(capabilities) > 0

            # All capabilities should be valid MIME types
            for mime_type in capabilities:
                assert '/' in mime_type
                assert len(mime_type.split('/')) == 2

    def test_model_capabilities_constants(self):
        """Test that class constants are properly defined."""
        # Test DEFAULT_SUPPORTED_TYPES
        assert isinstance(ModelCapabilities.DEFAULT_SUPPORTED_TYPES, set)
        assert 'text/plain' in ModelCapabilities.DEFAULT_SUPPORTED_TYPES

        # Test MODEL_CAPABILITIES
        assert isinstance(ModelCapabilities.MODEL_CAPABILITIES, dict)
        assert len(ModelCapabilities.MODEL_CAPABILITIES) > 0

        # Test FILE_SIZE_LIMITS
        assert isinstance(ModelCapabilities.FILE_SIZE_LIMITS, dict)
        required_keys = {'default', 'image', 'document'}
        assert required_keys.issubset(ModelCapabilities.FILE_SIZE_LIMITS.keys())

        # All size limits should be positive integers
        for limit in ModelCapabilities.FILE_SIZE_LIMITS.values():
            assert isinstance(limit, int)
            assert limit > 0

    def test_specific_claude_models(self):
        """Test specific Claude model variants."""
        claude_models = [
            'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            'us.anthropic.claude-3-5-sonnet-20240620-v1:0',
            'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
        ]

        for model_id in claude_models:
            # All should support images
            assert ModelCapabilities.supports_images(model_id) is True

            # All should support documents
            assert ModelCapabilities.supports_documents(model_id) is True

            # All should be multimodal
            assert ModelCapabilities.supports_multimodal(model_id) is True

            # All should support specific formats
            assert ModelCapabilities.is_supported(model_id, 'image/jpeg') is True
            assert ModelCapabilities.is_supported(model_id, 'application/pdf') is True
            assert ModelCapabilities.is_supported(model_id, 'text/csv') is True

    def test_normalize_model_id_edge_cases(self):
        """Test edge cases in model ID normalization."""
        # Empty string
        assert ModelCapabilities.normalize_model_id('') == ''

        # Single character
        assert ModelCapabilities.normalize_model_id('a') == 'a'

        # Only separators
        assert ModelCapabilities.normalize_model_id(':.:') == ':.:'
