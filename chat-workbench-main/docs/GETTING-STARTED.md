# Getting Started with Chat Workbench

This guide will help you set up your development environment and get Chat Workbench running locally. Follow these steps to go from zero to a fully functional development setup.

## Prerequisites

### Required Software

- **Docker**: Version 20.10+ with Docker Compose V2
- **Node.js**: Version 18+ (for UI development and CDK)
- **Python**: Version 3.11+ (for backend development)
- **AWS CLI**: Version 2+ (for deployment)

### AWS Account Setup

1. **Install and configure AWS CLI**:

   ```bash
   aws configure
   ```

2. **Verify Amazon Bedrock access**:

   ```bash
   aws bedrock list-foundation-models --region us-east-1
   ```

3. **Copy credentials if using external tools**:
   ```bash
   # Example for copying from external credential tools
   cp ~/.aws/credentials-external ~/.aws/credentials
   ```

## Quick Start

### AWS Internal Employees

If you're an AWS employee with access to internal systems, you can use the automated setup script:

```bash
# Clone the repository
git clone <repository-url>
cd chat-workbench

# Use internal setup script (requires mwinit signed keys)
./scripts/isengardcli_start_local_app.sh --email your-email@amazon.com
```

**Prerequisites for AWS employees:**

- Run `mwinit` first to sign your keys (required for credential access)
- Have `isengardcli` installed and configured
- Access to internal AWS systems

**Note:** This script will automatically:

- Fetch AWS credentials via Isengard CLI
- Update your `.env` file with proper AWS credentials
- Start the development stack with `docker-compose up`

### Standard Setup (External Contributors)

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd chat-workbench

# Copy environment configuration
cp .env.example .env
```

### 2. Configure Environment Variables

Edit the `.env` file with your settings:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# API Configuration
API_HOST=0.0.0.0
API_CORS_ORIGINS=["http://localhost:3000"]

# Database Configuration
DYNAMODB_TABLE_NAME=chat-workbench-dev
DYNAMODB_ENDPOINT_URL=http://dynamodb-local:8000

# OpenSearch Configuration
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_ENABLED=true

# Cache Configuration
VALKEY_HOST=valkey
VALKEY_PORT=6379

# Authentication Configuration
AUTH_ENABLED=true
AUTH_AUTHORITY=http://localhost:8080/realms/chat-workbench
AUTH_CLIENT_ID=chat-workbench-ui
AUTH_CLIENT_SECRET=chat-workbench-secret

# Next.js UI Configuration
NEXT_PUBLIC_API_URI=http://localhost:8000
NEXT_PUBLIC_BYPASS_AUTH=false

# Monitoring
GF_SECURITY_ADMIN_PASSWORD=admin
```

### 3. Start Development Environment

```bash
# Start all services in development mode
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f app
```

### 4. Verify Setup

Access the following services to verify everything is working:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Keycloak Admin**: http://localhost:8080/admin (admin/admin)
- **Grafana**: http://localhost:3006 (admin/admin)
- **Prometheus**: http://localhost:9090
- **OpenSearch**: http://localhost:9200
- **OpenSearch Dashboards**: http://localhost:5601

## Authentication Setup

Chat Workbench uses OIDC (OpenID Connect) for secure authentication. The development environment includes a preconfigured Keycloak instance.

### Default Authentication Configuration

**Local Development (Keycloak)**:

- **Admin Console**: http://localhost:8080/admin (admin/admin)
- **Realm**: `chat-workbench`
- **Client ID**: `chat-workbench-ui`
- **Client Secret**: `chat-workbench-secret`
- **Test User**: `testuser` / `password`

**Environment Variables**:

```bash
AUTH_ENABLED=true                                              # Enable authentication
AUTH_AUTHORITY=http://localhost:8080/realms/chat-workbench    # Keycloak realm URL
AUTH_CLIENT_ID=chat-workbench-ui                              # OIDC client identifier
AUTH_CLIENT_SECRET=chat-workbench-secret                      # Client secret for backend
```

