// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Models for schema validation.
/* eslint-disable @typescript-eslint/no-explicit-any */
import * as cdk from 'aws-cdk-lib';

import { z } from 'zod';
import { bedrock } from '@cdklabs/generative-ai-cdk-constructs';

const APP_VERSION: string = 'v1';

const REMOVAL_POLICIES: Record<string, cdk.RemovalPolicy> = {
  destroy: cdk.RemovalPolicy.DESTROY,
  retain: cdk.RemovalPolicy.RETAIN,
};

export const BEDROCK_FOUNDATION_MODELS: Record<
  string,
  bedrock.BedrockFoundationModel
> = {
  'amazon.titan-embed-text-v1':
    bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V1,
  'amazon.titan-embed-text-v2:0':
    bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024,
  'cohere.embed-english-v3':
    bedrock.BedrockFoundationModel.COHERE_EMBED_ENGLISH_V3,
  'cohere.embed-multilingual-v3':
    bedrock.BedrockFoundationModel.COHERE_EMBED_MULTILINGUAL_V3,
};

/**
 * Configuration schema for data resources
 */
export const DataConfigSchema = z.object({
  // ElastiCache Serverless
  elastiCacheStorageLimitGb: z.number().min(1).max(1000).default(50),
  elastiCacheEcpuLimit: z.number().min(1000).max(100000).default(10000),

  // File Storage
  fileStorageEnabled: z.boolean().default(true),
  fileStorageType: z.enum(['s3', 'local']).default('s3'),

  // OpenSearch Serverless Configuration
  openSearchEnabled: z.boolean().default(false),
  openSearchDefaultIndex: z.string().min(1).default('documents'),
  openSearchStandbyReplicas: z.boolean().default(false),

  // Neptune Configuration
  neptuneEnabled: z.boolean().default(false),

  // Bedrock Knowledge Base Configuration
  bedrockKnowledgeBaseEnabled: z.boolean().default(false),
  embeddingModelId: z.string().min(1).default('amazon.titan-embed-text-v1'),
  knowledgeBaseName: z.string().min(1).optional(),
  vectorIndexName: z.string().min(1).default('documents'),
  s3InclusionPrefixes: z.array(z.string().min(1)).optional(),
});

/**
 * Configuration schema for VPC.
 *
 * @property {string} [vpcId] - VPC ID for application. When undefined/null/empty, a new VPC will be created.
 * @property {string[]} [publicSubnetIds=[]] - Public subnet IDs for ALB and internet-facing resources.
 * @property {string[]} [privateSubnetIds=[]] - Private subnet IDs for ECS services with NAT gateway access.
 * @property {string[]} [isolatedSubnetIds=[]] - Private isolated subnet IDs for databases and cache services.
 * @property {Object} [serviceSubnets={}] - Service-specific subnet overrides for precise control.
 * @property {string[]} [serviceSubnets.ecs] - Specific subnets for ECS services (API and UI).
 * @property {string[]} [serviceSubnets.elasticache] - Specific subnets for ElastiCache Serverless.
 * @property {string[]} [serviceSubnets.alb] - Specific subnets for Application Load Balancer.
 */
