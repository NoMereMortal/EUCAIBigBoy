// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Deploy application to different stages.
import * as cdk from 'aws-cdk-lib';
import { Aspects } from 'aws-cdk-lib';
import type { Construct } from 'constructs';
import { AwsSolutionsChecks } from 'cdk-nag';

import { ApiStack } from './api-stack';
import { ComputeStack } from './compute-stack';
import { DistributionStack } from './distribution-stack';
import { DataStack } from './data-stack';
import { InfrastructureStack } from './infrastructure-stack';
import type { BaseProps } from './schema';
import { UiStack } from './ui-stack';
import { createCdkId, getWafScope, isGovCloudRegion } from './utils';
import { VpcStack } from './vpc-stack';
import { WafRegionalStack } from './waf-regional-stack';

interface CustomChatWorkbenchProps extends BaseProps {}
type ChatWorkbenchProps = CustomChatWorkbenchProps & cdk.StageProps;

/**
 * Application Stage.
 */
export class ChatWorkbenchStage extends cdk.Stage {
  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {ChatWorkbenchProps} props - Properties of the stage.
   */
  constructor(scope: Construct, id: string, props: ChatWorkbenchProps) {
    super(scope, id, props);

    const { config } = props;

    // Create CDK stacks and explicitly set dependencies
    const vpcStack = new VpcStack(this, 'Vpc', {
      config: config,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'vpc',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench VPC Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });

    const infrastructureStack = new InfrastructureStack(
      this,
      'Infrastructure',
      {
        config: config,
        vpc: vpcStack.vpc,
        stackName: createCdkId([
          config.deploymentName,
          config.appName,
          'infrastructure',
          config.deploymentStage,
        ]),
        description: `ChatWorkbench Infrastructure Stack: ${config.deploymentName}-${config.deploymentStage}`,
      },
    );
    infrastructureStack.addDependency(vpcStack);

    const computeStack = new ComputeStack(this, 'Compute', {
      config: config,
      vpc: vpcStack.vpc,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'compute',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench Compute Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });
    computeStack.addDependency(infrastructureStack);

    const dataStack = new DataStack(this, 'Data', {
      config: config,
      vpc: vpcStack.vpc,
      taskRoleArn: infrastructureStack.fastApiTaskRole.roleArn,
      serviceSg: infrastructureStack.fastApiServiceSg,
      elasticacheSg: infrastructureStack.elasticacheSg,
      allSubnets: vpcStack.allSubnets,
      filteredPublicSubnets: vpcStack.filteredPublicSubnets,
      filteredPrivateSubnets: vpcStack.filteredPrivateSubnets,
      filteredIsolatedSubnets: vpcStack.filteredIsolatedSubnets,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'data',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench Data Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });
    dataStack.addDependency(vpcStack);
    dataStack.addDependency(infrastructureStack);

    // Create WAF stack in us-east-1 for CloudFront (non-GovCloud only)
    let wafStack: WafRegionalStack | undefined;
    if (
      getWafScope(this.region) === 'CLOUDFRONT' &&
      !isGovCloudRegion(this.region)
    ) {
      wafStack = new WafRegionalStack(this, 'WafRegional', {
        config: config,
        stackName: createCdkId([
          config.deploymentName,
          config.appName,
          'waf',
          config.deploymentStage,
        ]),
        description: `ChatWorkbench WAF Stack: ${config.deploymentName}-${config.deploymentStage}`,
        env: { region: 'us-east-1' },
      });
    }

    const distributionStack = new DistributionStack(this, 'Distribution', {
      config: config,
      vpc: vpcStack.vpc,
      accessLogsBucket: infrastructureStack.accessLogsBucket,
      albSecurityGroup: infrastructureStack.albSecurityGroup,
      userPoolDomainUrl: infrastructureStack.userPoolDomainUrl.toString(),
      infrastructureStackName: cdk.Stack.of(infrastructureStack).stackName,
      apiVersion: infrastructureStack.apiVersion.toString(),
      webAclArn: wafStack?.webAclArn,
      allSubnets: vpcStack.allSubnets,
      filteredPublicSubnets: vpcStack.filteredPublicSubnets,
      filteredPrivateSubnets: vpcStack.filteredPrivateSubnets,
      filteredIsolatedSubnets: vpcStack.filteredIsolatedSubnets,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'distribution',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench Distribution Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });
    distributionStack.addDependency(infrastructureStack);
    if (wafStack) {
      distributionStack.addDependency(wafStack);
    }

    const apiStack = new ApiStack(this, 'Api', {
      config: config,
      vpc: vpcStack.vpc,
      apiAuthority: infrastructureStack.apiAuthority,
      clientId: infrastructureStack.clientId,
      taskRole: infrastructureStack.fastApiTaskRole,
      serviceSg: infrastructureStack.fastApiServiceSg,
      dataTable: dataStack.dataTable,
      elastiCacheServerless: dataStack.elastiCacheServerless,
      fileBucket: dataStack.fileBucket,
      documentsCollectionEndpoint:
        dataStack.documentsCollection?.attrCollectionEndpoint,
      ecsCluster: computeStack.cluster,
      apiTargetGroup: distributionStack.apiTargetGroup,
      allSubnets: vpcStack.allSubnets,
      filteredPublicSubnets: vpcStack.filteredPublicSubnets,
      filteredPrivateSubnets: vpcStack.filteredPrivateSubnets,
      filteredIsolatedSubnets: vpcStack.filteredIsolatedSubnets,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'api',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench API Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });
    apiStack.addDependency(distributionStack);
    apiStack.addDependency(infrastructureStack);
    apiStack.addDependency(dataStack);
    apiStack.addDependency(computeStack);

    const uiStack = new UiStack(this, 'Ui', {
      config: config,
      vpc: vpcStack.vpc,
      userPoolDomainUrl: infrastructureStack.userPoolDomainUrl.toString(),
      apiVersion: infrastructureStack.apiVersion.toString(),
      infrastructureStackName: cdk.Stack.of(infrastructureStack).stackName,
      uiTargetGroup: distributionStack.uiTargetGroup,
      applicationUri: distributionStack.applicationUri,
      ecsCluster: computeStack.cluster,
      allSubnets: vpcStack.allSubnets,
      filteredPublicSubnets: vpcStack.filteredPublicSubnets,
      filteredPrivateSubnets: vpcStack.filteredPrivateSubnets,
      filteredIsolatedSubnets: vpcStack.filteredIsolatedSubnets,
      stackName: createCdkId([
        config.deploymentName,
        config.appName,
        'ui',
        config.deploymentStage,
      ]),
      description: `ChatWorkbench UI Stack: ${config.deploymentName}-${config.deploymentStage}`,
    });
    uiStack.addDependency(distributionStack);
    uiStack.addDependency(infrastructureStack);
    uiStack.addDependency(computeStack);

    // Set resource tags
    for (const tag of config.tags ?? []) {
      cdk.Tags.of(this).add(tag['Key'], tag['Value']);
    }

    // Run CDK-nag on app if specified
    if (config.runCdkNag) {
      Aspects.of(this).add(
        new AwsSolutionsChecks({ reports: true, verbose: true }),
      );
    }
  }
}
