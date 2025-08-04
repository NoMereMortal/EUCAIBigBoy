// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Compute stack for ECS Cluster.
import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import type { Construct } from 'constructs';

import type { BaseProps } from './schema';

interface ComputeStackProps extends BaseProps {
  vpc: cdk.aws_ec2.IVpc;
}

/**
 * Compute Stack for deploying shared compute resources including the ECS Cluster.
 * Separated to prevent unnecessary rebuilds when service-specific stacks change.
 */
export class ComputeStack extends cdk.Stack {
  // Expose compute resources for use by other stacks
  public readonly cluster: ecs.ICluster;

  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {ComputeStackProps} props - Properties of the Stack.
   */
  constructor(
    scope: Construct,
    id: string,
    props: cdk.StackProps & ComputeStackProps,
  ) {
    super(scope, id, props);

    const { vpc } = props;

    const prefix = 'Compute';

    // Create ECS cluster
    this.cluster = new ecs.Cluster(this, `${prefix}Cluster`, {
      vpc: vpc,
      containerInsights: true,
    });

    // CFN outputs
    new cdk.CfnOutput(this, 'ComputeStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the compute stack',
    });

    new cdk.CfnOutput(this, 'EcsClusterName', {
      value: this.cluster.clusterName,
      description: 'Name of the ECS cluster',
    });

    new cdk.CfnOutput(this, 'EcsClusterArn', {
      value: this.cluster.clusterArn,
      description: 'ARN of the ECS cluster',
    });
  }
}
