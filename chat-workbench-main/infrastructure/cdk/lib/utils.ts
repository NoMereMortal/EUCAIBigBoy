// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Utility functions.
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';

import * as fs from 'fs';
import * as path from 'path';

import type { Config } from './schema';

export const projectRoot = path.resolve(__dirname, '../../..');
const IAM_DIR = path.join(__dirname, 'iam');

/**
 * Extract policy statements from JSON file.
 *
 * @param {string} serviceName - AWS service name.
 * @returns {iam.PolicyStatement[]} - Extracted IAM policy statements.
 */
const extractPolicyStatementsFromJson = (
  serviceName: string,
): iam.PolicyStatement[] => {
  const statementData = fs.readFileSync(
    path.join(IAM_DIR, `${serviceName.toLowerCase()}.json`),
    'utf8',
  );
  const statements = JSON.parse(statementData).Statement;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  statements.forEach((statement: any) => {
    if (statement.Resource) {
      statement.Resource = []
        .concat(statement.Resource)
        .map((resource: string) => {
          return resource
            .replace(/\${AWS::AccountId}/gi, cdk.Aws.ACCOUNT_ID)
            .replace(/\${AWS::Region}/gi, cdk.Aws.REGION)
            .replace(/\${AWS::Partition}/gi, cdk.Aws.PARTITION);
        });
    }
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return statements.map((statement: any) =>
    iam.PolicyStatement.fromJson(statement),
  );
};

/**
 * Wrapper to get IAM policy statements.
 *
 * @param {string} serviceName - AWS service name.
 * @returns {iam.PolicyStatement[]} - Extracted IAM policy statements.
 */
export const getIamPolicyStatements = (
  serviceName: string,
): iam.PolicyStatement[] => {
  return extractPolicyStatementsFromJson(serviceName);
};

/**
 * Creates a unique CDK ID using configuration data. The CDK ID is used to uniquely identify resources in the AWS
 * Cloud Development Kit (CDK). The maximum length of the CDK ID is 64 characters.
 *
 * @param {string[]} idParts - Name of the resource.
 * @param {number} [maxLength==64] - Maximum length of CDK ID.
 * @throws {Error} - Throws an error if the generated CDK ID is longer than 64 characters.
 * @returns {string} - Generated CDK ID for the model resource.
 */
export function createCdkId(idParts: string[], maxLength: number = 64): string {
  let cdkId = idParts.join('-').toLowerCase();
  const length = cdkId.length;

  if (length > maxLength) {
    // Truncate the last part to ensure the total length doesn't exceed maxLength
    const lastPartIndex = idParts.length - 1;
    idParts[lastPartIndex] = idParts[lastPartIndex].slice(
      0,
      maxLength - (length - idParts[lastPartIndex].length),
    );
    cdkId = idParts.join('-').toLowerCase();
  }

  // Ensure the first character is a lowercase letter
  if (!/^[a-z]/.test(cdkId)) {
    cdkId = 'a-' + cdkId.slice(1);
  }

  // Ensure the ID contains only lowercase letters, digits, and hyphens
  cdkId = cdkId.replace(/[^a-z0-9-]/g, '');

  return cdkId;
}

/**
 * Detects if region is AWS GovCloud
 *
 * @param region AWS region
 * @returns true if GovCloud region
 */
export function isGovCloudRegion(region?: string): boolean {
  return region?.startsWith('us-gov-') || false;
}

/**
 * Checks if AWS service is available in current region
 * @param service AWS service name
 * @param region AWS region
 * @returns true if service is available
 */
export function isServiceAvailable(service: string, region?: string): boolean {
  const isGovCloud = isGovCloudRegion(region);

  // Services not available in GovCloud
  const govCloudUnavailable = ['cloudfront'];

  if (isGovCloud && govCloudUnavailable.includes(service)) {
    return false;
  }

  return true;
}

/**
 * Gets appropriate WAF scope based on CloudFront availability
 *
 * @param region AWS region
 * @returns WAF scope (CLOUDFRONT or REGIONAL)
 */
export function getWafScope(region?: string): 'CLOUDFRONT' | 'REGIONAL' {
  return isServiceAvailable('cloudfront', region) ? 'CLOUDFRONT' : 'REGIONAL';
}

/**
 * Gets the correct deployment region for WAF resources
 *
 * CloudFront WAF must be deployed in us-east-1 regardless of stack region
 * @param region Current deployment region
 * @returns Correct region for WAF deployment
 */
export function getWafDeploymentRegion(region?: string): string {
  return getWafScope(region) === 'CLOUDFRONT'
    ? 'us-east-1'
    : region || 'us-east-1';
}

/**
 * Maps retention days to CloudWatch RetentionDays enum
 *
 * Throws an error if the retention period is not valid
 * @param days Number of days to retain logs
 * @returns CloudWatch RetentionDays enum value
 * @throws Error if retention period is invalid
 */
export function getCloudWatchRetentionDays(days: number): logs.RetentionDays {
  const retentionMap: Record<number, logs.RetentionDays> = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    120: logs.RetentionDays.FOUR_MONTHS,
    150: logs.RetentionDays.FIVE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
    400: logs.RetentionDays.THIRTEEN_MONTHS,
    545: logs.RetentionDays.EIGHTEEN_MONTHS,
    731: logs.RetentionDays.TWO_YEARS,
    1827: logs.RetentionDays.FIVE_YEARS,
    3653: logs.RetentionDays.TEN_YEARS,
  };

  const retention = retentionMap[days];
  if (!retention) {
    const validDays = Object.keys(retentionMap).join(', ');
    throw new Error(
      `Invalid CloudWatch log retention days: ${days}. Valid values are: ${validDays}`,
    );
  }

  return retention;
}

/**
 * Interface for VPC subnet availability results
 */
export interface VpcSubnetValidation {
  hasPublic: boolean;
  hasPrivate: boolean;
  hasIsolated: boolean;
  publicCount: number;
  privateCount: number;
  isolatedCount: number;
}

/**
 * Validates VPC subnet availability for different ALB placement strategies
 *
 * @param vpc VPC to validate
 * @returns VpcSubnetValidation object with subnet availability information
 */
export function validateVpcSubnets(vpc: ec2.IVpc): VpcSubnetValidation {
  const publicSubnets = vpc.publicSubnets || [];
  const privateSubnets = vpc.privateSubnets || [];
  const isolatedSubnets = vpc.isolatedSubnets || [];

  return {
    hasPublic: publicSubnets.length > 0,
    hasPrivate: privateSubnets.length > 0,
    hasIsolated: isolatedSubnets.length > 0,
    publicCount: publicSubnets.length,
    privateCount: privateSubnets.length,
    isolatedCount: isolatedSubnets.length,
  };
}

/**
 * Validates ALB placement requirements against VPC subnet availability
 * @param vpc VPC to validate
 * @param albPlacement ALB placement strategy
 * @throws Error if required subnets are not available
 */
export function validateAlbPlacement(
  vpc: ec2.IVpc,
  albPlacement: 'public' | 'private' | 'isolated',
): void {
  const validation = validateVpcSubnets(vpc);

  switch (albPlacement) {
    case 'public':
      if (!validation.hasPublic) {
        throw new Error(
          `ALB placement 'public' requires public subnets, but none found in VPC. ` +
            `Available subnets: ${validation.privateCount} private, ${validation.isolatedCount} isolated.`,
        );
      }
      break;
    case 'private':
      if (!validation.hasPrivate) {
        throw new Error(
          `ALB placement 'private' requires private subnets with NAT gateway access, but none found in VPC. ` +
            `Available subnets: ${validation.publicCount} public, ${validation.isolatedCount} isolated.`,
        );
      }
      break;
    case 'isolated':
      if (!validation.hasIsolated) {
        throw new Error(
          `ALB placement 'isolated' requires isolated subnets, but none found in VPC. ` +
            `Available subnets: ${validation.publicCount} public, ${validation.privateCount} private.`,
        );
      }
      break;
    default:
      throw new Error(
        `Invalid ALB placement: ${albPlacement}. Valid values are: public, private, isolated.`,
      );
  }
}

/**
 * Validates that resources requiring isolated subnets can coexist
 *
 * @param vpc VPC to validate
 * @param albPlacement ALB placement strategy
 * @param hasElastiCache Whether ElastiCache is enabled (requires isolated subnets)
 * @throws Error if isolated subnet requirements conflict
 */
export function validateIsolatedSubnetCompatibility(
  vpc: ec2.IVpc,
  albPlacement: 'public' | 'private' | 'isolated',
  hasElastiCache: boolean,
): void {
  const validation = validateVpcSubnets(vpc);
  const albUsesIsolated = albPlacement === 'isolated';

  if ((albUsesIsolated || hasElastiCache) && !validation.hasIsolated) {
    const services = [];
    if (albUsesIsolated) services.push('ALB (isolated placement)');
    if (hasElastiCache) services.push('ElastiCache');

    throw new Error(
      `The following services require isolated subnets: ${services.join(', ')}, but none found in VPC. ` +
        `Available subnets: ${validation.publicCount} public, ${validation.privateCount} private.`,
    );
  }

  // Warn if only one isolated subnet but multiple services need it
  if (albUsesIsolated && hasElastiCache && validation.isolatedCount === 1) {
    // This is actually fine - both ALB and ElastiCache can share the same isolated subnet
    // No error needed, just a note that they'll coexist in the same subnet
  }
}

/**
 * Gets subnet selection configuration for ALB based on placement strategy
 *
 * @param albPlacement ALB placement strategy
 * @returns Subnet selection configuration for ALB
 */
export function getAlbSubnetSelection(
  albPlacement: 'public' | 'private' | 'isolated',
): {
  internetFacing: boolean;
  subnetType: ec2.SubnetType;
} {
  switch (albPlacement) {
    case 'public':
      return {
        internetFacing: true,
        subnetType: ec2.SubnetType.PUBLIC,
      };
    case 'private':
      return {
        internetFacing: false,
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      };
    case 'isolated':
      return {
        internetFacing: false,
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      };
    default:
      throw new Error(
        `Invalid ALB placement: ${albPlacement}. Valid values are: public, private, isolated.`,
      );
  }
}

/**
 * Filters subnets based on configured subnet IDs
 *
 * @param allSubnets All available subnets from VPC discovery
 * @param configuredSubnetIds Optional array of specific subnet IDs to use
 * @returns Filtered subnets - either the specified ones or all if none specified
 */
export function getFilteredSubnets(
  allSubnets: ec2.ISubnet[],
  configuredSubnetIds?: string[],
): ec2.ISubnet[] {
  if (!configuredSubnetIds?.length) {
    return allSubnets; // Use all subnets if none specifically configured
  }

  const filteredSubnets = allSubnets.filter((subnet) =>
    configuredSubnetIds.includes(subnet.subnetId),
  );

  return filteredSubnets;
}

/**
 * Validates that all configured subnet IDs exist in the discovered VPC subnets
 *
 * @param allSubnets All available subnets from VPC discovery
 * @param configuredSubnetIds Array of configured subnet IDs
 * @param subnetType Type of subnet for error messaging
 * @throws Error if configured subnets are not found in VPC
 */
export function validateConfiguredSubnets(
  allSubnets: ec2.ISubnet[],
  configuredSubnetIds: string[],
  subnetType: string,
): void {
  const availableSubnetIds = allSubnets.map((subnet) => subnet.subnetId);
  const missingSubnets = configuredSubnetIds.filter(
    (configuredId) => !availableSubnetIds.includes(configuredId),
  );

  if (missingSubnets.length > 0) {
    throw new Error(
      `Configured ${subnetType} subnet IDs not found in VPC: ${missingSubnets.join(', ')}. ` +
        `Available ${subnetType} subnets: ${availableSubnetIds.join(', ')}`,
    );
  }
}

/**
 * Validates that filtered subnets meet AWS service deployment requirements.
 * ALB and ElastiCache both require subnets in multiple Availability Zones.
 * Also validates service-specific subnet overrides.
 *
 * @param config Configuration object containing VPC and load balancer settings
 * @param allSubnets All subnets discovered in the VPC (for service override validation)
 * @param filteredPublicSubnets Filtered public subnets
 * @param filteredPrivateSubnets Filtered private subnets
 * @param filteredIsolatedSubnets Filtered isolated subnets
 * @throws Error if AWS service requirements are not met
 */
export function validateFilteredSubnets(
  config: Config,
  allSubnets: ec2.ISubnet[],
  filteredPublicSubnets: ec2.ISubnet[],
  filteredPrivateSubnets: ec2.ISubnet[],
  filteredIsolatedSubnets: ec2.ISubnet[],
): void {
  const hasCustomSubnets =
    (config.vpcConfig?.publicSubnetIds &&
      config.vpcConfig.publicSubnetIds.length > 0) ||
    (config.vpcConfig?.privateSubnetIds &&
      config.vpcConfig.privateSubnetIds.length > 0) ||
    (config.vpcConfig?.isolatedSubnetIds &&
      config.vpcConfig.isolatedSubnetIds.length > 0) ||
    (config.vpcConfig?.serviceSubnets?.ecs &&
      config.vpcConfig.serviceSubnets.ecs.length > 0) ||
    (config.vpcConfig?.serviceSubnets?.elasticache &&
      config.vpcConfig.serviceSubnets.elasticache.length > 0) ||
    (config.vpcConfig?.serviceSubnets?.alb &&
      config.vpcConfig.serviceSubnets.alb.length > 0);

  if (!hasCustomSubnets) {
    return; // No custom subnets configured, validation not needed
  }

  // Get actual subnets that will be used by each service
  const albSubnets = getServiceSubnets('alb', config, allSubnets, {
    public: filteredPublicSubnets,
    private: filteredPrivateSubnets,
    isolated: filteredIsolatedSubnets,
  });

  const elasticacheSubnets = getServiceSubnets(
    'elasticache',
    config,
    allSubnets,
    {
      public: filteredPublicSubnets,
      private: filteredPrivateSubnets,
      isolated: filteredIsolatedSubnets,
    },
  );

  // ALB requires at least 2 subnets
  if (albSubnets.length < 2) {
    const hasAlbOverride =
      config.vpcConfig?.serviceSubnets?.alb &&
      config.vpcConfig.serviceSubnets.alb.length > 0;
    const errorSuggestion = hasAlbOverride
      ? 'Please specify more subnet IDs in vpcConfig.serviceSubnets.alb.'
      : `Please specify more subnet IDs in vpcConfig.${config.loadBalancerConfig?.albPlacement}SubnetIds.`;

    throw new Error(
      `ALB requires at least 2 subnets. Found ${albSubnets.length} subnets. ${errorSuggestion}`,
    );
  }

  // ALB requires subnets in at least 2 different Availability Zones (AWS requirement)
  const albAvailabilityZones = new Set(
    albSubnets.map((subnet) => subnet.availabilityZone),
  );
  if (albAvailabilityZones.size < 2) {
    const hasAlbOverride =
      config.vpcConfig?.serviceSubnets?.alb &&
      config.vpcConfig.serviceSubnets.alb.length > 0;
    const errorSuggestion = hasAlbOverride
      ? 'Please specify subnet IDs from different AZs in vpcConfig.serviceSubnets.alb.'
      : `Please specify subnet IDs from different AZs in vpcConfig.${config.loadBalancerConfig?.albPlacement}SubnetIds.`;

    throw new Error(
      `ALB requires subnets in at least 2 different Availability Zones. ` +
        `Subnets are all in AZ: ${Array.from(albAvailabilityZones).join(', ')}. ${errorSuggestion}`,
    );
  }

  // ElastiCache requires at least 2 subnets (AWS requirement)
  if (elasticacheSubnets.length < 2) {
    const hasElasticacheOverride =
      config.vpcConfig?.serviceSubnets?.elasticache &&
      config.vpcConfig.serviceSubnets.elasticache.length > 0;
    const errorSuggestion = hasElasticacheOverride
      ? 'Please specify at least 2 subnet IDs in vpcConfig.serviceSubnets.elasticache.'
      : 'Please specify at least 2 subnet IDs in vpcConfig.isolatedSubnetIds.';

    throw new Error(
      `ElastiCache requires at least 2 subnets. Found ${elasticacheSubnets.length}. ${errorSuggestion}`,
    );
  }

  // ElastiCache requires subnets in at least 2 different Availability Zones (AWS requirement)
  const elasticacheAvailabilityZones = new Set(
    elasticacheSubnets.map((subnet) => subnet.availabilityZone),
  );
  if (elasticacheAvailabilityZones.size < 2) {
    const hasElasticacheOverride =
      config.vpcConfig?.serviceSubnets?.elasticache &&
      config.vpcConfig.serviceSubnets.elasticache.length > 0;
    const errorSuggestion = hasElasticacheOverride
      ? 'Please specify subnet IDs from different AZs in vpcConfig.serviceSubnets.elasticache.'
      : 'Please specify subnet IDs from different AZs in vpcConfig.isolatedSubnetIds.';

    throw new Error(
      `ElastiCache requires subnets in at least 2 different Availability Zones. ` +
        `Subnets are all in AZ: ${Array.from(elasticacheAvailabilityZones).join(', ')}. ${errorSuggestion}`,
    );
  }
}

// Service subnet selection utilities

/**
 * Service types for subnet selection
 */
export type ServiceType = 'ecs' | 'elasticache' | 'alb';

/**
 * Extracts the repository name from a full ECR repository URI.
 *
 * @param repositoryUri Full ECR repository URI (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo)
 * @returns Repository name (e.g., my-repo)
 */
export function extractEcrRepositoryName(repositoryUri: string): string {
  const parts = repositoryUri.split('/');
  if (parts.length < 2) {
    throw new Error(`Invalid ECR repository URI: ${repositoryUri}`);
  }
  return parts.slice(1).join('/');
}

/**
 * Builds ECR repository ARN from repository URI and AWS account details.
 *
 * @param repositoryUri Full ECR repository URI
 * @param region AWS region
 * @param accountId AWS account ID
 * @returns ECR repository ARN
 */
export function buildEcrRepositoryArn(
  repositoryUri: string,
  region: string,
  accountId: string,
): string {
  const repositoryName = extractEcrRepositoryName(repositoryUri);
  return `arn:${cdk.Aws.PARTITION}:ecr:${region}:${accountId}:repository/${repositoryName}`;
}

/**
 * Validates ECR repository URI format.
 *
 * @param repositoryUri ECR repository URI to validate
 * @returns true if valid, false otherwise
 */
export function isValidEcrRepositoryUri(repositoryUri: string): boolean {
  return /^\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com\/[a-z0-9-_/]+$/.test(
    repositoryUri,
  );
}

/**
 * Gets subnets for a specific service, respecting service-specific overrides.
 * Service overrides take precedence over type-based subnet selection.
 *
 * @param service Service type requesting subnets
 * @param config Configuration object containing VPC and service subnet settings
 * @param allSubnets All subnets discovered in the VPC (for service override filtering)
 * @param filteredTypeSubnets Pre-filtered subnets by type (public/private/isolated)
 * @returns Array of subnets for the service to use
 */
export function getServiceSubnets(
  service: ServiceType,
  config: Config,
  allSubnets: ec2.ISubnet[],
  filteredTypeSubnets: {
    public: ec2.ISubnet[];
    private: ec2.ISubnet[];
    isolated: ec2.ISubnet[];
  },
): ec2.ISubnet[] {
  // Check for service-specific override first
  const serviceOverrideIds = config.vpcConfig?.serviceSubnets?.[service];
  if (serviceOverrideIds && serviceOverrideIds.length > 0) {
    const overrideSubnets = getFilteredSubnets(allSubnets, serviceOverrideIds);

    // For ALB, validate that override subnets match the expected placement type
    if (service === 'alb') {
      const albPlacement = config.loadBalancerConfig?.albPlacement || 'public';
      let expectedSubnets: ec2.ISubnet[];
      let placementName: string;

      switch (albPlacement) {
        case 'public':
          expectedSubnets = filteredTypeSubnets.public;
          placementName = 'public';
          break;
        case 'private':
          expectedSubnets = filteredTypeSubnets.private;
          placementName = 'private';
          break;
        case 'isolated':
          expectedSubnets = filteredTypeSubnets.isolated;
          placementName = 'isolated';
          break;
        default:
          throw new Error(`Invalid ALB placement: ${albPlacement}`);
      }

      // Validate that all override subnets are of the correct type
      const expectedSubnetIds = new Set(expectedSubnets.map((s) => s.subnetId));
      const invalidSubnets = overrideSubnets.filter(
        (s) => !expectedSubnetIds.has(s.subnetId),
      );

      if (invalidSubnets.length > 0) {
        throw new Error(
          `ALB placement is '${albPlacement}' but serviceSubnets.alb contains non-${placementName} subnets: ` +
            `${invalidSubnets.map((s) => s.subnetId).join(', ')}. ` +
            `Please ensure all subnets in serviceSubnets.alb are ${placementName} subnets, or change albPlacement setting.`,
        );
      }
    }

    return overrideSubnets;
  }

  // Fall back to service-specific logic using type-based filtered subnets
  switch (service) {
    case 'ecs':
      // ECS prefers private subnets with egress for ECR access, falls back to isolated
      return filteredTypeSubnets.private.length > 0
        ? filteredTypeSubnets.private
        : filteredTypeSubnets.isolated;

    case 'elasticache':
      // ElastiCache requires isolated subnets
      return filteredTypeSubnets.isolated;

    case 'alb': {
      // ALB uses placement-based selection
      const albPlacement = config.loadBalancerConfig?.albPlacement || 'public';
      switch (albPlacement) {
        case 'public':
          return filteredTypeSubnets.public;
        case 'private':
          return filteredTypeSubnets.private;
        case 'isolated':
          return filteredTypeSubnets.isolated;
        default:
          throw new Error(`Invalid ALB placement: ${albPlacement}`);
      }
    }

    default:
      throw new Error(`Unknown service type: ${service}`);
  }
}