export const VpcConfigSchema = z.object({
  vpcId: z
    .string()
    .optional()
    .nullable()
    .transform((value: any) => value ?? undefined),
  publicSubnetIds: z
    .array(z.string())
    .optional()
    .nullable()
    .transform((value: any) => value ?? [])
    .default([]),
  privateSubnetIds: z
    .array(z.string())
    .optional()
    .nullable()
    .transform((value: any) => value ?? [])
    .default([]),
  isolatedSubnetIds: z
    .array(z.string())
    .optional()
    .nullable()
    .transform((value: any) => value ?? [])
    .default([]),
  serviceSubnets: z
    .object({
      ecs: z
        .array(z.string())
        .optional()
        .nullable()
        .transform((value: any) => value ?? [])
        .default([]),
      elasticache: z
        .array(z.string())
        .optional()
        .nullable()
        .transform((value: any) => value ?? [])
        .default([]),
      alb: z
        .array(z.string())
        .optional()
        .nullable()
        .transform((value: any) => value ?? [])
        .default([]),
    })
    .default({})
    .optional(),
  vpcEndpoints: z
    .object({
      // Subnet types where endpoints will be created. Default: private and isolated.
      endpointSubnetTypes: z
        .array(z.enum(['private', 'isolated']))
        .default(['private', 'isolated']),

      // Essential for ECS containers
      ecrDocker: z.boolean().default(false),
      ecrApi: z.boolean().default(false),
      s3: z.boolean().default(false),

      // Essential for API functionality
      dynamodb: z.boolean().default(false),
      secretsmanager: z.boolean().default(false),
      ssm: z.boolean().default(false),
      kms: z.boolean().default(false),

      // AI/ML services
      bedrock: z.boolean().default(false),
      bedrockRuntime: z.boolean().default(false),
      bedrockAgent: z.boolean().default(false),

      // Logging & monitoring
      cloudwatchLogs: z.boolean().default(false),
      monitoring: z.boolean().default(false),

      // Infrastructure services
      sts: z.boolean().default(false),
      ec2: z.boolean().default(false),
      ecs: z.boolean().default(false),
      elasticloadbalancing: z.boolean().default(false),

      // Optional services
      opensearch: z.boolean().default(false),
    })
    .default({})
    .optional(),
  existingVpcEndpoints: z
    .object({
      // Existing VPC Endpoint IDs to use instead of creating new ones
      ecrDocker: z.string().optional(),
      ecrApi: z.string().optional(),
      s3: z.string().optional(),
      dynamodb: z.string().optional(),
      secretsmanager: z.string().optional(),
      ssm: z.string().optional(),
      kms: z.string().optional(),
      bedrock: z.string().optional(),
      bedrockRuntime: z.string().optional(),
      bedrockAgent: z.string().optional(),
      cloudwatchLogs: z.string().optional(),
      monitoring: z.string().optional(),
      sts: z.string().optional(),
      ec2: z.string().optional(),
      ecs: z.string().optional(),
      elasticloadbalancing: z.string().optional(),
      opensearch: z.string().optional(),
    })
    .default({})
    .optional(),
});

/**
 * Configuration schema for Cognito authorization.
 *
 * @property {string} userPoolName - Name of the Cognito user pool.
 * @property {string} userPoolId - ID of the Cognito user pool.
 * @property {string} userPoolClientId - ID of the Cognito user pool client.
 * @property {string} userPoolDomainName - Domain name of the Cognito user pool.
 */
export const CognitoAuthConfigSchema = z
  .object({
    userPoolName: z.string().optional(),
    userPoolId: z.string().optional(),
    userPoolClientId: z.string().optional(),
    userPoolDomainName: z
      .string()
      .min(1, { message: 'userPoolDomainName is required' }),
  })
  .superRefine((data, ctx) => {
    if (data.userPoolName && data.userPoolId) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['userPoolId'],
        message:
          'Either `userPoolId` or `userPoolName` must be provided, but not both. \
          Set `userPoolId` to use an existing User Pool or `userPoolName` to create a new User Pool.',
      });
    }

    if (!(data.userPoolName || data.userPoolId)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['userPoolId'],
        message:
          'One of `userPoolId` or `userPoolName` must be provided. \
          Set `userPoolId` to use an existing User Pool or `userPoolName` to create a new User Pool.',
      });
    }
  });

/**
 * Configuration schema for the load balancer.
 *
 * @property {number} idleTimeout - Idle timeout in seconds.
 * @property {string} [sslCertificateArn] - ARN of SSL certificate for HTTPS listener.
 * @property {string} [albPlacement='public'] - ALB placement strategy: 'public' (internet-facing in public subnets), 'private' (internal in private subnets with NAT), or 'isolated' (internal in isolated subnets).
 *
 * Note: HTTPS redirect behavior is automatically configured:
 * - CloudFront deployments: No ALB redirect (CloudFront handles HTTPS)
 * - Direct ALB deployments (GovCloud): Auto-redirect if SSL certificate provided
 */
