mod cli;
mod config;
mod commands;
mod utils;

use anyhow::Result;
use clap::Parser;
use cli::{Cli, Commands};
use config::{ProjectConfig, ComponentConfig, find_config_file};
use utils::logger;

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Err(e) = run(cli).await {
        logger::error(&format!("Command failed: {}", e));
        std::process::exit(1);
    }

    Ok(())
}

async fn run(cli: Cli) -> Result<()> {
    // Load project configuration
    let config_path = match &cli.config {
        Some(path) => std::path::PathBuf::from(path),
        None => find_config_file()?,
    };

    let project_config = ProjectConfig::load(&config_path)?;

    // Determine which environment to use
    let env = cli.env.as_deref()
        .unwrap_or_else(|| project_config.get_default_env());

    // Get environment-specific configuration
    let env_config = project_config.get_env_config(env)?;

    // Get component configurations for development commands
    let components = ComponentConfig::get_default_components();

    match &cli.command {
        Commands::Version => {
            println!("cwb {}", env!("CARGO_PKG_VERSION"));
            println!("Chat Workbench CLI Tool");
            println!("Environment: {}", env);
            println!("Config: {}", config_path.display());
            Ok(())
        }
        Commands::Config { action } => {
            commands::config::handle_config(action.clone(), &project_config, env, &cli).await
        }
        Commands::Doctor => {
            commands::doctor::handle_doctor(&project_config, env_config, &cli).await
        }
        Commands::Deploy(deploy_cmd) => {
            commands::deploy::handle_deploy(deploy_cmd.clone(), &project_config, env_config, &cli).await
        }
        Commands::Dev(dev_cmd) => {
            commands::dev::handle_dev(dev_cmd.clone(), &components, &cli).await
        }
        Commands::Deps(deps_cmd) => {
            commands::deps::handle_deps(deps_cmd.clone(), &components, &cli).await
        }
        _ => {
            logger::warning("Command not yet implemented");
            Ok(())
        }
    }
}
