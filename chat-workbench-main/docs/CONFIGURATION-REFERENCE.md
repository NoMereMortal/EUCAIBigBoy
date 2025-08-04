# Configuration Reference Guide

This document provides a comprehensive reference for all configuration options available in the `config.yaml` file used for deploying Chat Workbench.

## Configuration Structure

The configuration is organized by environment (e.g., `dev`, `staging`, `prod`). All settings are nested under the environment key:

```yaml
env: dev # Default environment to use

dev:
  # AWS Settings
  awsProfile: default
  deploymentName: demo
  # ... other settings
```

---

## **Global Settings**

| Key               | Type            | Required | Description                                                 | Default                                     |
| ----------------- | --------------- | -------- | ----------------------------------------------------------- | ------------------------------------------- |
| `env`             | `string`        | Yes      | The default environment to use when deploying               | -                                           |
| `awsProfile`      | `string`        | No       | The AWS CLI profile to use for deployment                   | Not specified (uses default profile)        |
| `deploymentName`  | `string`        | Yes      | A unique name for your deployment stack                     | -                                           |
| `accountNumber`   | `string/number` | Yes      | Your AWS account number (12 digits)                         | -                                           |
| `region`          | `string`        | Yes      | The AWS region for deployment                               | -                                           |
| `deploymentStage` | `string`        | Yes      | The deployment stage (dev, staging, prod)                   | -                                           |
| `appName`         | `string`        | No       | Name of the application                                     | `cwb`                                       |
| `removalPolicy`   | `string`        | No       | Resource behavior on stack deletion (`destroy` or `retain`) | `destroy`                                   |
| `runCdkNag`       | `boolean`       | No       | Whether to run CDK Nag security checks                      | `false`                                     |
| `logLevel`        | `string`        | Yes      | Application log level                                       | One of: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `targetPlatform`  | `string`        | Yes      | Docker build target platform                                | e.g., `linux/amd64`                         |

**Note on `deploymentStage`**: This value is also passed to the backend container as the `ENVIRONMENT` variable, which controls features like enabling/disabling API documentation. For example, setting `deploymentStage: prod` will disable the Swagger/Redoc UI.

---

## **Logging Configuration (`loggingConfig`)**

Configure retention policies for CloudWatch Logs across the application to manage costs and compliance.

| Key                   | Type     | Required | Description                                       | Default |
| --------------------- | -------- | -------- | ------------------------------------------------- | ------- |
| `logRetentionDays`    | `number` | No       | Retention period for application and service logs | `30`    |
| `wafLogRetentionDays` | `number` | No       | Retention period for AWS WAF logs (if enabled)    | `30`    |

**Valid Retention Values:** `1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653`

**Example:**

```yaml
loggingConfig:
  logRetentionDays: 90 # Keep application logs for 3 months
  wafLogRetentionDays: 365 # Keep WAF logs for 1 year
```

---

## **S3 Bucket Configuration (`s3Config`)**

Manage S3 bucket lifecycle policies for cost optimization by automatically transitioning logs to cheaper storage classes and eventually deleting them.

### Access Logs Lifecycle (`accessLogsLifecycle`)

Controls the lifecycle of Application Load Balancer access logs.

| Key                       | Type     | Required | Description                                                 | Default |
| ------------------------- | -------- | -------- | ----------------------------------------------------------- | ------- |
| `transitionToIADays`      | `number` | No       | Days until logs transition to S3 Standard-Infrequent Access | `30`    |
| `transitionToGlacierDays` | `number` | No       | Days until logs transition to S3 Glacier Flexible Retrieval | `90`    |
| `deletionDays`            | `number` | No       | Days until logs are permanently deleted                     | `365`   |

### CloudFront Logs Lifecycle (`cloudFrontLogsLifecycle`)

Controls the lifecycle of CloudFront distribution access logs (only applies in commercial AWS regions).

| Key                       | Type     | Required | Description                                                 | Default |
| ------------------------- | -------- | -------- | ----------------------------------------------------------- | ------- |
| `transitionToIADays`      | `number` | No       | Days until logs transition to S3 Standard-Infrequent Access | `30`    |
| `transitionToGlacierDays` | `number` | No       | Days until logs transition to S3 Glacier Flexible Retrieval | `90`    |
| `deletionDays`            | `number` | No       | Days until logs are permanently deleted                     | `365`   |

**Example:**

