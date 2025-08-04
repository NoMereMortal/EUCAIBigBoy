// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// API stack for handling API deployment separately.
import * as cdk from 'aws-cdk-lib';
import * as assets from 'aws-cdk-lib/aws-ecr-assets';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as logs from 'aws-cdk-lib/aws-logs';
import type { Construct } from 'constructs';

import type { BaseProps } from './schema';
import {
  projectRoot,
  getServiceSubnets,
  buildEcrRepositoryArn,
  extractEcrRepositoryName,
  getCloudWatchRetentionDays,
} from './utils';

interface ApiStackProps extends BaseProps {
  vpc: cdk.aws_ec2.IVpc;
  apiAuthority: string;
  clientId: string;
  taskRole: cdk.aws_iam.IRole;
  serviceSg: cdk.aws_ec2.ISecurityGroup;
  dataTable: cdk.aws_dynamodb.Table;
  elastiCacheServerless: cdk.aws_elasticache.CfnServerlessCache;
  fileBucket?: cdk.aws_s3.Bucket;
  documentsCollectionEndpoint?: string;
  ecsCluster: cdk.aws_ecs.ICluster;
  apiTargetGroup: cdk.aws_elasticloadbalancingv2.IApplicationTargetGroup;
  allSubnets: cdk.aws_ec2.ISubnet[];
  filteredPublicSubnets: cdk.aws_ec2.ISubnet[];
  filteredPrivateSubnets: cdk.aws_ec2.ISubnet[];
  filteredIsolatedSubnets: cdk.aws_ec2.ISubnet[];
}

/**
 * API Stack for deploying the REST API.
 * Separated from the main application stack to allow independent updates.
 */