### Authentication Flow Overview

1. **User Access**: Navigate to http://localhost:3000
2. **Login Redirect**: Click "Sign In" → redirected to Keycloak
3. **Authentication**: Enter `testuser` / `password`
4. **Token Exchange**: Automatic OIDC token exchange
5. **Authenticated Access**: Full application access with user context

### Production Authentication

For production deployments, Chat Workbench integrates with AWS Cognito:

```bash
# Production environment variables
AUTH_AUTHORITY=https://cognito-idp.region.amazonaws.com/user-pool-id
AUTH_CLIENT_ID=your-cognito-client-id
AUTH_CLIENT_SECRET=your-cognito-client-secret
```

**For detailed authentication information**, including OIDC flow diagrams, security implementation, JWT validation, and troubleshooting, see the [Authentication Flow Guide](guides/AUTHENTICATION_FLOW.md).

## Development Workflow

### Frontend Development

The frontend is a Next.js application located in the `ui/` directory.

#### Setup

```bash
cd ui
npm install
```

#### Development Commands

```bash
# Start development server (alternative to docker compose)
npm run dev

# Run linting
npm run lint

# Run type checking
npm run type-check

# Build for production
npm run build
```

#### Project Structure

```
ui/
├── app/                    # Next.js app router
├── components/             # Reusable React components
│   ├── auth/              # Authentication components
│   ├── chat/              # Chat-related components
│   ├── ui/                # Base UI components
│   └── providers/         # Context providers
├── hooks/                 # Custom React hooks
├── lib/                   # Utility libraries
└── public/                # Static assets
```

### Backend Development

The backend is a FastAPI application located in the `backend/` directory.

#### Setup

```bash
cd backend

# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

#### Development Commands

```bash
# Start development server (alternative to docker)
python -m app.api.main

# With hot reload
HOT_RELOAD=true python -m app.api.main

# Run tests
pytest

# Run type checking
mypy app/

# Run linting
ruff check app/
```

#### Project Structure

```
backend/app/
├── api/                   # FastAPI application and routing
│   ├── dependencies/      # Dependency injection
│   ├── middleware/        # Request/response middleware
│   ├── routes/           # API route handlers
│   └── state.py          # Application state management
├── clients/              # External service clients
├── repositories/         # Data access layer
├── services/            # Business logic services
├── task_handlers/       # AI task processing
├── config.py            # Configuration management
├── models.py            # Pydantic data models
└── utils.py             # Utility functions
```

### Infrastructure Development

The infrastructure is managed using AWS CDK in the `infrastructure/cdk/` directory.

#### Setup

```bash
cd infrastructure/cdk
npm install
```

#### Development Commands

```bash
# Build CDK application
npm run build

# Run CDK validation
npm run cdk synth

# Deploy to AWS (requires AWS credentials)
ENV=dev npm run cdk deploy --all