export const LoadBalancerConfigSchema = z.object({
  idleTimeout: z.number().min(30).max(300).default(300),
  sslCertificateArn: z.string().min(1).optional(),
  albPlacement: z.enum(['public', 'private', 'isolated']).default('public'),
});

/**
 * Configuration schema for AWS WAF v2.
 * WAF is always enabled for security - only rule configuration is customizable.
 *
 * @property {Object} managedRules - Configuration for AWS managed rule groups.
 * @property {boolean} [managedRules.coreRuleSet=false] - Enable AWS Common Rule Set (can be strict).
 * @property {boolean} [managedRules.knownBadInputs=true] - Enable Known Bad Inputs rule set (recommended).
 * @property {boolean} [managedRules.amazonIpReputation=true] - Enable Amazon IP Reputation List (recommended).
 * @property {Object} rateLimiting - Configuration for rate limiting rules.
 * @property {boolean} [rateLimiting.enabled=true] - Enable rate limiting.
 * @property {number} [rateLimiting.requestsPerMinute=2000] - Requests per minute limit (applied over 5-minute rolling window).
 * @property {boolean} [logging.enabled=false] - Enable WAF logging (disabled by default for cost).
 */
export const WafConfigSchema = z.object({
  managedRules: z
    .object({
      coreRuleSet: z.boolean().default(false), // Can be too strict for many apps
      knownBadInputs: z.boolean().default(true), // Essential protection
      amazonIpReputation: z.boolean().default(true), // Essential protection - Amazon IP reputation
    })
    .default({}),
  rateLimiting: z
    .object({
      enabled: z.boolean().default(true),
      requestsPerMinute: z.number().min(100).max(20000).default(2000),
    })
    .default({}),
  logging: z
    .object({
      enabled: z.boolean().default(false), // Disabled by default for cost considerations
    })
    .default({}),
});

/**
 * Configuration for ECS container health checks.
 *
 * @property {string[]} [command=['CMD-SHELL', 'exit 0']] - Command to run for health checks.
 * @property {number} [interval=10] - Time interval between health checks, in seconds.
 * @property {number} [startPeriod=30] - Time to wait before starting the first health check, in seconds.
 * @property {number} [timeout=5] - Maximum time allowed for each health check to complete, in seconds.
 * @property {number} [retries=3] - Number of times to retry a failed health check before considering the container
 *                                  as unhealthy.
 */
const EcsContainerHealthCheckConfigSchema = z.object({
  command: z
    .array(z.string().min(1))
    .default([
      'CMD-SHELL',
      'curl -f http://127.0.0.1:8000/api/health || exit 1',
    ]),
  interval: z.number().min(10).default(10),
  startPeriod: z.number().min(30).default(30),
  timeout: z.number().min(5).default(5),
  retries: z.number().min(3).default(3),
});

/**
 * Configuration for ECR container image.
 *
 * @property {string} repositoryUri - ECR repository URI (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo).
 * @property {string} [imageTag='latest'] - Image tag or SHA256 digest.
 */
const EcrContainerConfigSchema = z.object({
  repositoryUri: z
    .string()
    .min(1)
    .refine(
      (uri) =>
        /^\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com\/[a-z0-9-_/]+$/.test(
          uri,
        ),
      {
        message:
          'Invalid ECR repository URI format. Expected format: 123456789012.dkr.ecr.region.amazonaws.com/repo-name',
      },
    ),
  imageTag: z.string().default('latest'),
});

/**
 * Configuration for an ECS container.
 *
 * @property {number} [cpuLimit=1024] - CPU limit for container.
 * @property {number} [memoryLimit=2048] - Memory limit for container.
 * @property {EcsContainerHealthCheckConfigSchema} [healthCheckConfig={}] - Health check configuration for container.
 */
const EcsContainerConfigSchema = z.object({
  cpuLimit: z.number().min(256).max(16384).default(1024),
  memoryLimit: z.number().min(512).max(32768).default(2048),
  healthCheckConfig: EcsContainerHealthCheckConfigSchema.default({}),
});

