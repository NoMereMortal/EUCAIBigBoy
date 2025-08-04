#!/bin/bash
# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# ========================================================================
# CloudShell Deployment Script for Chat Workbench
# ========================================================================
#
# DESCRIPTION:
#   Automates the deployment of Chat Workbench in AWS CloudShell.
#   Handles dependencies, CDK bootstrap, configuration, and deployment.
#
# USAGE:
#   ./scripts/cloudshell_cdk_deploy.sh [OPTIONS] [ACCOUNT_NUMBER]
#
# ========================================================================

# Strict Mode
set -euo pipefail

# --- Globals ---
SYNTH_ONLY=false
ACCOUNT_NUMBER=""
FORCE_DEPLOY=false
HELP=false
REPO_ROOT=""

# --- Color Codes ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Logging Functions ---
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
    exit 1
}

# --- Core Functions ---

show_usage() {
    cat << EOF
CloudShell Deployment Script for Chat Workbench

DESCRIPTION:
  Automates the deployment of Chat Workbench in AWS CloudShell. It handles
  dependency installation, configuration, CDK bootstrapping, and deployment.

USAGE:
    $0 [OPTIONS] [ACCOUNT_NUMBER]

OPTIONS:
    -s, --synth-only      Only synthesize CDK templates; do not deploy.
    -a, --account NUM     Specify AWS account number. Overrides auto-detection.
    -f, --force           Force deployment without interactive approval (uses --require-approval never).
    -h, --help            Show this help message.

EXAMPLES:
    # Basic deployment (auto-detects account)
    $0

    # Deploy to a specific account
    $0 123456789012
    $0 --account 123456789012

    # Synthesize templates without deploying
    $0 --synth-only

    # Force non-interactive deployment (use with caution)
    $0 --force

ENVIRONMENT VARIABLES:
    REGION          - Override the AWS region from config.yaml (e.g., us-gov-west-1).
    ACCOUNT_NUMBER  - Override the AWS account number (lower priority than --account flag).

REQUIREMENTS:
    - Must be run from the chat-workbench project root directory.
    - An active AWS CloudShell environment.
    - Valid AWS credentials for the target account and region.
EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--synth-only)
                SYNTH_ONLY=true
                shift
                ;;
            -a|--account)
                if [[ -n "${2-}" && $2 != -* ]]; then
                    ACCOUNT_NUMBER="$2"
                    shift 2
                else
                    error "Option --account requires an argument."
                fi
                ;;
            -f|--force)
                FORCE_DEPLOY=true
                shift
                ;;
            -h|--help)
                HELP=true
                shift
                ;;
            -*)
                error "Unknown option: $1"
                ;;
            *)
                if [[ -z "$ACCOUNT_NUMBER" ]]; then
                    ACCOUNT_NUMBER="$1"
                else
                    error "Multiple account numbers specified. Use either a positional argument or the --account flag, not both."
                fi
                shift
                ;;
        esac
    done

    if [[ "$HELP" == true ]]; then
        show_usage
        exit 0
    fi
}

initial_checks() {
    if [[ $EUID -eq 0 ]]; then
        error "This script must not be run as root. Please run as the 'cloudshell-user'."
    fi

    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed or not in PATH. This script requires the AWS CLI."
    fi

    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    if [[ ! -f "${REPO_ROOT}/pyproject.toml" || ! -d "${REPO_ROOT}/infrastructure" ]]; then
        error "Script must be run from within the chat-workbench project structure."
    fi
}

determine_account_number() {
    log "Step 1: Determining AWS Account Number..."

    # Priority: 1) --account flag, 2) ACCOUNT_NUMBER env var, 3) AWS STS
    if [[ -n "$ACCOUNT_NUMBER" ]]; then
        log "  Using account from command-line argument: $ACCOUNT_NUMBER"
        return
    fi

    if [[ -n "${ACCOUNT_NUMBER_ENV-}" ]]; then
        ACCOUNT_NUMBER="$ACCOUNT_NUMBER_ENV"
        log "  Using account from ACCOUNT_NUMBER environment variable: $ACCOUNT_NUMBER"
        return
    fi

    log "  Attempting to auto-detect account from AWS STS..."
    local detected_account
    detected_account=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

    if [[ -z "$detected_account" ]]; then
        error "Failed to get account number from AWS STS. Please provide it via the --account flag or ACCOUNT_NUMBER environment variable."
    fi

    ACCOUNT_NUMBER="$detected_account"
    log "  Successfully auto-detected account: $ACCOUNT_NUMBER"
}

