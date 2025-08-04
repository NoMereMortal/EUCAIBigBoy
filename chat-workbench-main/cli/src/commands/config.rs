use anyhow::Result;
use crate::cli::{Cli, ConfigCommands};
use crate::config::ProjectConfig;
use crate::utils::logger;

pub async fn handle_config(action: Option<ConfigCommands>, project_config: &ProjectConfig, env: &str, _cli: &Cli) -> Result<()> {
    match action {
        Some(ConfigCommands::Show) | None => show_config(project_config, env).await,
        Some(ConfigCommands::Set { key, value }) => set_config(key, value, project_config, env).await,
        Some(ConfigCommands::Get { key }) => get_config(key, project_config, env).await,
    }
}

async fn show_config(project_config: &ProjectConfig, env: &str) -> Result<()> {
    println!("Project Configuration");
    println!("====================");
    println!("Current Environment: {}", env);
    println!("Default Environment: {}", project_config.get_default_env());
    println!("Available Environments: {:?}", project_config.get_available_environments());
    println!();

    // Show environment-specific configuration
    let env_config = project_config.get_env_config(env)?;

    println!("Environment Configuration ({})", env);
    println!("==============================");
    println!("AWS Profile: {}", env_config.aws_profile.as_ref().unwrap_or(&"default".to_string()));
    println!("Deployment Name: {}", env_config.deployment_name);
    println!("Account Number: {}", env_config.account_number);
    println!("Region: {}", env_config.region);
    println!("Deployment Stage: {}", env_config.deployment_stage);
    println!("App Name: {}", env_config.app_name);
    println!("Log Level: {}", env_config.log_level);

    // Show subset of other configurations
    println!();
    println!("Infrastructure Configuration");
    println!("============================");
    println!("VPC ID: {}", env_config.vpc_config.vpc_id.as_ref().unwrap_or(&"create new".to_string()));
    println!("Target Platform: {}", env_config.target_platform);
    println!("Removal Policy: {}", env_config.removal_policy);
    println!("CDK Nag: {}", env_config.run_cdk_nag);

    Ok(())
}

async fn set_config(_key: String, _value: String, _project_config: &ProjectConfig, _env: &str) -> Result<()> {
    logger::warning("Configuration modification is not supported through CLI.");
    logger::info("Please edit the config.yaml file directly to make changes.");
    Ok(())
}

async fn get_config(key: String, project_config: &ProjectConfig, env: &str) -> Result<()> {
    let env_config = project_config.get_env_config(env)?;

    // Parse the key path
    let parts: Vec<&str> = key.split('.').collect();

    let value = match parts.as_slice() {
        ["env"] => env.to_string(),
        ["default_env"] => project_config.get_default_env().to_string(),
        ["deployment_name"] => env_config.deployment_name.clone(),
        ["account_number"] => env_config.account_number.clone(),
        ["region"] => env_config.region.clone(),
        ["app_name"] => env_config.app_name.clone(),
        ["log_level"] => env_config.log_level.clone(),
        ["aws_profile"] => env_config.aws_profile.clone().unwrap_or_else(|| "default".to_string()),
        _ => {
            anyhow::bail!("Unsupported configuration key: {}. Available keys: env, default_env, deployment_name, account_number, region, app_name, log_level, aws_profile", key);
        }
    };

    println!("{}", value);

    Ok(())
}
