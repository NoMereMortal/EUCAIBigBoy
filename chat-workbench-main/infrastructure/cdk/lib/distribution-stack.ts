// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Distribution stack for ALB, Target Groups, and CloudFront.
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as cr from 'aws-cdk-lib/custom-resources';
import type * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import type { Construct } from 'constructs';

import type { BaseProps } from './schema';
import {
  createCdkId,
  isGovCloudRegion,
  getWafScope,
  getCloudWatchRetentionDays,
  validateAlbPlacement,
  getAlbSubnetSelection,
  getServiceSubnets,
} from './utils';

interface DistributionStackProps extends BaseProps {
  vpc: cdk.aws_ec2.IVpc;
  accessLogsBucket: s3.IBucket;
  albSecurityGroup: ec2.ISecurityGroup;
  userPoolDomainUrl: string;
  infrastructureStackName: string;
  apiVersion: string;
  webAclArn?: string; // Optional WAF ARN from regional stack
  allSubnets: ec2.ISubnet[];
  filteredPublicSubnets: ec2.ISubnet[];
  filteredPrivateSubnets: ec2.ISubnet[];
  filteredIsolatedSubnets: ec2.ISubnet[];
}

/**
 * Distribution Stack for deploying shared distribution resources including the ALB and CloudFront.
 * Separated to prevent dependencies between UI and API stacks.
 */
export class DistributionStack extends cdk.Stack {
  // Expose distribution resources for use by other stacks if needed
  public readonly alb: elbv2.IApplicationLoadBalancer;
  public readonly distribution: cloudfront.Distribution | undefined;
  public readonly apiTargetGroup: elbv2.IApplicationTargetGroup;
  public readonly uiTargetGroup: elbv2.IApplicationTargetGroup;
  public readonly applicationUri: string;
  public readonly uiConfigParam: ssm.StringParameter;

  /**
   * @param {Construct} scope - Parent or owner of the construct.
   * @param {string} id - Unique identifier for the construct within its scope.
   * @param {DistributionStackProps} props - Properties of the Stack.
   */
  constructor(
    scope: Construct,
    id: string,
    props: cdk.StackProps & DistributionStackProps,
  ) {
    super(scope, id, {
      ...props,
      crossRegionReferences: true, // Enable cross-region references for WAF ARN
    });

    const {
      config,
      vpc,
      accessLogsBucket,
      albSecurityGroup,
      webAclArn,
      userPoolDomainUrl,
      infrastructureStackName,
      apiVersion,
      allSubnets,
      filteredPublicSubnets,
      filteredPrivateSubnets,
      filteredIsolatedSubnets,
    } = props;

    // Detect deployment environment
    const currentRegion = config.region;
    const isGovCloud = isGovCloudRegion(currentRegion);

    // Note: CloudFront unavailable in GovCloud directly - will use direct ALB + Regional WAF

    const prefix = 'Distribution';
    const deploymentId = config.getDeploymentId('/');

    // Validate ALB placement requirements against VPC subnet availability
    validateAlbPlacement(vpc, config.loadBalancerConfig.albPlacement);

    // Get ALB configuration based on placement strategy
    const albConfig = getAlbSubnetSelection(
      config.loadBalancerConfig.albPlacement,
    );

    // Get subnets for ALB using the service subnet selection function
    const albSubnets = getServiceSubnets('alb', config, allSubnets, {
      public: filteredPublicSubnets,
      private: filteredPrivateSubnets,
      isolated: filteredIsolatedSubnets,
    });

    // Create application load balancer
    const alb = new elbv2.ApplicationLoadBalancer(this, `${prefix}Alb`, {
      vpc: vpc,
      securityGroup: albSecurityGroup,
      internetFacing: albConfig.internetFacing,
      idleTimeout: cdk.Duration.seconds(config.loadBalancerConfig.idleTimeout),
      vpcSubnets: {
        subnets: albSubnets,
      },
    });

    // Security group rules are configured in infrastructure-stack.ts
    // For CloudFront deployments: Only CloudFront IPs can access ALB (via prefix list)
    // For GovCloud deployments: ALB is directly exposed with WAF protection

    // Note: ALB ingress rules are handled by configureAlbForCloudFront() in infrastructure-stack.ts
    // This ensures proper CloudFront→ALB restriction and prevents direct internet access bypass

    // Set up access logging for ALB
    alb.logAccessLogs(accessLogsBucket, 'alb-logs');

    // Create a target group for the API service (without targets)
    this.apiTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      'ApiTargetGroup',
      {
        vpc: vpc,
        port: 8000,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targetType: elbv2.TargetType.IP,
        healthCheck: {
          path: config.restApiConfig.healthCheckConfig.path,
          interval: cdk.Duration.seconds(
            config.restApiConfig.healthCheckConfig.interval,
          ),
          timeout: cdk.Duration.seconds(
            config.restApiConfig.healthCheckConfig.timeout,
          ),
          healthyThresholdCount:
            config.restApiConfig.healthCheckConfig.healthyThresholdCount,
          unhealthyThresholdCount:
            config.restApiConfig.healthCheckConfig.unhealthyThresholdCount,
        },
      },
    );

