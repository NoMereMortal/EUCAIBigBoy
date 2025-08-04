// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// UI stack for handling UI deployment separately.
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as assets from 'aws-cdk-lib/aws-ecr-assets';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as iam from 'aws-cdk-lib/aws-iam';
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

interface UiStackProps extends BaseProps {
  config: BaseProps['config'] & {
    deploymentStage: string;
    deploymentName: string;
    appName: string;
    targetPlatform: string;
  };
  userPoolDomainUrl: string;
  apiVersion: string;
  infrastructureStackName: string;
  stackName: string;
  description: string;
  vpc: cdk.aws_ec2.IVpc;
  ecsCluster: cdk.aws_ecs.ICluster;
  uiTargetGroup: cdk.aws_elasticloadbalancingv2.IApplicationTargetGroup;
  applicationUri: string;
  allSubnets: cdk.aws_ec2.ISubnet[];
  filteredPublicSubnets: cdk.aws_ec2.ISubnet[];
  filteredPrivateSubnets: cdk.aws_ec2.ISubnet[];
  filteredIsolatedSubnets: cdk.aws_ec2.ISubnet[];
}

/**
 * UI Stack for deploying the user interface.
 * Separated from the main application stack to allow independent updates.
 */
export class UiStack extends cdk.Stack {
  // Expose service for distribution stack
  public readonly uiService: ecs.FargateService;
  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {UiStackProps} props - Properties of the Stack.
   */
  constructor(
    scope: Construct,
    id: string,
    props: cdk.StackProps & UiStackProps,
  ) {
    super(scope, id, props);

    const {
      config,
      vpc,
      ecsCluster,
      uiTargetGroup,
      allSubnets,
      filteredPublicSubnets,
      filteredPrivateSubnets,
      filteredIsolatedSubnets,
    } = props;

    // Get the SSM parameter name that will be used by the UI container
    const deploymentId = config.getDeploymentId('/');
    const uiConfigParamName = `${deploymentId}/ui-config`;

    // Create security group for UI service
    const uiServiceSg = new ec2.SecurityGroup(this, 'UiServiceSg', {
      vpc: vpc,
      description: 'Security group for UI Fargate service',
      allowAllOutbound: true,
    });

    // Allow traffic from ALB security group to UI service
    uiServiceSg.connections.allowFrom(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(3000),
      'Allow traffic to UI service',
    );

    // Create IAM role for UI tasks
    const uiTaskRole = new iam.Role(this, 'UiTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description: 'Role for UI Fargate tasks',
    });