export class ApiStack extends cdk.Stack {
  // Expose service for distribution stack
  public readonly apiService: ecs.FargateService;
  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {ApiStackProps} props - Properties of the Stack.
   */
  constructor(
    scope: Construct,
    id: string,
    props: cdk.StackProps & ApiStackProps,
  ) {
    super(scope, id, props);

    const {
      config,
      apiAuthority,
      clientId,
      taskRole,
      serviceSg,
      dataTable,
      elastiCacheServerless,
      fileBucket,
      documentsCollectionEndpoint,
      ecsCluster,
      apiTargetGroup,
      allSubnets,
      filteredPublicSubnets,
      filteredPrivateSubnets,
      filteredIsolatedSubnets,
    } = props;

    const prefix = 'RestApi';

    // Map the targetPlatform string from config to the Platform enum
    let platform: assets.Platform;
    if (config.targetPlatform === 'linux/amd64') {
      platform = assets.Platform.LINUX_AMD64;
    } else if (config.targetPlatform === 'linux/arm64') {
      platform = assets.Platform.LINUX_ARM64;
    } else {
      // Default to AMD64 if not specified or unknown
      platform = assets.Platform.LINUX_AMD64;
    }

    // Create container image based on configuration
    let dockerImage: ecs.ContainerImage;

    if (config.restApiConfig.ecrContainer) {
      // Use ECR container image (BYOC approach)
      const ecrConfig = config.restApiConfig.ecrContainer;
      const repositoryName = extractEcrRepositoryName(ecrConfig.repositoryUri);
      const repositoryArn = buildEcrRepositoryArn(
        ecrConfig.repositoryUri,
        config.region,
        config.accountNumber,
      );
      const repository = ecr.Repository.fromRepositoryAttributes(
        this,
        'ApiEcrRepo',
        {
          repositoryName,
          repositoryArn,
        },
      );

      dockerImage = ecs.ContainerImage.fromEcrRepository(
        repository,
        ecrConfig.imageTag,
      );

      console.log(
        `Using ECR container image: ${ecrConfig.repositoryUri}:${ecrConfig.imageTag}`,
      );
    } else {
      // Use traditional Docker build approach
      // When API_DEPLOYMENT=true, build/push the Docker image normally
      // When API_DEPLOYMENT is not set/false, use a Docker directory with skipPush for the first deployment
      // On subsequent deployments, this will use the existing ECR image without rebuilding/pushing
      if (process.env.API_DEPLOYMENT === 'true') {
        console.log(`Building Docker image for ${config.targetPlatform}`);
        dockerImage = ecs.ContainerImage.fromAsset(projectRoot, {
          file: 'infrastructure/docker/backend/Dockerfile',
          platform: platform,
        });
      } else {
        // For existing deployments, this will reference the already deployed image
        // For new deploys, we need to handle the first deployment case
        try {
          const appName = config.appName || 'cwb';
          const repoName = `${appName}-${config.deploymentStage}-api`;

          // Try to use existing repository and latest image (for re-deployments)
          const repo = cdk.aws_ecr.Repository.fromRepositoryName(
            this,
            'ApiRepo',
            repoName,
          );
          dockerImage = ecs.ContainerImage.fromEcrRepository(repo, 'latest');
        } catch (error) {
          // Fallback for first time deployment - we have to build the image
          console.log(
            'Warning: No existing ECR repository found. Will build image for first deployment.',
          );
          dockerImage = ecs.ContainerImage.fromAsset(projectRoot, {
            file: 'infrastructure/docker/backend/Dockerfile',
            platform: platform,
          });
        }
      }
    }

    // Build container environment variables
    const containerEnvironment: Record<string, string> = {
      AWS_REGION: config.region,
      API_VERSION: config.restApiConfig.apiVersion,
      API_LOG_LEVEL: config.logLevel,
      AUTH_AUTHORITY: apiAuthority,
      AUTH_CLIENT_ID: clientId,
      AUTH_ENABLED: true.toString(),
    };

    // Add DynamoDB table name from DataStack
    containerEnvironment.DYNAMODB_TABLE_NAME = dataTable.tableName;

    // Add ElastiCache Serverless configuration (always enabled)
    containerEnvironment.VALKEY_HOST =
      elastiCacheServerless.attrEndpointAddress;
    containerEnvironment.VALKEY_PORT = elastiCacheServerless.attrEndpointPort;

    // Add OpenSearch Serverless configuration if enabled
    if (config.dataConfig?.openSearchEnabled && documentsCollectionEndpoint) {
      containerEnvironment.OPENSEARCH_ENABLED = 'true';
      // Extract host from endpoint URL (remove https://)
      const openSearchHost = documentsCollectionEndpoint.replace(
        /^https?:\/\//,
        '',
      );
      containerEnvironment.OPENSEARCH_HOST = openSearchHost;
      containerEnvironment.OPENSEARCH_PORT = '443'; // HTTPS port for serverless
      containerEnvironment.OPENSEARCH_REGION = config.region;

      // Add OpenSearch endpoint as stack output for easier reference
      new cdk.CfnOutput(this, 'OpenSearchDocumentsEndpoint', {
        value: documentsCollectionEndpoint,
        description: 'OpenSearch Serverless documents collection endpoint',
      });
    } else {
      containerEnvironment.OPENSEARCH_ENABLED = 'false';
    }

    // Add file storage configuration based on data config
    if (fileBucket) {
      // Using S3 bucket for file storage
      containerEnvironment.CONTENT_STORAGE_FORCE_LOCAL = 'false';
      containerEnvironment.CONTENT_STORAGE_LOCAL_PATH = '/tmp/file_artifacts'; // Temp directory with write permissions
      containerEnvironment.CONTENT_STORAGE_BASE_BUCKET = fileBucket.bucketName;

      // Note: S3 permissions are handled in DataStack to avoid circular dependencies
      // DataStack grants the task role permissions using the taskRoleArn

      // Add S3 bucket name as stack output for easier reference
      new cdk.CfnOutput(this, 'FileStorageBucket', {
        value: fileBucket.bucketName,
        description: 'S3 bucket used for file storage',
      });
    } else {
      // Using local storage only
      containerEnvironment.CONTENT_STORAGE_FORCE_LOCAL = 'true';
      containerEnvironment.CONTENT_STORAGE_LOCAL_PATH = '/app/file_artifacts';

      // Add warning as stack output
      new cdk.CfnOutput(this, 'FileStorageWarning', {
        value:
          'Using local storage only - files will not persist across container restarts',
        description: 'Warning about file storage configuration',
      });
    }

    // Create ECS task definition
    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      `${prefix}FargateTaskDefinition`,
      {
        taskRole: taskRole,
        cpu: config.restApiConfig.containerConfig.cpuLimit,
        memoryLimitMiB: config.restApiConfig.containerConfig.memoryLimit,
      },
    );

    // Create CloudWatch log group
    const logGroup = new logs.LogGroup(this, `${prefix}LogGroup`, {
      retention: getCloudWatchRetentionDays(
        config.loggingConfig.logRetentionDays,
      ),
      removalPolicy: config.removalPolicy,
    });