    // Create a target group for the UI service (without targets)
    this.uiTargetGroup = new elbv2.ApplicationTargetGroup(
      this,
      'UiTargetGroup',
      {
        vpc: vpc,
        port: 3000,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targetType: elbv2.TargetType.IP,
        healthCheck: {
          path: config.uiConfig.healthCheckConfig.path,
          interval: cdk.Duration.seconds(
            config.uiConfig.healthCheckConfig.interval,
          ),
          timeout: cdk.Duration.seconds(
            config.uiConfig.healthCheckConfig.timeout,
          ),
          healthyThresholdCount:
            config.uiConfig.healthCheckConfig.healthyThresholdCount,
          unhealthyThresholdCount:
            config.uiConfig.healthCheckConfig.unhealthyThresholdCount,
        },
      },
    );

    // Add listener - following your example pattern
    let albListener;
    if (config.loadBalancerConfig.sslCertificateArn) {
      albListener = alb.addListener('AlbListener', {
        port: 443,
        open: false,
        certificates: [
          { certificateArn: config.loadBalancerConfig.sslCertificateArn },
        ],
        defaultAction: elbv2.ListenerAction.forward([this.uiTargetGroup]), // Default to UI
      });

      // HTTP to HTTPS redirect listener (only for direct ALB access without CloudFront)
      // CloudFront deployments don't need ALB redirect as CloudFront handles HTTPS
      const shouldEnableHttpsRedirect =
        isGovCloud && config.loadBalancerConfig.sslCertificateArn;
      if (shouldEnableHttpsRedirect) {
        alb.addListener('HttpRedirectListener', {
          port: 80,
          open: false,
          defaultAction: elbv2.ListenerAction.redirect({
            protocol: 'HTTPS',
            port: '443',
            permanent: true,
          }),
        });
      }
    } else {
      albListener = alb.addListener('AlbListener', {
        port: 80,
        open: false,
        defaultAction: elbv2.ListenerAction.forward([this.uiTargetGroup]), // Default to UI
      });
    }

    // Add action for API target group with higher priority (lower number)
    albListener.addAction('ApiAction', {
      priority: 1, // API has higher priority
      conditions: [elbv2.ListenerCondition.pathPatterns(['/api/*'])],
      action: elbv2.ListenerAction.forward([this.apiTargetGroup]),
    });

