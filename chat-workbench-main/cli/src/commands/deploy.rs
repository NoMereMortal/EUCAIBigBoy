use anyhow::Result;
use crate::cli::{Cli, DeployCommands};
use crate::config::{ProjectConfig, EnvConfig};
use crate::utils::{logger, executor::CommandExecutor, prompts};

pub async fn handle_deploy(deploy_cmd: DeployCommands, _project_config: &ProjectConfig, env_config: &EnvConfig, cli: &Cli) -> Result<()> {
    let executor = CommandExecutor::new(cli.dry_run, cli.verbose);

    match deploy_cmd {
        DeployCommands::Deploy { stack, all } => {
            deploy_stacks(stack, all, env_config, &executor, cli).await
        }
        DeployCommands::Destroy { stack, all } => {
            destroy_stacks(stack, all, env_config, &executor, cli).await
        }
        DeployCommands::Status => {
            show_deployment_status(env_config, &executor).await
        }
        DeployCommands::Diff { stack } => {
            show_deployment_diff(stack, env_config, &executor).await
        }
        DeployCommands::Bootstrap { region } => {
            bootstrap_environment(region, env_config, &executor).await
        }
        DeployCommands::Rollback { stack } => {
            rollback_deployment(stack, env_config, &executor, cli).await
        }
        DeployCommands::Clean => {
            clean_deployment_artifacts(&executor).await
        }
    }
}

async fn deploy_stacks(
    stack: Option<String>,
    all: bool,
    env_config: &EnvConfig,
    executor: &CommandExecutor,
    _cli: &Cli,
) -> Result<()> {
    logger::info(&format!("Deploying to environment: {} ({})", env_config.deployment_name, env_config.deployment_stage));

    // Get CDK directory - hardcoded based on project structure
    let cdk_dir = std::path::Path::new("./infrastructure/cdk");

    if !cdk_dir.exists() {
        anyhow::bail!("CDK directory not found: {}", cdk_dir.display());
    }

    // Set up environment variables for CDK deployment
    setup_cdk_environment(env_config)?;

    if all {
        logger::info("Deploying all stacks...");
        executor.execute_streaming("cdk", &["deploy", "--all", "--require-approval", "never"], Some(cdk_dir)).await?;
    } else if let Some(stack_name) = stack {
        logger::info(&format!("Deploying stack: {}", stack_name));
        executor.execute_streaming("cdk", &["deploy", &stack_name, "--require-approval", "never"], Some(cdk_dir)).await?;
    } else {
        // Interactive stack selection
        let available_stacks = get_available_stacks(executor, cdk_dir).await?;
        if available_stacks.is_empty() {
            anyhow::bail!("No CDK stacks found");
        }

        let stack_names: Vec<&str> = available_stacks.iter().map(|s| s.as_str()).collect();
        let selection = prompts::select_option("Select stack to deploy", &stack_names)?;
        let selected_stack = &available_stacks[selection];

        logger::info(&format!("Deploying stack: {}", selected_stack));
        executor.execute_streaming("cdk", &["deploy", selected_stack, "--require-approval", "never"], Some(cdk_dir)).await?;
    }

    logger::success("Deployment completed successfully!");

    Ok(())
}

async fn destroy_stacks(
    stack: Option<String>,
    all: bool,
    env_config: &EnvConfig,
    executor: &CommandExecutor,
    cli: &Cli,
) -> Result<()> {
    // Confirmation for destructive operation
    if !cli.force {
        let target = if all { "all stacks" } else { stack.as_deref().unwrap_or("selected stack") };
        let confirmed = prompts::confirm_destructive("destroy", &format!("{} in {}", target, env_config.deployment_name))?;
        if !confirmed {
            logger::info("Destroy operation cancelled");
            return Ok(());
        }
    }

    let cdk_dir = std::path::Path::new("./infrastructure/cdk");
    setup_cdk_environment(env_config)?;

    if all {
        logger::info("Destroying all stacks...");
        executor.execute_streaming("cdk", &["destroy", "--all", "--force"], Some(cdk_dir)).await?;
    } else if let Some(stack_name) = stack {
        logger::info(&format!("Destroying stack: {}", stack_name));
        executor.execute_streaming("cdk", &["destroy", &stack_name, "--force"], Some(cdk_dir)).await?;
    } else {
        let available_stacks = get_available_stacks(executor, cdk_dir).await?;
        if available_stacks.is_empty() {
            anyhow::bail!("No CDK stacks found");
        }

        let stack_names: Vec<&str> = available_stacks.iter().map(|s| s.as_str()).collect();
        let selection = prompts::select_option("Select stack to destroy", &stack_names)?;
        let selected_stack = &available_stacks[selection];

        logger::info(&format!("Destroying stack: {}", selected_stack));
        executor.execute_streaming("cdk", &["destroy", selected_stack, "--force"], Some(cdk_dir)).await?;
    }

    logger::success("Destroy operation completed successfully!");

    Ok(())
}