# Check differences
npm run cdk diff
```

### Deployment Configuration

Chat Workbench supports flexible deployment configurations with enhanced security features.

> **📖 Complete Configuration Guide**: For a comprehensive reference of all configuration options, see the **[Configuration Reference Guide](CONFIGURATION-REFERENCE.md)**. This includes logging retention, S3 lifecycle policies, security settings, and more.

#### Required Configuration (`config.yaml`)

The deployment configuration must include several key sections for proper operation. Here's a minimal example:

```yaml
dev:
  # Basic AWS Configuration
  awsProfile: default
  deploymentName: my-chat-workbench
  accountNumber: '123456789012'
  region: us-east-1 # or us-gov-west-1 for GovCloud
  deploymentStage: dev

  # Resource Management
  removalPolicy: destroy # 'destroy' for dev/test, 'retain' for production (prevents data loss)

  # VPC Configuration (optional - creates new VPC if not specified)
  vpcConfig:
    # Leave empty to create new VPC, or specify existing VPC resources:
    # - publicSubnets: For ALB and internet-facing resources
    # - privateSubnets: For ECS services with NAT gateway access
    # - isolatedSubnets: For databases (no internet access)

  # WAF Security Configuration (Always Enabled)
  wafConfig:
    managedRules:
      knownBadInputs: true # Recommended: blocks common attacks
      amazonIpReputation: true # Recommended: blocks malicious IPs
      coreRuleSet: false # Optional: can be strict for some apps
    rateLimiting:
      enabled: true
      requestsPerMinute: 2000 # Rate limit per 5-minute rolling window
    logging:
      enabled: false # Disabled by default for cost management

  # Load Balancer Configuration
  loadBalancerConfig:
    idleTimeout: 300
    # Optional SSL Certificate (ACM or IAM)
    sslCertificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/abc123'
    # Note: HTTPS redirect is automatically configured based on deployment type
```

> **📋 Need More Options?** This example shows only the essential configuration. For advanced settings like logging retention, S3 lifecycle policies, auto-scaling parameters, and more, see the **[Configuration Reference Guide](CONFIGURATION-REFERENCE.md)**.

#### SSL Certificate Configuration

**AWS Certificate Manager (ACM) - Recommended:**

```bash
# Request a certificate
aws acm request-certificate \
  --domain-name myapp.example.com \
  --validation-method DNS

# Get certificate ARN
aws acm list-certificates
```

**IAM Certificate (Self-signed or imported):**

```bash
# Upload certificate to IAM
aws iam upload-server-certificate \
  --server-certificate-name my-cert \
  --certificate-body file://cert.pem \
  --private-key file://private-key.pem

# Get certificate ARN
aws iam list-server-certificates
```

#### GovCloud Deployment Considerations

**Automatic Detection**: The system automatically detects GovCloud regions (`us-gov-*`) and adapts:

| Feature         | Commercial AWS    | AWS GovCloud                |
| --------------- | ----------------- | --------------------------- |
| **CloudFront**  | ✅ Enabled        | ❌ Disabled (not available) |
| **WAF Scope**   | `CLOUDFRONT`      | `REGIONAL`                  |
| **ALB Access**  | Behind CloudFront | Direct internet exposure    |
| **SSL Support** | CloudFront + ALB  | ALB only                    |

---

## **Bring Your Own Container (BYOC) Deployment**

For faster deployments and decoupled release cycles, you can deploy pre-built container images from Amazon ECR instead of building containers during CDK deployment.

### BYOC Quick Start

#### 1. Prerequisites

- Amazon ECR repository for your container images
- AWS CLI configured with ECR permissions
- Docker installed for building and pushing images

#### 2. Create ECR Repository

```bash
# Create repository for API container
aws ecr create-repository --repository-name my-app-api --region us-east-1

# Create repository for UI container
aws ecr create-repository --repository-name my-app-ui --region us-east-1
```

#### 3. Build and Push Container Images

**API Container:**

```bash
# Build API container
docker build -t my-app-api -f infrastructure/docker/backend/Dockerfile .

# Get ECR login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Tag and push image
docker tag my-app-api:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-api:v1.0.0
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-api:v1.0.0
```

**UI Container:**

```bash
# Build UI container
docker build -t my-app-ui -f ui/Dockerfile ui/

# Tag and push image
docker tag my-app-ui:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-ui:v1.0.0
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-ui:v1.0.0
```

#### 4. Configure BYOC in config.yaml

```yaml
dev:
  # ... other configuration ...

  # API Container Configuration
  restApiConfig:
    apiVersion: v1
    ecrContainer:
      repositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-api'
      imageTag: 'v1.0.0' # or SHA256 digest for production
    # ... other API settings ...

  # UI Container Configuration
  uiConfig:
    title: 'My Application'
    ecrContainer:
      repositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-ui'
      imageTag: 'v1.0.0' # or SHA256 digest for production
