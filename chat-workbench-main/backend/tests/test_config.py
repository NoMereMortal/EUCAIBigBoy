# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Tests for config module."""

from app.config import (
    APIConfig,
    AppConfig,
    AuthConfig,
    AWSConfig,
    ContentStorageConfig,
    DynamoDBConfig,
    NeptuneConfig,
    OpenSearchConfig,
    RateLimitConfig,
    SecretsManagerConfig,
    Settings,
    ValkeyConfig,
    get_settings,
)
from botocore.config import Config


class TestAppConfig:
    """Test AppConfig model."""

    def test_app_config_defaults(self):
        """Test default values for AppConfig."""
        config = AppConfig()
        assert config.title == 'Chat Workbench'
        assert (
            config.description
            == 'A comprehensive workbench for chat interactions with LLMs'
        )
        assert config.version is not None

    def test_app_config_custom_values(self):
        """Test custom values for AppConfig."""
        config = AppConfig(
            title='Custom Title', description='Custom Description', version='1.0.0'
        )
        assert config.title == 'Custom Title'
        assert config.description == 'Custom Description'
        assert config.version == '1.0.0'


class TestAPIConfig:
    """Test APIConfig model."""

    def test_api_config_defaults(self):
        """Test default values for APIConfig."""
        config = APIConfig()
        assert config.host == 'localhost'
        assert config.port == 8000
        assert config.cors_origins == ['*']
        assert config.cache_ttl == 300
        assert config.max_cache_items == 1000
        assert config.log_level == 'INFO'

    def test_cors_origins_json_string(self):
        """Test parsing CORS origins from JSON string."""
        config = APIConfig(
            cors_origins='["http://localhost:3000", "https://example.com"]'
        )
        assert config.cors_origins == ['http://localhost:3000', 'https://example.com']

    def test_cors_origins_comma_separated(self):
        """Test parsing CORS origins from comma-separated string."""
        config = APIConfig(cors_origins='http://localhost:3000,https://example.com')
        assert config.cors_origins == ['http://localhost:3000', 'https://example.com']

    def test_cors_origins_invalid_json(self):
        """Test handling invalid JSON in CORS origins."""
        config = APIConfig(cors_origins='invalid-json,another-origin')
        assert config.cors_origins == ['invalid-json', 'another-origin']

    def test_cors_origins_list(self):
        """Test CORS origins as list."""
        origins = ['http://localhost:3000', 'https://example.com']
        config = APIConfig(cors_origins=origins)
        assert config.cors_origins == origins


