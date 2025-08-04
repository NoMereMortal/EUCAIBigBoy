# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Application configuration."""

import json
from functools import lru_cache

from botocore.config import Config
from pydantic import BaseModel, Field, model_validator  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import get_version


class AppConfig(BaseModel):
    """Application configuration."""

    title: str = Field(default='Chat Workbench')
    description: str = Field(
        default='A comprehensive workbench for chat interactions with LLMs'
    )
    version: str = Field(default_factory=get_version)


class APIConfig(BaseModel):
    """API configuration."""

    host: str = Field(default='localhost')
    port: int = Field(default=8000)
    cors_origins: list[str] | str = Field(default=['*'])
    cache_ttl: int = Field(default=300)
    max_cache_items: int = Field(default=1000)
    log_level: str = Field(default='INFO')

    @model_validator(mode='after')
    def parse_cors_origins(self) -> 'APIConfig':
        """Parse CORS origins from string to list if needed."""
        if isinstance(self.cors_origins, str):
            try:
                self.cors_origins = json.loads(self.cors_origins)
            except json.JSONDecodeError:
                # Cast to str to satisfy mypy
                if isinstance(self.cors_origins, str):
                    self.cors_origins = self.cors_origins.split(',')
        return self


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(default=True)
    rate_limit: int = Field(default=100)
    window_size: int = Field(default=60)
    fail_closed: bool = Field(default=False)


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = Field(default=True)
    authority: str | None = Field(default=None)
    client_id: str | None = Field(default=None)
    secret_name: str = Field(default='app/auth/cognito')


class DynamoDBConfig(BaseModel):
    """DynamoDB configuration."""

    endpoint_url: str | None = Field(default=None)
    region: str = Field(default='us-east-1')
    table_name: str = Field(default='app_data')


class SecretsManagerConfig(BaseModel):
    """AWS Secrets Manager configuration."""

    secret_prefix: str = Field(default='app/')
    cache_ttl: int = Field(default=300)


class NeptuneConfig(BaseModel):
    """Neptune configuration."""

    enabled: bool = Field(default=False)
    endpoint_url: str | None = Field(default=None)
    iam_role_arn: str | None = Field(default=None)


class AWSConfig(BaseModel):
    """AWS configuration."""

    region: str = Field(default='us-east-1')
    endpoint_url: str | None = Field(default=None)
    profile_name: str | None = Field(default=None)
    iam_role_arn: str | None = Field(default=None)
    dynamodb: DynamoDBConfig = Field(default_factory=DynamoDBConfig)
    neptune: NeptuneConfig = Field(default_factory=NeptuneConfig)

    def get_boto_config(self, service_name: str) -> Config:
        """Get boto3 config for a service."""
        # Default configuration
        config_params = {
            'region_name': self.region,
            'signature_version': 'v4',
            'retries': {'max_attempts': 10, 'mode': 'standard'},
        }

        # Set higher timeouts specifically for Bedrock to handle streaming
        if service_name in ['bedrock', 'bedrock-runtime']:
            return Config(
                region_name=self.region,
                signature_version='v4',
                retries={'max_attempts': 10, 'mode': 'standard'},
                connect_timeout=60,
                read_timeout=300,
            )

        return Config(**config_params)


class ValkeyConfig(BaseModel):
    """Valkey configuration."""

    host: str = Field(default='localhost')
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str | None = Field(default=None)
    password_secret_name: str | None = Field(default=None)
    ttl: int = Field(default=0)  # Default TTL in seconds, 0 means no expiration
    use_tls: bool = Field(default=True)


class OpenSearchConfig(BaseModel):
    """OpenSearch configuration."""

    enabled: bool = Field(default=False)
    host: str = Field(default='localhost')
    port: int = Field(default=9200)
    region: str = Field(default='us-east-1')

    @model_validator(mode='after')
    def set_port_based_on_host(self) -> 'OpenSearchConfig':
        """Set port based on host - 443 for HTTPS hosts, 9200 for localhost. Strip https:// prefix if present."""
        # Strip https:// prefix if present
        if self.host.startswith('https://'):
            self.host = self.host.removeprefix('https://')

        if self.host != 'localhost' and '.amazonaws.com' in self.host:
            self.port = 443
        elif self.host == 'localhost' and self.port == 443:
            # Reset to default for localhost
            self.port = 9200
        return self


