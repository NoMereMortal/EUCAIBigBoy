// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// WAF stack for CloudFront - must be deployed in us-east-1
import * as cdk from 'aws-cdk-lib';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import type { Construct } from 'constructs';

import type { Config } from './schema';
import { createCdkId, getCloudWatchRetentionDays } from './utils';

export interface WafRegionalStackProps extends cdk.StackProps {
  config: Config;
}

export class WafRegionalStack extends cdk.Stack {
  public readonly webAclArn: string;
  public readonly webAclId: string;

  constructor(scope: Construct, id: string, props: WafRegionalStackProps) {
    super(scope, id, props);

    const { config } = props;

    // Build WAF rules array
    const rules: wafv2.CfnWebACL.RuleProperty[] = [];

    // AWS Managed Common Rule Set
    if (config.wafConfig.managedRules.coreRuleSet) {
      rules.push({
        name: 'AWSManagedRulesCommon',
        priority: rules.length + 1,
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
        priority: rules.length + 1,
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
        priority: rules.length + 1,
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

    // Add rate limiting rule if enabled
    if (config.wafConfig.rateLimiting.enabled) {
      rules.push({
        name: 'RateLimitRule',
        priority: rules.length + 1,
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

    // Create WAF Web ACL - Always CLOUDFRONT scope for this stack
    const webAcl = new wafv2.CfnWebACL(this, 'WebAcl', {
      scope: 'CLOUDFRONT',
      defaultAction: { allow: {} },
      rules: rules,
      name: createCdkId([
        config.deploymentName,
        config.appName,
        config.deploymentStage,
        'WebACL',
      ]),
      description: 'WAF Web ACL for CloudFront distribution protection',
      visibilityConfig: {
        sampledRequestsEnabled: true,
        cloudWatchMetricsEnabled: true,
        metricName: 'WebACL',
      },
      tags: config.tags?.map((tag) => ({ key: tag.Key, value: tag.Value })),
    });

    // Create WAF logging configuration if enabled
    if (config.wafConfig.logging.enabled) {
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
      });
    }

    // Export WAF properties
    this.webAclArn = webAcl.attrArn;
    this.webAclId = webAcl.attrId;

    // Outputs
    new cdk.CfnOutput(this, 'WebAclArn', {
      value: this.webAclArn,
      description: 'ARN of the WAF Web ACL',
    });

    new cdk.CfnOutput(this, 'WebAclId', {
      value: this.webAclId,
      description: 'ID of the WAF Web ACL',
    });
  }
}
