// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as logs from 'aws-cdk-lib/aws-logs';
import type { Construct } from 'constructs';

import type {
  BaseProps,
  Config,
  ExistingVpcEndpointsConfig,
  VpcEndpointsConfig,
} from './schema';
import { VpcEndpointsSchema, ExistingVpcEndpointsSchema } from './schema';
import {
  getCloudWatchRetentionDays,
  getFilteredSubnets,
  validateConfiguredSubnets,
  validateFilteredSubnets,
} from './utils';

/**
 * Properties for the VpcStack.
 */
export interface VpcStackProps extends cdk.StackProps, BaseProps {}

/**
 * Stack for VPC resources.
 */
export class VpcStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly filteredPublicSubnets: ec2.ISubnet[];
  public readonly filteredPrivateSubnets: ec2.ISubnet[];
  public readonly filteredIsolatedSubnets: ec2.ISubnet[];
  public readonly allSubnets: ec2.ISubnet[];

  constructor(scope: Construct, id: string, props: VpcStackProps) {
    super(scope, id, props);

    const { config } = props;

    // Create VPC
    if (!config.vpcConfig?.vpcId) {
      this.vpc = new ec2.Vpc(this, 'Vpc', {
        maxAzs: 2,
        ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
        natGatewayProvider: ec2.NatProvider.gateway(),
        natGateways: 1,
        subnetConfiguration: [
          {
            subnetType: ec2.SubnetType.PUBLIC,
            name: 'public',
            cidrMask: 24,
          },
          {
            subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
            name: 'privateIsolated',
            cidrMask: 24,
          },
          {
            subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
            name: 'private',
            cidrMask: 24,
          },
        ],
      });

      // For new VPCs, filtered subnets are same as all subnets since no config restrictions apply
      this.filteredPublicSubnets = this.vpc.publicSubnets;
      this.filteredPrivateSubnets = this.vpc.privateSubnets;
      this.filteredIsolatedSubnets = this.vpc.isolatedSubnets;
    } else {
      this.vpc = ec2.Vpc.fromLookup(this, 'Vpc', {
        vpcId: config.vpcConfig.vpcId,
      }) as ec2.Vpc;
    }

    // For existing VPCs, validate that configured subnet IDs exist in the VPC
    if (config.vpcConfig?.vpcId) {
      // Get all subnets from the VPC (regardless of CDK's categorization)
      const allSubnets = [
        ...this.vpc.publicSubnets,
        ...this.vpc.privateSubnets,
        ...this.vpc.isolatedSubnets,
      ];

      // Validate that all configured subnet IDs exist in the VPC (including service overrides)
      const allConfiguredSubnetIds = [
        ...(config.vpcConfig.publicSubnetIds || []),
        ...(config.vpcConfig.privateSubnetIds || []),
        ...(config.vpcConfig.isolatedSubnetIds || []),
        ...(config.vpcConfig.serviceSubnets?.ecs || []),
        ...(config.vpcConfig.serviceSubnets?.elasticache || []),
        ...(config.vpcConfig.serviceSubnets?.alb || []),
      ];

      if (allConfiguredSubnetIds.length > 0) {
        validateConfiguredSubnets(
          allSubnets,
          allConfiguredSubnetIds,
          'configured',
        );
      }
    }

    // Create filtered subnet collections
    if (config.vpcConfig?.vpcId) {
      // For existing VPCs, filter from all available subnets by configured IDs
      this.allSubnets = [
        ...this.vpc.publicSubnets,
        ...this.vpc.privateSubnets,
        ...this.vpc.isolatedSubnets,
      ];

      this.filteredPublicSubnets = getFilteredSubnets(
        this.vpc.publicSubnets,
        config.vpcConfig?.publicSubnetIds,
      );
      this.filteredPrivateSubnets = getFilteredSubnets(
        this.vpc.privateSubnets,
        config.vpcConfig?.privateSubnetIds,
      );
      this.filteredIsolatedSubnets = getFilteredSubnets(
        this.vpc.isolatedSubnets,
        config.vpcConfig?.isolatedSubnetIds,
      );
    } else {
      // For new VPCs, use CDK's categorized subnets
      this.allSubnets = [
        ...this.vpc.publicSubnets,
        ...this.vpc.privateSubnets,
        ...this.vpc.isolatedSubnets,
      ];

      this.filteredPublicSubnets = getFilteredSubnets(
        this.vpc.publicSubnets,
        config.vpcConfig?.publicSubnetIds,
      );
      this.filteredPrivateSubnets = getFilteredSubnets(
        this.vpc.privateSubnets,
        config.vpcConfig?.privateSubnetIds,
      );
      this.filteredIsolatedSubnets = getFilteredSubnets(
        this.vpc.isolatedSubnets,
        config.vpcConfig?.isolatedSubnetIds,
      );
    }

    validateFilteredSubnets(
      config,
      this.allSubnets,
      this.filteredPublicSubnets,
      this.filteredPrivateSubnets,
      this.filteredIsolatedSubnets,
    );

    // Create a log group for VPC Flow Logs
    const flowLogsGroup = new logs.LogGroup(this, 'VpcFlowLogsGroup', {
      retention: getCloudWatchRetentionDays(
        config.loggingConfig.logRetentionDays,
      ),
      removalPolicy: config.removalPolicy,
    });

    // Add Flow Logs to VPC
    new ec2.FlowLog(this, 'VpcFlowLogs', {
      resourceType: ec2.FlowLogResourceType.fromVpc(this.vpc),
      destination: ec2.FlowLogDestination.toCloudWatchLogs(flowLogsGroup),
      trafficType: ec2.FlowLogTrafficType.ALL,
    });

    // Add VPC Endpoints for isolated subnet access to AWS services
    this.createVpcEndpoints(config);

    // CFN outputs - VPC and networking information
    new cdk.CfnOutput(this, 'VpcStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the VPC stack',
    });

    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'ID of the VPC',
    });

    new cdk.CfnOutput(this, 'VpcCidr', {
      value: this.vpc.vpcCidrBlock,
      description: 'CIDR block of the VPC',
    });

    new cdk.CfnOutput(this, 'PublicSubnetIds', {
      value: this.vpc.publicSubnets.map((subnet) => subnet.subnetId).join(','),
      description:
        'Comma-separated list of all public subnet IDs discovered in VPC',
    });

    new cdk.CfnOutput(this, 'PrivateSubnetIds', {
      value: this.vpc.privateSubnets.map((subnet) => subnet.subnetId).join(','),
      description:
        'Comma-separated list of all private subnet IDs discovered in VPC',
    });

    new cdk.CfnOutput(this, 'IsolatedSubnetIds', {
      value: this.vpc.isolatedSubnets
        .map((subnet) => subnet.subnetId)
        .join(','),
      description:
        'Comma-separated list of all isolated subnet IDs discovered in VPC',
    });

    new cdk.CfnOutput(this, 'FilteredPublicSubnetIds', {
      value: this.filteredPublicSubnets
        .map((subnet) => subnet.subnetId)
        .join(','),
      description:
        'Comma-separated list of filtered public subnet IDs (configured or all if none specified)',
    });

    new cdk.CfnOutput(this, 'FilteredPrivateSubnetIds', {
      value: this.filteredPrivateSubnets
        .map((subnet) => subnet.subnetId)
        .join(','),
      description:
        'Comma-separated list of filtered private subnet IDs (configured or all if none specified)',
    });

    new cdk.CfnOutput(this, 'FilteredIsolatedSubnetIds', {
      value: this.filteredIsolatedSubnets
        .map((subnet) => subnet.subnetId)
        .join(','),
      description:
        'Comma-separated list of filtered isolated subnet IDs (configured or all if none specified)',
    });

    new cdk.CfnOutput(this, 'AvailabilityZones', {
      value: this.vpc.availabilityZones.join(','),
      description: 'Comma-separated list of availability zones used by the VPC',
    });
  }

  /**
   * Creates VPC endpoints for AWS services in the configured subnet types.
   * Supports both creating new endpoints and using existing ones.
   */
  private createVpcEndpoints(config: Config): void {
    const vpcEndpoints =
      config.vpcConfig?.vpcEndpoints ?? VpcEndpointsSchema.parse({});
    const existingEndpoints =
      config.vpcConfig?.existingVpcEndpoints ??
      ExistingVpcEndpointsSchema.parse({});

    const selectedSubnets = this.getEndpointSubnets(vpcEndpoints);
    if (selectedSubnets.length === 0) {
      return;
    }

    const securityGroup = this.createEndpointSecurityGroup();

    this.createGatewayEndpoints(
      vpcEndpoints,
      existingEndpoints,
      selectedSubnets,
    );
    this.createInterfaceEndpoints(
      vpcEndpoints,
      existingEndpoints,
      selectedSubnets,
      securityGroup,
    );
    this.createCustomServiceEndpoints(
      vpcEndpoints,
      existingEndpoints,
      selectedSubnets,
      securityGroup,
    );
  }

  /**
   * Gets the subnets to use for VPC endpoints based on configuration.
   */
  private getEndpointSubnets(vpcEndpoints: VpcEndpointsConfig): ec2.ISubnet[] {
    const endpointSubnetTypes = vpcEndpoints.endpointSubnetTypes || [
      'private',
      'isolated',
    ];
    let selectedSubnets: ec2.ISubnet[] = [];

    if (endpointSubnetTypes.includes('private')) {
      selectedSubnets = selectedSubnets.concat(this.filteredPrivateSubnets);
    }
    if (endpointSubnetTypes.includes('isolated')) {
      selectedSubnets = selectedSubnets.concat(this.filteredIsolatedSubnets);
    }

    if (selectedSubnets.length === 0) {
      console.warn(
        `VPC endpoint creation skipped: No subnets found for types: ${endpointSubnetTypes.join(', ')}`,
      );
    }

    return selectedSubnets;
  }

  /**
   * Creates a security group for VPC endpoints.
   */
  private createEndpointSecurityGroup(): ec2.SecurityGroup {
    const securityGroup = new ec2.SecurityGroup(
      this,
      'VpcEndpointSecurityGroup',
      {
        vpc: this.vpc,
        description: 'Security group for VPC endpoints',
        allowAllOutbound: false,
      },
    );

    securityGroup.addIngressRule(
      ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
      ec2.Port.tcp(443),
      'Allow HTTPS from VPC',
    );

    return securityGroup;
  }

  /**
   * Creates gateway endpoints (S3, DynamoDB) - these are free.
   */
  private createGatewayEndpoints(
    vpcEndpoints: VpcEndpointsConfig,
    existingEndpoints: ExistingVpcEndpointsConfig,
    selectedSubnets: ec2.ISubnet[],
  ): void {
    const gatewayEndpoints = [
      { key: 's3', service: ec2.GatewayVpcEndpointAwsService.S3 },
      { key: 'dynamodb', service: ec2.GatewayVpcEndpointAwsService.DYNAMODB },
    ];

    gatewayEndpoints.forEach(({ key, service }) => {
      if (
        vpcEndpoints?.[key as keyof VpcEndpointsConfig] &&
        !existingEndpoints?.[key as keyof ExistingVpcEndpointsConfig]
      ) {
        const endpointName =
          key.charAt(0).toUpperCase() + key.slice(1) + 'Endpoint';
        this.vpc.addGatewayEndpoint(endpointName, {
          service,
          subnets: [{ subnets: selectedSubnets }],
        });
      }
    });
  }

  /**
   * Creates interface endpoints for standard AWS services.
   */
  private createInterfaceEndpoints(
    vpcEndpoints: VpcEndpointsConfig,
    existingEndpoints: ExistingVpcEndpointsConfig,
    selectedSubnets: ec2.ISubnet[],
    securityGroup: ec2.SecurityGroup,
  ): void {
    const interfaceEndpoints = [
      {
        key: 'ecrDocker',
        service: ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
      },
      { key: 'ecrApi', service: ec2.InterfaceVpcEndpointAwsService.ECR },
      {
        key: 'secretsmanager',
        service: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
      },
      { key: 'ssm', service: ec2.InterfaceVpcEndpointAwsService.SSM },
      { key: 'kms', service: ec2.InterfaceVpcEndpointAwsService.KMS },
      {
        key: 'cloudwatchLogs',
        service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      },
      {
        key: 'monitoring',
        service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_MONITORING,
      },
      { key: 'sts', service: ec2.InterfaceVpcEndpointAwsService.STS },
      { key: 'ec2', service: ec2.InterfaceVpcEndpointAwsService.EC2 },
      { key: 'ecs', service: ec2.InterfaceVpcEndpointAwsService.ECS },
      {
        key: 'elasticloadbalancing',
        service: ec2.InterfaceVpcEndpointAwsService.ELASTIC_LOAD_BALANCING,
      },
    ];

    interfaceEndpoints.forEach(({ key, service }) => {
      if (
        vpcEndpoints?.[key as keyof VpcEndpointsConfig] &&
        !existingEndpoints?.[key as keyof ExistingVpcEndpointsConfig]
      ) {
        const endpointName =
          key.charAt(0).toUpperCase() + key.slice(1) + 'Endpoint';
        this.vpc.addInterfaceEndpoint(endpointName, {
          service,
          subnets: { subnets: selectedSubnets },
          privateDnsEnabled: true,
          securityGroups: [securityGroup],
        });
      }
    });
  }

  /**
   * Creates custom service endpoints for Bedrock and other services.
   */
  private createCustomServiceEndpoints(
    vpcEndpoints: VpcEndpointsConfig,
    existingEndpoints: ExistingVpcEndpointsConfig,
    selectedSubnets: ec2.ISubnet[],
    securityGroup: ec2.SecurityGroup,
  ): void {
    const customEndpoints = [
      { key: 'bedrock', serviceName: 'bedrock' },
      { key: 'bedrockRuntime', serviceName: 'bedrock-runtime' },
      { key: 'bedrockAgent', serviceName: 'bedrock-agent-runtime' },
      { key: 'opensearch', serviceName: 'aoss' },
    ];

    customEndpoints.forEach(({ key, serviceName }) => {
      if (
        vpcEndpoints?.[key as keyof VpcEndpointsConfig] &&
        !existingEndpoints?.[key as keyof ExistingVpcEndpointsConfig]
      ) {
        const endpointName =
          key.charAt(0).toUpperCase() + key.slice(1) + 'Endpoint';
        this.vpc.addInterfaceEndpoint(endpointName, {
          service: new ec2.InterfaceVpcEndpointService(
            `com.amazonaws.${this.region}.${serviceName}`,
          ),
          subnets: { subnets: selectedSubnets },
          privateDnsEnabled: true,
          securityGroups: [securityGroup],
        });
      }
    });
  }
}