```

#### 5. Deploy with BYOC

```bash
# Deploy using ECR containers
ENV=dev npm run cdk deploy --all
```

### BYOC vs Traditional Deployment

| Aspect               | Traditional Build           | BYOC                       |
| -------------------- | --------------------------- | -------------------------- |
| **Build Time**       | During CDK deployment       | Separate CI/CD pipeline    |
| **Deployment Speed** | Slower (includes build)     | Faster (no build required) |
| **Flexibility**      | Coupled with infrastructure | Decoupled release cycles   |
| **Use Case**         | Development/testing         | Production/CI-CD workflows |

### Production BYOC Best Practices

**Use SHA256 Digests for Production:**

```yaml
prod:
  restApiConfig:
    ecrContainer:
      repositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app-api'
      imageTag: 'sha256:3a20c10fe4f296c229af3554ac5540e63cbd3830fb30849809b46034067136a6'
```

**Security Considerations:**

- Use private ECR repositories
- Enable ECR image scanning for vulnerability detection
- Implement proper IAM permissions for ECR access
- Use immutable image tags in production

**CI/CD Integration:**

```bash
# Example CI/CD pipeline step
# 1. Build and test application
# 2. Build container image
# 3. Push to ECR with unique tag
# 4. Update config.yaml with new image tag
# 5. Deploy infrastructure with new container
```

**GovCloud Example Configuration:**

```yaml
prod:
  region: us-gov-west-1
  # ... other configuration
  loadBalancerConfig:
    sslCertificateArn: 'arn:aws-us-gov:acm:us-gov-west-1:123456789012:certificate/abc123'
    # Note: HTTPS redirect automatically enabled for GovCloud when SSL certificate provided
```

#### Security Features

**Mandatory WAF Protection:**

- Cannot be disabled - always provides security baseline
- Managed rules protect against common attacks
- Rate limiting prevents abuse (configurable 100-20,000 requests per 5-minute period)
- Automatically scoped for deployment environment

**Dynamic Security Groups:**

- **HTTPS Configuration**: Opens port 443 + optional port 80 (redirect)
- **HTTP Configuration**: Opens port 80 only
- **Least Privilege**: Only necessary ports are opened

**Partition-Aware Deployment:**

- All ARNs automatically use correct partition (`aws` vs `aws-us-gov`)
- Cross-partition compatibility built-in
- No manual ARN adjustments required

## Development Patterns

### Hot Reload Development

The `docker-compose.yml` is configured to enable hot reloading for both the frontend (`ui`) and backend (`app`) services by default. When you make changes to the source code in the `ui/` or `backend/app/` directories, the services running inside the containers will automatically restart to apply the changes.

```bash
# Start the development environment
docker compose up -d

# Watch logs in real-time to see services restart
docker compose logs -f app ui
```

### Database Development

```bash
# Access local DynamoDB
docker compose exec app python -c "
import boto3
dynamodb = boto3.resource('dynamodb', endpoint_url='http://dynamodb-local:8000')
print(list(dynamodb.tables.all()))
"

# Check OpenSearch indices
curl http://localhost:9200/_cat/indices?v
```

### API Development

#### Adding New Endpoints

1. **Create route handler**:

   ```python
   # backend/app/api/routes/v1/example/endpoints.py
   from fastapi import APIRouter, Depends
   from app.api.dependencies.auth import get_current_user

   router = APIRouter(prefix='/example', tags=['Example'])

   @router.get('/items')
   async def list_items(user: dict = Depends(get_current_user)):
       return {"items": []}
   ```

2. **Register in main router**:

   ```python
   # backend/app/api/routes/v1/__init__.py
   from .example import router as example_router

   router.include_router(example_router)
   ```

#### Testing API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# List models
curl http://localhost:8000/api/v1/models

# Test with authentication (requires valid JWT token)
curl -H "Authorization: Bearer <jwt-token>" http://localhost:8000/api/v1/chat
```