```yaml
s3Config:
  accessLogsLifecycle:
    transitionToIADays: 30 # Move to IA after 1 month
    transitionToGlacierDays: 90 # Move to Glacier after 3 months
    deletionDays: 365 # Delete after 1 year
  cloudFrontLogsLifecycle:
    transitionToIADays: 7 # Move to IA after 1 week (CloudFront can be verbose)
    transitionToGlacierDays: 30 # Move to Glacier after 1 month
    deletionDays: 180 # Delete after 6 months
```

---

## **VPC Configuration (`vpcConfig`)**

Configure Virtual Private Cloud settings. Leave empty to create a new VPC, or specify existing VPC details.

| Key                                | Type       | Required | Description                    | Default                         |
| ---------------------------------- | ---------- | -------- | ------------------------------ | ------------------------------- |
| `vpcId`                            | `string`   | No       | ID of existing VPC to use      | Not specified (creates new VPC) |
| `publicSubnetIds`                  | `string[]` | No       | List of public subnet IDs      | `[]`                            |
| `privateSubnetIds`                 | `string[]` | No       | List of private subnet IDs     | `[]`                            |
| `isolatedSubnetIds`                | `string[]` | No       | List of isolated subnet IDs    | `[]`                            |
| `vpcEndpoints.endpointSubnetTypes` | `string[]` | No       | Subnet types for VPC endpoints | `['private', 'isolated']`       |

**Note:** When `vpcId` is omitted or left empty, a new VPC will be created automatically. Subnet arrays can be omitted and will default to empty arrays.

**VPC Endpoint Subnet Types:** Valid values are `'private'` (for ECS services with NAT gateway access) and `'isolated'` (for databases with no internet access). The default `['private', 'isolated']` serves the full application stack.

**Example:**

```yaml
vpcConfig:
  vpcId: vpc-12345678
  publicSubnetIds:
    - subnet-12345678
    - subnet-87654321
  privateSubnetIds:
    - subnet-abcdefgh
    - subnet-hgfedcba
```

---

## **Cognito Authentication (`cognitoAuthConfig`)**

Configure AWS Cognito for user authentication. Either specify an existing User Pool or create a new one.

| Key                  | Type     | Required    | Description                                              | Default |
| -------------------- | -------- | ----------- | -------------------------------------------------------- | ------- |
| `userPoolName`       | `string` | Conditional | Name for new User Pool (conflicts with `userPoolId`)     | -       |
| `userPoolId`         | `string` | Conditional | ID of existing User Pool (conflicts with `userPoolName`) | -       |
| `userPoolClientId`   | `string` | No          | ID of existing User Pool Client                          | -       |
| `userPoolDomainName` | `string` | Yes         | Domain prefix for Cognito hosted UI                      | -       |

**Note:** You must provide either `userPoolName` OR `userPoolId`, but not both.

**Example:**

```yaml
cognitoAuthConfig:
  userPoolName: cwb-users # Creates new User Pool
  userPoolDomainName: cwb-dev # Domain: cwb-dev.auth.region.amazoncognito.com
```

---

## **Load Balancer Configuration (`loadBalancerConfig`)**

Configure the Application Load Balancer settings.

| Key                 | Type     | Required | Description                                 | Default |
| ------------------- | -------- | -------- | ------------------------------------------- | ------- |
| `idleTimeout`       | `number` | No       | Connection idle timeout in seconds (30-300) | `300`   |
| `sslCertificateArn` | `string` | No       | ARN of SSL certificate for HTTPS            | -       |

> **🔄 Automatic HTTPS Redirect**: HTTP to HTTPS redirect is automatically configured based on deployment type - enabled for direct ALB access (GovCloud) when SSL certificate is provided, disabled for CloudFront deployments to prevent redirect loops.

**Example:**

```yaml
loadBalancerConfig:
  idleTimeout: 300
  sslCertificateArn: 'arn:aws:acm:us-west-2:123456789012:certificate/demo-cert'
```

---

## **WAF Security Configuration (`wafConfig`)**

Configure AWS Web Application Firewall for security protection. WAF is always enabled.

> **📍 Regional Deployment**: For CloudFront in commercial AWS, WAF resources are automatically deployed to `us-east-1` regardless of your target region. GovCloud deployments use regional WAF in the same region as your application.

### Managed Rules (`managedRules`)

