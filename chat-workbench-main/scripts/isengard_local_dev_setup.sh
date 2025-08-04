#!/bin/bash

# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# ========================================================================
# Local Development Environment Setup Script for Chat Workbench
# ========================================================================
#
# DESCRIPTION:
#   AWS Employee tool for setting up local development environment.
#   Authenticates with AWS using internal Isengard CLI tool to obtain
#   temporary AWS credentials, configures local environment variables,
#   and starts the development server stack using Docker Compose.
#
# AUDIENCE:
#   This script is intended for AWS employees only. It requires access to
#   internal AWS systems and the Isengard CLI tool for credential management.
#
# USAGE:
#   ./scripts/isengardcli_start_local_app.sh --email <email> [OPTIONS]
#
# ========================================================================

# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# Strict Mode
set -euo pipefail

# --- Globals ---
EMAIL=""
ROLE="admin"
REGION="us-east-1"
HELP=false
ENV_FILE=".env"

# --- Color Codes ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Logging Functions ---
log() {
    echo "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" >&2
    exit 1
}

# --- Core Functions ---

show_usage() {
    cat << EOF
Local Development Environment Setup Script for Chat Workbench

DESCRIPTION:
  AWS Employee tool for local development environment setup.
  Uses internal Isengard CLI to obtain temporary AWS credentials,
  updates local environment variables in .env file, validates credentials,
  and starts the development server stack using Docker Compose.

AUDIENCE:
  This script is for AWS employees only and requires access to internal
  AWS systems and the Isengard CLI tool.

USAGE:
    $0 --email <email> [OPTIONS]

OPTIONS:
    --email EMAIL         Your AWS email address for Isengard authentication (required).
    --role ROLE           AWS IAM role to assume (default: admin).
    --region REGION       AWS region to use (default: us-east-1).
    -h, --help            Show this help message.

EXAMPLES:
    # Basic usage with default role and region
    $0 --email user@amazon.com

    # Specify custom role and region
    $0 --email user@amazon.com --role developer --region us-west-2

REQUIREMENTS:
    - AWS employee access to internal systems
    - isengardcli (internal AWS tool) must be installed and configured
    - jq must be installed for JSON parsing
    - docker-compose must be available for starting the development stack
    - Valid Isengard access for the specified AWS email and role

ENVIRONMENT:
    This script will update the .env file in the current directory with:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_SESSION_TOKEN (if provided)
EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --email)
                if [[ -n "${2-}" && $2 != -* ]]; then
                    EMAIL="$2"
                    shift 2
                else
                    error "Option --email requires an argument."
                fi
                ;;
            --role)
                if [[ -n "${2-}" && $2 != -* ]]; then
                    ROLE="$2"
                    shift 2
                else
                    error "Option --role requires an argument."
                fi
                ;;
            --region)
                if [[ -n "${2-}" && $2 != -* ]]; then
                    REGION="$2"
                    shift 2
                else
                    error "Option --region requires an argument."
                fi
                ;;
            -h|--help)
                HELP=true
                shift
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done

    if [[ "$HELP" == true ]]; then
        show_usage
        exit 0
    fi

    if [[ -z "$EMAIL" ]]; then
        error "Email is required. Use --email <email> or --help for usage information."
    fi
}

validate_dependencies() {
    log "Step 1: Validating dependencies..."

    local missing_deps=()

    if ! command -v isengardcli >/dev/null 2>&1; then
        missing_deps+=("isengardcli")
    fi

    if ! command -v jq >/dev/null 2>&1; then
        missing_deps+=("jq")
    fi

    if ! command -v docker-compose >/dev/null 2>&1; then
        missing_deps+=("docker-compose")
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Missing required dependencies: ${missing_deps[*]}. Please install them before running this script."
    fi

    log "  All required dependencies are available."
}

fetch_aws_credentials() {
    log "Step 2: Fetching AWS credentials..."
    log "  Email: $EMAIL"
    log "  Role: $ROLE"
    log "  Region: $REGION"

    local credentials
    if ! credentials=$(isengardcli credentials --awscli "$EMAIL" --role "$ROLE" --region "$REGION" 2>/dev/null); then
        error "Failed to fetch credentials from Isengard CLI. Please check your email, role, and network connectivity."
    fi

    log "  Successfully retrieved credentials from Isengard CLI."

    # Parse credentials using jq
    ACCESS_KEY_ID=$(echo "$credentials" | jq -r '.AccessKeyId // .Credentials.AccessKeyId')
    SECRET_ACCESS_KEY=$(echo "$credentials" | jq -r '.SecretAccessKey // .Credentials.SecretAccessKey')
    SESSION_TOKEN=$(echo "$credentials" | jq -r '.SessionToken // .Credentials.SessionToken')

    if [[ "$ACCESS_KEY_ID" == "null" || "$SECRET_ACCESS_KEY" == "null" ]]; then
        error "Invalid credentials received from Isengard CLI. Access key or secret key is null."
    fi

    log "  Credentials parsed successfully."
}

