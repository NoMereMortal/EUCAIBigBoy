use anyhow::{Context, Result};
use std::path::Path;
use crate::cli::Cli;
use crate::config::CwbConfig;
use crate::utils::{logger, prompts};

pub async fn handle_init(name: Option<String>, project_type: String, cli: &Cli) -> Result<()> {
    logger::info("Initializing cwb configuration...");

    // Check if config already exists
    let config_path = Path::new("cwb.yaml");
    if config_path.exists() && !cli.force {
        let overwrite = prompts::confirm(
            "Configuration file already exists. Overwrite?",
            false,
        )?;

        if !overwrite {
            logger::info("Initialization cancelled");
            return Ok(());
        }
    }

    // Get project name
    let project_name = match name {
        Some(n) => n,
        None => {
            let current_dir = std::env::current_dir()
                .context("Failed to get current directory")?;
            let default_name = current_dir
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("my-project");

            prompts::input_string("Project name", Some(default_name))?
        }
    };

    // Create default config
    let mut config = CwbConfig::create_default();
    config.project.name = project_name;
    config.project.r#type = project_type;

    // Detect existing components
    detect_project_structure(&mut config)?;

    // Save configuration
    config.save("cwb.yaml")
        .context("Failed to save configuration file")?;

    logger::success("Configuration initialized successfully!");
    logger::info("Edit cwb.yaml to customize your project settings");
    logger::info("Run 'cwb doctor' to check your setup");

    Ok(())
}

fn detect_project_structure(config: &mut CwbConfig) -> Result<()> {
    logger::info("Detecting project structure...");

    // Check for common project structures
    let paths_to_check = vec![
        ("backend", "./backend", "Python backend detected"),
        ("frontend", "./ui", "Frontend (ui) detected"),
        ("frontend", "./frontend", "Frontend detected"),
        ("infrastructure", "./infrastructure/cdk", "CDK infrastructure detected"),
        ("infrastructure", "./infra", "Infrastructure detected"),
    ];

    for (component_type, path, message) in paths_to_check {
        if Path::new(path).exists() {
            logger::info(message);

            // Update the component path if it exists in config
            if let Some(component) = config.components.get_mut(component_type) {
                component.path = path.to_string();
            }
        }
    }

    // Check for specific files to determine language/package manager
    if Path::new("./backend/pyproject.toml").exists() {
        logger::info("Python project with pyproject.toml detected");
        if let Some(backend) = config.components.get_mut("backend") {
            backend.package_manager = crate::config::PackageManager::Uv;
        }
    }

    if Path::new("./ui/package.json").exists() {
        logger::info("Node.js frontend detected");
        // Check for specific package managers
        if Path::new("./ui/yarn.lock").exists() {
            if let Some(frontend) = config.components.get_mut("frontend") {
                frontend.package_manager = crate::config::PackageManager::Yarn;
            }
        } else if Path::new("./ui/pnpm-lock.yaml").exists() {
            if let Some(frontend) = config.components.get_mut("frontend") {
                frontend.package_manager = crate::config::PackageManager::Pnpm;
            }
        } else if Path::new("./ui/bun.lockb").exists() {
            if let Some(frontend) = config.components.get_mut("frontend") {
                frontend.package_manager = crate::config::PackageManager::Bun;
            }
        }
    }

    Ok(())
}