/**
 * Configuration schema for health checks on ECS.
 *
 * @property {string} path - Path for the health check.
 * @property {number} [interval=60] - Interval in seconds between health checks.
 * @property {number} [timeout=30] - Timeout in seconds for each health check.
 * @property {number} [healthyThresholdCount=2] - Number of consecutive successful health checks required to consider
 *                                                the target healthy.
 * @property {number} [unhealthyThresholdCount=10] - Number of consecutive failed health checks required to consider the
 *                                                  target unhealthy.
 */
const EcsHealthCheckConfigSchema = z.object({
  path: z.string().min(1),
  interval: z.number().min(10).default(60),
  timeout: z.number().min(5).default(30),
  healthyThresholdCount: z.number().min(2).default(2),
  unhealthyThresholdCount: z.number().min(2).default(10),
});

/**
 * Configuration schema for ECS auto scaling metrics.
 *
 * @property {string} albMetricName - Name of the ALB metric.
 * @property {number} targetValue - Target value for the metric.
 * @property {number} [duration=60] - Duration in seconds for metric evaluation.
 * @property {number} [estimatedInstanceWarmup=60] - Estimated warm-up time in seconds until a newly launched instance
 *                                                    can send metrics to CloudWatch.
 *
 */
const EcsMetricConfigSchema = z.object({
  albMetricName: z.string().min(1),
  targetValue: z.number().min(60),
  duration: z.number().min(60).default(60),
  estimatedInstanceWarmup: z.number().min(60).default(60),
});

/**
 * Configuration schema for ECS auto scaling settings.
 *
 * @property {number} [minCapacity=1] - Minimum capacity for auto scaling. Must be at least 1.
 * @property {number} [maxCapacity=5] - Maximum capacity for auto scaling. Must be at least 1.
 * @property {number} [defaultInstanceWarmup=120] - Default warm-up time in seconds until a newly launched instance can
 *                                                  send metrics to CloudWatch.
 * @property {number} [cooldown=300] - Cool down period in seconds between scaling activities.
 * @property {MetricConfig} metricConfig - Metric configuration for auto scaling.
 */
const EcsAutoScalingConfigSchema = z.object({
  minCapacity: z.number().min(1).default(1),
  maxCapacity: z.number().min(1).default(5),
  defaultInstanceWarmup: z.number().min(120).default(120),
  cooldown: z.number().min(300).default(300),
  metricConfig: EcsMetricConfigSchema,
});

// Valid CloudWatch log retention days
const VALID_RETENTION_DAYS = [
  1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653,
] as const;

/**
 * Configuration schema for logging settings.
 *
 * @property {number} [logRetentionDays=30] - CloudWatch log retention in days. Must be one of: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653.
 * @property {number} [wafLogRetentionDays=30] - WAF log retention in days. Must be one of: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653.
 */
export const LoggingConfigSchema = z.object({
  logRetentionDays: z
    .number()
    .refine(
      (val) =>
        VALID_RETENTION_DAYS.includes(
          val as (typeof VALID_RETENTION_DAYS)[number],
        ),
      {
        message: `logRetentionDays must be one of: ${VALID_RETENTION_DAYS.join(', ')}`,
      },
    )
    .default(30),
  wafLogRetentionDays: z
    .number()
    .refine(
      (val) =>
        VALID_RETENTION_DAYS.includes(
          val as (typeof VALID_RETENTION_DAYS)[number],
        ),
      {
        message: `wafLogRetentionDays must be one of: ${VALID_RETENTION_DAYS.join(', ')}`,
      },
    )
    .default(30),
});

/**
 * Configuration schema for S3 lifecycle policies.
 *
 * @property {Object} [accessLogsLifecycle={}] - Lifecycle configuration for access logs bucket.
 * @property {number} [transitionToIADays=30] - Days to transition to Infrequent Access.
 * @property {number} [transitionToGlacierDays=90] - Days to transition to Glacier.
 * @property {number} [deletionDays=365] - Days to delete objects.
 * @property {Object} [cloudFrontLogsLifecycle={}] - Lifecycle configuration for CloudFront logs bucket.
 * @property {number} [transitionToIADays=30] - Days to transition to Infrequent Access.
 * @property {number} [transitionToGlacierDays=90] - Days to transition to Glacier.
 * @property {number} [deletionDays=365] - Days to delete objects.
 */
