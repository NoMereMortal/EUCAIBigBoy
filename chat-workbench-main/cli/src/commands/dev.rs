use anyhow::{Context, Result};
use std::path::PathBuf;
use std::collections::HashMap;
use crate::cli::{Cli, DevCommands};
use crate::config::ComponentConfig;
use crate::utils::{logger, executor::CommandExecutor};

pub async fn handle_dev(dev_cmd: DevCommands, components: &HashMap<String, ComponentConfig>, cli: &Cli) -> Result<()> {
    let executor = CommandExecutor::new(cli.dry_run, cli.verbose);

    match dev_cmd {
        DevCommands::Start { component, backend_port, frontend_port } => {
            start_dev_server(component, backend_port, frontend_port, components, &executor).await
        }
        DevCommands::Build { component, release } => {
            build_components(component, release, components, &executor).await
        }
        DevCommands::Test { component, coverage, test } => {
            run_tests(component, coverage, test, components, &executor).await
        }
        DevCommands::Lint { component, fix } => {
            run_linting(component, fix, components, &executor).await
        }
        DevCommands::Format { component } => {
            format_code(component, components, &executor).await
        }
        DevCommands::Typecheck { component } => {
            run_typecheck(component, components, &executor).await
        }
        DevCommands::PreCommit => {
            run_pre_commit(&executor).await
        }
    }
}

async fn start_dev_server(
    component: String,
    _backend_port: Option<u16>,
    _frontend_port: Option<u16>,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Starting all development servers...");

        // Start backend first
        if let Some(backend) = components.get("backend") {
            if let Some(dev_cmd) = &backend.dev_command {
                let parts: Vec<&str> = dev_cmd.split_whitespace().collect();
                if !parts.is_empty() {
                    logger::info("Starting backend development server...");
                    let backend_path = PathBuf::from(&backend.path);
                    // For development servers, we'd typically want to start them in background
                    // For now, this will run sequentially
                    executor.execute_streaming(parts[0], &parts[1..], Some(&backend_path)).await?;
                }
            }
        }

        // Start frontend
        if let Some(frontend) = components.get("frontend") {
            if let Some(dev_cmd) = &frontend.dev_command {
                let parts: Vec<&str> = dev_cmd.split_whitespace().collect();
                if !parts.is_empty() {
                    logger::info("Starting frontend development server...");
                    let frontend_path = PathBuf::from(&frontend.path);
                    executor.execute_streaming(parts[0], &parts[1..], Some(&frontend_path)).await?;
                }
            }
        }
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if let Some(dev_cmd) = &comp_config.dev_command {
            logger::info(&format!("Starting {} development server...", component));
            let parts: Vec<&str> = dev_cmd.split_whitespace().collect();
            if !parts.is_empty() {
                let comp_path = PathBuf::from(&comp_config.path);
                executor.execute_streaming(parts[0], &parts[1..], Some(&comp_path)).await?;
            }
        } else {
            logger::warning(&format!("No dev command configured for component '{}'", component));
        }
    }

    Ok(())
}

async fn build_components(
    component: String,
    _release: bool,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Building all components...");

        let mut build_commands = Vec::new();

        for (name, comp_config) in components {
            if let Some(build_cmd) = &comp_config.build_command {
                let parts: Vec<&str> = build_cmd.split_whitespace().collect();
                if !parts.is_empty() {
                    let comp_path = PathBuf::from(&comp_config.path);
                    build_commands.push((parts[0], parts[1..].to_vec(), Some(comp_path), name.clone()));
                }
            }
        }

        for (cmd, args, dir, comp_name) in build_commands {
            logger::info(&format!("Building {}...", comp_name));
            let args_refs: Vec<&str> = args.iter().map(|s| s.as_ref()).collect();
            executor.execute_streaming(cmd, &args_refs, dir.as_deref()).await
                .with_context(|| format!("Failed to build component: {}", comp_name))?;
        }

        logger::success("All components built successfully!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if let Some(build_cmd) = &comp_config.build_command {
            logger::info(&format!("Building {}...", component));
            let parts: Vec<&str> = build_cmd.split_whitespace().collect();
            if !parts.is_empty() {
                let comp_path = PathBuf::from(&comp_config.path);
                executor.execute_streaming(parts[0], &parts[1..], Some(&comp_path)).await?;
            }
            logger::success(&format!("{} built successfully!", component));
        } else {
            logger::warning(&format!("No build command configured for component '{}'", component));
        }
    }

    Ok(())
}

async fn run_tests(
    component: String,
    coverage: bool,
    test_filter: Option<String>,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Running tests for all components...");

        for (name, comp_config) in components {
            if let Some(test_cmd) = &comp_config.test_command {
                logger::info(&format!("Testing {}...", name));
                run_component_test(comp_config, test_cmd, coverage, test_filter.as_deref(), executor).await
                    .with_context(|| format!("Tests failed for component: {}", name))?;
            }
        }

        logger::success("All tests passed!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if let Some(test_cmd) = &comp_config.test_command {
            logger::info(&format!("Running tests for {}...", component));
            run_component_test(comp_config, test_cmd, coverage, test_filter.as_deref(), executor).await?;
            logger::success(&format!("{} tests passed!", component));
        } else {
            logger::warning(&format!("No test command configured for component '{}'", component));
        }
    }

    Ok(())
}