setup_mde_environment() {
    log "Step 2: Setting up CloudShell MDE environment..."
    local mde_path="/aws/mde/ide-runtimes"
    local repo_name
    repo_name=$(basename "$REPO_ROOT")
    local target_dir="${mde_path}/${repo_name}"

    if [[ ! -d "$mde_path" ]]; then
        error "MDE mount point '$mde_path' not found. This script is designed for AWS CloudShell."
    fi
    log "  MDE mount found."

    if [[ "$REPO_ROOT" != "$mde_path"* ]]; then
        log "  Project is outside MDE. Syncing to '$target_dir'..."
        if ! command -v rsync &> /dev/null; then
            error "rsync is required for copying files but is not installed."
        fi

        # Use rsync to copy files, excluding .git and other common temporary files
        sudo rsync -av --delete "$REPO_ROOT/" "$target_dir/" \
            --exclude=".git" \
            --exclude=".venv" \
            --exclude="*.pyc" \
            --exclude="__pycache__" \
            --exclude=".pytest_cache" \
            --exclude=".ruff_cache" \
            --exclude="node_modules"

        sudo chown -R cloudshell-user:cloudshell-user "$target_dir"

        log "  Sync complete. Changing directory to '$target_dir'."
        cd "$target_dir"
        REPO_ROOT="$target_dir"
    else
        log "  Project is already within MDE. Ensuring correct ownership..."
        sudo chown -R cloudshell-user:cloudshell-user "$REPO_ROOT"
        log "  Ownership updated."
    fi
}

