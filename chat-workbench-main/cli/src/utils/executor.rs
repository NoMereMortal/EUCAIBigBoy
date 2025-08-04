use anyhow::{Context, Result};
use std::path::Path;
use std::process::Stdio;
use tokio::process::Command;
use colored::Colorize;
use indicatif::{ProgressBar, ProgressStyle};

pub struct CommandExecutor {
    dry_run: bool,
    verbose: bool,
}

impl CommandExecutor {
    pub fn new(dry_run: bool, verbose: bool) -> Self {
        Self { dry_run, verbose }
    }

    pub async fn execute(
        &self,
        cmd: &str,
        args: &[&str],
        working_dir: Option<&Path>,
    ) -> Result<String> {
        let full_command = format!("{} {}", cmd, args.join(" "));

        if self.verbose || self.dry_run {
            println!("{} {}", "Executing:".cyan().bold(), full_command);
            if let Some(dir) = working_dir {
                println!("{} {}", "Working directory:".cyan(), dir.display());
            }
        }

        if self.dry_run {
            println!("{}", "DRY RUN: Command not executed".yellow());
            return Ok("DRY RUN".to_string());
        }

        let mut command = Command::new(cmd);
        command.args(args);

        if let Some(dir) = working_dir {
            command.current_dir(dir);
        }

        let output = command
            .output()
            .await
            .with_context(|| format!("Failed to execute command: {}", full_command))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            let stdout = String::from_utf8_lossy(&output.stdout);

            eprintln!("{} Command failed: {}", "Error:".red().bold(), full_command);
            if !stdout.is_empty() {
                eprintln!("{} {}", "Stdout:".yellow(), stdout);
            }
            if !stderr.is_empty() {
                eprintln!("{} {}", "Stderr:".red(), stderr);
            }

            anyhow::bail!("Command failed with exit code: {:?}", output.status.code());
        }

        let stdout = String::from_utf8(output.stdout)
            .context("Command output is not valid UTF-8")?;

        if self.verbose && !stdout.trim().is_empty() {
            println!("{} {}", "Output:".green(), stdout.trim());
        }

        Ok(stdout)
    }

    pub async fn execute_streaming(
        &self,
        cmd: &str,
        args: &[&str],
        working_dir: Option<&Path>,
    ) -> Result<()> {
        let full_command = format!("{} {}", cmd, args.join(" "));

        if self.verbose || self.dry_run {
            println!("{} {}", "Executing:".cyan().bold(), full_command);
            if let Some(dir) = working_dir {
                println!("{} {}", "Working directory:".cyan(), dir.display());
            }
        }

        if self.dry_run {
            println!("{}", "DRY RUN: Command not executed".yellow());
            return Ok(());
        }

        let mut command = Command::new(cmd);
        command.args(args);
        command.stdout(Stdio::inherit());
        command.stderr(Stdio::inherit());

        if let Some(dir) = working_dir {
            command.current_dir(dir);
        }

        let status = command
            .status()
            .await
            .with_context(|| format!("Failed to execute command: {}", full_command))?;

        if !status.success() {
            anyhow::bail!("Command failed with exit code: {:?}", status.code());
        }

        Ok(())
    }

    pub async fn execute_parallel(
        &self,
        commands: Vec<(String, Vec<String>, Option<std::path::PathBuf>)>,
    ) -> Result<Vec<String>> {
        if self.dry_run {
            println!("{}", "DRY RUN: Parallel commands not executed".yellow());
            for (cmd, args, dir) in &commands {
                let full_command = format!("{} {}", cmd, args.join(" "));
                println!("{} {}", "Would execute:".cyan(), full_command);
                if let Some(dir) = dir {
                    println!("{} {}", "Working directory:".cyan(), dir.display());
                }
            }
            return Ok(vec!["DRY RUN".to_string(); commands.len()]);
        }

        let pb = if !self.verbose {
            let pb = ProgressBar::new(commands.len() as u64);
            pb.set_style(
                ProgressStyle::default_bar()
                    .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} {msg}")
                    .unwrap()
            );
            pb.set_message("Executing commands...");
            Some(pb)
        } else {
            None
        };

        let handles: Vec<_> = commands
            .into_iter()
            .enumerate()
            .map(|(i, (cmd, args, dir))| {
                let pb = pb.clone();
                let verbose = self.verbose;
                tokio::spawn(async move {
                    let args_refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
                    let result = Self::execute_single(&cmd, &args_refs, dir.as_deref(), verbose).await;
                    if let Some(pb) = pb {
                        pb.inc(1);
                        pb.set_message(format!("Completed {}", i + 1));
                    }
                    result
                })
            })
            .collect();

        let results = futures::future::join_all(handles).await;

        if let Some(pb) = pb {
            pb.finish_with_message("All commands completed");
        }

        let mut outputs = Vec::new();
        for result in results {
            let output = result
                .context("Task panicked")?
                .context("Command execution failed")?;
            outputs.push(output);
        }

        Ok(outputs)
    }

    async fn execute_single(
        cmd: &str,
        args: &[&str],
        working_dir: Option<&Path>,
        verbose: bool,
    ) -> Result<String> {
        let mut command = Command::new(cmd);
        command.args(args);

        if let Some(dir) = working_dir {
            command.current_dir(dir);
        }

        if verbose {
            let full_command = format!("{} {}", cmd, args.join(" "));
            println!("{} {}", "Executing:".cyan().bold(), full_command);
        }

        let output = command
            .output()
            .await
            .with_context(|| format!("Failed to execute: {} {}", cmd, args.join(" ")))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("Command failed: {} {}\nError: {}", cmd, args.join(" "), stderr);
        }

        Ok(String::from_utf8(output.stdout)?)
    }

    pub fn check_command_exists(&self, cmd: &str) -> bool {
        if self.dry_run {
            return true; // Assume commands exist in dry run mode
        }

        std::process::Command::new("which")
            .arg(cmd)
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }
}

#[derive(Debug)]
pub struct CommandBuilder {
    command: String,
    args: Vec<String>,
    working_dir: Option<std::path::PathBuf>,
    env_vars: Vec<(String, String)>,
}

impl CommandBuilder {
    pub fn new<S: Into<String>>(command: S) -> Self {
        Self {
            command: command.into(),
            args: Vec::new(),
            working_dir: None,
            env_vars: Vec::new(),
        }
    }

    pub fn arg<S: Into<String>>(mut self, arg: S) -> Self {
        self.args.push(arg.into());
        self
    }

    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.args.extend(args.into_iter().map(|s| s.into()));
        self
    }

    pub fn working_dir<P: Into<std::path::PathBuf>>(mut self, dir: P) -> Self {
        self.working_dir = Some(dir.into());
        self
    }

    pub fn env<K, V>(mut self, key: K, value: V) -> Self
    where
        K: Into<String>,
        V: Into<String>,
    {
        self.env_vars.push((key.into(), value.into()));
        self
    }

    pub async fn execute(self, executor: &CommandExecutor) -> Result<String> {
        let args: Vec<&str> = self.args.iter().map(|s| s.as_str()).collect();
        executor.execute(
            &self.command,
            &args,
            self.working_dir.as_deref(),
        ).await
    }

    pub async fn execute_streaming(self, executor: &CommandExecutor) -> Result<()> {
        let args: Vec<&str> = self.args.iter().map(|s| s.as_str()).collect();
        executor.execute_streaming(
            &self.command,
            &args,
            self.working_dir.as_deref(),
        ).await
    }
}