    // Create a bucket for CloudFront access logs with ACLs enabled
    const loggingBucket = new s3.Bucket(this, 'LoggingBucket', {
      removalPolicy: config.removalPolicy,
      autoDeleteObjects: config.deploymentStage === 'dev',
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      // Required for CloudFront log delivery
      objectOwnership: s3.ObjectOwnership.OBJECT_WRITER,
      accessControl: s3.BucketAccessControl.LOG_DELIVERY_WRITE,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'distribution-logs-bucket-logs/',
      lifecycleRules: [
        {
          id: 'CloudFrontLogsLifecycleRule',
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(
                config.s3Config.cloudFrontLogsLifecycle.transitionToIADays,
              ),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(
                config.s3Config.cloudFrontLogsLifecycle.transitionToGlacierDays,
              ),
            },
          ],
          expiration: cdk.Duration.days(
            config.s3Config.cloudFrontLogsLifecycle.deletionDays,
          ),
        },
      ],
    });

    // Create WAF Web ACL - Always enabled for security
    // Use provided webAclArn if available (from WafRegionalStack), otherwise create local WAF
    let webAcl: wafv2.CfnWebACL | undefined;
    let webAclArnToUse: string;

    if (webAclArn) {
      // Use external WAF ARN (CloudFront WAF from us-east-1)
      webAclArnToUse = webAclArn;
    } else {
      // Create local WAF (for GovCloud/Regional scenarios)
      const wafScope = getWafScope(currentRegion);
      const rules: wafv2.CfnWebACL.RuleProperty[] = [];

      // AWS Managed Common Rule Set
      if (config.wafConfig.managedRules.coreRuleSet) {
        rules.push({
          name: 'AWSManagedRulesCommon',
          priority: 1,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesCommonRuleSet',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'AWSManagedRulesCore',
          },
        });
      }

      // AWS Managed Known Bad Inputs Rule Set
      if (config.wafConfig.managedRules.knownBadInputs) {
        rules.push({
          name: 'AWSManagedRulesKnownBadInputs',
          priority: 2,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesKnownBadInputsRuleSet',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'AWSManagedRulesKnownBadInputs',
          },
        });
      }

      // Amazon IP Reputation List
      if (config.wafConfig.managedRules.amazonIpReputation) {
        rules.push({
          name: 'AWSManagedRulesAmazonIPReputation',
          priority: 3,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: {
              vendorName: 'AWS',
              name: 'AWSManagedRulesAmazonIpReputationList',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'AWSManagedRulesAmazonIPReputation',
          },
        });
      }

      // Rate limiting rule
      if (config.wafConfig.rateLimiting.enabled) {
        rules.push({
          name: 'RateLimitRule',
          priority: 4,
          action: { block: {} },
          statement: {
            rateBasedStatement: {
              limit: config.wafConfig.rateLimiting.requestsPerMinute * 5, // WAF uses 5-minute rolling window
              aggregateKeyType: 'IP',
            },
          },
          visibilityConfig: {
            sampledRequestsEnabled: true,
            cloudWatchMetricsEnabled: true,
            metricName: 'RateLimitRule',
          },
        });
      }

      webAcl = new wafv2.CfnWebACL(this, 'WebAcl', {
        scope: wafScope,
        defaultAction: { allow: {} },
        rules: rules,
        name: createCdkId([
          config.deploymentName,
          config.appName,
          config.deploymentStage,
          'WebACL',
        ]),
        description: 'WAF Web ACL distribution protection',
        visibilityConfig: {
          sampledRequestsEnabled: true,
          cloudWatchMetricsEnabled: true,
          metricName: 'WebACL',
        },
        tags: config.tags?.map((tag) => ({ key: tag.Key, value: tag.Value })),
      });

      webAclArnToUse = webAcl.attrArn;

      // Create WAF logging configuration if enabled for local WAF
      if (config.wafConfig.logging.enabled && webAcl) {
        // Create log group for WAF logs
        const wafLogGroup = new logs.LogGroup(this, 'WafLogGroup', {
          logGroupName: `aws-waf-logs-${createCdkId([config.deploymentName, config.appName, config.deploymentStage])}`,
          retention: getCloudWatchRetentionDays(
            config.loggingConfig.wafLogRetentionDays,
          ),
          removalPolicy: config.removalPolicy,
        });

        new wafv2.CfnLoggingConfiguration(this, 'WebAclLogging', {
          resourceArn: webAcl.attrArn,
          logDestinationConfigs: [wafLogGroup.logGroupArn],
          redactedFields: [
            {
              singleHeader: {
                name: 'authorization',
              },
            },
            {
              singleHeader: {
                name: 'cookie',
              },
            },
          ],
        });
      }
    }

    // Create CloudFront distribution only if not in GovCloud
    let distribution: cloudfront.Distribution | undefined;
    let applicationUri: string;

    if (!isGovCloud) {
      const origin = new origins.LoadBalancerV2Origin(alb, {
        protocolPolicy: config.loadBalancerConfig.sslCertificateArn
          ? cloudfront.OriginProtocolPolicy.HTTPS_ONLY
          : cloudfront.OriginProtocolPolicy.HTTP_ONLY,
        httpsPort: config.loadBalancerConfig.sslCertificateArn
          ? 443
          : undefined,
        httpPort: config.loadBalancerConfig.sslCertificateArn ? undefined : 80,
      });

      // Create the origin request policy for UI with a unique name
      const originRequestPolicy = new cloudfront.OriginRequestPolicy(
        this,
        'OriginRequestPolicy',
        {
          headerBehavior: cloudfront.OriginRequestHeaderBehavior.all(),
          queryStringBehavior:
            cloudfront.OriginRequestQueryStringBehavior.all(),
          cookieBehavior: cloudfront.OriginRequestCookieBehavior.all(),
          originRequestPolicyName: createCdkId([
            config.deploymentName,
            config.appName,
            config.deploymentStage,
            config.region,
          ]),
        },
      );

      distribution = new cloudfront.Distribution(this, 'Distribution', {
        defaultBehavior: {
          origin: origin,
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          compress: true,
          originRequestPolicy: originRequestPolicy,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED, // Dev
        },
        additionalBehaviors: {
          '/api/*': {
            origin: origin,
            allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
            viewerProtocolPolicy:
              cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            originRequestPolicy: originRequestPolicy,
            cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          },
        },
        errorResponses: [
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
          },
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: '/index.html',
          },
        ],
        comment: 'CloudFront distribution to serve UI and API from ALB',
        enableLogging: true,
        logBucket: loggingBucket,
        logIncludesCookies: true,
        logFilePrefix: 'cloudfront-logs',
        priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
        webAclId: webAclArnToUse,
      });
      applicationUri = `https://${distribution.distributionDomainName}`;
    } else {
      // GovCloud: Use ALB directly with Regional WAF
      const protocol = config.loadBalancerConfig.sslCertificateArn
        ? 'https'
        : 'http';
      applicationUri = `${protocol}://${alb.loadBalancerDnsName}`;

      // Associate Regional WAF with ALB (only for local WAF)
      if (webAcl) {
        new wafv2.CfnWebACLAssociation(this, 'WebAclAssociation', {
          resourceArn: alb.loadBalancerArn,
          webAclArn: webAcl.attrArn,
        });
      }
    }

    // Set application URI and distribution reference
    this.applicationUri = applicationUri;
    this.distribution = distribution; // Defined in commercial AWS, undefined in GovCloud
    this.alb = alb;

    // Create SSM parameter for UI runtime configuration
    this.uiConfigParam = new ssm.StringParameter(this, 'UiConfigParameter', {
      parameterName: `${deploymentId}/ui-config`,
      stringValue: JSON.stringify({
        // Initial placeholder values that will be updated by the custom resource
        API_URI: 'placeholder',
        API_VERSION: apiVersion,
        COGNITO: {
          authority: userPoolDomainUrl,
          client_id: cdk.Fn.importValue(
            `${infrastructureStackName}-CognitoClientId`,
          ),
          redirect_uri: 'placeholder',
          post_logout_redirect_uri: 'placeholder',
          scope: 'openid',
          response_type: 'code',
          loadUserInfo: true,
          metadata: {
            authorization_endpoint: `${userPoolDomainUrl}/oauth2/authorize`,
            token_endpoint: `${userPoolDomainUrl}/oauth2/token`,
            userinfo_endpoint: `${userPoolDomainUrl}/oauth2/userInfo`,
            end_session_endpoint: `${userPoolDomainUrl}/logout`,
          },
        },
      }),
      description: 'Runtime configuration for UI container',
      tier: ssm.ParameterTier.STANDARD,
    });

    // Create a custom resource that will update the SSM parameter
    // This allows us to incorporate dynamic values from CloudFormation
    const configUpdater = new lambda.Function(this, 'ConfigUpdater', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda-config')),
      timeout: cdk.Duration.minutes(2),
      environment: {
        APPLICATION_URI: this.applicationUri,
      },
    });

    // Grant the Lambda permissions to update SSM parameter
    configUpdater.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['ssm:PutParameter', 'ssm:GetParameter'],
        resources: [this.uiConfigParam.parameterArn],
        effect: iam.Effect.ALLOW,
      }),
    );

    // Grant the Lambda permission to update Cognito
    configUpdater.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'cognito-idp:UpdateUserPoolClient',
          'cognito-idp:DescribeUserPoolClient',
        ],
        resources: ['*'],
        effect: iam.Effect.ALLOW,
      }),
    );

    // Create the custom resource to update the SSM parameter
    new cr.AwsCustomResource(this, 'UpdateConfig', {
      onCreate: {
        service: 'Lambda',
        action: 'invoke',
        parameters: {
          FunctionName: configUpdater.functionName,
          Payload: JSON.stringify({
            ResourceProperties: {
              applicationUri: this.applicationUri,
              apiVersion: apiVersion,
              userPoolDomainUrl: userPoolDomainUrl,
              clientId: cdk.Fn.importValue(
                `${infrastructureStackName}-CognitoClientId`,
              ),
              parameterName: this.uiConfigParam.parameterName,
              userPoolId: cdk.Fn.importValue(
                `${infrastructureStackName}-UserPoolId`,
              ),
              uiTitle: config.uiConfig?.title || '',
              timestamp: new Date().toISOString(), // Force execution on each deployment
            },
          }),
        },
        physicalResourceId: cr.PhysicalResourceId.of('config-updater-resource'),
      },
      onUpdate: {
        service: 'Lambda',
        action: 'invoke',
        parameters: {
          FunctionName: configUpdater.functionName,
          Payload: JSON.stringify({
            ResourceProperties: {
              applicationUri: this.applicationUri,
              apiVersion: apiVersion,
              userPoolDomainUrl: userPoolDomainUrl,
              clientId: cdk.Fn.importValue(
                `${infrastructureStackName}-CognitoClientId`,
              ),
              parameterName: this.uiConfigParam.parameterName,
              userPoolId: cdk.Fn.importValue(
                `${infrastructureStackName}-UserPoolId`,
              ),
              uiTitle: config.uiConfig?.title || '',
              timestamp: new Date().toISOString(), // Force execution on each update too
            },
          }),
        },
        physicalResourceId: cr.PhysicalResourceId.of('config-updater-resource'),
      },
      policy: cr.AwsCustomResourcePolicy.fromStatements([
        new iam.PolicyStatement({
          actions: ['lambda:InvokeFunction'],
          resources: [configUpdater.functionArn],
          effect: iam.Effect.ALLOW,
        }),
      ]),
    });

    // CFN outputs
    new cdk.CfnOutput(this, 'DistributionStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the distribution stack',
    });

    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: this.alb.loadBalancerDnsName,
      description: 'DNS name of the Application Load Balancer',
    });

    new cdk.CfnOutput(this, 'AlbArn', {
      value: this.alb.loadBalancerArn,
      description: 'ARN of the Application Load Balancer',
    });

    new cdk.CfnOutput(this, 'AlbUrl', {
      value: `${config.loadBalancerConfig.sslCertificateArn ? 'https' : 'http'}://${this.alb.loadBalancerDnsName}`,
      description: 'Full URL of the ALB',
    });

    new cdk.CfnOutput(this, 'AlbPlacement', {
      value: config.loadBalancerConfig.albPlacement,
      description: 'ALB placement strategy (public/private/isolated)',
    });

    new cdk.CfnOutput(this, 'ApiTargetGroupArn', {
      value: this.apiTargetGroup.targetGroupArn,
      description: 'ARN of the API target group',
    });

    new cdk.CfnOutput(this, 'UiTargetGroupArn', {
      value: this.uiTargetGroup.targetGroupArn,
      description: 'ARN of the UI target group',
    });

    // CloudFront outputs (only in commercial AWS)
    if (this.distribution) {
      new cdk.CfnOutput(this, 'DistributionDomainName', {
        value: this.distribution.distributionDomainName,
        description: 'Domain name of the CloudFront distribution',
      });

      new cdk.CfnOutput(this, 'DistributionId', {
        value: this.distribution.distributionId,
        description: 'ID of the CloudFront distribution',
      });
    }

    // WAF outputs - always present since WAF is always enabled
    new cdk.CfnOutput(this, 'WebAclArn', {
      value: webAclArnToUse,
      description: 'ARN of the WAF Web ACL',
    });

    new cdk.CfnOutput(this, 'WebAclId', {
      value: webAcl
        ? webAcl.attrId
        : webAclArnToUse.split('/').pop() || 'external-waf',
      description: 'ID of the WAF Web ACL',
    });
  }
}