setup_cache_directories() {
    log "Step 3: Setting up cache directories in MDE..."

    local cache_base="/aws/mde/ide-runtimes/cache"
    local uv_cache="${cache_base}/uv"
    local npm_cache="${cache_base}/npm"
    local pip_cache="${cache_base}/pip"
    local tmp_dir="/aws/mde/ide-runtimes/tmp"

    # Create cache and temp directories
    sudo mkdir -p "$uv_cache" "$npm_cache" "$pip_cache" "$tmp_dir"
    sudo chown -R cloudshell-user:cloudshell-user "$cache_base" "$tmp_dir"
    sudo chmod -R 755 "$cache_base" "$tmp_dir"

    # Export cache environment variables
    export UV_CACHE_DIR="$uv_cache"
    export NPM_CONFIG_CACHE="$npm_cache"
    export PIP_CACHE_DIR="$pip_cache"

    # Redirect temporary directories to MDE
    export TMPDIR="$tmp_dir"
    export TMP="$tmp_dir"
    export TEMP="$tmp_dir"
    export XDG_CACHE_HOME="$cache_base"

    log "  Cache directories configured:"
    log "    UV_CACHE_DIR: $UV_CACHE_DIR"
    log "    NPM_CONFIG_CACHE: $NPM_CONFIG_CACHE"
    log "    PIP_CACHE_DIR: $PIP_CACHE_DIR"
    log "    TMPDIR: $TMPDIR"
    log "    XDG_CACHE_HOME: $XDG_CACHE_HOME"

    # Clean existing home directory caches to free space
    log "  Cleaning existing caches to free space..."
    rm -rf "$HOME/.cache/pip" "$HOME/.cache/uv" "$HOME/.npm" 2>/dev/null || true
    rm -rf /tmp/* 2>/dev/null || true

    # Configure Docker to use MDE storage
    if command -v docker &> /dev/null; then
        log "  Configuring Docker to use MDE storage..."

        # Create Docker directory in MDE
        sudo mkdir -p /aws/mde/ide-runtimes/docker
        sudo chown -R cloudshell-user:cloudshell-user /aws/mde/ide-runtimes/docker

        # Configure Docker daemon to use MDE (requires daemon restart)
        sudo mkdir -p /etc/docker
        echo '{"data-root": "/aws/mde/ide-runtimes/docker"}' | sudo tee /etc/docker/daemon.json

        # Stop Docker completely first
        sudo pkill -f dockerd 2>/dev/null || true
        sudo pkill -f containerd 2>/dev/null || true
        sleep 2

        # Start fresh (reads daemon.json)
        sudo dockerd &
        sleep 3

        # Verify Docker is using the correct root directory
        if docker info | grep -q "Docker Root Dir: /aws/mde/ide-runtimes/docker"; then
            log "    Docker successfully configured to use /aws/mde/ide-runtimes/docker"
        else
            warn "    Docker may not be using the expected root directory"
            docker info | grep "Docker Root Dir" || true
        fi
    fi
}

install_dependencies() {
    log "Step 4: Installing dependencies..."

    # Install uv if not present
    if ! command -v uv &> /dev/null; then
        log "  Installing uv (Python package manager)..."
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Add uv to PATH (it installs to ~/.local/bin)
        export PATH="$HOME/.local/bin:$PATH"

        # Verify installation
        if ! command -v uv &> /dev/null; then
            error "uv installation failed or not found in PATH"
        fi

        log "  uv installation complete."
    else
        log "  uv is already installed."
    fi

    log "  Installing Python dependencies with uv..."
    uv sync || error "Failed to install Python dependencies."

    if [ -d "ui" ]; then
        log "  Installing UI dependencies..."
        (cd ui && npm install) || error "Failed to install UI dependencies."
    fi

    log "  Installing CDK dependencies..."
    (cd infrastructure/cdk && npm install) || error "Failed to install CDK dependencies."

    # Add local node_modules to PATH for CDK
    export PATH="${REPO_ROOT}/infrastructure/cdk/node_modules/.bin:$PATH"
    log "  CDK executable is now available in PATH."
}

setup_configuration() {
    log "Step 5: Setting up configuration..."
    local config_file="config.yaml"
    local example_config="config.yaml.example"
    local rag_oss_config="examples/rag_oss/config.yaml"

    if [ -f "$config_file" ]; then
        log "  '$config_file' already exists. Skipping creation."
        return
    fi

    if [ -f "$rag_oss_config" ]; then
        log "  Creating '$config_file' from RAG example..."
        cp "$rag_oss_config" "$config_file"
    elif [ -f "$example_config" ]; then
        log "  Creating '$config_file' from example..."
        cp "$example_config" "$config_file"
    else
        error "Could not find a configuration template to create '$config_file'."
    fi
}

run_cdk() {
    log "Step 6: Running CDK..."

    # Determine region from environment or default
    local deploy_region="${REGION:-us-east-1}"
    local deploy_account="$ACCOUNT_NUMBER"

    log "  Deployment Plan:"
    log "    Account: $deploy_account"
    log "    Region:  $deploy_region"
    log "    Synth-Only: $SYNTH_ONLY"
    log "    Force-Deploy: $FORCE_DEPLOY"

    # Export variables for the CDK app
    export ACCOUNT_NUMBER="$deploy_account"
    export REGION="$deploy_region"
    export CONFIG_PATH="${REPO_ROOT}/config.yaml"
    export AWS_PROFILE="default"

    log "  Bootstrapping CDK for account $deploy_account in region $deploy_region..."
    cdk bootstrap "aws://$deploy_account/$deploy_region" || error "CDK bootstrap failed."

    log "  Configuration file is located at: $CONFIG_PATH"
    warn "Please review the configuration file before proceeding."
    read -p "Press ENTER to continue, or Ctrl+C to abort and edit the config..." -r

    (cd "${REPO_ROOT}/infrastructure/cdk"

    if [[ "$SYNTH_ONLY" == true ]]; then
        log "Synthesizing CDK templates..."
        cdk synth 'dev/*' || error "CDK synthesis failed."
        log "Synthesis successful. Templates are in 'cdk.out/'."
    else
        log "Deploying CDK application..."
        local cdk_args=("deploy" "dev/*")
        if [[ "$FORCE_DEPLOY" == true ]]; then
            warn "Using --require-approval never. This will bypass interactive prompts for security changes."
            cdk_args+=("--require-approval" "never")
        fi

        cdk "${cdk_args[@]}" || error "CDK deployment failed."
        log "Deployment successful!"
    fi)
}

print_summary() {
    local deploy_region="${REGION:-us-east-1}"
    log "========================================================================"
    if [[ "$SYNTH_ONLY" == true ]]; then
        log "Synthesis complete!"
    else
        log "Deployment complete!"
    fi
    log "------------------------------------------------------------------------"
    log "  Account: $ACCOUNT_NUMBER"
    log "  Region:  $deploy_region"
    log "  Config:  ${REPO_ROOT}/config.yaml"
    log "------------------------------------------------------------------------"
    log "Next Steps:"
    log "  - To redeploy: $0 --account $ACCOUNT_NUMBER"
    log "  - To destroy:  (cd ${REPO_ROOT}/infrastructure/cdk && cdk destroy 'dev/*')"
    log "========================================================================"
}

# --- Main Execution ---
main() {
    parse_arguments "$@"
    initial_checks
    determine_account_number
    setup_mde_environment
    setup_cache_directories
    install_dependencies
    setup_configuration
    run_cdk
    print_summary
}

# Run the main function, passing all script arguments
main "$@"
