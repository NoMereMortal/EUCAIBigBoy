use anyhow::Result;
use std::path::Path;
use crate::cli::Cli;
use crate::config::{ProjectConfig, EnvConfig};
use crate::utils::{logger, executor::CommandExecutor};
use colored::Colorize;

pub async fn handle_doctor(project_config: &ProjectConfig, env_config: &EnvConfig, cli: &Cli) -> Result<()> {
    logger::info("Running cwb doctor...");
    println!();

    let mut issues = Vec::new();
    let executor = CommandExecutor::new(cli.dry_run, cli.verbose);

    // Check 1: Configuration file
    check_config_file(&mut issues, project_config).await;

    // Check 2: Required tools
    check_required_tools(&mut issues, &executor).await;

    // Check 3: Project structure
    check_project_structure(&mut issues).await;

    // Check 4: AWS configuration
    check_aws_config(&mut issues, &executor, env_config).await;

    // Check 5: Git repository
    check_git_repository(&mut issues).await;

    // Summary
    println!();
    if issues.is_empty() {
        logger::success("All checks passed! Your setup looks good.");
    } else {
        logger::warning(&format!("Found {} issue(s):", issues.len()));
        for (i, issue) in issues.iter().enumerate() {
            println!("  {}. {}", i + 1, issue);
        }
        println!();
        println!("Please address these issues for the best cwb experience.");
    }

    Ok(())
}

async fn check_config_file(issues: &mut Vec<String>, project_config: &ProjectConfig) {
    print!("Checking configuration file... ");

    // Configuration is already loaded, so just check basic validity
    println!("{}", "✓".green());

    // Check environment availability
    let envs = project_config.get_available_environments();
    if envs.is_empty() {
        issues.push("No environments configured in config.yaml".to_string());
    }

    // Check if default environment exists
    let default_env = project_config.get_default_env();
    if !envs.contains(&default_env) {
        issues.push(format!("Default environment '{}' is not available in configuration", default_env));
    }
}

async fn check_required_tools(issues: &mut Vec<String>, executor: &CommandExecutor) {
    let tools = vec![
        ("git", "Git version control"),
        ("docker", "Docker container runtime"),
        ("node", "Node.js runtime"),
        ("npm", "Node package manager"),
        ("python3", "Python runtime"),
        ("uv", "Python package manager (uv)"),
        ("aws", "AWS CLI"),
        ("cdk", "AWS CDK CLI"),
    ];

    for (tool, description) in tools {
        print!("Checking {}... ", description);

        if executor.check_command_exists(tool) {
            println!("{}", "✓".green());
        } else {
            println!("{}", "✗".red());
            issues.push(format!("{} ({}) not found in PATH", description, tool));
        }
    }
}

async fn check_project_structure(issues: &mut Vec<String>) {
    print!("Checking project structure... ");

    let expected_paths = vec![
        ("./backend", "Backend directory"),
        ("./ui", "Frontend directory"),
        ("./infrastructure/cdk", "CDK infrastructure directory"),
    ];

    let mut missing_paths = Vec::new();

    for (path, description) in expected_paths {
        if !Path::new(path).exists() {
            missing_paths.push(description);
        }
    }

    if missing_paths.is_empty() {
        println!("{}", "✓".green());
    } else {
        println!("{}", "⚠".yellow());
        issues.push(format!("Some expected directories are missing: {}", missing_paths.join(", ")));
    }
}

async fn check_aws_config(issues: &mut Vec<String>, executor: &CommandExecutor, env_config: &EnvConfig) {
    print!("Checking AWS configuration... ");

    // Check AWS credentials for the specific profile
    let aws_profile = env_config.aws_profile.clone().unwrap_or_else(|| "default".to_string());
    let mut args = vec!["sts", "get-caller-identity"];

    if aws_profile != "default" {
        args.extend(&["--profile", &aws_profile]);
    }

    match executor.execute("aws", &args, None).await {
        Ok(output) => {
            println!("{}", "✓".green());

            // Verify the account matches configuration
            if let Ok(identity) = serde_json::from_str::<serde_json::Value>(&output) {
                if let Some(account) = identity.get("Account").and_then(|a| a.as_str()) {
                    if account != env_config.account_number {
                        issues.push(format!(
                            "AWS account mismatch: credentials show '{}' but config expects '{}'",
                            account, env_config.account_number
                        ));
                    }
                }
            }
        }
        Err(_) => {
            println!("{}", "✗".red());
            if aws_profile == "default" {
                issues.push("AWS credentials not configured. Run 'aws configure' or set environment variables.".to_string());
            } else {
                issues.push(format!("AWS profile '{}' not configured. Run 'aws configure --profile {}'.", aws_profile, aws_profile));
            }
        }
    }
}

async fn check_git_repository(_issues: &mut Vec<String>) {
    print!("Checking Git repository... ");

    if Path::new(".git").exists() {
        println!("{}", "✓".green());
    } else {
        println!("{}", "⚠".yellow());
        // This is not a critical issue, so we don't add it to issues
        // issues.push("Not a Git repository. Consider initializing with 'git init'.".to_string());
    }
}