    // Add container to task definition
    const containerHealthCheckConfig =
      config.restApiConfig.containerConfig.healthCheckConfig;
    taskDefinition.addContainer(`${prefix}ContainerDefinition`, {
      image: dockerImage,
      environment: containerEnvironment,
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: prefix,
        logGroup: logGroup,
      }),
      portMappings: [{ containerPort: 8000, protocol: ecs.Protocol.TCP }],
      healthCheck: {
        command: containerHealthCheckConfig.command,
        interval: cdk.Duration.seconds(containerHealthCheckConfig.interval),
        startPeriod: cdk.Duration.seconds(
          containerHealthCheckConfig.startPeriod,
        ),
        timeout: cdk.Duration.seconds(containerHealthCheckConfig.timeout),
        retries: containerHealthCheckConfig.retries,
      },
      readonlyRootFilesystem: false,
    });

    // Get subnets for ECS service using the service subnet selection function
    const serviceSubnets = getServiceSubnets('ecs', config, allSubnets, {
      public: filteredPublicSubnets,
      private: filteredPrivateSubnets,
      isolated: filteredIsolatedSubnets,
    });

    // Create ECS service with circuit breaker for automatic rollback on deployment failure
    this.apiService = new ecs.FargateService(this, `${prefix}FargateService`, {
      cluster: ecsCluster,
      taskDefinition: taskDefinition,
      securityGroups: [serviceSg],
      vpcSubnets: {
        subnets: serviceSubnets,
      },
      assignPublicIp: false,
      deploymentController: {
        type: ecs.DeploymentControllerType.ECS,
      },
      circuitBreaker: { rollback: true },
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
    });

    // Register the service with the target group
    apiTargetGroup.addTarget(this.apiService);

    // Add autoscaling
    const autoscalingConfig = config.restApiConfig.autoScalingConfig;
    this.apiService
      .autoScaleTaskCount({
        minCapacity: autoscalingConfig.minCapacity,
        maxCapacity: autoscalingConfig.maxCapacity,
      })
      .scaleOnCpuUtilization(`${prefix}CpuScaling`, {
        targetUtilizationPercent: 70,
        scaleInCooldown: cdk.Duration.seconds(autoscalingConfig.cooldown),
        scaleOutCooldown: cdk.Duration.seconds(autoscalingConfig.cooldown),
      });

    // Setup alarms if enabled
    if (config.alarmConfig?.enable) {
      const errorMetricFilter = new cdk.aws_logs.MetricFilter(
        this,
        `${prefix}MetricFilter`,
        {
          logGroup: logGroup,
          metricNamespace: `${config.deploymentPrefix}/${prefix}Errors`,
          metricName: `${prefix}ErrorCount`,
          filterPattern: cdk.aws_logs.FilterPattern.anyTerm(
            ...config.alarmConfig.loggingFilterPatterns,
          ),
          metricValue: '1',
        },
      );

      const metric = errorMetricFilter.metric({
        period: cdk.Duration.minutes(config.alarmConfig.period),
      });

      const topic = new cdk.aws_sns.Topic(this, `${prefix}Topic`, {
        displayName: `${prefix} Alarm: ${config.deploymentPrefix}`,
      });

      (config.alarmConfig.emailAddresses as string[]).forEach(
        (email: string) => {
          topic.addSubscription(
            new cdk.aws_sns_subscriptions.EmailSubscription(email),
          );
        },
      );

      const alarm = new cdk.aws_cloudwatch.Alarm(this, `${prefix}Alarm`, {
        metric: metric,
        threshold: config.alarmConfig.threshold,
        evaluationPeriods: config.alarmConfig.evaluationPeriods,
        alarmDescription:
          'Alarm when the error count exceeds threshold within a period',
        actionsEnabled: true,
        comparisonOperator:
          cdk.aws_cloudwatch.ComparisonOperator
            .GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      });

      alarm.addAlarmAction(new cdk.aws_cloudwatch_actions.SnsAction(topic));
      alarm.addOkAction(new cdk.aws_cloudwatch_actions.SnsAction(topic));
      alarm.addInsufficientDataAction(
        new cdk.aws_cloudwatch_actions.SnsAction(topic),
      );
    }

    // CFN outputs
    new cdk.CfnOutput(this, 'ApiStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the API stack',
    });

    new cdk.CfnOutput(this, 'ApiServiceName', {
      value: this.apiService.serviceName,
      description: 'Name of the API ECS service',
    });

    new cdk.CfnOutput(this, 'ApiServiceArn', {
      value: this.apiService.serviceArn,
      description: 'ARN of the API ECS service',
    });

    new cdk.CfnOutput(this, 'ApiTaskDefinitionArn', {
      value: taskDefinition.taskDefinitionArn,
      description: 'ARN of the API task definition',
    });

    // Add ECR configuration output if using BYOC
    if (config.restApiConfig.ecrContainer) {
      new cdk.CfnOutput(this, 'ApiEcrRepositoryUri', {
        value: config.restApiConfig.ecrContainer.repositoryUri,
        description: 'ECR repository URI used for API container',
      });

      new cdk.CfnOutput(this, 'ApiEcrImageTag', {
        value: config.restApiConfig.ecrContainer.imageTag,
        description: 'ECR image tag used for API container',
      });
    }
  }
}