| Key                  | Type      | Required | Description                                | Default |
| -------------------- | --------- | -------- | ------------------------------------------ | ------- |
| `coreRuleSet`        | `boolean` | No       | Enable AWS Common Rule Set (can be strict) | `false` |
| `knownBadInputs`     | `boolean` | No       | Enable Known Bad Inputs protection         | `true`  |
| `amazonIpReputation` | `boolean` | No       | Block requests from known malicious IPs    | `true`  |

### Rate Limiting (`rateLimiting`)

| Key                 | Type      | Required | Description                           | Default |
| ------------------- | --------- | -------- | ------------------------------------- | ------- |
| `enabled`           | `boolean` | No       | Enable rate limiting                  | `true`  |
| `requestsPerMinute` | `number`  | No       | Requests per minute limit (100-20000) | `2000`  |

### Logging (`logging`)

| Key       | Type      | Required | Description                      | Default |
| --------- | --------- | -------- | -------------------------------- | ------- |
| `enabled` | `boolean` | No       | Enable WAF logging (costs apply) | `false` |

**Example:**

```yaml
wafConfig:
  managedRules:
    coreRuleSet: false # Disabled to avoid blocking legitimate traffic
    knownBadInputs: true # Essential protection
    amazonIpReputation: true # Block known bad actors
  rateLimiting:
    enabled: true
    requestsPerMinute: 1000 # Lower limit for production
  logging:
    enabled: true # Enable for security monitoring
```

---

## **REST API Configuration (`restApiConfig`)**

Configure the backend API service settings.

| `apiVersion` | `string` | No | API version string passed to the container. Controls the `/api/{version}` path. | `v1` |
| `ecrContainer` | `object` | No | Configuration for using a pre-built ECR container image. | - |

### Bring Your Own Container (BYOC) Configuration (`ecrContainer`)

**Optional**: Instead of building the API container from source, you can specify a pre-built container image stored in Amazon ECR. This enables faster deployments and decouples your infrastructure deployment from your application build process.

| Key             | Type     | Required | Description                                                                                                                               | Default  |
| --------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `repositoryUri` | `string` | Yes      | Full ECR repository URI (e.g., `123456789012.dkr.ecr.us-east-1.amazonaws.com/my-api`)                                                     | -        |
| `imageTag`      | `string` | No       | Container image tag or SHA256 digest. For production, use SHA256 digests for immutable deployments (e.g., `sha256:abc123...` or `v1.2.3`) | `latest` |

**Security Note**: For production deployments, always use SHA256 digests instead of mutable tags like `latest` or `v1.2.3`. This ensures immutable, reproducible deployments.

**Mutual Exclusion**: You cannot use both traditional Docker builds and ECR containers simultaneously. Choose one approach per deployment.

**Example:**

```yaml
restApiConfig:
  apiVersion: v1
  ecrContainer:
    repositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/my-api'
    imageTag: 'sha256:3a20c10fe4f296c229af3554ac5540e63cbd3830fb30849809b46034067136a6'
```

### Container Configuration (`containerConfig`)

| Key           | Type     | Required | Description                         | Default |
| ------------- | -------- | -------- | ----------------------------------- | ------- |
| `cpuLimit`    | `number` | No       | CPU units for container (256-16384) | `1024`  |
| `memoryLimit` | `number` | No       | Memory limit in MB (512-32768)      | `2048`  |

### Health Check Configuration (`healthCheckConfig`)

| Key                       | Type     | Required | Description                               | Default |
| ------------------------- | -------- | -------- | ----------------------------------------- | ------- |
| `path`                    | `string` | Yes      | Health check endpoint path                | -       |
| `interval`                | `number` | No       | Health check interval in seconds          | `60`    |
| `timeout`                 | `number` | No       | Health check timeout in seconds           | `30`    |
| `healthyThresholdCount`   | `number` | No       | Consecutive successful checks for healthy | `2`     |
| `unhealthyThresholdCount` | `number` | No       | Consecutive failed checks for unhealthy   | `10`    |

### Auto Scaling Configuration (`autoScalingConfig`)

| Key                     | Type     | Required | Description                  | Default |
| ----------------------- | -------- | -------- | ---------------------------- | ------- |
| `minCapacity`           | `number` | No       | Minimum number of containers | `1`     |
| `maxCapacity`           | `number` | No       | Maximum number of containers | `5`     |
| `defaultInstanceWarmup` | `number` | No       | Warm-up time in seconds      | `120`   |
| `cooldown`              | `number` | No       | Cooldown period in seconds   | `300`   |

**Example:**

