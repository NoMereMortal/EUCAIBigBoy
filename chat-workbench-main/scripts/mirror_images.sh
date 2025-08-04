#!/bin/bash
# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

# mirror_images.sh - Mirror Docker images to GitLab registry

# Configuration
GITLAB_REGISTRY="registry.gitlab.aws.dev"
PROJECT_PATH="genaiic-reusable-assets/shareable-assets/chat-workbench"
TARGET_REGISTRY="${GITLAB_REGISTRY}/${PROJECT_PATH}"

# Detect CI environment
if [ -n "$CI_JOB_TOKEN" ]; then
  # We're in a CI environment, use CI_JOB_TOKEN
  echo "CI environment detected. Using CI_JOB_TOKEN for authentication."
  echo "Logging in to GitLab registry at ${CI_REGISTRY}..."
  docker login "${CI_REGISTRY}" -u "${CI_REGISTRY_USER}" -p "${CI_JOB_TOKEN}"
else
  # We're in a manual environment, use a fixed username with the token
  echo "Logging in to GitLab registry at ${GITLAB_REGISTRY}..."
  echo "Please enter your GitLab project access token (input will be hidden):"
  read -rs TOKEN
  echo "$TOKEN" | docker login "${GITLAB_REGISTRY}" -u "deployment" --password-stdin
fi

if [ $? -ne 0 ]; then
  echo "Error: Failed to authenticate with GitLab registry."
  exit 1
fi

# ============================================
# SECTION 1: CI Pipeline Images
# ============================================
echo "============================================="
echo "Mirroring CI Pipeline Images"
echo "============================================="
# Use parallel arrays instead of associative arrays
source_ci_images=(
  "ghcr.io/astral-sh/uv:python3.13-alpine"
  "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
  "valkey/valkey:alpine"
  "public.ecr.aws/aws-dynamodb-local/aws-dynamodb-local:latest"
  "public.ecr.aws/docker/library/node:20-alpine"
  "public.ecr.aws/docker/library/rust:alpine"
)

target_ci_images=(
  "${TARGET_REGISTRY}/uv:python3.13-alpine"
  "${TARGET_REGISTRY}/uv:python3.13-bookworm-slim"
  "${TARGET_REGISTRY}/valkey:alpine"
  "${TARGET_REGISTRY}/dynamodb-local:latest"
  "${TARGET_REGISTRY}/node:20-alpine"
  "${TARGET_REGISTRY}/rust:alpine"
)

# Loop through arrays in parallel
for i in "${!source_ci_images[@]}"; do
  source_image="${source_ci_images[$i]}"
  target_image="${target_ci_images[$i]}"

  echo "Processing: $source_image -> $target_image"
  echo "  Pulling $source_image (amd64 platform)..."
  docker pull --platform=linux/amd64 "$source_image"

  if [ $? -ne 0 ]; then
    echo "  Warning: Failed to pull $source_image. Skipping."
    continue
  fi

  echo "  Tagging as $target_image..."
  docker tag "$source_image" "$target_image"

  echo "  Pushing to $target_image..."
  docker push "$target_image"

  if [ $? -ne 0 ]; then
    echo "  Error: Failed to push $target_image."
  else
    echo "  Successfully mirrored $source_image to $target_image"
  fi
done

# ============================================
# SECTION 2: Build Images
# ============================================
echo "============================================="
echo "Mirroring Build Images"
echo "============================================="
# Use parallel arrays instead of associative arrays
source_build_images=(
  "python:3.13-slim"
  "node:23-alpine"
)

target_build_images=(
  "${TARGET_REGISTRY}/python:3.13-slim"
  "${TARGET_REGISTRY}/node:23-alpine"
)

# Loop through arrays in parallel
for i in "${!source_build_images[@]}"; do
  source_image="${source_build_images[$i]}"
  target_image="${target_build_images[$i]}"

  echo "Processing: $source_image -> $target_image"
  echo "  Pulling $source_image (amd64 platform)..."
  docker pull --platform=linux/amd64 "$source_image"

  if [ $? -ne 0 ]; then
    echo "  Warning: Failed to pull $source_image. Skipping."
    continue
  fi

  echo "  Tagging as $target_image..."
  docker tag "$source_image" "$target_image"

  echo "  Pushing to $target_image..."
  docker push "$target_image"

  if [ $? -ne 0 ]; then
    echo "  Error: Failed to push $target_image."
  else
    echo "  Successfully mirrored $source_image to $target_image"
  fi
done

# ============================================
# SECTION 3: Development Environment Images
# ============================================
echo "============================================="
echo "Mirroring Development Environment Images"
echo "============================================="
# Use parallel arrays instead of associative arrays
source_dev_images=(
  "amazon/dynamodb-local:latest"
  "prom/prometheus:latest"
  "grafana/grafana:latest"
  "opensearchproject/opensearch:latest"
  "opensearchproject/opensearch-dashboards:latest"
  "quay.io/keycloak/keycloak:latest"
)

target_dev_images=(
  "${TARGET_REGISTRY}/dynamodb-local:latest"
  "${TARGET_REGISTRY}/prometheus:latest"
  "${TARGET_REGISTRY}/grafana:latest"
  "${TARGET_REGISTRY}/opensearch:latest"
  "${TARGET_REGISTRY}/opensearch-dashboards:latest"
  "${TARGET_REGISTRY}/keycloak:latest"
)

# Loop through arrays in parallel
for i in "${!source_dev_images[@]}"; do
  source_image="${source_dev_images[$i]}"
  target_image="${target_dev_images[$i]}"

  echo "Processing: $source_image -> $target_image"
  echo "  Pulling $source_image (amd64 platform)..."
  docker pull --platform=linux/amd64 "$source_image"

  if [ $? -ne 0 ]; then
    echo "  Warning: Failed to pull $source_image. Skipping."
    continue
  fi

  echo "  Tagging as $target_image..."
  docker tag "$source_image" "$target_image"

  echo "  Pushing to $target_image..."
  docker push "$target_image"

  if [ $? -ne 0 ]; then
    echo "  Error: Failed to push $target_image."
  else
    echo "  Successfully mirrored $source_image to $target_image"
  fi
done

echo "Image mirroring process completed."
docker logout "${GITLAB_REGISTRY}"