export const S3ConfigSchema = z.object({
  accessLogsLifecycle: z
    .object({
      transitionToIADays: z.number().min(1).default(30),
      transitionToGlacierDays: z.number().min(30).default(90),
      deletionDays: z.number().min(90).default(365),
    })
    .default({}),
  cloudFrontLogsLifecycle: z
    .object({
      transitionToIADays: z.number().min(1).default(30),
      transitionToGlacierDays: z.number().min(30).default(90),
      deletionDays: z.number().min(90).default(365),
    })
    .default({}),
});

/**
 * Configuration schema for CloudWatch alarms.
 *
 * @property {boolean} [enable=false] - Whether to enable alarm.
 * @property {number} [period=1] - Duration in minutes to collect data.
 * @property {number} [threshold=1] - Value against which the statistic is compared.
 * @property {number} [evaluationPeriods=1] - Number of periods over which data is compared to the threshold.
 * @property {string[]} loggingFilterPatterns - Logging filter patterns to use to trigger alarm response.
 * @property {string[]} [emailAddresses] - Email addresses to send SNS notifications for alarm actions.
 */
export const AlarmConfigSchema = z
  .object({
    enable: z.boolean().default(false),
    period: z.number().min(1).default(1),
    threshold: z.number().min(1).default(1),
    evaluationPeriods: z.number().min(1).default(1),
    loggingFilterPatterns: z.array(
      z.union([
        z.literal('WARNING'),
        z.literal('ERROR'),
        z.literal('CRITICAL'),
      ]),
    ),
    emailAddresses: z.array(z.string().email()).optional(),
  })
  .refine(
    (data) => {
      // If alarms are enabled, check that emailAddresses is provided and not empty
      if (
        data.enable &&
        (!data.emailAddresses || data.emailAddresses.length === 0)
      ) {
        return false;
      }
      return true;
    },
    {
      message:
        'Email addresses must be provided and not empty when the alarm is enabled.',
      path: ['emailAddresses'],
    },
  );

export type AlarmConfig = z.infer<typeof AlarmConfigSchema>;

/**
 * Configuration schema for REST API.
 *
 * @property {string} [apiVersion='v1'] - API version.
 * @property {EcsContainerConfigSchema} containerConfig - Configuration for the container.
 * @property {EcsHealthCheckConfigSchema} healthCheckConfig - Health check configuration for the target group.
 * @property {EcsAutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 * @property {EcrContainerConfigSchema} [ecrContainer] - Optional ECR container configuration for BYOC.
 */
const RestApiConfigSchema = z.object({
  apiVersion: z.literal('v1').default('v1'),
  containerConfig: EcsContainerConfigSchema,
  healthCheckConfig: EcsHealthCheckConfigSchema.default({
    path: '/api/health',
    interval: 60,
    timeout: 30,
    healthyThresholdCount: 2,
    unhealthyThresholdCount: 10,
  }),
  autoScalingConfig: EcsAutoScalingConfigSchema,
  ecrContainer: EcrContainerConfigSchema.optional(),
});

/**
 * Configuration schema for ECS Target Group.
 *
 * @property {EcsContainerConfigSchema} containerConfig - Configuration for the container.
 * @property {EcsHealthCheckConfigSchema} healthCheckConfig - Health check configuration for the target group.
 * @property {EcsAutoScalingConfigSchema} autoScalingConfig - Configuration for auto scaling settings.
 */
export const EcsTargetGroupConfigSchema = z.object({
  containerConfig: EcsContainerConfigSchema,
  healthCheckConfig: EcsHealthCheckConfigSchema,
  autoScalingConfig: EcsAutoScalingConfigSchema,
});