```yaml
restApiConfig:
  containerConfig:
    cpuLimit: 2048
    memoryLimit: 4096
  healthCheckConfig:
    path: /health
    interval: 30
    timeout: 10
  autoScalingConfig:
    minCapacity: 2
    maxCapacity: 10
```

---

## **Data Configuration (`dataConfig`)**

Configure data storage and processing services.

### ElastiCache Configuration

| Key                         | Type     | Required | Description                  | Default |
| --------------------------- | -------- | -------- | ---------------------------- | ------- |
| `elastiCacheStorageLimitGb` | `number` | No       | Storage limit in GB (1-1000) | `50`    |
| `elastiCacheEcpuLimit`      | `number` | No       | ECPU limit (1000-100000)     | `10000` |

### File Storage

| Key                  | Type      | Required | Description                    | Default |
| -------------------- | --------- | -------- | ------------------------------ | ------- |
| `fileStorageEnabled` | `boolean` | No       | Enable file storage            | `true`  |
| `fileStorageType`    | `string`  | No       | Storage type (`s3` or `local`) | `s3`    |

### OpenSearch Configuration

| Key                         | Type      | Required | Description                  | Default     |
| --------------------------- | --------- | -------- | ---------------------------- | ----------- |
| `openSearchEnabled`         | `boolean` | No       | Enable OpenSearch Serverless | `false`     |
| `openSearchDefaultIndex`    | `string`  | No       | Default index name           | `documents` |
| `openSearchStandbyReplicas` | `boolean` | No       | Enable standby replicas      | `false`     |

### Bedrock Knowledge Base

| Key                           | Type       | Required | Description                   | Default                      |
| ----------------------------- | ---------- | -------- | ----------------------------- | ---------------------------- |
| `bedrockKnowledgeBaseEnabled` | `boolean`  | No       | Enable Bedrock Knowledge Base | `false`                      |
| `embeddingModelId`            | `string`   | No       | Embedding model ID            | `amazon.titan-embed-text-v1` |
| `knowledgeBaseName`           | `string`   | No       | Knowledge base name           | -                            |
| `vectorIndexName`             | `string`   | No       | Vector index name             | `documents`                  |
| `s3InclusionPrefixes`         | `string[]` | No       | S3 prefixes to include        | -                            |

---

## **UI Configuration (`uiConfig`)**

Configure the frontend user interface.

| Key     | Type     | Required | Description                       | Default                        |
| ------- | -------- | -------- | --------------------------------- | ------------------------------ |
| `title` | `string` | No       | Application title displayed in UI | Not specified (no title shown) |

### Bring Your Own Container (BYOC) Configuration (`ecrContainer`)

**Optional**: Instead of building the UI container from source, you can specify a pre-built container image stored in Amazon ECR. This enables faster deployments and decouples your infrastructure deployment from your application build process.

| Key             | Type     | Required | Description                                                                                                                               | Default  |
| --------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `repositoryUri` | `string` | Yes      | Full ECR repository URI (e.g., `123456789012.dkr.ecr.us-east-1.amazonaws.com/my-ui`)                                                      | -        |
| `imageTag`      | `string` | No       | Container image tag or SHA256 digest. For production, use SHA256 digests for immutable deployments (e.g., `sha256:abc123...` or `v1.2.3`) | `latest` |

**Security Note**: For production deployments, always use SHA256 digests instead of mutable tags like `latest` or `v1.2.3`. This ensures immutable, reproducible deployments.

**Mutual Exclusion**: You cannot use both traditional Docker builds and ECR containers simultaneously. Choose one approach per deployment.

**Example:**

```yaml
uiConfig:
  title: 'My Application'
  ecrContainer:
    repositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/my-ui'
    imageTag: 'sha256:1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890'
```

---

## **CloudWatch Alarms (`alarmConfig`)**

Configure monitoring and alerting.

| Key                     | Type       | Required    | Description                                             | Default |
| ----------------------- | ---------- | ----------- | ------------------------------------------------------- | ------- |
| `enable`                | `boolean`  | No          | Enable CloudWatch alarms                                | `false` |
| `period`                | `number`   | No          | Data collection period in minutes                       | `1`     |
| `threshold`             | `number`   | No          | Alarm threshold value                                   | `1`     |
| `evaluationPeriods`     | `number`   | No          | Number of periods to evaluate                           | `1`     |
| `loggingFilterPatterns` | `string[]` | Yes         | Log patterns to monitor                                 | -       |
| `emailAddresses`        | `string[]` | Conditional | Email addresses for notifications (required if enabled) | -       |

