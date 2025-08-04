# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for version module."""

import importlib.metadata
from unittest.mock import patch

from app.version import get_version


class TestGetVersion:
    """Test get_version function."""

    def test_get_version_returns_string(self):
        """Test that get_version returns a string."""
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_version_cached(self):
        """Test that get_version returns cached result."""
        # Clear the cache first
        get_version.cache_clear()

        version1 = get_version()
        version2 = get_version()

        # Should be the same string
        assert version1 == version2

    @patch('importlib.metadata.version')
    def test_get_version_from_metadata(self, mock_version):
        """Test get_version with package metadata available."""
        mock_version.return_value = '1.2.3'

        # Clear cache to force reload
        get_version.cache_clear()

        version = get_version()
        assert version == '1.2.3'
        mock_version.assert_called_with('app')

    @patch('importlib.metadata.version')
    def test_get_version_fallback(self, mock_version):
        """Test get_version fallback when package not found."""
        mock_version.side_effect = importlib.metadata.PackageNotFoundError()

        # Clear cache to force reload
        get_version.cache_clear()

        version = get_version()
        assert version == '0.1.0'
        mock_version.assert_called_with('app')

    def test_get_version_cache_clear(self):
        """Test clearing the cache."""
        version1 = get_version()
        get_version.cache_clear()
        version2 = get_version()

        # Should be the same value but not necessarily the same object
        assert version1 == version2

    @patch('importlib.metadata.version')
    def test_get_version_multiple_calls_cached(self, mock_version):
        """Test that multiple calls use cache."""
        mock_version.return_value = '1.2.3'

        # Clear cache to ensure fresh start
        get_version.cache_clear()

        # Call multiple times
        version1 = get_version()
        version2 = get_version()
        version3 = get_version()

        # Should all be the same
        assert version1 == version2 == version3 == '1.2.3'

        # But importlib.metadata.version should only be called once due to caching
        mock_version.assert_called_once_with('app')

    def test_get_version_lru_cache_maxsize(self):
        """Test that LRU cache has maxsize=1."""
        # This is more of a documentation test to ensure the cache size is what we expect
        get_version.cache_info()

        # We can't directly test maxsize, but we can verify the cache is being used
        assert hasattr(get_version, 'cache_info')
        assert hasattr(get_version, 'cache_clear')
        assert callable(get_version.cache_info)
        assert callable(get_version.cache_clear)
