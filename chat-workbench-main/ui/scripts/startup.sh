#!/bin/bash
# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

set -e

# Environment variables that should be set in the ECS task definition:
# - SSM_PARAM_NAME: the name of the SSM parameter containing the UI configuration
# - AWS_REGION: the AWS region
# - DEPLOYMENT_STAGE: the deployment stage (dev, prod, etc.)

echo "Starting UI container..."

# Log environment information
echo "Environment: ${NODE_ENV:-not set}"

# Only log AWS configuration in production mode
if [ "$NODE_ENV" = "production" ]; then
  echo "AWS Configuration:"
  echo "  Region: ${AWS_REGION:-not set}"
  echo "  Profile: ${AWS_PROFILE:-not set}"
  echo "  SSM Parameter: ${SSM_PARAM_NAME:-not set}"
fi

# Check if we have a SSM parameter name set
if [ -z "$SSM_PARAM_NAME" ]; then
  echo "SSM_PARAM_NAME not set, using default parameter name"
  SSM_PARAM_NAME="/chatworkbench/${DEPLOYMENT_STAGE:-dev}/ui-config"
fi

# Check if AWS_REGION is set
if [ -z "$AWS_REGION" ]; then
  echo "AWS_REGION not set, using default region"
  AWS_REGION="us-east-1"
fi

# Make sure the directory exists
mkdir -p /app/public

# Create a simple health check file immediately to ensure the container passes health checks
echo "OK" > /app/public/health

# Set NODE_PATH to ensure modules can be found
export NODE_PATH="/app/node_modules"

# Check if we're in development mode
if [ "$NODE_ENV" = "development" ]; then
  # In development, use local env.js if it exists
  if [ -f "/app/public/env.js" ]; then
    echo "Development environment detected with local env.js file, using it instead of fetching from SSM"
  else
    echo "Development environment detected without local env.js file, creating mock configuration"
    # Use the create-dev-config.cjs script
    node /app/scripts/create-dev-config.cjs
  fi
else
  # In production, always fetch from SSM regardless of whether a local env.js exists
  echo "Fetching configuration from SSM parameter: $SSM_PARAM_NAME"
  echo "Using pre-installed AWS SDK v3..."

  # Run the fetch-ssm.cjs script
  node /app/scripts/fetch-ssm.cjs
fi

echo "Loading environment variables from env.js..."
# Parse env.js into environment variables
if [ -f "/app/public/env.js" ]; then
  # Extract the JSON object from window.env = {...};
  ENV_CONFIG=$(grep -o '{.*}' /app/public/env.js | sed 's/^{//;s/}$//')

  # Extract API_URI and set as environment variable
  API_URI=$(echo "$ENV_CONFIG" | grep -o '"API_URI": *"[^"]*"' | cut -d'"' -f4)
  if [ ! -z "$API_URI" ]; then
    export NEXT_PUBLIC_API_URI="$API_URI"
    echo "  Set NEXT_PUBLIC_API_URI=$API_URI"
  fi

  # Extract API_VERSION and set as environment variable
  API_VERSION=$(echo "$ENV_CONFIG" | grep -o '"API_VERSION": *"[^"]*"' | cut -d'"' -f4)
  if [ ! -z "$API_VERSION" ]; then
    export NEXT_PUBLIC_API_VERSION="$API_VERSION"
    echo "  Set NEXT_PUBLIC_API_VERSION=$API_VERSION"
  fi

  # Extract UI_TITLE and set as environment variable
  UI_TITLE=$(echo "$ENV_CONFIG" | grep -o '"UI_TITLE": *"[^"]*"' | cut -d'"' -f4)
  if [ ! -z "$UI_TITLE" ]; then
    export NEXT_PUBLIC_UI_TITLE="$UI_TITLE"
    echo "  Set NEXT_PUBLIC_UI_TITLE=$UI_TITLE"
  fi

  echo "Environment variables loaded successfully from env.js"
else
  echo "Warning: env.js not found, environment variables not set"
fi

echo "Starting Next.js server..."

# Determine how to start the server
if [ -f "/app/server.js" ]; then
  echo "Using standalone server.js"
  exec node server.js
elif [ -d "/app/out" ]; then
  echo "Using static export - starting a simple HTTP server"
  # Use the static-server.cjs script
  exec node /app/scripts/static-server.cjs
else
  echo "Error: Neither server.js nor out directory found"
  exit 1
fi
