# Chat Workbench Infrastructure

AWS CDK infrastructure for Chat Workbench with TypeScript. This guide covers local development, deployment strategies, and infrastructure extension patterns.

## Tech Stack

- **Framework**: AWS CDK v2 with TypeScript
- **Language**: TypeScript
- **Infrastructure**: Multi-stack architecture with AWS services
- **Deployment**: ECS Fargate, DynamoDB, OpenSearch, S3, CloudFront
- **Authentication**: AWS Cognito User Pools
- **Monitoring**: CloudWatch, Prometheus metrics

## Configuration

All deployments are driven by YAML configuration files that define AWS resources, security settings, logging policies, and more.

> **📖 Complete Configuration Reference**: See the **[Configuration Reference Guide](../../docs/CONFIGURATION-REFERENCE.md)** for comprehensive documentation of all available options including logging retention, S3 lifecycle policies, security settings, and environment-specific configurations.

**Key configuration features:**

- **Zod-based validation** with clear error messages for invalid configurations
- **Environment-specific settings** (dev, staging, prod)
- **Cost optimization** through configurable logging retention and S3 lifecycle policies
- **Security controls** via WAF rules, rate limiting, and SSL/TLS configuration
- **Cross-region WAF deployment** for CloudFront (automatically deployed to us-east-1)
- **Auto-scaling parameters** for ECS services and load balancers

## Architecture Overview

```
infrastructure/cdk/
├── lib/
│   ├── api-stack.ts              # Backend API service
│   ├── ui-stack.ts               # Frontend UI service
│   ├── data-stack.ts             # Databases and storage
│   ├── compute-stack.ts          # ECS cluster and services
│   ├── distribution-stack.ts     # CloudFront and load balancer
│   ├── waf-regional-stack.ts     # WAF for CloudFront (deployed to us-east-1)
│   ├── infrastructure-stack.ts   # Shared infrastructure
│   ├── chat-workbench-stage.ts   # Environment staging
│   ├── schema.ts                 # Configuration validation with Zod
│   └── utils.ts                  # Utility functions (CloudWatch retention mapping, etc.)
├── bin/
│   └── chat-workbench.ts         # CDK app entry point
├── config/
│   ├── dev.yaml                  # Development configuration
│   ├── staging.yaml              # Staging configuration
│   └── production.yaml           # Production configuration
└── cdk.json                      # CDK configuration
```

**Key Concept**: Multi-stack architecture allows independent deployment and scaling of different components while maintaining clear separation of concerns.

## Quick Start

### Prerequisites

- Node.js 18+
- AWS CLI configured with appropriate permissions
- Docker (for local testing)

### Development Setup

```bash
# 1. Install dependencies
cd infrastructure/cdk
npm install

# 2. Build CDK application
npm run build

# 3. Synthesize CloudFormation templates
npm run cdk synth

# 4. Deploy to development environment
ENV=dev npm run cdk deploy --all
```

**Verification:**

- Check AWS Console for deployed resources
- Verify CloudFormation stacks are created successfully
- Test API endpoints and UI accessibility

## Development Commands

```bash
# Build and Validation
npm run build           # Compile TypeScript
npm run watch           # Watch for changes and compile
npm run test            # Run unit tests
npm run cdk synth       # Generate CloudFormation templates

# Deployment
ENV=dev npm run cdk deploy --all        # Deploy all stacks
ENV=prod npm run cdk deploy ApiStack    # Deploy specific stack
npm run cdk diff                        # Show differences
npm run cdk destroy                     # Destroy stacks

# Debugging
npm run cdk ls          # List all stacks
npm run cdk doctor      # Check CDK environment
```

## Configuration Management

### Environment Configuration

Each environment has its own configuration file:

```yaml
# config/dev.yaml
appName: chat-workbench-dev
environment: dev
region: us-east-1

# Compute configuration
compute:
  apiCpu: 512
  apiMemory: 1024
  uiCpu: 256
  uiMemory: 512

# Database configuration
database:
  dynamodbBillingMode: PAY_PER_REQUEST
  opensearchInstanceType: t3.small.search

# Authentication
auth:
  cognitoUserPoolName: chat-workbench-dev-users
  cognitoClientName: chat-workbench-dev-client

# Networking
network:
  createVpc: true
  maxAzs: 2
```

### Using Configuration

```typescript
// lib/chat-workbench-stage.ts
import { Config } from './schema';
import * as yaml from 'js-yaml';
import * as fs from 'fs';

export class ChatWorkbenchStage extends Stage {
  constructor(scope: Construct, id: string, props: StageProps) {
    super(scope, id, props);

    // Load environment-specific configuration
    const configFile = `config/${process.env.ENV || 'dev'}.yaml`;
    const config = yaml.load(fs.readFileSync(configFile, 'utf8')) as Config;

    // Create stacks with configuration
    const dataStack = new DataStack(this, 'DataStack', { config });
    const apiStack = new ApiStack(this, 'ApiStack', {
      config,
      dataResources: dataStack.resources,
    });
  }
}
```

