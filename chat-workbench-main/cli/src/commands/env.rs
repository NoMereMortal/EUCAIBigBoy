use anyhow::{Context, Result};
use crate::cli::{Cli, EnvCommands};
use crate::config::{CwbConfig, EnvironmentConfig, find_config_file};
use crate::utils::{logger, prompts};
use colored::Colorize;

pub async fn handle_env(env_cmd: EnvCommands, cli: &Cli) -> Result<()> {
    match env_cmd {
        EnvCommands::List => list_environments(cli).await,
        EnvCommands::Create { name, from } => create_environment(name, from, cli).await,
        EnvCommands::Switch { name } => switch_environment(name, cli).await,
        EnvCommands::Delete { name } => delete_environment(name, cli).await,
        EnvCommands::Show { name } => show_environment(name, cli).await,
    }
}

async fn list_environments(_cli: &Cli) -> Result<()> {
    let config_path = find_config_file()?;

    if !config_path.exists() {
        logger::error("No configuration file found. Run 'cwb init' to create one.");
        return Ok(());
    }

    let config = CwbConfig::load(&config_path)?;

    println!("Available environments:");
    println!();

    let current_env = config.current_environment.as_deref();

    for (name, env_config) in &config.environments {
        let marker = if Some(name.as_str()) == current_env {
            "●".green()
        } else {
            "○".white()
        };

        println!("  {} {} ({})", marker, name.bold(), env_config.aws_region);

        if let Some(profile) = &env_config.aws_profile {
            println!("    AWS Profile: {}", profile);
        }

        if let Some(account) = &env_config.aws_account_id {
            println!("    AWS Account: {}", account);
        }

        println!();
    }

    if let Some(current) = current_env {
        println!("Current environment: {}", current.green().bold());
    } else {
        println!("{}", "No current environment set".yellow());
    }

    Ok(())
}

async fn create_environment(name: String, from: Option<String>, cli: &Cli) -> Result<()> {
    let config_path = find_config_file()?;

    if !config_path.exists() {
        logger::error("No configuration file found. Run 'cwb init' to create one.");
        return Ok(());
    }

    let mut config = CwbConfig::load(&config_path)?;

    // Check if environment already exists
    if config.environments.contains_key(&name) && !cli.force {
        let overwrite = prompts::confirm(
            &format!("Environment '{}' already exists. Overwrite?", name),
            false,
        )?;

        if !overwrite {
            logger::info("Environment creation cancelled");
            return Ok(());
        }
    }

    let new_env = if let Some(source_env) = from {
        // Copy from existing environment
        let source_config = config.environments.get(&source_env)
            .ok_or_else(|| anyhow::anyhow!("Source environment '{}' not found", source_env))?
            .clone();

        logger::info(&format!("Creating environment '{}' from '{}'", name, source_env));
        source_config
    } else {
        // Create with default values
        logger::info(&format!("Creating environment '{}'", name));

        let aws_region = prompts::input_string("AWS Region", Some("us-east-1"))?;
        let aws_profile = prompts::input_string("AWS Profile (optional)", Some(&name))?;

        EnvironmentConfig {
            aws_region,
            aws_profile: if aws_profile.is_empty() { None } else { Some(aws_profile) },
            aws_account_id: None,
            variables: None,
        }
    };

    config.environments.insert(name.clone(), new_env);

    // Set as current environment if it's the first one
    if config.current_environment.is_none() {
        config.current_environment = Some(name.clone());
        logger::info(&format!("Set '{}' as current environment", name));
    }

    config.save(&config_path)
        .context("Failed to save configuration")?;

    logger::success(&format!("Environment '{}' created successfully", name));

    Ok(())
}

async fn switch_environment(name: String, _cli: &Cli) -> Result<()> {
    let config_path = find_config_file()?;

    if !config_path.exists() {
        logger::error("No configuration file found. Run 'cwb init' to create one.");
        return Ok(());
    }

    let mut config = CwbConfig::load(&config_path)?;

    if !config.environments.contains_key(&name) {
        anyhow::bail!("Environment '{}' not found", name);
    }

    let previous = config.current_environment.clone();
    config.current_environment = Some(name.clone());

    config.save(&config_path)
        .context("Failed to save configuration")?;

    if let Some(prev) = previous {
        logger::success(&format!("Switched from '{}' to '{}'", prev, name));
    } else {
        logger::success(&format!("Switched to environment '{}'", name));
    }

    Ok(())
}

async fn delete_environment(name: String, cli: &Cli) -> Result<()> {
    let config_path = find_config_file()?;

    if !config_path.exists() {
        logger::error("No configuration file found. Run 'cwb init' to create one.");
        return Ok(());
    }

    let mut config = CwbConfig::load(&config_path)?;

    if !config.environments.contains_key(&name) {
        anyhow::bail!("Environment '{}' not found", name);
    }

    // Prevent deletion if it's the current environment
    if config.current_environment.as_deref() == Some(&name) {
        anyhow::bail!("Cannot delete current environment. Switch to another environment first.");
    }

    // Confirmation
    if !cli.force {
        let confirmed = prompts::confirm_destructive("delete environment", &name)?;
        if !confirmed {
            logger::info("Environment deletion cancelled");
            return Ok(());
        }
    }

    config.environments.remove(&name);

    config.save(&config_path)
        .context("Failed to save configuration")?;

    logger::success(&format!("Environment '{}' deleted successfully", name));

    Ok(())
}

async fn show_environment(name: Option<String>, _cli: &Cli) -> Result<()> {
    let config_path = find_config_file()?;

    if !config_path.exists() {
        logger::error("No configuration file found. Run 'cwb init' to create one.");
        return Ok(());
    }

    let config = CwbConfig::load(&config_path)?;

    let env_name = match name {
        Some(n) => n,
        None => {
            config.current_environment
                .ok_or_else(|| anyhow::anyhow!("No current environment set"))?
        }
    };

    let env_config = config.environments.get(&env_name)
        .ok_or_else(|| anyhow::anyhow!("Environment '{}' not found", env_name))?;

    println!("Environment: {}", env_name.bold());
    println!("AWS Region: {}", env_config.aws_region);

    if let Some(profile) = &env_config.aws_profile {
        println!("AWS Profile: {}", profile);
    }

    if let Some(account) = &env_config.aws_account_id {
        println!("AWS Account: {}", account);
    }

    if let Some(variables) = &env_config.variables {
        if !variables.is_empty() {
            println!("Environment Variables:");
            for (key, value) in variables {
                println!("  {}: {}", key, value);
            }
        }
    }

    Ok(())
}