export type EcsTargetGroupConfig = z.infer<typeof EcsTargetGroupConfigSchema>;

/**
 * VPC Endpoints schema for creating default values
 */
export const VpcEndpointsSchema = z.object({
  endpointSubnetTypes: z
    .array(z.enum(['private', 'isolated']))
    .default(['private', 'isolated']),
  ecrDocker: z.boolean().default(false),
  ecrApi: z.boolean().default(false),
  s3: z.boolean().default(false),
  dynamodb: z.boolean().default(false),
  secretsmanager: z.boolean().default(false),
  ssm: z.boolean().default(false),
  kms: z.boolean().default(false),
  bedrock: z.boolean().default(false),
  bedrockRuntime: z.boolean().default(false),
  bedrockAgent: z.boolean().default(false),
  cloudwatchLogs: z.boolean().default(false),
  monitoring: z.boolean().default(false),
  sts: z.boolean().default(false),
  ec2: z.boolean().default(false),
  ecs: z.boolean().default(false),
  elasticloadbalancing: z.boolean().default(false),
  opensearch: z.boolean().default(false),
});

export type VpcEndpointsConfig = z.infer<typeof VpcEndpointsSchema>;

/**
 * Existing VPC Endpoints schema for creating default values
 */
export const ExistingVpcEndpointsSchema = z.object({
  ecrDocker: z.string().optional(),
  ecrApi: z.string().optional(),
  s3: z.string().optional(),
  dynamodb: z.string().optional(),
  secretsmanager: z.string().optional(),
  ssm: z.string().optional(),
  kms: z.string().optional(),
  bedrock: z.string().optional(),
  bedrockRuntime: z.string().optional(),
  bedrockAgent: z.string().optional(),
  cloudwatchLogs: z.string().optional(),
  monitoring: z.string().optional(),
  sts: z.string().optional(),
  ec2: z.string().optional(),
  ecs: z.string().optional(),
  elasticloadbalancing: z.string().optional(),
  opensearch: z.string().optional(),
});

export type ExistingVpcEndpointsConfig = z.infer<
  typeof ExistingVpcEndpointsSchema
>;

/**
 * Configuration schema for application.
 *
 * Note: This schema uses semantic null handling via z.preprocess():
 * - Optional fields: null/undefined/empty → undefined (for truly optional fields)
 * - Array fields: null/undefined → empty array (for fields that should be present but empty)
 *
 * @property {string} [appName='cwb'] - Name of the application.
 * @property {string} [awsProfile] - AWS CLI profile for deployment. When undefined, uses default profile.
 * @property {string} deploymentName - Name of the deployment.
 * @property {string} accountNumber - AWS account number for deployment. Must be 12 digits.
 * @property {string} region - AWS region for deployment.
 * @property {string} deploymentStage - Deployment stage for the application.
 * @property {string} removalPolicy - Removal policy for resources (destroy or retain).
 * @property {boolean} [runCdkNag=false] - Whether to run CDK Nag checks.
 * @property {string} logLevel - Log level for application.
 * @property {string} targetPlatform - Target platform for building Docker images.
 * @property {VpcConfigSchema} vpcConfig - VPC configuration.
 * @property {CognitoAuthConfigSchema} cognitoAuthConfig - Cognito auth configuration.
 * @property {LoadBalancerConfigSchema} loadBalancerConfig - Load balancer configuration.
 * @property {AlarmConfigSchema} alarmConfig - Alarm configuration.
 * @property {RestApiConfigSchema} restApiConfig - REST API configuration.
 * @property {Array<{ Key: string, Value: string }>} [tags=[]] - Array of key-value pairs for tagging.
 */