class TestRateLimitConfig:
    """Test RateLimitConfig model."""

    def test_rate_limit_config_defaults(self):
        """Test default values for RateLimitConfig."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.rate_limit == 100
        assert config.window_size == 60
        assert config.fail_closed is False

    def test_rate_limit_config_custom(self):
        """Test custom values for RateLimitConfig."""
        config = RateLimitConfig(
            enabled=False, rate_limit=50, window_size=120, fail_closed=True
        )
        assert config.enabled is False
        assert config.rate_limit == 50
        assert config.window_size == 120
        assert config.fail_closed is True


class TestAuthConfig:
    """Test AuthConfig model."""

    def test_auth_config_defaults(self):
        """Test default values for AuthConfig."""
        config = AuthConfig()
        assert config.enabled is True
        assert config.authority is None
        assert config.client_id is None
        assert config.secret_name == 'app/auth/cognito'

    def test_auth_config_custom(self):
        """Test custom values for AuthConfig."""
        config = AuthConfig(
            enabled=False,
            authority='https://example.auth0.com/',
            client_id='test-client-id',
            secret_name='custom/secret',  # noqa: S106
        )
        assert config.enabled is False
        assert config.authority == 'https://example.auth0.com/'
        assert config.client_id == 'test-client-id'
        assert config.secret_name == 'custom/secret'


class TestDynamoDBConfig:
    """Test DynamoDBConfig model."""

    def test_dynamodb_config_defaults(self):
        """Test default values for DynamoDBConfig."""
        config = DynamoDBConfig()
        assert config.endpoint_url is None
        assert config.region == 'us-east-1'
        assert config.table_name == 'app_data'

    def test_dynamodb_config_custom(self):
        """Test custom values for DynamoDBConfig."""
        config = DynamoDBConfig(
            endpoint_url='http://localhost:8000',
            region='us-west-2',
            table_name='custom_table',
        )
        assert config.endpoint_url == 'http://localhost:8000'
        assert config.region == 'us-west-2'
        assert config.table_name == 'custom_table'


class TestSecretsManagerConfig:
    """Test SecretsManagerConfig model."""

    def test_secrets_manager_config_defaults(self):
        """Test default values for SecretsManagerConfig."""
        config = SecretsManagerConfig()
        assert config.secret_prefix == 'app/'
        assert config.cache_ttl == 300

    def test_secrets_manager_config_custom(self):
        """Test custom values for SecretsManagerConfig."""
        config = SecretsManagerConfig(secret_prefix='custom/', cache_ttl=600)  # noqa: S106
        assert config.secret_prefix == 'custom/'
        assert config.cache_ttl == 600


class TestNeptuneConfig:
    """Test NeptuneConfig model."""

    def test_neptune_config_defaults(self):
        """Test default values for NeptuneConfig."""
        config = NeptuneConfig()
        assert config.enabled is False
        assert config.endpoint_url is None
        assert config.iam_role_arn is None

    def test_neptune_config_custom(self):
        """Test custom values for NeptuneConfig."""
        config = NeptuneConfig(
            enabled=True,
            endpoint_url='https://neptune.amazonaws.com',
            iam_role_arn='arn:aws:iam::123456789012:role/NeptuneRole',
        )
        assert config.enabled is True
        assert config.endpoint_url == 'https://neptune.amazonaws.com'
        assert config.iam_role_arn == 'arn:aws:iam::123456789012:role/NeptuneRole'


class TestAWSConfig:
    """Test AWSConfig model."""

    def test_aws_config_defaults(self):
        """Test default values for AWSConfig."""
        config = AWSConfig()
        assert config.region == 'us-east-1'
        assert config.endpoint_url is None
        assert config.profile_name is None
        assert config.iam_role_arn is None
        assert isinstance(config.dynamodb, DynamoDBConfig)
        assert isinstance(config.neptune, NeptuneConfig)

    def test_get_boto_config_default(self):
        """Test getting boto config for default service."""
        config = AWSConfig()
        boto_config = config.get_boto_config('s3')

        assert isinstance(boto_config, Config)
        # Access the config values from the internal dictionary
        assert boto_config._user_provided_options['region_name'] == 'us-east-1'
        assert boto_config._user_provided_options['signature_version'] == 'v4'

    def test_get_boto_config_bedrock(self):
        """Test getting boto config for Bedrock service."""
        config = AWSConfig()
        boto_config = config.get_boto_config('bedrock')

        assert isinstance(boto_config, Config)
        assert boto_config._user_provided_options['region_name'] == 'us-east-1'
        assert boto_config._user_provided_options['signature_version'] == 'v4'
        assert boto_config._user_provided_options['connect_timeout'] == 60
        assert boto_config._user_provided_options['read_timeout'] == 300

    def test_get_boto_config_bedrock_runtime(self):
        """Test getting boto config for Bedrock Runtime service."""
        config = AWSConfig()
        boto_config = config.get_boto_config('bedrock-runtime')

        assert isinstance(boto_config, Config)
        assert boto_config._user_provided_options['connect_timeout'] == 60
        assert boto_config._user_provided_options['read_timeout'] == 300


class TestValkeyConfig:
    """Test ValkeyConfig model."""

    def test_valkey_config_defaults(self):
        """Test default values for ValkeyConfig."""
        config = ValkeyConfig()
        assert config.host == 'localhost'
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.password_secret_name is None
        assert config.ttl == 0
        assert config.use_tls is True

    def test_valkey_config_custom(self):
        """Test custom values for ValkeyConfig."""
        config = ValkeyConfig(
            host='redis.example.com',
            port=6380,
            db=1,
            password='secret',  # noqa: S106
            password_secret_name='redis/password',  # noqa: S106
            ttl=3600,
            use_tls=False,
        )
        assert config.host == 'redis.example.com'
        assert config.port == 6380
        assert config.db == 1
        assert config.password == 'secret'
        assert config.password_secret_name == 'redis/password'
        assert config.ttl == 3600
        assert config.use_tls is False


class TestOpenSearchConfig:
    """Test OpenSearchConfig model."""

    def test_opensearch_config_defaults(self):
        """Test default values for OpenSearchConfig."""
        config = OpenSearchConfig()
        assert config.enabled is False
        assert config.host == 'localhost'
        assert config.port == 9200
        assert config.region == 'us-east-1'

    def test_opensearch_config_localhost(self):
        """Test OpenSearch config with localhost."""
        config = OpenSearchConfig(host='localhost')
        assert config.host == 'localhost'
        assert config.port == 9200

    def test_opensearch_config_aws_host(self):
        """Test OpenSearch config with AWS host."""
        config = OpenSearchConfig(host='search-domain.us-east-1.es.amazonaws.com')
        assert config.host == 'search-domain.us-east-1.es.amazonaws.com'
        assert config.port == 443

    def test_opensearch_config_https_prefix(self):
        """Test OpenSearch config with https:// prefix."""
        config = OpenSearchConfig(
            host='https://search-domain.us-east-1.es.amazonaws.com'
        )
        assert config.host == 'search-domain.us-east-1.es.amazonaws.com'
        assert config.port == 443

    def test_opensearch_config_localhost_port_443_reset(self):
        """Test OpenSearch config resets port 443 to 9200 for localhost."""
        config = OpenSearchConfig(host='localhost', port=443)
        assert config.host == 'localhost'
        assert config.port == 9200