class ContentStorageConfig(BaseModel):
    """Content storage configuration."""

    ttl_days: int = Field(default=60)
    base_bucket: str = Field(default='chat-content')
    local_storage_path: str | None = Field(default=None)
    force_local_storage: bool = Field(
        default=False
    )  # When True, always use local storage even if S3 is available
    max_file_size_mb: int = Field(default=4)
    max_cache_size_mb: int = Field(default=500)
    allowed_mime_types: list[str] = Field(
        default=[
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
            'image/svg+xml',
            'application/pdf',
            'text/plain',
            'text/csv',
            'text/html',
            'text/markdown',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/json',
            'application/xml',
        ]
    )


class Settings(BaseSettings):
    """Application settings using Pydantic's BaseSettings for automatic env var loading."""

    # Application Environment
    environment: str = Field(
        default='dev', description='Application environment (e.g., dev, prod)'
    )

    # API settings
    api_version: str = Field(default='v1', description='API version string (e.g., v1)')
    api_host: str = Field(default='localhost')
    api_port: int = Field(default=8000)
    api_cors_origins: list[str] | str = Field(default=['*'])
    api_cache_ttl: int = Field(default=300)
    api_max_cache_items: int = Field(default=1000)
    api_log_level: str = Field(default='INFO')

    # Rate limiting settings
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_rate_limit: int = Field(default=100)
    rate_limit_window_size: int = Field(default=60)
    rate_limit_fail_closed: bool = Field(default=False)

    # Authentication settings
    auth_enabled: bool = Field(default=True)
    auth_authority: str | None = Field(default=None)
    auth_client_id: str | None = Field(default=None)
    auth_secret_name: str = Field(default='app/auth/cognito')

    # AWS settings
    aws_region: str = Field(default='us-east-1')
    aws_endpoint_url: str | None = Field(default=None)
    aws_profile_name: str | None = Field(default=None)
    aws_iam_role_arn: str | None = Field(default=None)

    # DynamoDB settings
    dynamodb_endpoint_url: str | None = Field(default=None)
    dynamodb_region: str = Field(default='us-east-1')
    dynamodb_table_name: str = Field(default='app_data')

    # Neptune settings
    neptune_enabled: bool = Field(default=False)
    neptune_endpoint_url: str | None = Field(default=None)
    neptune_iam_role_arn: str | None = Field(default=None)

    # Secrets Manager settings
    secrets_manager_secret_prefix: str = Field(default='app/')
    secrets_manager_cache_ttl: int = Field(default=300)

    # Valkey settings
    valkey_host: str = Field(default='localhost')
    valkey_port: int = Field(default=6379)
    valkey_db: int = Field(default=0)
    valkey_password: str | None = Field(default=None)
    valkey_password_secret_name: str | None = Field(default=None)
    valkey_ttl: int = Field(default=0)
    valkey_use_tls: bool = Field(default=True)

    # OpenSearch settings
    opensearch_enabled: bool = Field(default=False)
    opensearch_host: str = Field(default='localhost')
    opensearch_port: int = Field(default=9200)
    opensearch_region: str = Field(default='us-east-1')

    # Content Storage settings
    content_storage_ttl_days: int = Field(default=60)
    content_storage_base_bucket: str = Field(default='chat-content')
    content_storage_local_path: str | None = Field(default=None)
    content_storage_force_local: bool = Field(default=False)
    content_storage_max_file_size_mb: int = Field(default=4)
    content_storage_max_cache_size_mb: int = Field(default=500)
    content_storage_allowed_mime_types: list[str] = Field(
        default=[
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/webp',
            'image/svg+xml',
            'application/pdf',
            'text/plain',
            'text/csv',
            'text/html',
            'text/markdown',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/json',
            'application/xml',
        ]
    )

    # Configure environment variable loading
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    def get_app_config(self) -> AppConfig:
        """Get application configuration."""
        return AppConfig()

    def get_api_config(self) -> APIConfig:
        """Get API configuration."""
        return APIConfig(
            host=self.api_host,
            port=self.api_port,
            cors_origins=self.api_cors_origins,
            cache_ttl=self.api_cache_ttl,
            max_cache_items=self.api_max_cache_items,
            log_level=self.api_log_level,
        )

    def get_rate_limit_config(self) -> RateLimitConfig:
        """Get rate limiting configuration."""
        return RateLimitConfig(
            enabled=self.rate_limit_enabled,
            rate_limit=self.rate_limit_rate_limit,
            window_size=self.rate_limit_window_size,
            fail_closed=self.rate_limit_fail_closed,
        )

    def get_auth_config(self) -> AuthConfig:
        """Get authentication configuration."""
        return AuthConfig(
            enabled=self.auth_enabled,
            authority=self.auth_authority,
            client_id=self.auth_client_id,
            secret_name=self.auth_secret_name,
        )

    def get_aws_config(self) -> AWSConfig:
        """Get AWS configuration."""
        return AWSConfig(
            region=self.aws_region,
            endpoint_url=self.aws_endpoint_url,
            profile_name=self.aws_profile_name,
            iam_role_arn=self.aws_iam_role_arn,
            neptune=NeptuneConfig(
                enabled=self.neptune_enabled,
                endpoint_url=self.neptune_endpoint_url,
                iam_role_arn=self.neptune_iam_role_arn,
            ),
        )

    def get_dynamodb_config(self) -> DynamoDBConfig:
        """Get DynamoDB configuration."""
        return DynamoDBConfig(
            endpoint_url=self.dynamodb_endpoint_url,
            region=self.dynamodb_region,
            table_name=self.dynamodb_table_name,
        )

    def get_secrets_manager_config(self) -> SecretsManagerConfig:
        """Get Secrets Manager configuration."""
        return SecretsManagerConfig(
            secret_prefix=self.secrets_manager_secret_prefix,
            cache_ttl=self.secrets_manager_cache_ttl,
        )

    def get_valkey_config(self) -> ValkeyConfig:
        """Get Valkey configuration."""
        return ValkeyConfig(
            host=self.valkey_host,
            port=self.valkey_port,
            db=self.valkey_db,
            password=self.valkey_password,
            password_secret_name=self.valkey_password_secret_name,
            ttl=self.valkey_ttl,
            use_tls=self.valkey_use_tls,
        )

    def get_opensearch_config(self) -> OpenSearchConfig:
        """Get OpenSearch configuration."""
        return OpenSearchConfig(
            enabled=self.opensearch_enabled,
            host=self.opensearch_host,
            port=self.opensearch_port,
            region=self.opensearch_region,
        )

    def get_content_storage_config(self) -> ContentStorageConfig:
        """Get content storage configuration."""
        return ContentStorageConfig(
            ttl_days=self.content_storage_ttl_days,
            base_bucket=self.content_storage_base_bucket,
            local_storage_path=self.content_storage_local_path,
            force_local_storage=self.content_storage_force_local,
            max_file_size_mb=self.content_storage_max_file_size_mb,
            max_cache_size_mb=self.content_storage_max_cache_size_mb,
            allowed_mime_types=self.content_storage_allowed_mime_types,
        )

    @property
    def app(self) -> AppConfig:
        """Get application configuration."""
        return self.get_app_config()

    @property
    def api(self) -> APIConfig:
        """Get API configuration."""
        return self.get_api_config()

    @property
    def rate_limit(self) -> RateLimitConfig:
        """Get rate limiting configuration."""
        return self.get_rate_limit_config()

    @property
    def auth(self) -> AuthConfig:
        """Get authentication configuration."""
        return self.get_auth_config()

    @property
    def aws(self) -> AWSConfig:
        """Get AWS configuration."""
        return self.get_aws_config()

    @property
    def dynamodb(self) -> DynamoDBConfig:
        """Get DynamoDB configuration."""
        return self.get_dynamodb_config()

    @property
    def secrets_manager(self) -> SecretsManagerConfig:
        """Get Secrets Manager configuration."""
        return self.get_secrets_manager_config()

    @property
    def valkey(self) -> ValkeyConfig:
        """Get Valkey configuration."""
        return self.get_valkey_config()

    @property
    def opensearch(self) -> OpenSearchConfig:
        """Get OpenSearch configuration."""
        return self.get_opensearch_config()

    @property
    def content_storage(self) -> ContentStorageConfig:
        """Get content storage configuration."""
        return self.get_content_storage_config()


@lru_cache
def get_settings() -> Settings:
    """Get application settings with caching."""
    return Settings()