const RawConfigSchema = z.object({
  appName: z
    .string()
    .default('cwb')
    .transform((value) => value.toLowerCase()),
  awsProfile: z
    .string()
    .optional()
    .nullable()
    .transform((value: any) => value ?? undefined),
  dataConfig: DataConfigSchema.default({}),
  deploymentName: z.string().min(1),
  accountNumber: z
    .union([z.string(), z.number()])
    .transform((value) => {
      // Convert to string if it's a number
      const strValue = value.toString();

      // If it's a number, pad with leading zeros
      if (typeof value === 'number') {
        return strValue.padStart(12, '0');
      }
      return strValue;
    })
    .refine((value) => value.length === 12, {
      message: 'AWS account number should be 12 digits',
    }),
  region: z.string().min(1),
  deploymentStage: z.string().min(1),
  removalPolicy: z
    .union([z.literal('destroy'), z.literal('retain')])
    .transform((value) => REMOVAL_POLICIES[value]),
  runCdkNag: z.boolean().default(false),
  logLevel: z.union([
    z.literal('DEBUG'),
    z.literal('INFO'),
    z.literal('WARNING'),
    z.literal('ERROR'),
  ]),
  targetPlatform: z.string().min(1),
  vpcConfig: VpcConfigSchema.optional(),
  cognitoAuthConfig: CognitoAuthConfigSchema,
  loadBalancerConfig: LoadBalancerConfigSchema,
  wafConfig: WafConfigSchema.default({}),
  loggingConfig: LoggingConfigSchema.default({}),
  s3Config: S3ConfigSchema.default({ accessLogsLifecycle: {} }),
  alarmConfig: AlarmConfigSchema,
  restApiConfig: RestApiConfigSchema,
  uiConfig: z
    .object({
      title: z.string().default('Chat Workbench'),
      ecrContainer: EcrContainerConfigSchema.optional(),
      containerHealthCheckConfig: EcsContainerHealthCheckConfigSchema.default({
        command: [
          'CMD-SHELL',
          'curl -f http://127.0.0.1:3000/health || exit 1',
        ],
        interval: 60,
        timeout: 10,
        retries: 5,
        startPeriod: 120,
      }),
      healthCheckConfig: EcsHealthCheckConfigSchema.default({
        path: '/health',
        interval: 60,
        timeout: 10,
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 10,
      }),
    })
    .default({}),
  tags: z
    .array(
      z.object({
        Key: z.string().min(1),
        Value: z.string().min(1),
      }),
    )
    .default([]),
});

/**
 * Apply transformations to the raw application configuration schema.
 *
 * @param {Object} rawConfig - Raw application configuration.
 * @returns {Object} Transformed application configuration.
 */
export const ConfigSchema = RawConfigSchema.transform((rawConfig) => {
  const deploymentPrefix = `/${rawConfig.deploymentStage}/${rawConfig.deploymentName}/${rawConfig.appName}`;

  // Function that takes joiner as parameter for flexible naming
  const getDeploymentId = (joiner: string) => {
    const id = `${rawConfig.deploymentStage}${joiner}${rawConfig.deploymentName}${joiner}${rawConfig.appName}`;
    // For SSM hierarchical names, ensure they start with /
    return joiner === '/' ? `/${id}` : id;
  };

  // Initialize tags if not present; otherwise, shallow copy to prevent direct mutation
  const tags = rawConfig.tags ? [...rawConfig.tags] : [];

  // Function to check if a tag key exists and update its value or append a new tag
  const upsertTag = (key: string, value: string) => {
    const existingTagIndex = tags.findIndex((tag) => tag.Key === key);
    if (existingTagIndex !== -1) {
      tags[existingTagIndex].Value = value;
    } else {
      tags.push({ Key: key, Value: value });
    }
  };

  // Ensure essential tags are set or updated
  upsertTag('deploymentPrefix', deploymentPrefix);
  upsertTag('deploymentName', rawConfig.deploymentName);
  upsertTag('deploymentStage', rawConfig.deploymentStage);
  upsertTag('version', APP_VERSION);

  return {
    ...rawConfig,
    getDeploymentId,
    tags,
    deploymentPrefix,
  };
});

/**
 * Application configuration type.
 */
export type Config = z.infer<typeof ConfigSchema>;

/**
 * Basic properties required for a Construct or Stack definition in CDK.
 *
 * @property {Config} config - The application configuration.
 */
export interface BaseProps {
  config: Config;
}
