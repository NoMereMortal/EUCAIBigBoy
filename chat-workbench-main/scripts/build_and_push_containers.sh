#!/bin/bash

# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# ========================================================================
# Container Build and Push Script
# ========================================================================
#
# DESCRIPTION:
#   Builds and pushes the API and UI container images to Amazon ECR.
#   This script supports multiple architectures, local builds without
#   pushing, and automatic ECR repository creation.
#
# USAGE:
#   ./scripts/build_and_push_containers.sh [OPTIONS]
#
# OPTIONS:
#   --region REGION             AWS region (required).
#   --account-number ACCOUNT    AWS account number (required).
#   --aws-profile PROFILE       AWS CLI profile to use (optional).
#   --api-repo REPO_NAME        ECR repository name for the API image (required).
#   --ui-repo REPO_NAME         ECR repository name for the UI image (required).
#   --api-tag TAG               Tag for the API image (default: "latest").
#   --ui-tag TAG                Tag for the UI image (default: "latest").
#   --platform PLATFORM         Target platform for Docker build (default: "linux/amd64").
#   --no-push                   Build images locally but do not push to ECR.
#   --create-repos              Create ECR repositories if they do not exist.
#   --verbose                   Enable verbose output for debugging.
#   --help                      Show this help message.
#
# EXAMPLES:
#   # Build and push with specific tags and profile
#   ./build_and_push_containers.sh --region us-east-1 --account-number 123456789012 \
#     --aws-profile production --api-repo my-api --ui-repo my-ui \
#     --api-tag v1.2.0 --ui-tag v1.1.5
#
#   # Build for ARM64 architecture (AWS Graviton)
#   ./build_and_push_containers.sh -r us-east-1 -a 123456789012 \
#     --api-repo my-api --ui-repo my-ui --platform linux/arm64
#
#   # Build locally for testing without pushing
#   ./build_and_push_containers.sh -r us-east-1 -a 123456789012 \
#     --api-repo my-api --ui-repo my-ui --no-push
#
# PREREQUISITES:
#   - Docker must be installed and running.
#   - AWS CLI must be installed and configured.
#
# REQUIRED IAM PERMISSIONS:
#   - ecr:GetAuthorizationToken
#   - ecr:PutImage
#   - ecr:InitiateLayerUpload
#   - ecr:UploadLayerPart
#   - ecr:CompleteLayerUpload
#   - ecr:CreateRepository (only if using --create-repos)
#   - ecr:DescribeRepositories
#
# ========================================================================

set -euo pipefail  # Exit on any error, treat unset variables as error, fail on pipe errors


# Default values
AWS_REGION=""
AWS_ACCOUNT_NUMBER=""
AWS_PROFILE=""
API_REPO_NAME=""
UI_REPO_NAME=""
API_TAG="latest"
UI_TAG="latest"
PLATFORM="linux/amd64"
PUSH_TO_ECR=true
CREATE_REPOS=false
VERBOSE=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Build and push Chat Workbench container images to ECR

Options:
    --region REGION             AWS region (required)
    --account-number ACCOUNT    AWS account number (required)
    --aws-profile PROFILE       AWS profile to use (optional)
    --api-repo REPO_NAME        API repository name (required)
    --ui-repo REPO_NAME         UI repository name (required)
    --api-tag TAG               API image tag (default: latest)
    --ui-tag TAG                UI image tag (default: latest)
    --platform PLATFORM         Target platform (default: linux/amd64)
    --no-push                   Build only, don't push to ECR
    --create-repos              Create ECR repositories if they don't exist
    --verbose                   Enable verbose output
    --help                      Show this help message

Examples:
    # Build and push with specific tags
    $0 --region us-east-1 --account-number 123456789012 --api-repo my-api-repo --ui-repo my-ui-repo --api-tag v1.0.0 --ui-tag v1.0.0

    # Build with different tags for API and UI
    $0 --region us-east-1 --account-number 123456789012 --api-repo my-api-repo --ui-repo my-ui-repo --api-tag v2.0.0 --ui-tag v1.5.0

    # Build with specific AWS profile for production
    $0 --region us-east-1 --account-number 123456789012 --aws-profile production --api-repo my-api-repo --ui-repo my-ui-repo --api-tag v1.0.0 --ui-tag v1.0.0

    # Build for ARM architecture
    $0 --region us-east-1 --account-number 123456789012 --api-repo my-api-repo --ui-repo my-ui-repo --api-tag v1.0.0 --ui-tag v1.0.0 --platform linux/arm64

    # Build locally without pushing
    $0 --region us-east-1 --account-number 123456789012 --api-repo my-api-repo --ui-repo my-ui-repo --api-tag local-test --ui-tag local-test --no-push

    # Create repositories and push
    $0 --region us-east-1 --account-number 123456789012 --api-repo my-api-repo --ui-repo my-ui-repo --api-tag v1.0.0 --ui-tag v1.0.0 --create-repos

