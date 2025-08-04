use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

/// Main project configuration structure matching config.yaml
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ProjectConfig {
    /// Default environment (dev, staging, prod)
    pub env: String,
    /// Development environment configuration
    pub dev: EnvConfig,
    /// Staging environment configuration (optional)
    pub staging: Option<EnvConfig>,
    /// Production environment configuration (optional)
    pub prod: Option<EnvConfig>,
}

/// Environment-specific configuration
#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct EnvConfig {
    /// AWS CLI profile for deployment
    pub aws_profile: Option<String>,
    /// Name of the deployment
    pub deployment_name: String,
    /// AWS account number (12 digits)
    pub account_number: String,
    /// AWS region for deployment
    pub region: String,
    /// Deployment stage for the application
    pub deployment_stage: String,
    /// Name of the application
    pub app_name: String,
    /// Log level for application
    pub log_level: String,
    /// Target platform for building Docker images
    pub target_platform: String,
    /// Removal policy for resources
    pub removal_policy: String,
    /// Whether to run CDK Nag checks
    #[serde(default)]
    pub run_cdk_nag: bool,
    /// UI configuration
    pub ui_config: UiConfig,
    /// VPC configuration
    pub vpc_config: VpcConfig,
    /// Cognito auth configuration
    pub cognito_auth_config: CognitoAuthConfig,
    /// Load balancer configuration
    pub load_balancer_config: LoadBalancerConfig,
    /// WAF configuration
    pub waf_config: WafConfig,
    /// Alarm configuration
    pub alarm_config: AlarmConfig,
    /// Authentication configuration
    pub auth_config: AuthConfig,
    /// REST API configuration
    pub rest_api_config: RestApiConfig,
    /// Data configuration
    pub data_config: DataConfig,
    /// Resource tags
    pub tags: Vec<Tag>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct UiConfig {
    pub title: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct VpcConfig {
    /// Optional VPC ID to use existing VPC
    pub vpc_id: Option<String>,
    /// Public subnet IDs
    #[serde(default)]
    pub public_subnet_ids: Vec<String>,
    /// Private subnet IDs
    #[serde(default)]
    pub private_subnet_ids: Vec<String>,
    /// Isolated subnet IDs
    #[serde(default)]
    pub isolated_subnet_ids: Vec<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CognitoAuthConfig {
    pub user_pool_name: String,
    pub user_pool_domain_name: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct LoadBalancerConfig {
    pub idle_timeout: u32,
    /// ALB placement strategy
    #[serde(default = "default_alb_placement")]
    pub alb_placement: String,
    /// SSL certificate ARN
    pub ssl_certificate_arn: Option<String>,
}

fn default_alb_placement() -> String {
    "public".to_string()
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct WafConfig {
    pub managed_rules: ManagedRules,
    pub rate_limiting: RateLimiting,
    pub logging: WafLogging,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ManagedRules {
    #[serde(default)]
    pub core_rule_set: bool,
    #[serde(default = "default_true")]
    pub known_bad_inputs: bool,
    #[serde(default = "default_true")]
    pub amazon_ip_reputation: bool,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct RateLimiting {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_rate_limit")]
    pub requests_per_minute: u32,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct WafLogging {
    #[serde(default)]
    pub enabled: bool,
}

fn default_true() -> bool {
    true
}

fn default_rate_limit() -> u32 {
    2000
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AlarmConfig {
    #[serde(default)]
    pub enable: bool,
    #[serde(default = "default_one")]
    pub period: u32,
    #[serde(default = "default_one")]
    pub threshold: u32,
    #[serde(default = "default_one")]
    pub evaluation_periods: u32,
    pub logging_filter_patterns: Vec<String>,
    pub email_addresses: Option<Vec<String>>,
}

fn default_one() -> u32 {
    1
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AuthConfig {
    #[serde(default = "default_true")]
    pub enable_auth: bool,
    pub authority: String,
    pub client_id: String,
    pub secret_name: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct RestApiConfig {
    #[serde(default = "default_api_version")]
    pub api_version: String,
    pub container_config: ContainerConfig,
    pub health_check_config: HealthCheckConfig,
    pub auto_scaling_config: AutoScalingConfig,
}

fn default_api_version() -> String {
    "v1".to_string()
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ContainerConfig {
    #[serde(default = "default_cpu_limit")]
    pub cpu_limit: u32,
    #[serde(default = "default_memory_limit")]
    pub memory_limit: u32,
    pub health_check_config: ContainerHealthCheckConfig,
}

fn default_cpu_limit() -> u32 {
    1024
}

fn default_memory_limit() -> u32 {
    2048
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ContainerHealthCheckConfig {
    #[serde(default = "default_health_command")]
    pub command: Vec<String>,
    #[serde(default = "default_interval")]
    pub interval: u32,
    #[serde(default = "default_start_period")]
    pub start_period: u32,
    #[serde(default = "default_timeout")]
    pub timeout: u32,
    #[serde(default = "default_retries")]
    pub retries: u32,
}

fn default_health_command() -> Vec<String> {
    vec!["CMD-SHELL".to_string(), "exit 0".to_string()]
}

fn default_interval() -> u32 {
    10
}

fn default_start_period() -> u32 {
    30
}

fn default_timeout() -> u32 {
    5
}

fn default_retries() -> u32 {
    3
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct HealthCheckConfig {
    pub path: String,
    #[serde(default = "default_health_interval")]
    pub interval: u32,
    #[serde(default = "default_health_timeout")]
    pub timeout: u32,
    #[serde(default = "default_healthy_threshold")]
    pub healthy_threshold_count: u32,
    #[serde(default = "default_unhealthy_threshold")]
    pub unhealthy_threshold_count: u32,
}

fn default_health_interval() -> u32 {
    60
}

fn default_health_timeout() -> u32 {
    30
}

fn default_healthy_threshold() -> u32 {
    2
}

fn default_unhealthy_threshold() -> u32 {
    10
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct AutoScalingConfig {
    #[serde(default = "default_min_capacity")]
    pub min_capacity: u32,
    #[serde(default = "default_max_capacity")]
    pub max_capacity: u32,
    #[serde(default = "default_instance_warmup")]
    pub default_instance_warmup: u32,
    #[serde(default = "default_cooldown")]
    pub cooldown: u32,
    pub metric_config: MetricConfig,
}

fn default_min_capacity() -> u32 {
    1
}

fn default_max_capacity() -> u32 {
    5
}

fn default_instance_warmup() -> u32 {
    120
}

fn default_cooldown() -> u32 {
    300
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MetricConfig {
    pub alb_metric_name: String,
    pub target_value: u32,
    #[serde(default = "default_duration")]
    pub duration: u32,
    #[serde(default = "default_estimated_warmup")]
    pub estimated_instance_warmup: u32,
}

fn default_duration() -> u32 {
    60
}

fn default_estimated_warmup() -> u32 {
    60
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct DataConfig {
    /// ElastiCache Serverless configuration
    #[serde(default = "default_storage_limit")]
    pub elasti_cache_storage_limit_gb: u32,
    #[serde(default = "default_ecpu_limit")]
    pub elasti_cache_ecpu_limit: u32,
    /// File storage configuration
    #[serde(default = "default_true")]
    pub file_storage_enabled: bool,
    #[serde(default = "default_storage_type")]
    pub file_storage_type: String,
    /// OpenSearch configuration
    #[serde(default)]
    pub open_search_enabled: bool,
    #[serde(default = "default_index_name")]
    pub open_search_default_index: String,
    #[serde(default)]
    pub open_search_standby_replicas: bool,
    /// Neptune configuration
    #[serde(default)]
    pub neptune_enabled: bool,
    /// Bedrock Knowledge Base configuration
    #[serde(default)]
    pub bedrock_knowledge_base_enabled: bool,
    #[serde(default = "default_embedding_model")]
    pub embedding_model_id: String,
    #[serde(default = "default_index_name")]
    pub vector_index_name: String,
}

fn default_storage_limit() -> u32 {
    50
}

fn default_ecpu_limit() -> u32 {
    10000
}

fn default_storage_type() -> String {
    "s3".to_string()
}

fn default_index_name() -> String {
    "documents".to_string()
}

fn default_embedding_model() -> String {
    "amazon.titan-embed-text-v1".to_string()
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "PascalCase")]
pub struct Tag {
    pub key: String,
    pub value: String,
}

impl ProjectConfig {
    /// Load project configuration from config.yaml file
    pub fn load<P: AsRef<Path>>(config_path: P) -> Result<Self> {
        let path = config_path.as_ref();

        if !path.exists() {
            anyhow::bail!("Configuration file not found: {}", path.display());
        }

        let content = fs::read_to_string(path)
            .with_context(|| format!("Failed to read config file: {}", path.display()))?;

        let config: ProjectConfig = serde_yaml::from_str(&content)
            .with_context(|| format!("Failed to parse config file: {}", path.display()))?;

        Ok(config)
    }

    /// Get configuration for a specific environment
    pub fn get_env_config(&self, env: &str) -> Result<&EnvConfig> {
        match env {
            "dev" => Ok(&self.dev),
            "staging" => self.staging.as_ref()
                .ok_or_else(|| anyhow::anyhow!("Staging environment not configured")),
            "prod" => self.prod.as_ref()
                .ok_or_else(|| anyhow::anyhow!("Production environment not configured")),
            _ => anyhow::bail!("Invalid environment '{}'. Valid options: dev, staging, prod", env),
        }
    }

    /// Get the default environment
    pub fn get_default_env(&self) -> &str {
        &self.env
    }

    /// Get all available environments
    pub fn get_available_environments(&self) -> Vec<&str> {
        let mut envs = vec!["dev"];
        if self.staging.is_some() {
            envs.push("staging");
        }
        if self.prod.is_some() {
            envs.push("prod");
        }
        envs
    }
}

/// Find the project configuration file by searching up the directory tree
pub fn find_config_file() -> Result<PathBuf> {
    let current_dir = std::env::current_dir()
        .context("Failed to get current directory")?;

    // Look for config.yaml in current directory and parent directories
    let mut dir = current_dir.as_path();

    loop {
        let config_path = dir.join("config.yaml");
        if config_path.exists() {
            return Ok(config_path);
        }

        // Also check for the example file as a fallback
        let example_path = dir.join("config.yaml.example");
        if example_path.exists() {
            return Ok(example_path);
        }

        match dir.parent() {
            Some(parent) => dir = parent,
            None => break,
        }
    }

    anyhow::bail!("No config.yaml file found. Make sure you're in the project directory.")
}

/// Component configuration for development commands
/// This maps the project structure to development tools
#[derive(Debug, Clone)]
pub struct ComponentConfig {
    pub name: String,
    pub path: String,
    pub language: String,
    pub package_manager: String,
    pub test_command: Option<String>,
    pub lint_command: Option<String>,
    pub build_command: Option<String>,
    pub format_command: Option<String>,
    pub dev_command: Option<String>,
}

impl ComponentConfig {
    /// Get default component configurations based on project structure
    pub fn get_default_components() -> HashMap<String, ComponentConfig> {
        let mut components = HashMap::new();

        components.insert("backend".to_string(), ComponentConfig {
            name: "backend".to_string(),
            path: "./backend".to_string(),
            language: "python".to_string(),
            package_manager: "uv".to_string(),
            test_command: Some("pytest".to_string()),
            lint_command: Some("ruff check".to_string()),
            build_command: None,
            format_command: Some("ruff format".to_string()),
            dev_command: Some("python -m app.api.main".to_string()),
        });

        components.insert("frontend".to_string(), ComponentConfig {
            name: "frontend".to_string(),
            path: "./ui".to_string(),
            language: "typescript".to_string(),
            package_manager: "npm".to_string(),
            test_command: Some("npm test".to_string()),
            lint_command: Some("npm run lint".to_string()),
            build_command: Some("npm run build".to_string()),
            format_command: Some("npm run format".to_string()),
            dev_command: Some("npm run dev".to_string()),
        });

        components.insert("infrastructure".to_string(), ComponentConfig {
            name: "infrastructure".to_string(),
            path: "./infrastructure/cdk".to_string(),
            language: "typescript".to_string(),
            package_manager: "npm".to_string(),
            test_command: Some("npm test".to_string()),
            lint_command: Some("npm run lint".to_string()),
            build_command: Some("npm run build".to_string()),
            format_command: None,
            dev_command: None,
        });

        components
    }
}