class TestContentStorageConfig:
    """Test ContentStorageConfig model."""

    def test_content_storage_config_defaults(self):
        """Test default values for ContentStorageConfig."""
        config = ContentStorageConfig()
        assert config.ttl_days == 60
        assert config.base_bucket == 'chat-content'
        assert config.local_storage_path is None
        assert config.force_local_storage is False
        assert config.max_file_size_mb == 4
        assert config.max_cache_size_mb == 500
        assert len(config.allowed_mime_types) > 0
        assert 'image/jpeg' in config.allowed_mime_types
        assert 'application/pdf' in config.allowed_mime_types

    def test_content_storage_config_custom(self):
        """Test custom values for ContentStorageConfig."""
        mime_types = ['image/png', 'text/plain']
        config = ContentStorageConfig(
            ttl_days=30,
            base_bucket='custom-bucket',
            local_storage_path='/tmp/storage',  # noqa: S108
            force_local_storage=True,
            max_file_size_mb=10,
            max_cache_size_mb=1000,
            allowed_mime_types=mime_types,
        )
        assert config.ttl_days == 30
        assert config.base_bucket == 'custom-bucket'
        assert config.local_storage_path == '/tmp/storage'  # noqa: S108
        assert config.force_local_storage is True
        assert config.max_file_size_mb == 10
        assert config.max_cache_size_mb == 1000
        assert config.allowed_mime_types == mime_types


class TestSettings:
    """Test Settings model."""

    def test_settings_defaults(self):
        """Test default values for Settings."""
        settings = Settings()
        assert settings.api_host == 'localhost'
        assert settings.api_port == 8000
        assert settings.auth_enabled is True
        assert settings.aws_region == 'us-east-1'

    def test_settings_property_access(self):
        """Test property access for settings."""
        settings = Settings()

        assert isinstance(settings.app, AppConfig)
        assert isinstance(settings.api, APIConfig)
        assert isinstance(settings.rate_limit, RateLimitConfig)
        assert isinstance(settings.auth, AuthConfig)
        assert isinstance(settings.aws, AWSConfig)
        assert isinstance(settings.dynamodb, DynamoDBConfig)
        assert isinstance(settings.secrets_manager, SecretsManagerConfig)
        assert isinstance(settings.valkey, ValkeyConfig)
        assert isinstance(settings.opensearch, OpenSearchConfig)
        assert isinstance(settings.content_storage, ContentStorageConfig)

    def test_settings_method_access(self):
        """Test method access for settings."""
        settings = Settings()

        assert isinstance(settings.get_app_config(), AppConfig)
        assert isinstance(settings.get_api_config(), APIConfig)
        assert isinstance(settings.get_rate_limit_config(), RateLimitConfig)
        assert isinstance(settings.get_auth_config(), AuthConfig)
        assert isinstance(settings.get_aws_config(), AWSConfig)
        assert isinstance(settings.get_dynamodb_config(), DynamoDBConfig)
        assert isinstance(settings.get_secrets_manager_config(), SecretsManagerConfig)
        assert isinstance(settings.get_valkey_config(), ValkeyConfig)
        assert isinstance(settings.get_opensearch_config(), OpenSearchConfig)
        assert isinstance(settings.get_content_storage_config(), ContentStorageConfig)

    def test_settings_env_vars(self, monkeypatch):
        """Test settings loading from environment variables."""
        # Set environment variables using monkeypatch
        monkeypatch.setenv('API_HOST', 'test-host')
        monkeypatch.setenv('API_PORT', '9000')
        monkeypatch.setenv('AUTH_ENABLED', 'false')
        monkeypatch.setenv('AWS_REGION', 'us-west-2')

        # Clear the lru_cache to force reloading
        get_settings.cache_clear()

        settings = Settings()
        assert settings.api_host == 'test-host'
        assert settings.api_port == 9000
        assert settings.auth_enabled is False
        assert settings.aws_region == 'us-west-2'

    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_nested_config_mapping(self, monkeypatch):
        """Test that nested configurations are properly mapped."""
        # Clear environment to avoid interference
        for key in [
            'API_HOST',
            'API_PORT',
            'VALKEY_HOST',
            'VALKEY_PORT',
            'OPENSEARCH_HOST',
            'OPENSEARCH_PORT',
        ]:
            monkeypatch.delenv(key, raising=False)

        settings = Settings(
            api_host='custom-host',
            api_port=9000,
            valkey_host='redis-host',
            valkey_port=6380,
            opensearch_host='search-host',
            opensearch_port=9201,
        )

        api_config = settings.get_api_config()
        assert api_config.host == 'custom-host'
        assert api_config.port == 9000

        valkey_config = settings.get_valkey_config()
        assert valkey_config.host == 'redis-host'
        assert valkey_config.port == 6380

        opensearch_config = settings.get_opensearch_config()
        assert opensearch_config.host == 'search-host'
        assert opensearch_config.port == 9201


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_caching(self):
        """Test that get_settings caches the result."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance due to caching
        assert settings1 is settings2

    def test_get_settings_cache_clear(self):
        """Test clearing the cache."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # Should be different instances after cache clear
        assert settings1 is not settings2
        assert isinstance(settings1, Settings)
        assert isinstance(settings2, Settings)
