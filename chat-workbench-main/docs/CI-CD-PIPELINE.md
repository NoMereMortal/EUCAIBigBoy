# CI/CD Pipeline Documentation

This document provides information about the CI/CD pipeline configuration for the Chat Workbench project.

> **Note:** Currently, this project implements Continuous Integration (CI) with a focus on automated testing and validation. Continuous Deployment (CD) capabilities will be added in a future update.

## Pipeline Overview

The GitLab CI/CD pipeline consists of four main stages that run in an optimized parallel structure:

1. **Pre-commit Hooks**: Runs various code quality checks
2. **Tests**: Runs all tests in parallel (unit, integration, API, slow, AWS, frontend, and CLI)
3. **Coverage**: Combines coverage reports from all test jobs
4. **Infrastructure**: Validates infrastructure code with CDK Nag and synthesizes CloudFormation templates

![Pipeline Diagram](https://mermaid.ink/img/pako:eNp9ksFuwjAMhl_F8m3aEBJIC9CKOnFgEyduh8QLXUiTysmQqureHdPSDtohOS2-fz_2X2YsTJQsWLSiMZ3xH53XIN7MOXljrTiXQwj_oojBKQ_nlPgx3A-5VgcRt6auATV3UdUmugI7G5Du8YKDwDVG4JsznMa7w2MRY2Q0FUdU9k3hKYVWR63_YCrtBgrNqrVCF-E4qKd662JLMdbJv8aamt_P7-vtJsBXiupMqdV0hqjeuPQB1axtTDavxjlARpgcU9rlYczR51wrsWIMK7QO94bsa8fxRaiB7oAba+E1Wq-cGVAvNeteDzH7BfqDtPewfWnTZ1bnWB9i9gLq0N3uYvQVtY5aDdZWYCORFj5v9bBhl6hDLG2H2nqatbFWzRl_Om9UMI6W_nrYv3sye9BD7WJ0ofr3SstQeiMvsPnRi59gdhuZb-5Y3_Wp?type=png)

## Stage 1: Pre-commit Hooks

This stage leverages the pre-commit framework to run a variety of checks:

- Code formatting via Prettier, ESLint, Ruff, etc.
- Security checks (detect-secrets, etc.)
- License headers
- Various quality checks

The configuration uses the project's existing `.pre-commit-config.yaml` file.

## Stage 2: Tests

### Backend Tests

- Runs Python tests using pytest
- Generates test coverage reports
- Uses Valkey service (Redis-compatible) for tests requiring it

### Frontend Tests

- Lints frontend code with ESLint
- Builds the UI to verify it compiles correctly

### CLI Tests

- Checks formatting with cargo fmt
- Runs linting with clippy
- Builds and tests the Rust CLI

## Stage 3: Infrastructure

### CDK Nag

Runs AWS CDK Nag to check for security and compliance issues in infrastructure code:

- Analyzes CloudFormation templates for best practices
- Validates against security standards
- Enforces organizational policies

### CDK Synthesis

- Synthesizes CloudFormation templates
- Validates template JSON structure
- Preserves artifacts for deployment

## Additional Jobs

The pipeline also includes optional manual jobs:

- **Security Scan**: Runs security tools like safety, bandit, and npm audit
- **Dependency Check**: Checks for outdated dependencies in Python and Node.js packages

## Pipeline Triggers

The pipeline runs automatically on:

- Pushes to the main/master branch
- Merge requests
- Tagged commits
- Manual triggers via the GitLab web interface

## Cache Configuration

The pipeline uses caching to speed up execution:

- Python dependencies via uv
- Node.js packages via npm
- Rust dependencies and build artifacts via cargo

## Docker Images

All pipeline jobs use Docker images from AWS ECR Public Gallery:

- `public.ecr.aws/docker/library/python:3.11-slim` for Python jobs
- `public.ecr.aws/docker/library/node:20-alpine` for Node.js jobs
- `public.ecr.aws/docker/library/rust:1.70-slim` for Rust jobs
- `public.ecr.aws/valkey/valkey:2.16-alpine` for Valkey services (Redis-compatible)

Using AWS ECR images provides several benefits:

- Improved security with AWS-managed container images
- Better reliability with AWS's global content delivery network
- Simplified compliance for AWS-based projects

## Artifacts

Each job produces artifacts that are preserved for a specified period:

- Test reports
- Coverage reports
- Build outputs
- CloudFormation templates

## Using the Pipeline

### Local Testing

Before pushing changes, you can run pre-commit checks locally:

```bash
# Install pre-commit
pip install pre-commit

# Run pre-commit hooks
pre-commit run --all-files
```

### Backend Testing

```bash
cd backend
uv sync --dev
uv run pytest
```

### Frontend Testing

```bash
cd ui
npm ci
npm run lint
npm run build
```

### CDK Validation

```bash
cd infrastructure/cdk
npm ci
npx cdk synth --strict
```

## Extending the Pipeline

To add new jobs or modify existing ones, edit the `.gitlab-ci.yml` file in the project root.

## Future CD Implementation

The current pipeline focuses on Continuous Integration (CI) with automated testing and quality checks. Future Continuous Deployment (CD) enhancements will include:

1. **Environment-based deployments**:
   - Development/staging/production deployment pipelines
   - Environment-specific configuration management

2. **Deployment automation**:
   - Automatic deployment to AWS resources
   - Blue-green or canary deployment strategies
   - Rollback mechanisms

3. **Approval workflows**:
   - Manual approval gates for production deployments
   - Automated integration tests before production promotion

4. **Monitoring integration**:
   - Post-deployment health checks
   - Metrics and alerting integration

When implemented, these CD capabilities will complete the CI/CD pipeline, enabling fully automated testing and deployment.