## Stack Architecture

### Data Stack

Manages databases and storage resources:

```typescript
// lib/data-stack.ts
export class DataStack extends Stack {
  public readonly resources: DataResources;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    // DynamoDB table for application data
    const dynamoTable = new Table(this, 'AppDataTable', {
      tableName: `${props.config.appName}-data`,
      partitionKey: { name: 'PK', type: AttributeType.STRING },
      sortKey: { name: 'SK', type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      encryption: TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
    });

    // OpenSearch domain for vector search
    const opensearchDomain = new Domain(this, 'SearchDomain', {
      version: EngineVersion.OPENSEARCH_2_11,
      capacity: {
        dataNodeInstanceType: props.config.database.opensearchInstanceType,
        dataNodes: 1,
      },
      ebs: {
        volumeSize: 20,
        volumeType: EbsDeviceVolumeType.GP3,
      },
      encrypt: {
        atRest: { enabled: true },
      },
    });

    this.resources = {
      dynamoTable,
      opensearchDomain,
    };
  }
}
```

### API Stack

Manages backend services:

```typescript
// lib/api-stack.ts
export class ApiStack extends Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    // ECS task definition for API service
    const taskDefinition = new FargateTaskDefinition(this, 'ApiTaskDef', {
      cpu: props.config.compute.apiCpu,
      memoryLimitMiB: props.config.compute.apiMemory,
    });

    // Container with backend application
    const container = taskDefinition.addContainer('ApiContainer', {
      image: ContainerImage.fromAsset('../../', {
        file: 'infrastructure/docker/backend/Dockerfile',
      }),
      environment: {
        DYNAMODB_TABLE_NAME: props.dataResources.dynamoTable.tableName,
        OPENSEARCH_DOMAIN: props.dataResources.opensearchDomain.domainEndpoint,
        API_VERSION: props.config.restApiConfig.apiVersion,
        ENVIRONMENT: props.config.deploymentStage,
      },
      logging: LogDrivers.awsLogs({
        streamPrefix: 'api',
        logGroup: new LogGroup(this, 'ApiLogGroup', {
          retention: RetentionDays.ONE_WEEK,
        }),
      }),
    });

    // ECS service with auto-scaling
    const service = new FargateService(this, 'ApiService', {
      cluster: props.cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
    });

    // Auto-scaling configuration
    const scaling = service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 10,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
    });
  }
}
```

### UI Stack

Manages frontend services:

```typescript
// lib/ui-stack.ts
export class UiStack extends Stack {
  constructor(scope: Construct, id: string, props: UiStackProps) {
    super(scope, id, props);

    // ECS task definition for UI service
    const taskDefinition = new FargateTaskDefinition(this, 'UiTaskDef', {
      cpu: props.config.compute.uiCpu,
      memoryLimitMiB: props.config.compute.uiMemory,
    });

    // Container with frontend application
    const container = taskDefinition.addContainer('UiContainer', {
      image: ContainerImage.fromAsset('../../', {
        file: 'infrastructure/docker/ui/Dockerfile',
      }),
      environment: {
        NEXT_PUBLIC_API_URI: `https://${props.apiDomain}`,
        NEXT_PUBLIC_COGNITO_USER_POOL_ID: props.cognitoUserPool.userPoolId,
        NEXT_PUBLIC_COGNITO_CLIENT_ID: props.cognitoClient.userPoolClientId,
      },
      portMappings: [{ containerPort: 3000 }],
    });

    // ECS service
    const service = new FargateService(this, 'UiService', {
      cluster: props.cluster,
      taskDefinition,
      desiredCount: 1,
    });
  }
}
```

## Cross-Region WAF Architecture

**Important**: For CloudFront deployments in commercial AWS, the WAF WebACL must be deployed to `us-east-1` regardless of your application's target region. This is an AWS service requirement.

The CDK automatically handles this through:

- **WafRegionalStack**: Dedicated stack deployed to `us-east-1`
- **Cross-region references**: CDK manages CloudFormation exports/imports between regions
- **Automatic region detection**: GovCloud deployments use regional WAF instead

> **📖 Architecture Details**: See the **[Architecture Guide](../../docs/ARCHITECTURE.md)** for complete diagrams and explanations of the cross-region deployment pattern.

## Deployment Strategies

### Environment-Specific Deployment

```bash
# Deploy to development
ENV=dev npm run cdk deploy --all

# Deploy to staging
ENV=staging npm run cdk deploy --all

# Deploy to production
ENV=production npm run cdk deploy --all
```

### Selective Stack Deployment

```bash
# Deploy only data layer changes
ENV=prod npm run cdk deploy DataStack

# Deploy API changes without affecting UI
ENV=prod npm run cdk deploy ApiStack