update_environment_file() {
    log "Step 3: Updating environment file..."

    # Create .env file if it doesn't exist
    touch "$ENV_FILE"
    log "  Environment file: $ENV_FILE"

    local append_lines=""

    # Function to update or add key-value pairs
    update_key() {
        local key="$1" value="$2"
        if grep -q "^${key}=" "$ENV_FILE"; then
            # Update existing key
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i "" "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
            else
                sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
            fi
            log "    Updated $key"
        else
            # Add new key
            append_lines+="${key}=${value}"$'\n'
            log "    Added $key"
        fi
    }

    # Update AWS credentials
    update_key "AWS_ACCESS_KEY_ID" "$ACCESS_KEY_ID"
    update_key "AWS_SECRET_ACCESS_KEY" "$SECRET_ACCESS_KEY"

    if [[ "$SESSION_TOKEN" != "null" ]]; then
        update_key "AWS_SESSION_TOKEN" "$SESSION_TOKEN"
    fi

    # Append new lines if any
    if [[ -n "$append_lines" ]]; then
        # Ensure file ends with exactly two newlines (blank line separator)
        if [[ -s "$ENV_FILE" ]]; then
            [[ "$(tail -c1 "$ENV_FILE")" != $'\n' ]] && echo >> "$ENV_FILE"
            [[ -n "$(tail -n1 "$ENV_FILE")" ]] && echo >> "$ENV_FILE"
        fi
        printf "%s" "$append_lines" >> "$ENV_FILE"
    fi

    log "  Environment file updated successfully."
}

validate_aws_credentials() {
    log "Step 4: Validating AWS credentials..."

    if AWS_ACCESS_KEY_ID="$ACCESS_KEY_ID" \
       AWS_SECRET_ACCESS_KEY="$SECRET_ACCESS_KEY" \
       AWS_SESSION_TOKEN="$SESSION_TOKEN" \
       aws sts get-caller-identity >/dev/null 2>&1; then
        log "  AWS credentials are valid and working."

        # Get caller identity for logging
        local caller_info
        caller_info=$(AWS_ACCESS_KEY_ID="$ACCESS_KEY_ID" \
                     AWS_SECRET_ACCESS_KEY="$SECRET_ACCESS_KEY" \
                     AWS_SESSION_TOKEN="$SESSION_TOKEN" \
                     aws sts get-caller-identity 2>/dev/null)

        local account_id user_arn
        account_id=$(echo "$caller_info" | jq -r '.Account')
        user_arn=$(echo "$caller_info" | jq -r '.Arn')

        log "    Account: $account_id"
        log "    Identity: $user_arn"
    else
        error "AWS credential validation failed. Please check your Isengard access and try again."
    fi
}

start_development_stack() {
    log "Step 5: Starting development stack..."

    # Stop any existing containers and clean up orphans
    log "  Stopping any existing containers and cleaning up orphans..."
    if docker-compose down --remove-orphans >/dev/null 2>&1; then
        log "    Existing containers stopped and orphans cleaned up."
    else
        log "    No existing containers to stop."
    fi

    # Start the development stack
    log "  Starting Docker Compose stack..."
    log "    This may take a few moments for initial container setup..."

    if docker-compose up -d; then
        log "  Development stack started successfully in detached mode."
        log "    Containers are running in the background."
    else
        error "Failed to start development stack. Please check Docker Compose configuration and container logs."
    fi
}

print_summary() {
    log "========================================================================"
    log "Local Development Environment Setup Complete!"
    log "------------------------------------------------------------------------"
    log "  Email: $EMAIL"
    log "  Role: $ROLE"
    log "  Region: $REGION"
    log "  Environment File: $ENV_FILE"
    log "------------------------------------------------------------------------"
    log "Next Steps:"
    log "  - Your development environment is now running in the background"
    log "  - AWS credentials have been configured in $ENV_FILE"
    log "  - To view logs: docker-compose logs -f"
    log "  - To stop: docker-compose down"
    log "  - To restart: docker-compose up -d"
    log "========================================================================"
}

# --- Main Execution ---
main() {
    parse_arguments "$@"
    validate_dependencies
    fetch_aws_credentials
    update_environment_file
    validate_aws_credentials
    start_development_stack
    print_summary
}

# Run the main function, passing all script arguments
main "$@"