Environment Variables:
    AWS_REGION              AWS region
    AWS_ACCOUNT_NUMBER      AWS account number
    AWS_PROFILE             AWS profile to use
    API_REPO_NAME           API repository name
    UI_REPO_NAME            UI repository name
    API_TAG                 API image tag
    UI_TAG                  UI image tag
    TARGET_PLATFORM         Target platform
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --account-number)
            AWS_ACCOUNT_NUMBER="$2"
            shift 2
            ;;
        --aws-profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --api-repo)
            API_REPO_NAME="$2"
            shift 2
            ;;
        --ui-repo)
            UI_REPO_NAME="$2"
            shift 2
            ;;
        --api-tag)
            API_TAG="$2"
            shift 2
            ;;
        --ui-tag)
            UI_TAG="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --no-push)
            PUSH_TO_ECR=false
            shift
            ;;
        --create-repos)
            CREATE_REPOS=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Override with environment variables if not provided
AWS_REGION=${AWS_REGION:-$AWS_REGION}
AWS_ACCOUNT_NUMBER=${AWS_ACCOUNT_NUMBER:-$AWS_ACCOUNT_NUMBER}
AWS_PROFILE=${AWS_PROFILE:-$AWS_PROFILE}
API_REPO_NAME=${API_REPO_NAME:-$API_REPO_NAME}
UI_REPO_NAME=${UI_REPO_NAME:-$UI_REPO_NAME}
API_TAG=${API_TAG:-${API_TAG:-latest}}
UI_TAG=${UI_TAG:-${UI_TAG:-latest}}

# Validate that we have actual values (not empty strings)
if [[ -z "$API_TAG" ]]; then
    API_TAG="latest"
fi
if [[ -z "$UI_TAG" ]]; then
    UI_TAG="latest"
fi
PLATFORM=${PLATFORM:-${TARGET_PLATFORM:-linux/amd64}}