async fn run_component_test(
    comp_config: &ComponentConfig,
    base_test_cmd: &str,
    coverage: bool,
    test_filter: Option<&str>,
    executor: &CommandExecutor,
) -> Result<()> {
    let mut cmd_parts: Vec<String> = base_test_cmd.split_whitespace().map(|s| s.to_string()).collect();

    // Add coverage flags based on package manager and language
    if coverage {
        match comp_config.package_manager.as_str() {
            "npm" | "yarn" | "pnpm" => {
                // For Node.js projects, coverage is usually handled by the test runner
                // This would depend on your specific setup
            }
            "uv" | "pip" => {
                // For Python projects with pytest
                if base_test_cmd.contains("pytest") {
                    cmd_parts.push("--cov".to_string());
                }
            }
            _ => {}
        }
    }

    // Add test filter
    if let Some(filter) = test_filter {
        match comp_config.package_manager.as_str() {
            "npm" | "yarn" | "pnpm" => {
                cmd_parts.push("--testNamePattern".to_string());
                cmd_parts.push(filter.to_string());
            }
            "uv" | "pip" => {
                if base_test_cmd.contains("pytest") {
                    cmd_parts.push("-k".to_string());
                    cmd_parts.push(filter.to_string());
                }
            }
            _ => {}
        }
    }

    let comp_path = PathBuf::from(&comp_config.path);
    let cmd = &cmd_parts[0];
    let args: Vec<&str> = cmd_parts[1..].iter().map(|s| s.as_str()).collect();

    executor.execute_streaming(cmd, &args, Some(&comp_path)).await?;

    Ok(())
}

async fn run_linting(
    component: String,
    fix: bool,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Running linting for all components...");

        for (name, comp_config) in components {
            if let Some(lint_cmd) = &comp_config.lint_command {
                logger::info(&format!("Linting {}...", name));
                run_component_lint(comp_config, lint_cmd, fix, executor).await
                    .with_context(|| format!("Linting failed for component: {}", name))?;
            }
        }

        logger::success("All linting checks passed!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if let Some(lint_cmd) = &comp_config.lint_command {
            logger::info(&format!("Linting {}...", component));
            run_component_lint(comp_config, lint_cmd, fix, executor).await?;
            logger::success(&format!("{} linting passed!", component));
        } else {
            logger::warning(&format!("No lint command configured for component '{}'", component));
        }
    }

    Ok(())
}

async fn run_component_lint(
    comp_config: &ComponentConfig,
    base_lint_cmd: &str,
    fix: bool,
    executor: &CommandExecutor,
) -> Result<()> {
    let mut cmd_parts: Vec<String> = base_lint_cmd.split_whitespace().map(|s| s.to_string()).collect();

    // Add fix flags based on the linter
    if fix {
        if base_lint_cmd.contains("ruff") {
            cmd_parts.push("--fix".to_string());
        } else if base_lint_cmd.contains("eslint") {
            cmd_parts.push("--fix".to_string());
        }
    }

    let comp_path = PathBuf::from(&comp_config.path);
    let cmd = &cmd_parts[0];
    let args: Vec<&str> = cmd_parts[1..].iter().map(|s| s.as_str()).collect();

    executor.execute_streaming(cmd, &args, Some(&comp_path)).await?;

    Ok(())
}

async fn format_code(
    component: String,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Formatting all components...");

        for (name, comp_config) in components {
            if let Some(format_cmd) = &comp_config.format_command {
                logger::info(&format!("Formatting {}...", name));
                let parts: Vec<&str> = format_cmd.split_whitespace().collect();
                if !parts.is_empty() {
                    let comp_path = PathBuf::from(&comp_config.path);
                    executor.execute_streaming(parts[0], &parts[1..], Some(&comp_path)).await
                        .with_context(|| format!("Formatting failed for component: {}", name))?;
                }
            }
        }

        logger::success("All components formatted!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if let Some(format_cmd) = &comp_config.format_command {
            logger::info(&format!("Formatting {}...", component));
            let parts: Vec<&str> = format_cmd.split_whitespace().collect();
            if !parts.is_empty() {
                let comp_path = PathBuf::from(&comp_config.path);
                executor.execute_streaming(parts[0], &parts[1..], Some(&comp_path)).await?;
            }
            logger::success(&format!("{} formatted!", component));
        } else {
            logger::warning(&format!("No format command configured for component '{}'", component));
        }
    }

    Ok(())
}

async fn run_typecheck(
    component: String,
    components: &HashMap<String, ComponentConfig>,
    executor: &CommandExecutor,
) -> Result<()> {
    if component == "all" {
        logger::info("Running type checking for all components...");

        for (name, comp_config) in components {
            // For TypeScript components, we can run tsc --noEmit
            if comp_config.language == "typescript" {
                logger::info(&format!("Type checking {}...", name));
                let comp_path = PathBuf::from(&comp_config.path);
                executor.execute_streaming("npx", &["tsc", "--noEmit"], Some(&comp_path)).await
                    .with_context(|| format!("Type checking failed for component: {}", name))?;
            }
        }

        logger::success("All type checks passed!");
    } else {
        let comp_config = components.get(&component)
            .ok_or_else(|| anyhow::anyhow!("Component '{}' not found", component))?;

        if comp_config.language == "typescript" {
            logger::info(&format!("Type checking {}...", component));
            let comp_path = PathBuf::from(&comp_config.path);
            executor.execute_streaming("npx", &["tsc", "--noEmit"], Some(&comp_path)).await?;
            logger::success(&format!("{} type checking passed!", component));
        } else {
            logger::warning(&format!("Type checking not supported for {} ({} language)", component, comp_config.language));
        }
    }

    Ok(())
}

async fn run_pre_commit(executor: &CommandExecutor) -> Result<()> {
    logger::info("Running pre-commit hooks...");

    if !executor.check_command_exists("pre-commit") {
        logger::warning("pre-commit not found. Install with: pip install pre-commit");
        return Ok(());
    }

    executor.execute_streaming("pre-commit", &["run", "--all-files"], None).await?;

    logger::success("Pre-commit hooks passed!");

    Ok(())
}
