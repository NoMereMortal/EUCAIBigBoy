# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Version management utilities."""

import importlib.metadata
from functools import lru_cache


@lru_cache(maxsize=1)
def get_version() -> str:
    """Get the application version from package metadata.

    Returns:
        The version string from the installed package metadata.
        Falls back to a default version in development environments.
    """
    try:
        return importlib.metadata.version('app')
    except importlib.metadata.PackageNotFoundError:
        # Fallback for development environments where package isn't installed
        return '0.1.0'