# Comprehensive validation of all required parameters
validate_required_parameters() {
    local errors=0

    print_info "Validating required parameters..."

    # Check required parameters
    if [[ -z "$AWS_REGION" ]]; then
        print_error "AWS region is required. Use --region or set AWS_REGION environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$AWS_ACCOUNT_NUMBER" ]]; then
        print_error "AWS account number is required. Use --account-number or set AWS_ACCOUNT_NUMBER environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$API_REPO_NAME" ]]; then
        print_error "API repository name is required. Use --api-repo or set API_REPO_NAME environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$UI_REPO_NAME" ]]; then
        print_error "UI repository name is required. Use --ui-repo or set UI_REPO_NAME environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$API_TAG" ]]; then
        print_error "API tag is required. Use --api-tag or set API_TAG environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$UI_TAG" ]]; then
        print_error "UI tag is required. Use --ui-tag or set UI_TAG environment variable."
        errors=$((errors + 1))
    fi

    if [[ -z "$PLATFORM" ]]; then
        print_error "Platform is required. Use --platform or set TARGET_PLATFORM environment variable."
        errors=$((errors + 1))
    fi

    # Validate format of provided parameters
    if [[ -n "$AWS_ACCOUNT_NUMBER" ]] && ! [[ "$AWS_ACCOUNT_NUMBER" =~ ^[0-9]{12}$ ]]; then
        print_error "Invalid AWS account number format. Must be 12 digits, got: '$AWS_ACCOUNT_NUMBER'"
        errors=$((errors + 1))
    fi

    if [[ -n "$AWS_REGION" ]] && ! [[ "$AWS_REGION" =~ ^[a-z0-9-]+$ ]]; then
        print_error "Invalid AWS region format. Must contain only lowercase letters, numbers, and hyphens, got: '$AWS_REGION'"
        errors=$((errors + 1))
    fi

    if [[ -n "$API_REPO_NAME" ]] && ! [[ "$API_REPO_NAME" =~ ^[a-z0-9][a-z0-9._/-]*[a-z0-9]$|^[a-z0-9]$ ]]; then
        print_error "Invalid API repository name format. Must follow ECR naming rules, got: '$API_REPO_NAME'"
        errors=$((errors + 1))
    fi

    if [[ -n "$UI_REPO_NAME" ]] && ! [[ "$UI_REPO_NAME" =~ ^[a-z0-9][a-z0-9._/-]*[a-z0-9]$|^[a-z0-9]$ ]]; then
        print_error "Invalid UI repository name format. Must follow ECR naming rules, got: '$UI_REPO_NAME'"
        errors=$((errors + 1))
    fi

    if [[ -n "$API_TAG" ]] && ! [[ "$API_TAG" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
        print_error "Invalid API tag format. Must start with alphanumeric and contain only letters, numbers, periods, underscores, and hyphens, got: '$API_TAG'"
        errors=$((errors + 1))
    fi

    if [[ -n "$UI_TAG" ]] && ! [[ "$UI_TAG" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
        print_error "Invalid UI tag format. Must start with alphanumeric and contain only letters, numbers, periods, underscores, and hyphens, got: '$UI_TAG'"
        errors=$((errors + 1))
    fi

    if [[ -n "$PLATFORM" ]] && ! [[ "$PLATFORM" =~ ^linux/(amd64|arm64)$ ]]; then
        print_error "Invalid platform format. Must be 'linux/amd64' or 'linux/arm64', got: '$PLATFORM'"
        errors=$((errors + 1))
    fi

    # Check for tag length limits (ECR has a 300 character limit)
    if [[ -n "$API_TAG" ]] && [[ ${#API_TAG} -gt 300 ]]; then
        print_error "API tag too long. Maximum 300 characters, got ${#API_TAG} characters"
        errors=$((errors + 1))
    fi

    if [[ -n "$UI_TAG" ]] && [[ ${#UI_TAG} -gt 300 ]]; then
        print_error "UI tag too long. Maximum 300 characters, got ${#UI_TAG} characters"
        errors=$((errors + 1))
    fi

    # Check for repository name length limits (ECR has a 256 character limit)
    if [[ -n "$API_REPO_NAME" ]] && [[ ${#API_REPO_NAME} -gt 256 ]]; then
        print_error "API repository name too long. Maximum 256 characters, got ${#API_REPO_NAME} characters"
        errors=$((errors + 1))
    fi

    if [[ -n "$UI_REPO_NAME" ]] && [[ ${#UI_REPO_NAME} -gt 256 ]]; then
        print_error "UI repository name too long. Maximum 256 characters, got ${#UI_REPO_NAME} characters"
        errors=$((errors + 1))
    fi

    # Check for same repository with same tag (would cause overwrite)
    if [[ -n "$API_REPO_NAME" ]] && [[ -n "$UI_REPO_NAME" ]] && [[ -n "$API_TAG" ]] && [[ -n "$UI_TAG" ]]; then
        if [[ "$API_REPO_NAME" == "$UI_REPO_NAME" ]] && [[ "$API_TAG" == "$UI_TAG" ]]; then
            print_error "API and UI cannot use the same repository name AND the same tag."
            print_error "This would cause one container to overwrite the other."
            print_info "Solutions:"
            print_info "  1. Use different repositories: --api-repo my-api-repo --ui-repo my-ui-repo"
            print_info "  2. Use different tags: --api-tag api-v1.0.0 --ui-tag ui-v1.0.0"
            print_info "  3. Use component prefixes: --api-tag api-latest --ui-tag ui-latest"
            errors=$((errors + 1))
        fi
    fi

    # Summary of validation results
    if [[ $errors -gt 0 ]]; then
        print_error "Found $errors validation error(s). Please fix the issues above before proceeding."
        print_info "Use --help to see usage examples and requirements."
        exit 1
    fi

    print_success "All required parameters validated successfully"
}

# Set full repository URIs
ECR_REGISTRY="${AWS_ACCOUNT_NUMBER}.dkr.ecr.${AWS_REGION}.amazonaws.com"
API_REPO_URI="${ECR_REGISTRY}/${API_REPO_NAME}"
UI_REPO_URI="${ECR_REGISTRY}/${UI_REPO_NAME}"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

print_info "Starting container build process..."
print_info "Project root: ${PROJECT_ROOT}"
print_info "AWS Region: ${AWS_REGION}"
print_info "AWS Account Number: ${AWS_ACCOUNT_NUMBER}"
if [[ -n "$AWS_PROFILE" ]]; then
    print_info "AWS Profile: ${AWS_PROFILE}"
fi
print_info "API Repository: ${API_REPO_NAME}"
print_info "UI Repository: ${UI_REPO_NAME}"
print_info "API tag: ${API_TAG}"
print_info "UI tag: ${UI_TAG}"
print_info "Target platform: ${PLATFORM}"
print_info "Push to ECR: ${PUSH_TO_ECR}"

# Check for .dockerignore file
if [[ ! -f "${PROJECT_ROOT}/.dockerignore" ]]; then
    print_warning ".dockerignore file not found. Consider creating one to optimize build performance."
fi

# Check if required files exist
if [[ ! -f "${PROJECT_ROOT}/infrastructure/docker/backend/Dockerfile" ]]; then
    print_error "API Dockerfile not found at: ${PROJECT_ROOT}/infrastructure/docker/backend/Dockerfile"
    exit 1
fi

if [[ ! -f "${PROJECT_ROOT}/ui/Dockerfile" ]]; then
    print_error "UI Dockerfile not found at: ${PROJECT_ROOT}/ui/Dockerfile"
    exit 1
fi

# Function to create ECR repository if it doesn't exist
create_ecr_repository() {
    local repo_name="$1"
    local repo_uri="$2"

    print_info "Checking if ECR repository exists: ${repo_name}"

    local aws_describe_cmd="aws ecr describe-repositories --repository-names ${repo_name} --region ${AWS_REGION}"
    local aws_create_cmd="aws ecr create-repository --repository-name ${repo_name} --region ${AWS_REGION} --image-scanning-configuration scanOnPush=true --encryption-configuration encryptionType=AES256"

    if [[ -n "$AWS_PROFILE" ]]; then
        aws_describe_cmd="$aws_describe_cmd --profile ${AWS_PROFILE}"
        aws_create_cmd="$aws_create_cmd --profile ${AWS_PROFILE}"
    fi

    if $aws_describe_cmd >/dev/null 2>&1; then
        print_info "Repository ${repo_name} already exists"
    else
        if [[ "$CREATE_REPOS" == true ]]; then
            print_info "Creating ECR repository: ${repo_name}"
            $aws_create_cmd
            print_success "Created ECR repository: ${repo_name}"
        else
            print_error "Repository ${repo_name} does not exist. Use --create-repos to create it."
            exit 1
        fi
    fi
}

# Function to authenticate with ECR
authenticate_ecr() {
    print_info "Authenticating with ECR..."
    local aws_cmd="aws ecr get-login-password --region ${AWS_REGION}"
    if [[ -n "$AWS_PROFILE" ]]; then
        aws_cmd="aws ecr get-login-password --region ${AWS_REGION} --profile ${AWS_PROFILE}"
    fi
    $aws_cmd | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    print_success "Successfully authenticated with ECR"
}

# Function to build container image
build_image() {
    local image_name="$1"
    local dockerfile_path="$2"
    local context_path="$3"
    local full_image_name="$4"
    local tag="$5"

    print_info "Building ${image_name} container image..."
    print_info "Dockerfile: ${dockerfile_path}"
    print_info "Context: ${context_path}"
    print_info "Platform: ${PLATFORM}"

    if [[ "$VERBOSE" == true ]]; then
        print_info "Running: docker build --platform ${PLATFORM} -f ${dockerfile_path} -t ${image_name}:${tag} ${context_path}"
        set -x
    fi

    # Build the image - avoid eval for security
    docker build --platform "${PLATFORM}" -f "${dockerfile_path}" -t "${image_name}:${tag}" "${context_path}"

    if [[ "$VERBOSE" == true ]]; then
        set +x
    fi

    if [[ "$PUSH_TO_ECR" == true ]]; then
        # Tag for ECR
        docker tag "${image_name}:${tag}" "${full_image_name}:${tag}"
        print_success "Built and tagged ${image_name}:${tag}"
    else
        print_success "Built ${image_name}:${tag}"
    fi
}

# Function to push image to ECR
push_image() {
    local image_name="$1"
    local full_image_name="$2"
    local tag="$3"

    print_info "Pushing ${image_name} to ECR..."
    docker push "${full_image_name}:${tag}"

    # Get image digest
    local digest=$(docker inspect "${full_image_name}:${tag}" --format='{{index .RepoDigests 0}}' 2>/dev/null || echo "")

    print_success "Successfully pushed ${image_name} to ECR"
    print_info "Repository URI: ${full_image_name}"
    print_info "Image Tag: ${tag}"
    if [[ -n "$digest" ]]; then
        print_info "Image Digest: ${digest}"
    fi
}

# Function to display final configuration
display_config() {
    print_info "Container images ready for BYOC deployment!"
    echo ""
    echo "Add the following to your config.yaml:"
    echo ""
    echo "restApiConfig:"
    echo "  ecrContainer:"
    echo "    repositoryUri: \"${API_REPO_URI}\""
    echo "    imageTag: \"${API_TAG}\""
    echo ""
    echo "uiConfig:"
    echo "  ecrContainer:"
    echo "    repositoryUri: \"${UI_REPO_URI}\""
    echo "    imageTag: \"${UI_TAG}\""
    echo ""

    # If we can get the digest, show production-ready config
    local api_digest
    api_digest=$(docker inspect "${API_REPO_URI}:${API_TAG}" --format='{{index .RepoDigests 0}}' 2>/dev/null | cut -d'@' -f2) || api_digest=""
    local ui_digest
    ui_digest=$(docker inspect "${UI_REPO_URI}:${UI_TAG}" --format='{{index .RepoDigests 0}}' 2>/dev/null | cut -d'@' -f2) || ui_digest=""

    if [[ -n "$api_digest" && -n "$ui_digest" ]]; then
        echo "For production (with immutable SHA256 digests):"
        echo ""
        echo "restApiConfig:"
        echo "  ecrContainer:"
        echo "    repositoryUri: \"${API_REPO_URI}\""
        echo "    imageTag: \"${api_digest}\""
        echo ""
        echo "uiConfig:"
        echo "  ecrContainer:"
        echo "    repositoryUri: \"${UI_REPO_URI}\""
        echo "    imageTag: \"${ui_digest}\""
    fi
}

# Check system prerequisites
check_prerequisites() {
    print_info "Checking system prerequisites..."

    # Set AWS profile if specified
    if [[ -n "$AWS_PROFILE" ]]; then
        export AWS_PROFILE="$AWS_PROFILE"
        print_info "Using AWS profile: $AWS_PROFILE"
    fi

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"

    # Check if AWS CLI is installed and configured
    if ! command -v aws >/dev/null 2>&1; then
        print_error "AWS CLI is not installed. Please install AWS CLI and try again."
        exit 1
    fi
    print_success "AWS CLI is installed"

    # Check if AWS credentials are configured
    local aws_cmd="aws sts get-caller-identity"
    if [[ -n "$AWS_PROFILE" ]]; then
        aws_cmd="aws sts get-caller-identity --profile $AWS_PROFILE"
    fi

    if ! $aws_cmd >/dev/null 2>&1; then
        print_error "AWS CLI is not configured or credentials are invalid."
        if [[ -n "$AWS_PROFILE" ]]; then
            print_info "Please check that AWS profile '$AWS_PROFILE' exists and has valid credentials."
        else
            print_info "Please run 'aws configure' or set AWS_PROFILE environment variable."
        fi
        exit 1
    fi
    print_success "AWS CLI is configured with valid credentials"

    # Verify AWS account matches provided account number
    local actual_account
    if [[ -n "$AWS_PROFILE" ]]; then
        actual_account=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text 2>/dev/null)
    else
        actual_account=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    fi

    if [[ "$actual_account" != "$AWS_ACCOUNT_NUMBER" ]]; then
        print_error "AWS account mismatch. Configured account: $actual_account, Expected: $AWS_ACCOUNT_NUMBER"
        if [[ -n "$AWS_PROFILE" ]]; then
            print_info "Please check your AWS profile '$AWS_PROFILE' or update the --account-number parameter."
        else
            print_info "Please check your AWS credentials or update the --account-number parameter."
        fi
        exit 1
    fi
    print_success "AWS account verified: $AWS_ACCOUNT_NUMBER"
}

# Main execution
main() {
    # Validate all required parameters first
    validate_required_parameters

    # Check system prerequisites
    check_prerequisites

    # Create repositories if requested
    if [[ "$PUSH_TO_ECR" == true ]]; then
        create_ecr_repository "${API_REPO_NAME}" "${API_REPO_URI}"
        create_ecr_repository "${UI_REPO_NAME}" "${UI_REPO_URI}"
        authenticate_ecr
    fi

    # Build images sequentially for better error visibility
    print_info "Building API container image..."
    build_image "cwb-api" "${PROJECT_ROOT}/infrastructure/docker/backend/Dockerfile" "${PROJECT_ROOT}" "${API_REPO_URI}" "${API_TAG}"

    print_info "Building UI container image..."
    build_image "cwb-ui" "${PROJECT_ROOT}/ui/Dockerfile" "${PROJECT_ROOT}/ui" "${UI_REPO_URI}" "${UI_TAG}"

    print_success "All container images built successfully"

    # Push images if requested
    if [[ "$PUSH_TO_ECR" == true ]]; then
        print_info "Pushing API container image..."
        push_image "cwb-api" "${API_REPO_URI}" "${API_TAG}"

        print_info "Pushing UI container image..."
        push_image "cwb-ui" "${UI_REPO_URI}" "${UI_TAG}"

        print_success "All container images pushed successfully"
    fi

    # Display final configuration
    display_config

    print_success "Container build and push process completed successfully!"
}

# Run main function
main
