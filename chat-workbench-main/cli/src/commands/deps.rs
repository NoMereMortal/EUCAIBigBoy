use anyhow::Result;
use std::collections::HashMap;
use crate::cli::{Cli, DepsCommands};
use crate::config::ComponentConfig;
use crate::utils::{logger, executor::CommandExecutor};

pub async fn handle_deps(deps_cmd: DepsCommands, components: &HashMap<String, ComponentConfig>, cli: &Cli) -> Result<()> {
    let executor = CommandExecutor::new(cli.dry_run, cli.verbose);

    match deps_cmd {
        DepsCommands::Install { component } => {
            install_dependencies(component, components, &executor).await
        }
        DepsCommands::Update { component } => {
            update_dependencies(component, components, &executor).await
        }
        DepsCommands::Outdated { component } => {
            show_outdated_packages(component, components, &executor).await
        }
        DepsCommands::Sync => {
            sync_all_dependencies(components, &executor).await
        }
    }
}

async fn install_dependencies(
    component: String,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Installing dependencies for all components...");

        // Install backend dependencies (Python/uv)
        if components.contains_key("backend") {
            logger::info("Installing backend dependencies with uv...");
            executor.execute_streaming("uv", &["sync"], None).await?;
        }

        // Install frontend dependencies (Node.js/npm)
        if components.contains_key("frontend") {
            logger::info("Installing frontend dependencies...");
            executor.execute_streaming("npm", &["install"], Some(&std::path::Path::new("ui"))).await?;
        }

        // Install infrastructure dependencies (CDK/npm)
        if components.contains_key("infrastructure") {
            logger::info("Installing infrastructure dependencies...");
            executor.execute_streaming("npm", &["install"], Some(&std::path::Path::new("infrastructure/cdk"))).await?;
        }

        logger::success("All dependencies installed successfully!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        logger::info(&format!("Installing dependencies for {}...", component));

        let path = std::path::Path::new(&comp_config.path);

        match comp_config.package_manager.as_str() {
            "uv" => {
                executor.execute_streaming("uv", &["sync"], Some(path)).await?;
            }
            "npm" => {
                executor.execute_streaming("npm", &["install"], Some(path)).await?;
            }
            "yarn" => {
                executor.execute_streaming("yarn", &["install"], Some(path)).await?;
            }
            "pnpm" => {
                executor.execute_streaming("pnpm", &["install"], Some(path)).await?;
            }
            _ => {
                logger::warning(&format!("Unknown package manager: {}", comp_config.package_manager));
            }
        }

        logger::success(&format!("{} dependencies installed successfully!", component));
    }

    Ok(())
}

async fn update_dependencies(
    component: String,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Updating dependencies for all components...");

        // Update backend dependencies
        if components.contains_key("backend") {
            logger::info("Updating backend dependencies...");
            executor.execute_streaming("uv", &["lock", "--upgrade"], None).await?;
            executor.execute_streaming("uv", &["sync"], None).await?;
        }

        // Update frontend dependencies
        if components.contains_key("frontend") {
            logger::info("Updating frontend dependencies...");
            executor.execute_streaming("npm", &["update"], Some(&std::path::Path::new("ui"))).await?;
        }

        // Update infrastructure dependencies
        if components.contains_key("infrastructure") {
            logger::info("Updating infrastructure dependencies...");
            executor.execute_streaming("npm", &["update"], Some(&std::path::Path::new("infrastructure/cdk"))).await?;
        }

        logger::success("All dependencies updated successfully!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        logger::info(&format!("Updating dependencies for {}...", component));

        let path = std::path::Path::new(&comp_config.path);

        match comp_config.package_manager.as_str() {
            "uv" => {
                executor.execute_streaming("uv", &["lock", "--upgrade"], Some(path)).await?;
                executor.execute_streaming("uv", &["sync"], Some(path)).await?;
            }
            "npm" => {
                executor.execute_streaming("npm", &["update"], Some(path)).await?;
            }
            "yarn" => {
                executor.execute_streaming("yarn", &["upgrade"], Some(path)).await?;
            }
            "pnpm" => {
                executor.execute_streaming("pnpm", &["update"], Some(path)).await?;
            }
            _ => {
                logger::warning(&format!("Unknown package manager: {}", comp_config.package_manager));
            }
        }

        logger::success(&format!("{} dependencies updated successfully!", component));
    }

    Ok(())
}

async fn show_outdated_packages(
    component: String,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Checking outdated packages for all components...");

        // Check backend outdated packages
        if components.contains_key("backend") {
            logger::info("Backend (uv) outdated packages:");
            // uv doesn't have a direct outdated command, but we can show the lock diff
            if let Err(_) = executor.execute_streaming("uv", &["lock", "--dry-run"], None).await {
                logger::info("No outdated information available for uv packages");
            }
        }

        // Check frontend outdated packages
        if components.contains_key("frontend") {
            logger::info("Frontend (npm) outdated packages:");
            executor.execute_streaming("npm", &["outdated"], Some(&std::path::Path::new("ui"))).await.ok();
        }

        // Check infrastructure outdated packages
        if components.contains_key("infrastructure") {
            logger::info("Infrastructure (npm) outdated packages:");
            executor.execute_streaming("npm", &["outdated"], Some(&std::path::Path::new("infrastructure/cdk"))).await.ok();
        }
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        logger::info(&format!("Checking outdated packages for {}...", component));

        let path = std::path::Path::new(&comp_config.path);

        match comp_config.package_manager.as_str() {
            "uv" => {
                logger::info("Checking uv lock for changes...");
                executor.execute_streaming("uv", &["lock", "--dry-run"], Some(path)).await.ok();
            }
            "npm" => {
                executor.execute_streaming("npm", &["outdated"], Some(path)).await.ok();
            }
            "yarn" => {
                executor.execute_streaming("yarn", &["outdated"], Some(path)).await.ok();
            }
            "pnpm" => {
                executor.execute_streaming("pnpm", &["outdated"], Some(path)).await.ok();
            }
            _ => {
                logger::warning(&format!("Unknown package manager: {}", comp_config.package_manager));
            }
        }
    }

    Ok(())
}

async fn sync_all_dependencies(
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    logger::info("Syncing all dependencies across the project...");

    // This is equivalent to install all, but with explicit sync semantics
    // Backend: uv sync (ensures virtual environment matches lockfile)
    if components.contains_key("backend") {
        logger::info("Syncing backend dependencies with uv...");
        executor.execute_streaming("uv", &["sync"], None).await?;
    }

    // Frontend: npm ci (clean install from lockfile)
    if components.contains_key("frontend") {
        logger::info("Syncing frontend dependencies...");
        executor.execute_streaming("npm", &["ci"], Some(&std::path::Path::new("ui"))).await?;
    }

    // Infrastructure: npm ci (clean install from lockfile)
    if components.contains_key("infrastructure") {
        logger::info("Syncing infrastructure dependencies...");
        executor.execute_streaming("npm", &["ci"], Some(&std::path::Path::new("infrastructure/cdk"))).await?;
    }

    logger::success("All dependencies synced successfully!");

    Ok(())
}