## Testing

### Frontend Testing

```bash
cd ui

# Run unit tests
npm run test

# Run integration tests
npm run test:integration

# Run E2E tests
npm run test:e2e
```

### Backend Testing

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_chat.py
```

### Integration Testing

```bash
# Run full integration test suite
docker compose -f docker-compose.test.yml up --build --exit-code-from test
```

## Debugging

### Backend Debugging

```bash
# Enable debug logging
export API_LOG_LEVEL=DEBUG

# View detailed logs
docker compose logs -f app

# Access container for debugging
docker compose exec app bash
```

### Frontend Debugging

```bash
# Enable debug mode
export NODE_ENV=development

# Bypass authentication for development (optional)
export NEXT_PUBLIC_BYPASS_AUTH=true

# Enable OIDC debug logging
export NODE_ENV=development
```

### Common Issues

1. **AWS Credentials Not Found**:

   ```bash
   # Check AWS configuration
   aws sts get-caller-identity

   # Verify credentials file
   cat ~/.aws/credentials

   # Test Bedrock access
   aws bedrock list-foundation-models --region us-east-1
   ```

   **For AWS employees using isengardcli:**

   ```bash
   # Make sure you've signed your keys first
   mwinit

   # Then run the setup script
   ./scripts/isengardcli_start_local_app.sh --email your-email@amazon.com

   # If you get credential errors, check your access
   isengardcli credentials --awscli your-email@amazon.com --role admin --region us-east-1
   ```

2. **Services Not Starting**:

   ```bash
   # Check Docker status
   docker compose ps

   # View specific service logs
   docker compose logs app

   # Restart specific service
   docker compose restart app
   ```

3. **Authentication Issues**:

   ```bash
   # Check Keycloak service status
   docker compose logs keycloak

   # Verify Keycloak configuration
   curl http://localhost:8080/realms/chat-workbench/.well-known/openid-configuration

   # Test user login (requires running Keycloak)
   # Navigate to: http://localhost:8080/admin
   ```

4. **Database Connection Issues**:

   ```bash
   # Test DynamoDB connection
   aws dynamodb list-tables --endpoint-url http://localhost:8001

   # Test OpenSearch connection
   curl http://localhost:9200/_cluster/health
   ```

## Database Management

The local development environment uses Docker to run local instances of DynamoDB and OpenSearch. Database tables need to be created manually after starting the services.

### Manual Table Setup

After starting the services with `docker compose up -d`, you need to manually run the table setup script to create the DynamoDB table.

**Basic setup:**

```bash
python scripts/setup_ddb.py
```

The script performs the following actions:

1. **Connects to local DynamoDB**: Uses hardcoded endpoint `http://localhost:8001`
2. **Checks for Table**: Checks if the table already exists
3. **Creates Table**: If the table doesn't exist, creates it with the required `PK` (Partition Key) and `SK` (Sort Key) schema
4. **Safe to re-run**: Won't error if table already exists

### Resetting the Database

If you need to clear all data and start with a fresh table, use the `RESET_TABLE` environment variable:

```bash
RESET_TABLE=true python scripts/setup_ddb.py
```

When this variable is set, the script will:

1. Delete the existing DynamoDB table
2. Create a new empty table

**Note**: This completely wipes all data, so use with caution.

### OpenSearch Document Indexing (for Document Chat Handler)

To enable the Document Chat handler with RAG capabilities, you need to populate OpenSearch with document embeddings:

```bash
python examples/rag_oss/scripts/02_hydrate_oss.py --host localhost --port 9200 --index documents
```

This will:

- Connect to your local OpenSearch instance at `localhost:9200`
- Use the pre-existing embeddings from `examples/rag_oss/data/embeddings.jsonl`
- Create a `documents` index with vector search configuration
- Enable semantic search for the Document Chat handler

