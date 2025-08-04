# CWB - Chat Workbench CLI

A comprehensive command-line interface for managing the Chat Workbench fullstack application, including deployments, development workflow, testing, and maintenance operations.

## Features

- **Deployment Management**: Deploy, destroy, and manage AWS CDK stacks
- **Development Workflow**: Start dev servers, run tests, lint code, and format files
- **Environment Management**: Switch between dev, staging, and production environments
- **Configuration Management**: Centralized YAML-based configuration
- **Health Checking**: Diagnose setup issues and validate dependencies
- **Security Features**: Planned security scanning and secrets management
- **Monitoring**: Planned log viewing and metrics collection

## Installation

### From Source

```bash
# Clone the repository
git clone <repository-url>
cd chat-workbench/cli

# Build the release binary
cargo build --release

# Install to PATH (optional)
cargo install --path .
```

### Pre-built Binaries

Pre-built binaries will be available in future releases.

## Quick Start

1. **Initialize cwb in your project**:

   ```bash
   cwb init --name "my-project"
   ```

2. **Check your setup**:

   ```bash
   cwb doctor
   ```

3. **View available environments**:

   ```bash
   cwb env list
   ```

4. **Run tests**:
   ```bash
   cwb dev test all
   ```

## Commands Overview

### Deployment Management

- `cwb deploy deploy [stack]` - Deploy CDK stack(s)
- `cwb deploy destroy [stack]` - Destroy CDK stack(s)
- `cwb deploy status` - Show deployment status
- `cwb deploy diff [stack]` - Show deployment differences
- `cwb deploy bootstrap` - Bootstrap CDK environment
- `cwb deploy clean` - Clean deployment artifacts

### Development Workflow

- `cwb dev start [component]` - Start development servers
- `cwb dev build [component]` - Build application components
- `cwb dev test [component]` - Run tests with optional coverage
- `cwb dev lint [component]` - Run linting with optional auto-fix
- `cwb dev format [component]` - Format code
- `cwb dev typecheck [component]` - Run type checking

### Environment Management

- `cwb env list` - List all environments
- `cwb env create <name>` - Create new environment
- `cwb env switch <name>` - Switch active environment
- `cwb env delete <name>` - Delete environment
- `cwb env show [name]` - Show environment details

### Configuration

- `cwb config show` - Display configuration
- `cwb config set <key> <value>` - Set configuration value
- `cwb config get <key>` - Get configuration value

### Utilities

- `cwb init` - Initialize cwb in project
- `cwb doctor` - Diagnose setup issues
- `cwb version` - Show version information

## Configuration

CWB uses a `cwb.yaml` file for configuration:

```yaml
project:
  name: 'chat-workbench'
  type: 'fullstack'
  description: 'Chat Workbench Application'

current_environment: 'dev'

environments:
  dev:
    aws_region: 'us-east-1'
    aws_profile: 'dev'
  prod:
    aws_region: 'us-west-2'
    aws_profile: 'prod'

components:
  backend:
    path: './backend'
    language: python
    package_manager: uv
    test_command: 'pytest'
    lint_command: 'ruff check'
    format_command: 'ruff format'
    typecheck_command: 'mypy'
    dev_command: 'python -m app.api.main'

  frontend:
    path: './ui'
    language: typescript
    package_manager: npm
    test_command: 'npm test'
    lint_command: 'npm run lint'
    build_command: 'npm run build'
    format_command: 'npm run format'
    typecheck_command: 'npm run typecheck'
    dev_command: 'npm run dev'

  infrastructure:
    path: './infrastructure/cdk'
    language: typescript
    package_manager: npm
    build_command: 'npm run build'
    lint_command: 'npm run lint'

hooks:
  pre_deploy:
    - 'cwb dev test all'
    - 'cwb dev lint all'
  post_deploy:
    - 'cwb monitor health'
```

## Global Options

- `--verbose, -v` - Enable verbose output
- `--dry-run` - Show what commands would be executed without running them
- `--force, -f` - Skip confirmation prompts
- `--config <path>` - Use custom configuration file path

## Examples

### Deploy to Production

```bash
# Switch to production environment
cwb env switch prod

# Deploy all stacks with confirmation
cwb deploy deploy --all

# Deploy specific stack
cwb deploy deploy api-stack
```

### Development Workflow

```bash
# Start all development servers
cwb dev start all

# Run tests with coverage
cwb dev test all --coverage

# Lint and auto-fix issues
cwb dev lint all --fix

# Format all code
cwb dev format all
```

### Environment Management

```bash
# Create staging environment
cwb env create staging

# Switch environments
cwb env switch staging

# Show current environment details
cwb env show
```

## Requirements

- **Rust** 1.70+ (if building from source)
- **Node.js** 18+ (for frontend and CDK operations)
- **Python** 3.11+ (for backend operations)
- **AWS CLI** configured with appropriate credentials
- **AWS CDK** CLI installed globally

## Supported Package Managers

- **Node.js**: npm, yarn, pnpm, bun
- **Python**: pip, uv, poetry
- **Rust**: cargo

## Development

### Building

```bash
# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test

# Check code
cargo check
```

### Architecture

- **CLI Framework**: `clap` with derive API
- **Async Runtime**: `tokio`
- **Configuration**: `serde` + `serde_yaml`
- **Error Handling**: `anyhow` + `thiserror`
- **User Interaction**: `dialoguer` for prompts, `indicatif` for progress

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run `cargo test` and `cargo fmt`
6. Submit a pull request

## License

This project is licensed under the MIT License. See the LICENSE file for details.