async fn show_deployment_status(
    env_config: &EnvConfig,
    executor: &CommandExecutor,
) -> Result<()> {
    logger::info(&format!("Deployment status for environment: {}", env_config.deployment_name));

    let cdk_dir = std::path::Path::new("./infrastructure/cdk");
    setup_cdk_environment(env_config)?;

    executor.execute_streaming("cdk", &["list"], Some(cdk_dir)).await?;

    Ok(())
}

async fn show_deployment_diff(
    stack: Option<String>,
    env_config: &EnvConfig,
    executor: &CommandExecutor,
) -> Result<()> {
    logger::info(&format!("Showing deployment diff for environment: {}", env_config.deployment_name));

    let cdk_dir = std::path::Path::new("./infrastructure/cdk");
    setup_cdk_environment(env_config)?;

    if let Some(stack_name) = stack {
        executor.execute_streaming("cdk", &["diff", &stack_name], Some(cdk_dir)).await?;
    } else {
        executor.execute_streaming("cdk", &["diff"], Some(cdk_dir)).await?;
    }

    Ok(())
}

async fn bootstrap_environment(
    region: Option<String>,
    env_config: &EnvConfig,
    executor: &CommandExecutor,
) -> Result<()> {
    let aws_region = region.unwrap_or_else(|| env_config.region.clone());

    logger::info(&format!("Bootstrapping CDK in region: {} for account: {}", aws_region, env_config.account_number));

    let cdk_dir = std::path::Path::new("./infrastructure/cdk");
    setup_cdk_environment(env_config)?;

    let mut args = vec!["bootstrap"];
    args.push("--region");
    args.push(&aws_region);

    executor.execute_streaming("cdk", &args, Some(cdk_dir)).await?;

    logger::success("Bootstrap completed successfully!");

    Ok(())
}

async fn rollback_deployment(
    stack: String,
    env_config: &EnvConfig,
    _executor: &CommandExecutor,
    _cli: &Cli,
) -> Result<()> {
    logger::warning("Rollback functionality requires custom implementation based on your deployment strategy");
    logger::info(&format!("Would rollback stack '{}' in environment '{}'", stack, env_config.deployment_name));

    // This would typically involve:
    // 1. Getting the previous deployment version/state
    // 2. Re-deploying with the previous configuration
    // 3. Updating any external dependencies

    Ok(())
}

async fn clean_deployment_artifacts(executor: &CommandExecutor) -> Result<()> {
    logger::info("Cleaning deployment artifacts...");

    // Clean CDK artifacts
    if std::path::Path::new("./infrastructure/cdk/cdk.out").exists() {
        executor.execute("rm", &["-rf", "./infrastructure/cdk/cdk.out"], None).await?;
        logger::info("Removed CDK output directory");
    }

    logger::success("Cleanup completed successfully!");

    Ok(())
}

async fn get_available_stacks(executor: &CommandExecutor, cdk_dir: &std::path::Path) -> Result<Vec<String>> {
    let output = executor.execute("cdk", &["list"], Some(cdk_dir)).await?;

    let stacks: Vec<String> = output
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| line.trim().to_string())
        .collect();

    Ok(stacks)
}

fn setup_cdk_environment(env_config: &EnvConfig) -> Result<()> {
    // Set environment variables for CDK deployment
    std::env::set_var("AWS_REGION", &env_config.region);
    std::env::set_var("AWS_ACCOUNT", &env_config.account_number);

    if let Some(profile) = &env_config.aws_profile {
        std::env::set_var("AWS_PROFILE", profile);
    }

    // Set CDK context variables based on configuration
    std::env::set_var("CDK_DEFAULT_REGION", &env_config.region);
    std::env::set_var("CDK_DEFAULT_ACCOUNT", &env_config.account_number);

    Ok(())
}