**Optional**: If you need to process new documents or regenerate embeddings, first run:

```bash
python examples/rag_oss/scripts/01_prepare_data.py
```

### Manual Database Access

The local DynamoDB instance is accessible at `http://localhost:8001` from your host machine.

#### DynamoDB Local

```bash
# List tables
aws dynamodb list-tables --endpoint-url http://localhost:8001

# Query all data from your table
aws dynamodb scan --table-name $(grep DYNAMODB_TABLE_NAME .env | cut -d'=' -f2) --endpoint-url http://localhost:8001

# Query specific item
aws dynamodb get-item \
  --table-name $(grep DYNAMODB_TABLE_NAME .env | cut -d'=' -f2) \
  --key '{"PK": {"S": "your-partition-key"}, "SK": {"S": "your-sort-key"}}' \
  --endpoint-url http://localhost:8001
```

#### OpenSearch

```bash
# Check cluster health
curl http://localhost:9200/_cluster/health

# List indices
curl http://localhost:9200/_cat/indices?v

# Create index
curl -X PUT http://localhost:9200/documents

# Search documents
curl -X GET http://localhost:9200/documents/_search
```

### Troubleshooting Database Issues

1. **Table Creation Fails**:

   ```bash
   # Check if DynamoDB is running
   docker compose ps dynamodb

   # Check setup service logs
   docker compose logs ddb-setup

   # Manual table creation (if needed)
   docker compose run --rm ddb-setup
   ```

2. **Connection Issues**:

   ```bash
   # Test DynamoDB connection from host
   aws dynamodb list-tables --endpoint-url http://localhost:8001

   # Test connection from within container
   docker compose exec app python -c "
   import boto3
   import os
   ddb = boto3.resource('dynamodb', endpoint_url=os.environ['DYNAMODB_ENDPOINT_URL'])
   print(list(ddb.tables.all()))
   "
   ```

3. **Permission Errors**:

   ```bash
   # Check AWS credentials (not needed for local DynamoDB)
   aws sts get-caller-identity

   # For local development, ensure Docker has proper permissions
   docker compose logs app | grep -i permission
   ```

## Environment Management

### Development Environment

```bash
# Start development stack
docker compose up -d

# Hot reload for backend
HOT_RELOAD=true docker compose up -d app

# Development with specific services
docker compose up -d app ui dynamodb-local
```

### Testing Environment

```bash
# Run tests in isolated environment
docker compose -f docker-compose.test.yml up --build

# Run specific test suites
docker compose -f docker-compose.test.yml run --rm test pytest tests/unit/
```

### Production-like Environment

```bash
# Build production images
docker compose --profile prod build

# Start production configuration
docker compose --profile prod up -d
```

## Next Steps

Now that you have Chat Workbench running locally, here are some next steps:

1. **Explore the Architecture**: Read the [Architecture Guide](ARCHITECTURE.md) to understand the system design
2. **Build Your First Feature**: Follow the [Backend Development Guide](../backend/README.md) to create a custom task handler
3. **Customize the Frontend**: Check the [Frontend Development Guide](../ui/README.md) for UI customization
4. **Deploy to AWS**: Use the [Infrastructure Guide](../infrastructure/cdk/README.md) for production deployment

## Getting Help

- **Documentation**: Check the relevant guides in the [docs/](README.md) directory
- **Troubleshooting**: Review the troubleshooting sections in each component guide
- **Issues**: Report problems via GitHub Issues with steps to reproduce
- **Discussions**: Join conversations about development and best practices

## Documentation Standards

When contributing to documentation:

1. **Clear Structure**: Use consistent heading levels and organization
2. **Code Examples**: Provide working code snippets with context
3. **Step-by-Step**: Break complex processes into numbered steps
4. **Cross-References**: Link to related documentation
5. **Keep Updated**: Ensure examples work with current versions