    // Grant permission to read SSM parameter
    uiTaskRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['ssm:GetParameter'],
        resources: [
          cdk.Arn.format(
            {
              service: 'ssm',
              resource: 'parameter',
              resourceName: uiConfigParamName.startsWith('/')
                ? uiConfigParamName.slice(1)
                : uiConfigParamName,
            },
            this,
          ),
        ],
        effect: iam.Effect.ALLOW,
      }),
    );

    // Grant ECR permissions if using ECR container
    if (config.uiConfig.ecrContainer) {
      uiTaskRole.addToPolicy(
        new iam.PolicyStatement({
          actions: ['ecr:GetAuthorizationToken'],
          resources: ['*'],
          effect: iam.Effect.ALLOW,
        }),
      );

      uiTaskRole.addToPolicy(
        new iam.PolicyStatement({
          actions: [
            'ecr:BatchCheckLayerAvailability',
            'ecr:GetDownloadUrlForLayer',
            'ecr:BatchGetImage',
          ],
          resources: [
            cdk.Arn.format(
              {
                service: 'ecr',
                resource: 'repository',
                resourceName: extractEcrRepositoryName(
                  config.uiConfig.ecrContainer.repositoryUri,
                ),
              },
              this,
            ),
          ],
          effect: iam.Effect.ALLOW,
        }),
      );
    }

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
    let uiDockerImage: ecs.ContainerImage;

    if (config.uiConfig.ecrContainer) {
      // Use ECR container image (BYOC approach)
      const ecrConfig = config.uiConfig.ecrContainer;
      const repositoryName = extractEcrRepositoryName(ecrConfig.repositoryUri);
      const repositoryArn = buildEcrRepositoryArn(
        ecrConfig.repositoryUri,
        config.region,
        config.accountNumber,
      );
      const repository = ecr.Repository.fromRepositoryAttributes(
        this,
        'UiEcrRepo',
        {
          repositoryName,
          repositoryArn,
        },
      );

      uiDockerImage = ecs.ContainerImage.fromEcrRepository(
        repository,
        ecrConfig.imageTag,
      );

      console.log(
        `Using ECR container image for UI: ${ecrConfig.repositoryUri}:${ecrConfig.imageTag}`,
      );
    } else {
      // Use traditional Docker build approach
      uiDockerImage = ecs.ContainerImage.fromAsset(
        path.join(projectRoot, 'ui'),
        {
          file: 'Dockerfile',
          platform: platform,
        },
      );
    }

    // Create ECS task definition
    const uiTaskDefinition = new ecs.FargateTaskDefinition(
      this,
      `UiFargateTaskDefinition`,
      {
        taskRole: uiTaskRole,
        cpu: 1024,
        memoryLimitMiB: 2048,
      },
    );

    // Create CloudWatch log group
    const logGroup = new logs.LogGroup(this, `UiLogGroup`, {
      retention: getCloudWatchRetentionDays(
        config.loggingConfig.logRetentionDays,
      ),
      removalPolicy: config.removalPolicy,
    });

    // Add container to task definition
    uiTaskDefinition.addContainer(`UiContainerDefinition`, {
      image: uiDockerImage,
      environment: {
        NODE_ENV: 'production',
        PORT: '3000',
        HOSTNAME: '0.0.0.0',
        SSM_PARAM_NAME: uiConfigParamName,
        DEPLOYMENT_STAGE: config.deploymentStage,
        AWS_REGION: config.region,
      },
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: 'ui',
        logGroup: logGroup,
      }),
      portMappings: [{ containerPort: 3000, protocol: ecs.Protocol.TCP }],
      healthCheck: {
        command: config.uiConfig.containerHealthCheckConfig.command,
        interval: cdk.Duration.seconds(
          config.uiConfig.containerHealthCheckConfig.interval,
        ),
        timeout: cdk.Duration.seconds(
          config.uiConfig.containerHealthCheckConfig.timeout,
        ),
        retries: config.uiConfig.containerHealthCheckConfig.retries,
        startPeriod: cdk.Duration.seconds(
          config.uiConfig.containerHealthCheckConfig.startPeriod,
        ),
      },
    });

    // Get subnets for UI ECS service using the service subnet selection function
    const serviceSubnets = getServiceSubnets('ecs', config, allSubnets, {
      public: filteredPublicSubnets,
      private: filteredPrivateSubnets,
      isolated: filteredIsolatedSubnets,
    });

    // Create ECS service with zero-downtime deployment configuration
    this.uiService = new ecs.FargateService(this, `UiFargateService`, {
      cluster: ecsCluster,
      taskDefinition: uiTaskDefinition,
      securityGroups: [uiServiceSg],
      vpcSubnets: {
        subnets: serviceSubnets,
      },
      assignPublicIp: false,
      deploymentController: {
        type: ecs.DeploymentControllerType.ECS,
      },
      // Disable circuit breaker to allow more time for startup
      circuitBreaker: undefined,
      minHealthyPercent: 100, // Keep all existing tasks running during deployment
      maxHealthyPercent: 200, // Allow double capacity during deployment
      // More generous grace period for container startup
      healthCheckGracePeriod: cdk.Duration.seconds(120),
    });

    // Set up auto scaling
    const scaling = this.uiService.autoScaleTaskCount({
      minCapacity: 2,
      maxCapacity: 10,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(300),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Register the service with the target group
    uiTargetGroup.addTarget(this.uiService);

    // CFN outputs
    new cdk.CfnOutput(this, 'UiStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the UI stack',
    });

    new cdk.CfnOutput(this, 'UiServiceName', {
      value: this.uiService.serviceName,
      description: 'Name of the UI ECS service',
    });

    new cdk.CfnOutput(this, 'UiServiceArn', {
      value: this.uiService.serviceArn,
      description: 'ARN of the UI ECS service',
    });

    new cdk.CfnOutput(this, 'UiTaskDefinitionArn', {
      value: uiTaskDefinition.taskDefinitionArn,
      description: 'ARN of the UI task definition',
    });

    new cdk.CfnOutput(this, 'UiLogGroupName', {
      value: logGroup.logGroupName,
      description: 'Name of the UI CloudWatch log group',
    });

    new cdk.CfnOutput(this, 'UiLogGroupArn', {
      value: logGroup.logGroupArn,
      description: 'ARN of the UI CloudWatch log group',
    });

    new cdk.CfnOutput(this, 'UiConfigParamName', {
      value: uiConfigParamName,
      description: 'SSM parameter name containing UI runtime configuration',
    });

    new cdk.CfnOutput(this, 'UiTaskRoleArn', {
      value: uiTaskRole.roleArn,
      description: 'ARN of the UI task role',
    });

    // Add ECR configuration output if using BYOC
    if (config.uiConfig.ecrContainer) {
      new cdk.CfnOutput(this, 'UiEcrRepositoryUri', {
        value: config.uiConfig.ecrContainer.repositoryUri,
        description: 'ECR repository URI used for UI container',
      });

      new cdk.CfnOutput(this, 'UiEcrImageTag', {
        value: config.uiConfig.ecrContainer.imageTag,
        description: 'ECR image tag used for UI container',
      });
    }
  }
}