# Deploy infrastructure updates
ENV=prod npm run cdk deploy InfrastructureStack
```

### Blue-Green Deployment

```typescript
// For production deployments with zero downtime
const blueGreenDeployment = new BlueGreenDeploymentConfiguration(
  this,
  'BlueGreen',
  {
    terminationWaitTimeInMinutes: 5,
    deploymentReadyWaitTimeInMinutes: 0,
    blueGreenDeploymentConfig: {
      terminateBlueInstancesOnDeploymentSuccess: {
        action: 'TERMINATE',
        terminationWaitTimeInMinutes: 5,
      },
      deploymentReadyOption: {
        actionOnTimeout: 'CONTINUE_DEPLOYMENT',
      },
    },
  },
);
```

## Monitoring and Observability

### CloudWatch Integration

```typescript
// API metrics and alarms
const apiErrorRate = new Metric({
  namespace: 'ChatWorkbench/API',
  metricName: 'ErrorRate',
  statistic: 'Average',
});

new Alarm(this, 'HighErrorRate', {
  metric: apiErrorRate,
  threshold: 5,
  evaluationPeriods: 2,
  treatMissingData: TreatMissingData.NOT_BREACHING,
});

// Custom dashboard
new Dashboard(this, 'AppDashboard', {
  dashboardName: `${props.config.appName}-monitoring`,
  widgets: [
    [
      new GraphWidget({
        title: 'API Response Times',
        left: [apiResponseTime],
      }),
      new GraphWidget({
        title: 'Database Performance',
        left: [dynamoReadLatency, dynamoWriteLatency],
      }),
    ],
  ],
});
```

### Cost Optimization

```typescript
// Scheduled scaling for predictable workloads
const scheduledScaling = service.autoScaleTaskCount({
  minCapacity: 1,
  maxCapacity: 10,
});

// Scale down during off-hours
scheduledScaling.scaleOnSchedule('ScaleDown', {
  schedule: Schedule.cron({ hour: '22', minute: '0' }),
  minCapacity: 1,
  maxCapacity: 2,
});

// Scale up during business hours
scheduledScaling.scaleOnSchedule('ScaleUp', {
  schedule: Schedule.cron({ hour: '8', minute: '0' }),
  minCapacity: 2,
  maxCapacity: 10,
});
```

## Security Configuration

### IAM Roles and Policies

```typescript
// API service role with minimal required permissions
const apiRole = new Role(this, 'ApiRole', {
  assumedBy: new ServicePrincipal('ecs-tasks.amazonaws.com'),
  inlinePolicies: {
    DynamoDBAccess: new PolicyDocument({
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
            'dynamodb:DeleteItem',
            'dynamodb:Query',
            'dynamodb:Scan',
          ],
          resources: [props.dataResources.dynamoTable.tableArn],
        }),
      ],
    }),
  },
});
```

### Network Security

```typescript
// Security groups with least privilege access
const apiSecurityGroup = new SecurityGroup(this, 'ApiSecurityGroup', {
  vpc: props.vpc,
  description: 'Security group for API service',
});

// Allow inbound traffic only from load balancer
apiSecurityGroup.addIngressRule(
  props.loadBalancerSecurityGroup,
  Port.tcp(8000),
  'Allow traffic from load balancer',
);

// Allow outbound HTTPS for AWS services
apiSecurityGroup.addEgressRule(
  Peer.anyIpv4(),
  Port.tcp(443),
  'Allow HTTPS outbound for AWS services',
);
```

## Testing Infrastructure

### Unit Testing

```typescript
// test/data-stack.test.ts
import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/data-stack';

test('DynamoDB table created with correct configuration', () => {
  const app = new App();
  const stack = new DataStack(app, 'TestStack', {
    config: testConfig,
  });

  const template = Template.fromStack(stack);

  template.hasResourceProperties('AWS::DynamoDB::Table', {
    BillingMode: 'PAY_PER_REQUEST',
    PointInTimeRecoverySpecification: {
      PointInTimeRecoveryEnabled: true,
    },
  });
});
```

### Integration Testing

```bash
# Run CDK tests
npm run test

# Test synthesized templates
npm run cdk synth > /tmp/synth-output.yaml
# Validate CloudFormation templates
aws cloudformation validate-template --template-body file:///tmp/synth-output.yaml
```

## Troubleshooting

### Common Issues

1. **Deployment Failures**: Check CloudFormation stack events for detailed error messages
2. **Permission Issues**: Verify IAM roles have required permissions for AWS services
3. **Network Connectivity**: Check security groups and NACLs for proper configurations
4. **Resource Limits**: Ensure AWS account limits aren't exceeded

### Debug Commands

```bash
# Check CDK context
npm run cdk context --clear

# Validate CDK app
npm run cdk doctor

# View differences before deployment
npm run cdk diff

# Check CloudFormation stack status
aws cloudformation describe-stacks --stack-name ChatWorkbenchStack
```

## Next Steps

- **Architecture Guide**: See [Architecture Overview](../../docs/ARCHITECTURE.md) for system design details
- **Deployment Guide**: Read [Infrastructure Guide](../../docs/infrastructure.md) for production deployment
- **API Integration**: Check [API Reference](../../docs/API-REFERENCE.md) for service endpoints
- **Monitoring Setup**: Configure CloudWatch dashboards and alarms for production monitoring