**Valid Filter Patterns:** `WARNING`, `ERROR`, `CRITICAL`

---

## **Resource Tags (`tags`)**

Apply tags to all AWS resources for organization and cost tracking.

| Key     | Type     | Required | Description  |
| ------- | -------- | -------- | ------------ |
| `Key`   | `string` | Yes      | Tag key name |
| `Value` | `string` | Yes      | Tag value    |

**Example:**

```yaml
tags:
  - Key: Project
    Value: ChatWorkbench
  - Key: Environment
    Value: Development
  - Key: Owner
    Value: DevOps Team
```

---

## **Environment-Specific Examples**

### Development Environment

```yaml
dev:
  deploymentStage: dev
  removalPolicy: destroy # Resources deleted on stack deletion
  loggingConfig:
    logRetentionDays: 7 # Short retention for cost savings
    wafLogRetentionDays: 14
  s3Config:
    accessLogsLifecycle:
      deletionDays: 90 # Quick cleanup for dev
  wafConfig:
    managedRules:
      coreRuleSet: false # Less strict for testing
    rateLimiting:
      requestsPerMinute: 5000 # Higher limit for testing
```

### Production Environment

```yaml
prod:
  deploymentStage: prod
  removalPolicy: retain # Preserve resources on deletion
  loggingConfig:
    logRetentionDays: 365 # Long retention for compliance
    wafLogRetentionDays: 1827 # 5 years for security analysis
  s3Config:
    accessLogsLifecycle:
      deletionDays: 2555 # 7 years for compliance
  wafConfig:
    managedRules:
      coreRuleSet: true # Enable all protections
    rateLimiting:
      requestsPerMinute: 1000 # Stricter limits
    logging:
      enabled: true # Enable for security monitoring
  alarmConfig:
    enable: true
    emailAddresses:
      - ops-team@company.com
```

---

## **Validation and Error Handling**

The configuration uses strict validation to prevent deployment issues:

- **Required fields** will cause deployment to fail if missing
- **Invalid values** (e.g., retention days not supported by CloudWatch) will be caught early with clear error messages
- **Type mismatches** are automatically detected and reported
- **Conflicting settings** (e.g., both `userPoolId` and `userPoolName`) are prevented

Common validation errors and solutions:

- `logRetentionDays must be one of: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653`
- `AWS account number should be 12 digits`
- `Email addresses must be provided when alarms are enabled`
- `Invalid ECR repository URI format` - Repository URI must follow the format: `123456789012.dkr.ecr.region.amazonaws.com/repository-name`

---

## **BYOC Troubleshooting**

### Common ECR Container Issues

**ECR Authentication Failures (403 Forbidden)**

- **Problem**: ECS cannot pull the container image due to authentication issues
- **Solution**: Verify the ECS task execution role has the correct ECR permissions:
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage"
    ],
    "Resource": "*"
  }
  ```

**Repository Not Found**

- **Problem**: ECR repository URI is incorrect or repository doesn't exist
- **Solution**: Verify the repository URI format and ensure the repository exists in the specified region
- **Check**: Use AWS CLI to verify: `aws ecr describe-repositories --repository-names your-repo-name --region your-region`

**Image Not Found**

- **Problem**: Specified image tag or digest doesn't exist in the repository
- **Solution**: Verify the image exists: `aws ecr describe-images --repository-name your-repo-name --image-ids imageTag=your-tag --region your-region`

**Cross-Region ECR Access**

- **Problem**: ECR repository is in a different region than your deployment
- **Solution**: Ensure the repository URI includes the correct region and that the repository exists in that region

**Container Startup Failures**

- **Problem**: Container starts but fails health checks
- **Solution**:
  - Check CloudWatch logs for container startup errors
  - Verify the container image is built for the correct platform (`linux/amd64` or `linux/arm64`)
  - Ensure the container exposes the correct port (8000 for API, 3000 for UI)

### Security Best Practices

**Image Validation**

- Always use SHA256 digests for production deployments
- Enable ECR image scanning for vulnerability detection
- Use private ECR repositories to prevent unauthorized access

**IAM Permissions**

- Follow the principle of least privilege
- Scope ECR permissions to specific repositories when possible
- Regularly audit ECR access permissions

**Container Security**

- Keep base images updated with security patches
- Scan images for vulnerabilities before deployment
- Use minimal base images to reduce attack surface
