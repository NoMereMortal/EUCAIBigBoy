// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Infrastructure stack for shared resources.
import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import type { Construct } from 'constructs';

import type { BaseProps, Config } from './schema';
import { createCdkId, getIamPolicyStatements, isGovCloudRegion } from './utils';

interface InfrastructureStackProps extends BaseProps {
  vpc: cdk.aws_ec2.IVpc;
}

/**
 * Infrastructure Stack for shared resources that are used across multiple stacks.
 * This stack helps avoid circular dependencies between stacks.
 */
export class InfrastructureStack extends cdk.Stack {
  // Expose resources for use by other stacks
  public readonly accessLogsBucket: s3.IBucket;
  public readonly fastApiTaskRole: iam.Role;
  public readonly fastApiServiceSg: ec2.SecurityGroup;
  public readonly albSecurityGroup: ec2.SecurityGroup;
  public readonly elasticacheSg: ec2.SecurityGroup;

  // Cognito resources
  public readonly userPool: cognito.IUserPool;
  public readonly userPoolClient: cognito.IUserPoolClient;
  public readonly userPoolDomainUrl: string;
  public readonly clientId: string;
  public readonly apiAuthority: string;

  // API version moved from ChatWorkbenchStack
  public readonly apiVersion: string;

  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {InfrastructureStackProps} props - Properties of the Stack.
   */
  constructor(
    scope: Construct,
    id: string,
    props: cdk.StackProps & InfrastructureStackProps,
  ) {
    super(scope, id, props);

    const { config, vpc } = props;

    // Create S3 bucket for access logs
    this.accessLogsBucket = new s3.Bucket(this, 'AccessLogsBucket', {
      removalPolicy: config.removalPolicy,
      autoDeleteObjects: config.deploymentStage === 'dev',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      accessControl: s3.BucketAccessControl.LOG_DELIVERY_WRITE,
      lifecycleRules: [
        {
          id: 'AccessLogsLifecycleRule',
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(
                config.s3Config.accessLogsLifecycle.transitionToIADays,
              ),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(
                config.s3Config.accessLogsLifecycle.transitionToGlacierDays,
              ),
            },
          ],
          expiration: cdk.Duration.days(
            config.s3Config.accessLogsLifecycle.deletionDays,
          ),
        },
      ],
    });

    // Create security group for ALB first (needed for FastAPI security group ingress rule)
    this.albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc: vpc,
      description: 'Security group for the application load balancer',
      allowAllOutbound: true,
    });

    // Create security group for FastAPI service
    this.fastApiServiceSg = new ec2.SecurityGroup(this, 'FastApiServiceSg', {
      vpc: vpc,
      description: 'Security group for the FastAPI Fargate service',
      allowAllOutbound: true, // Explicitly allow all outbound traffic
    });

    // Add explicit outbound rule for HTTPS (OpenSearch Serverless, Bedrock, etc.)
    this.fastApiServiceSg.addEgressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS outbound for AWS services (OpenSearch, Bedrock, etc.)',
    );

    // Add explicit outbound rule for HTTP (for any HTTP-based AWS service calls)
    this.fastApiServiceSg.addEgressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP outbound for AWS services',
    );

    // Allow inbound traffic from ALB to FastAPI service on port 8000
    this.fastApiServiceSg.addIngressRule(
      ec2.Peer.securityGroupId(this.albSecurityGroup.securityGroupId),
      ec2.Port.tcp(8000),
      'Allow inbound HTTP traffic from ALB to FastAPI service',
    );

    // Create security group for ElastiCache Serverless
    this.elasticacheSg = new ec2.SecurityGroup(
      this,
      'ElastiCacheSecurityGroup',
      {
        vpc: vpc,
        description: 'Security group for ElastiCache Serverless',
        allowAllOutbound: true,
      },
    );

    // To avoid circular dependencies between security groups, use connections to set up rules
    // This is a higher-level abstraction that handles the bidirectional nature properly
    const elasticacheConnection = new ec2.Connections({
      securityGroups: [this.elasticacheSg],
      defaultPort: ec2.Port.tcp(6379),
    });

    // Allow the FastAPI service security group to access the ElastiCache security group
    elasticacheConnection.allowFrom(
      this.fastApiServiceSg,
      ec2.Port.tcp(6379),
      'Allow FastAPI service to access ElastiCache',
    );

    // Allow the ElastiCache security group to access the FastAPI service security group
    const fastApiConnection = new ec2.Connections({
      securityGroups: [this.fastApiServiceSg],
      defaultPort: ec2.Port.tcp(6379),
    });

    fastApiConnection.allowFrom(
      this.elasticacheSg,
      ec2.Port.tcp(6379),
      'Allow ElastiCache to access FastAPI service',
    );

    // Allow traffic from within VPC for dev deployments
    if (config.deploymentStage === 'dev') {
      this.albSecurityGroup.addIngressRule(
        ec2.Peer.ipv4(vpc.vpcCidrBlock),
        ec2.Port.tcp(80),
        'Allow traffic from within VPC',
      );
    }

    // Configure ALB access based on deployment environment
    const currentRegion = config.region;
    const isGovCloud = isGovCloudRegion(currentRegion);

    // Log region detection for troubleshooting
    console.log(
      `InfrastructureStack - Region: ${currentRegion}, IsGovCloud: ${isGovCloud}`,
    );

    if (isGovCloud) {
      // GovCloud: Direct ALB access (no CloudFront) with SSL support
      if (config.loadBalancerConfig.sslCertificateArn) {
        // HTTPS configuration for direct access
        this.albSecurityGroup.addIngressRule(
          ec2.Peer.anyIpv4(),
          ec2.Port.tcp(443),
          'Allow HTTPS traffic (GovCloud direct ALB access)',
        );

        // HTTP for HTTPS redirect
        this.albSecurityGroup.addIngressRule(
          ec2.Peer.anyIpv4(),
          ec2.Port.tcp(80),
          'Allow HTTP traffic for HTTPS redirect (GovCloud)',
        );
      } else {
        // HTTP only configuration for direct access
        this.albSecurityGroup.addIngressRule(
          ec2.Peer.anyIpv4(),
          ec2.Port.tcp(80),
          'Allow HTTP traffic (GovCloud direct ALB access)',
        );
      }
    } else {
      // Commercial AWS: Configure CloudFront → ALB restriction
      this.configureAlbForCloudFront(
        this.albSecurityGroup,
        config.region,
        config,
      );
    }

    // Create IAM role for FastAPI tasks
    const prefix = 'RestApi';
    const statements = getIamPolicyStatements('ecs');
    this.fastApiTaskRole = new iam.Role(this, createCdkId([prefix, 'Role']), {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      description: 'Allow REST API ECS tasks access to AWS resources',
      inlinePolicies: {
        [createCdkId([prefix, 'RoleInlinePolicy'])]: new iam.PolicyDocument({
          statements: statements,
        }),
      },
    });

    // Create or import cognito resources
    let userPool;
    const cognitoAuthConfig = config.cognitoAuthConfig;
    if (!cognitoAuthConfig.userPoolId) {
      // Create new user pool
      userPool = new cognito.UserPool(this, 'UserPool', {
        userPoolName: cognitoAuthConfig.userPoolName,
        selfSignUpEnabled: false,
        signInAliases: {
          email: true,
          username: false,
          phone: false,
        },
        accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
        passwordPolicy: {
          minLength: 8,
          requireLowercase: true,
          requireUppercase: true,
          requireDigits: true,
          requireSymbols: true,
        },
        removalPolicy: config.removalPolicy,
      });
    } else {
      // Use existing user pool
      userPool = cognito.UserPool.fromUserPoolId(
        this,
        'UserPool',
        cognitoAuthConfig.userPoolId,
      );
    }

    // Create or use existing user pool client
    let userPoolClient;
    if (!cognitoAuthConfig.userPoolClientId) {
      userPoolClient = userPool.addClient('CognitoUserPoolClient', {
        generateSecret: false,
        oAuth: {
          flows: {
            authorizationCodeGrant: true,
          },
          scopes: [cognito.OAuthScope.OPENID],
          callbackUrls: [
            'https://placeholder-will-be-replaced-by-ui-stack.example.com',
            'http://localhost:3000',
          ],
          logoutUrls: [
            'https://placeholder-will-be-replaced-by-ui-stack.example.com',
            'http://localhost:3000',
          ],
        },
        supportedIdentityProviders: [
          cognito.UserPoolClientIdentityProvider.COGNITO,
        ],
        preventUserExistenceErrors: true,
      });
    } else {
      userPoolClient = cognito.UserPoolClient.fromUserPoolClientId(
        this,
        'UserPoolClientId',
        cognitoAuthConfig.userPoolClientId,
      );
    }

    // If it's a new user pool, create the domain
    if (!cognitoAuthConfig.userPoolId) {
      userPool.addDomain('CognitoUserPoolDomain', {
        cognitoDomain: {
          domainPrefix: cognitoAuthConfig.userPoolDomainName,
        },
      });
    }

    // Expose these values
    this.userPool = userPool;
    this.userPoolClient = userPoolClient;
    this.clientId = userPoolClient.userPoolClientId;
    this.apiAuthority = `https://cognito-idp.${config.region}.amazonaws.com/${userPool.userPoolId}`;
    this.userPoolDomainUrl = `https://${cognitoAuthConfig.userPoolDomainName}.auth.${config.region}.amazoncognito.com`;

    // Set API version (moved from ChatWorkbenchStack)
    this.apiVersion = config.restApiConfig.apiVersion;

    // Export values for cross-stack references
    const stackName = cdk.Stack.of(this).stackName;

    // CFN outputs with explicit exports for cross-stack references
    new cdk.CfnOutput(this, 'InfrastructureStackName', {
      value: stackName,
      exportName: `${stackName}-StackName`,
    });

    new cdk.CfnOutput(this, 'CognitoApiAuthorityUrl', {
      value: this.apiAuthority,
      exportName: `${stackName}-CognitoApiAuthorityUrl`,
    });

    new cdk.CfnOutput(this, 'CognitoClientId', {
      value: this.clientId,
      exportName: `${stackName}-CognitoClientId`,
    });

    new cdk.CfnOutput(this, 'CognitoUserPoolId', {
      value: this.userPool.userPoolId,
      exportName: `${stackName}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'CognitoDomainUrl', {
      value: this.userPoolDomainUrl,
      exportName: `${stackName}-CognitoDomainUrl`,
    });

    new cdk.CfnOutput(this, 'ApiVersion', {
      value: this.apiVersion,
      exportName: `${stackName}-ApiVersion`,
    });

    new cdk.CfnOutput(this, 'AccessLogsBucketName', {
      value: this.accessLogsBucket.bucketName,
      description: 'Name of the S3 bucket for access logs',
    });

    new cdk.CfnOutput(this, 'AccessLogsBucketArn', {
      value: this.accessLogsBucket.bucketArn,
      description: 'ARN of the S3 bucket for access logs',
    });

    new cdk.CfnOutput(this, 'FastApiTaskRoleArn', {
      value: this.fastApiTaskRole.roleArn,
      description: 'ARN of the FastAPI task role',
    });

    new cdk.CfnOutput(this, 'ElastiCacheSecurityGroupId', {
      value: this.elasticacheSg.securityGroupId,
      description: 'ID of the ElastiCache security group',
    });
  }

  /**
   * Configure the ALB security group to allow traffic from CloudFront
   * Conditionally adds rules based on SSL certificate configuration to minimize rule count
   *
   * @param albSecurityGroup The ALB security group
   * @param region The AWS region
   * @param config The deployment configuration
   */
  private configureAlbForCloudFront(
    albSecurityGroup: ec2.SecurityGroup,
    region: string,
    config: Config,
  ): void {
    // Skip CloudFront configuration if in GovCloud (CloudFront not available)
    if (isGovCloudRegion(region)) {
      console.log(
        `Skipping CloudFront configuration for GovCloud region: ${region}`,
      );
      return;
    }

    // Use Custom Resource to get CloudFront prefix list ID
    const getPrefixListId = new cdk.custom_resources.AwsCustomResource(
      this,
      'GetPrefixListId',
      {
        onUpdate: {
          service: 'EC2',
          action: 'describeManagedPrefixLists',
          parameters: {
            Filters: [
              {
                Name: 'prefix-list-name',
                Values: ['com.amazonaws.global.cloudfront.origin-facing'],
              },
            ],
          },
          region: region,
          physicalResourceId: cdk.custom_resources.PhysicalResourceId.of(
            `cloudfront-prefix-list-id-${region}`,
          ),
        },
        policy: cdk.custom_resources.AwsCustomResourcePolicy.fromStatements([
          new iam.PolicyStatement({
            actions: ['ec2:DescribeManagedPrefixLists'],
            resources: ['*'],
            effect: iam.Effect.ALLOW,
          }),
        ]),
      },
    );
    const prefixListId = getPrefixListId.getResponseField(
      'PrefixLists.0.PrefixListId',
    );

    // Conditionally add ingress rules based on SSL certificate configuration
    // This matches the CloudFront origin protocol policy and minimizes security group rules
    if (config.loadBalancerConfig.sslCertificateArn) {
      // Certificate exists: CloudFront uses HTTPS_ONLY protocol policy
      // Only allow HTTPS traffic from CloudFront to ALB (55 rules)
      albSecurityGroup.addIngressRule(
        ec2.Peer.prefixList(prefixListId),
        ec2.Port.tcp(443),
        `Allow HTTPS inbound from CloudFront (${region}) - certificate configured`,
      );
    } else {
      // No certificate: CloudFront uses HTTP_ONLY protocol policy
      // Only allow HTTP traffic from CloudFront to ALB (55 rules)
      albSecurityGroup.addIngressRule(
        ec2.Peer.prefixList(prefixListId),
        ec2.Port.tcp(80),
        `Allow HTTP inbound from CloudFront (${region}) - no certificate`,
      );
    }
  }
}
