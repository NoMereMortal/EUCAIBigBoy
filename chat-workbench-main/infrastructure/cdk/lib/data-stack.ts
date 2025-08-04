// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Data resources stack.
import * as cdk from 'aws-cdk-lib';
import type * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as s3 from 'aws-cdk-lib/aws-s3';
import type { Construct } from 'constructs';
import { bedrock } from '@cdklabs/generative-ai-cdk-constructs';

import type { BaseProps, Config } from './schema';
import { BEDROCK_FOUNDATION_MODELS } from './schema';
import { createCdkId, getServiceSubnets } from './utils';

/**
 * Properties for the DataStack.
 *
 * @property {cdk.aws_ec2.IVpc} vpc - VPC for the data resources.
 * @property {string} taskRoleArn - ARN of the ECS task role for OpenSearch access.
 * @property {ec2.ISecurityGroup} serviceSg - ECS service security group for ElastiCache access.
 * @property {ec2.ISecurityGroup} elasticacheSg - Security group for ElastiCache Serverless.
 */
export interface DataStackProps extends cdk.StackProps, BaseProps {
  vpc: cdk.aws_ec2.IVpc;
  taskRoleArn: string;
  serviceSg: ec2.ISecurityGroup;
  elasticacheSg: ec2.ISecurityGroup;
  allSubnets: ec2.ISubnet[];
  filteredPublicSubnets: ec2.ISubnet[];
  filteredPrivateSubnets: ec2.ISubnet[];
  filteredIsolatedSubnets: ec2.ISubnet[];
}

/**
 * Stack for data resources including DynamoDB tables, ElastiCache Serverless, and OpenSearch Serverless.
 */
export class DataStack extends cdk.Stack {
  public dataTable: dynamodb.Table;
  public elastiCacheServerless: elasticache.CfnServerlessCache;
  public fileBucket?: cdk.aws_s3.Bucket;
  public documentsCollection?: opensearchserverless.CfnCollection;
  public knowledgeBase?: bedrock.VectorKnowledgeBase;
  public knowledgeBaseDataBucket?: s3.Bucket;
  public knowledgeBaseSupplementalBucket?: s3.Bucket;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    const {
      config,
      vpc,
      elasticacheSg,
      allSubnets,
      filteredPublicSubnets,
      filteredPrivateSubnets,
      filteredIsolatedSubnets,
    } = props;

    // Create DynamoDB tables
    this.createDynamoDbTables(config);

    // Create ElastiCache Serverless
    this.createElastiCacheServerless(vpc, config, elasticacheSg, allSubnets, {
      public: filteredPublicSubnets,
      private: filteredPrivateSubnets,
      isolated: filteredIsolatedSubnets,
    });

    // Create S3 bucket for file storage if enabled
    if (
      config.dataConfig.fileStorageEnabled !== false &&
      config.dataConfig.fileStorageType === 's3'
    ) {
      this.createFileBucket(config);
    }

    // Create OpenSearch Serverless collection if enabled
    if (config.dataConfig.openSearchEnabled) {
      this.createDocumentsCollection(config, props.taskRoleArn);
    }

    // Create Bedrock Knowledge Base if enabled (independent of other services)
    if (config.dataConfig.bedrockKnowledgeBaseEnabled) {
      this.createBedrockKnowledgeBase(config, props.taskRoleArn);
    }

    // Grant permissions to the task role ARN
    this.grantPermissionsToTaskRole(props.taskRoleArn);

    // CFN outputs - Stack identification
    new cdk.CfnOutput(this, 'DataStackName', {
      value: cdk.Stack.of(this).stackName,
      description: 'Name of the data stack',
    });
  }

  /**
   * Grant permissions to the ECS task role for accessing data resources.
   *
   * @param {string} taskRoleArn - ARN of the ECS task role
   */
  private grantPermissionsToTaskRole(taskRoleArn: string): void {
    // Import the task role from ARN
    const taskRole = iam.Role.fromRoleArn(
      this,
      'ImportedTaskRole',
      taskRoleArn,
    );

    // Create and attach inline policy to the role
    const policyStatements: iam.PolicyStatement[] = [];

    // Add DynamoDB permissions
    policyStatements.push(...this.getDynamoDbPolicyStatements());

    // Add ElastiCache permissions if serverless cache exists
    if (this.elastiCacheServerless) {
      policyStatements.push(...this.getElastiCachePolicyStatements());
    }

    // Add Bedrock permissions
    policyStatements.push(...this.getBedrockPolicyStatements());

    // Add S3 permissions if bucket exists
    if (this.fileBucket) {
      policyStatements.push(...this.getS3PolicyStatements());
    }

    // Add OpenSearch permissions if collection exists
    if (this.documentsCollection) {
      policyStatements.push(...this.getOpenSearchPolicyStatements());
    }

    // Add Knowledge Base permissions if exists
    if (this.knowledgeBase && this.knowledgeBaseDataBucket) {
      policyStatements.push(...this.getKnowledgeBasePolicyStatements());
    }

    // Create inline policy with all statements
    if (policyStatements.length > 0) {
      const inlinePolicy = new iam.Policy(this, 'DataStackTaskRolePolicy', {
        statements: policyStatements,
      });
      taskRole.attachInlinePolicy(inlinePolicy);
    }
  }

  /**
   * Get DynamoDB policy statements.
   */
  private getDynamoDbPolicyStatements(): iam.PolicyStatement[] {
    if (!this.dataTable) return [];

    return [
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'dynamodb:GetItem',
          'dynamodb:PutItem',
          'dynamodb:UpdateItem',
          'dynamodb:DeleteItem',
          'dynamodb:Query',
          'dynamodb:Scan',
          'dynamodb:BatchGetItem',
          'dynamodb:BatchWriteItem',
          'dynamodb:DescribeTable',
        ],
        resources: [this.dataTable.tableArn],
      }),
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['dynamodb:Query', 'dynamodb:Scan'],
        resources: [`${this.dataTable.tableArn}/index/*`],
      }),
    ];
  }

  /**
   * Get ElastiCache Serverless policy statements.
   */
  private getElastiCachePolicyStatements(): iam.PolicyStatement[] {
    if (!this.elastiCacheServerless) return [];

    return [
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'elasticache:Connect',
          'elasticache:DescribeServerlessCaches',
          'elasticache:DescribeUserGroups',
          'elasticache:DescribeUsers',
        ],
        resources: [this.elastiCacheServerless.attrArn],
      }),
    ];
  }

  /**
   * Get Bedrock policy statements.
   */
  private getBedrockPolicyStatements(): iam.PolicyStatement[] {
    return [
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
          'bedrock:ApplyGuardrail',
          'bedrock:ListFoundationModels',
          'bedrock:GetFoundationModel',
          'bedrock:ListCustomModels',
          'bedrock:GetCustomModel',
        ],
        resources: ['*'],
      }),
    ];
  }

  /**
   * Get S3 policy statements.
   */
  private getS3PolicyStatements(): iam.PolicyStatement[] {
    if (!this.fileBucket) return [];

    return [
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          's3:GetObject',
          's3:PutObject',
          's3:DeleteObject',
          's3:GetObjectVersion',
          's3:ListBucket',
        ],
        resources: [
          this.fileBucket.bucketArn,
          `${this.fileBucket.bucketArn}/*`,
        ],
      }),
    ];
  }

  /**
   * Get OpenSearch Serverless policy statements.
   */
  private getOpenSearchPolicyStatements(): iam.PolicyStatement[] {
    if (!this.documentsCollection) return [];

    const collectionName = this.documentsCollection.name;
    if (!collectionName) return [];

    return [
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'aoss:CreateCollectionItems',
          'aoss:DeleteCollectionItems',
          'aoss:UpdateCollectionItems',
          'aoss:DescribeCollectionItems',
          'aoss:CreateIndex',
          'aoss:DeleteIndex',
          'aoss:UpdateIndex',
          'aoss:DescribeIndex',
          'aoss:ReadDocument',
          'aoss:WriteDocument',
        ],
        resources: [
          `arn:${cdk.Aws.PARTITION}:aoss:${this.region}:${this.account}:collection/${collectionName}`,
          `arn:${cdk.Aws.PARTITION}:aoss:${this.region}:${this.account}:index/${collectionName}/*`,
        ],
      }),
    ];
  }

  /**
   * Get Bedrock Knowledge Base policy statements.
   */
  private getKnowledgeBasePolicyStatements(): iam.PolicyStatement[] {
    if (!this.knowledgeBase || !this.knowledgeBaseDataBucket) return [];

    return [
      // Permissions to retrieve from Knowledge Base
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'],
        resources: [this.knowledgeBase.knowledgeBaseArn],
      }),
      // Permissions to access the Knowledge Base data bucket (if needed)
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['s3:GetObject', 's3:ListBucket'],
        resources: [
          this.knowledgeBaseDataBucket.bucketArn,
          `${this.knowledgeBaseDataBucket.bucketArn}/*`,
        ],
      }),
    ];
  }

  /**
   * Create S3 bucket for file storage.
   *
   * @param {Config} config - Configuration object
   */
  private createFileBucket(config: Config): void {
    // Create the S3 bucket with auto-generated name to avoid global naming conflicts
    this.fileBucket = new cdk.aws_s3.Bucket(this, 'FileStorageBucket', {
      removalPolicy: config.removalPolicy || cdk.RemovalPolicy.RETAIN,
      autoDeleteObjects: config.removalPolicy === cdk.RemovalPolicy.DESTROY,
      cors: [
        {
          allowedMethods: [
            cdk.aws_s3.HttpMethods.GET,
            cdk.aws_s3.HttpMethods.POST,
            cdk.aws_s3.HttpMethods.PUT,
          ],
          allowedOrigins: ['*'], // Restrict in production
          allowedHeaders: ['*'],
          exposedHeaders: [
            'ETag',
            'x-amz-meta-custom-header',
            'Content-Type',
            'Content-Disposition',
          ],
        },
      ],
      lifecycleRules: [
        {
          // Set all objects to expire after 60 days
          expiration: cdk.Duration.days(60),
          // No prefix - applies to all objects in the bucket
        },
      ],
      versioned: false,
    });

    // Add outputs
    new cdk.CfnOutput(this, 'FileStorageBucketName', {
      value: this.fileBucket.bucketName,
      description: 'Name of the S3 bucket for file storage',
    });

    new cdk.CfnOutput(this, 'FileStorageUrl', {
      value: `s3://${this.fileBucket.bucketName}`,
      description: 'S3 URL for file storage',
    });
  }

  /**
   * Create single DynamoDB table following single-table design pattern.
   *
   * @param {Config} config - Configuration object.
   */
  private createDynamoDbTables(config: Config): void {
    // Create single table with PK/SK pattern
    const dataTable = new dynamodb.Table(this, 'DataTable', {
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      removalPolicy: config.removalPolicy,
    });

    // Add UserDataIndex for user-based queries
    dataTable.addGlobalSecondaryIndex({
      indexName: 'UserDataIndex',
      partitionKey: { name: 'UserPK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'UserSK', type: dynamodb.AttributeType.STRING },
    });

    // Add MessageHierarchyIndex for parent-child relationships
    dataTable.addGlobalSecondaryIndex({
      indexName: 'MessageHierarchyIndex',
      partitionKey: { name: 'ParentPK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'ParentSK', type: dynamodb.AttributeType.STRING },
    });

    // Add AdminLookupIndex for admin queries
    dataTable.addGlobalSecondaryIndex({
      indexName: 'AdminLookupIndex',
      partitionKey: { name: 'AdminPK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'AdminSK', type: dynamodb.AttributeType.STRING },
    });

    // Add GlobalResourceIndex for global resource type queries
    dataTable.addGlobalSecondaryIndex({
      indexName: 'GlobalResourceIndex',
      partitionKey: { name: 'GlobalPK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'GlobalSK', type: dynamodb.AttributeType.STRING },
    });

    // Store the table reference
    this.dataTable = dataTable;

    // Add outputs
    new cdk.CfnOutput(this, 'DataTableName', {
      value: dataTable.tableName,
      description: 'Name of the data DynamoDB table',
    });

    new cdk.CfnOutput(this, 'DataTableArn', {
      value: dataTable.tableArn,
      description: 'ARN of the data DynamoDB table',
    });

    new cdk.CfnOutput(this, 'TableAccessPatterns', {
      value: JSON.stringify({
        chats: 'pk=CHAT#{chat_id}, sk=METADATA',
        messages: 'pk=CHAT#{chat_id}, sk=MESSAGE#{message_id}',
        prompts: 'pk=PROMPT#{prompt_id}, sk=METADATA',
        personas: 'pk=PERSONA#{persona_id}, sk=METADATA',
        task_handlers: 'pk=TASK_HANDLER#{name}, sk=METADATA',
        user_chats: 'gsi1pk=USER#{user_id}, gsi1sk=CHAT#{created_at}#{chat_id}',
        prompt_categories:
          'gsi2pk=PROMPT_CATEGORY#{category}, gsi2sk=PROMPT#{prompt_id}',
        persona_names:
          'gsi2pk=PERSONA_NAME#{name}, gsi2sk=PERSONA#{persona_id}',
      }),
      description: 'Single-table access patterns for different entity types',
    });
  }

  /**
   * Create ElastiCache Serverless for Redis.
   *
   * @param {ec2.IVpc} vpc - VPC for the ElastiCache Serverless.
   * @param {Config} config - Configuration object.
   * @param {ec2.ISecurityGroup} elasticacheSg - Security group for ElastiCache.
   * @param {ec2.ISubnet[]} allSubnets - All subnets in the VPC.
   * @param {Object} filteredSubnets - Filtered subnets by type.
   */
  private createElastiCacheServerless(
    vpc: ec2.IVpc,
    config: Config,
    elasticacheSg: ec2.ISecurityGroup,
    allSubnets: ec2.ISubnet[],
    filteredSubnets: {
      public: ec2.ISubnet[];
      private: ec2.ISubnet[];
      isolated: ec2.ISubnet[];
    },
  ): void {
    // Use the security group passed as parameter

    // Create the serverless cache with a shorter name (must be < 40 chars)
    const cacheName = createCdkId(
      [config.deploymentName, config.deploymentStage, 'cache'],
      39,
    );
    this.elastiCacheServerless = new elasticache.CfnServerlessCache(
      this,
      'ElastiCacheServerless',
      {
        serverlessCacheName: cacheName,
        engine: 'redis',
        description: `ElastiCache Serverless for ${config.appName}-${config.deploymentStage}`,
        subnetIds: getServiceSubnets(
          'elasticache',
          config,
          allSubnets,
          filteredSubnets,
        ).map((subnet) => subnet.subnetId),
        securityGroupIds: [elasticacheSg.securityGroupId],
        cacheUsageLimits: {
          dataStorage: {
            maximum: config.dataConfig.elastiCacheStorageLimitGb,
            unit: 'GB',
          },
          ecpuPerSecond: {
            maximum: config.dataConfig.elastiCacheEcpuLimit,
          },
        },
      },
    );

    // Add outputs
    new cdk.CfnOutput(this, 'ElastiCacheName', {
      value: this.elastiCacheServerless.serverlessCacheName || cacheName,
      description: 'Name of the ElastiCache Serverless',
    });

    new cdk.CfnOutput(this, 'ElastiCacheArn', {
      value: this.elastiCacheServerless.attrArn,
      description: 'ARN of the ElastiCache Serverless',
    });

    new cdk.CfnOutput(this, 'ElastiCacheEndpoint', {
      value: this.elastiCacheServerless.attrEndpointAddress,
      description: 'Endpoint of the ElastiCache Serverless',
    });

    new cdk.CfnOutput(this, 'ElastiCachePort', {
      value: this.elastiCacheServerless.attrEndpointPort,
      description: 'Port number for ElastiCache Serverless connections',
    });

    new cdk.CfnOutput(this, 'ElastiCacheConnectionString', {
      value: `${this.elastiCacheServerless.attrEndpointAddress}:${this.elastiCacheServerless.attrEndpointPort}`,
      description:
        'Connection string for ElastiCache Serverless (endpoint:port)',
    });
  }

  /**
   * Create single OpenSearch Serverless "documents" collection with IAM authentication.
   *
   * @param {Config} config - Configuration object
   * @param {string} taskRoleArn - ARN of the ECS task role for OpenSearch access
   */
  private createDocumentsCollection(
    config: Config,
    taskRoleArn?: string,
  ): void {
    // Create unique collection name with truncation to fit OpenSearch limits
    const collectionName = createCdkId(
      [config.getDeploymentId('-'), 'documents'],
      31,
    );

    // IAM principals for data access policy
    const principals: string[] = [];
    if (taskRoleArn) {
      principals.push(taskRoleArn);
    }

    // Add development access if in dev stage
    if (config.deploymentStage === 'dev') {
      const userArn = this.node.tryGetContext('USER_ARN');
      if (userArn) {
        principals.push(userArn);
      }
    }

    // Create OpenSearch Serverless collection
    this.documentsCollection = new opensearchserverless.CfnCollection(
      this,
      'DocumentsCollection',
      {
        name: collectionName,
        type: 'VECTORSEARCH',
        standbyReplicas: config.dataConfig.openSearchStandbyReplicas
          ? 'ENABLED'
          : 'DISABLED',
        description: `Documents collection for ${config.appName}-${config.deploymentStage}`,
      },
    );

    // Create encryption policy
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(
      this,
      'OpenSearchEncryptionPolicy',
      {
        name: createCdkId(
          [config.getDeploymentId('-'), 'encryption'],
          31,
        ).toLowerCase(),
        type: 'encryption',
        description: `Chat Workbench Encryption Security Policy: ${config.appName}-${config.deploymentStage}`,
        policy: JSON.stringify({
          Rules: [
            {
              ResourceType: 'collection',
              Resource: [`collection/${collectionName}`],
            },
          ],
          AWSOwnedKey: true,
        }),
      },
    );

    // Create network policy (public access)
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(
      this,
      'OpenSearchNetworkPolicy',
      {
        name: createCdkId(
          [config.getDeploymentId('-'), 'network'],
          31,
        ).toLowerCase(),
        type: 'network',
        description: `Chat Workbench Network Security Policy: ${config.appName}-${config.deploymentStage}`,
        policy: JSON.stringify([
          {
            Rules: [
              {
                ResourceType: 'collection',
                Resource: [`collection/${collectionName}`],
              },
              {
                ResourceType: 'dashboard',
                Resource: [`collection/${collectionName}`],
              },
            ],
            AllowFromPublic: true,
          },
        ]),
      },
    );

    // Create data access policy if we have principals
    if (principals.length > 0) {
      const dataPolicy = new opensearchserverless.CfnAccessPolicy(
        this,
        'OpenSearchDataPolicy',
        {
          name: createCdkId(
            [config.getDeploymentId('-'), 'data'],
            31,
          ).toLowerCase(),
          type: 'data',
          description: `Chat Workbench Data Access Policy: ${config.appName}-${config.deploymentStage}`,
          policy: JSON.stringify([
            {
              Rules: [
                {
                  Resource: [`collection/${collectionName}`],
                  Permission: [
                    'aoss:CreateCollectionItems',
                    'aoss:DeleteCollectionItems',
                    'aoss:UpdateCollectionItems',
                    'aoss:DescribeCollectionItems',
                  ],
                  ResourceType: 'collection',
                },
                {
                  Resource: [`index/${collectionName}/*`],
                  Permission: [
                    'aoss:CreateIndex',
                    'aoss:DeleteIndex',
                    'aoss:UpdateIndex',
                    'aoss:DescribeIndex',
                    'aoss:ReadDocument',
                    'aoss:WriteDocument',
                  ],
                  ResourceType: 'index',
                },
              ],
              Principal: principals,
            },
          ]),
        },
      );

      // Add dependencies
      this.documentsCollection.addDependency(encryptionPolicy);
      this.documentsCollection.addDependency(networkPolicy);
      this.documentsCollection.addDependency(dataPolicy);
    } else {
      // Add dependencies without data policy
      this.documentsCollection.addDependency(encryptionPolicy);
      this.documentsCollection.addDependency(networkPolicy);
    }

    // Add outputs
    new cdk.CfnOutput(this, 'DocumentsCollectionName', {
      value: this.documentsCollection.name || collectionName,
      description: 'Name of the documents OpenSearch Serverless collection',
    });

    new cdk.CfnOutput(this, 'DocumentsCollectionEndpoint', {
      value: this.documentsCollection.attrCollectionEndpoint,
      description: 'Endpoint of the documents OpenSearch Serverless collection',
    });

    new cdk.CfnOutput(this, 'DocumentsCollectionDashboard', {
      value: this.documentsCollection.attrDashboardEndpoint,
      description: 'Dashboard URL for the documents OpenSearch collection',
    });
  }

  /**
   * Create Bedrock Knowledge Base with dedicated S3 bucket and OpenSearch integration.
   *
   * @param {Config} config - Configuration object
   */
  private createBedrockKnowledgeBase(
    config: Config,
    taskRoleArn: string,
  ): void {
    // Create dedicated S3 bucket for Knowledge Base data source
    this.knowledgeBaseDataBucket = new s3.Bucket(
      this,
      'KnowledgeBaseDataBucket',
      {
        removalPolicy: config.removalPolicy || cdk.RemovalPolicy.RETAIN,
        autoDeleteObjects: config.removalPolicy === cdk.RemovalPolicy.DESTROY,
      },
    );

    // Create supplemental S3 bucket for multimodal data (images from PDFs)
    this.knowledgeBaseSupplementalBucket = new s3.Bucket(
      this,
      'KnowledgeBaseSupplementalBucket',
      {
        removalPolicy: config.removalPolicy || cdk.RemovalPolicy.RETAIN,
        autoDeleteObjects: config.removalPolicy === cdk.RemovalPolicy.DESTROY,
      },
    );

    // Create Knowledge Base name
    const knowledgeBaseName =
      config.dataConfig.knowledgeBaseName ||
      createCdkId([config.deploymentName, config.deploymentStage, 'kb'], 50);

    // Create the Knowledge Base using the new construct with multimodal support
    const embeddingsModel =
      BEDROCK_FOUNDATION_MODELS[config.dataConfig.embeddingModelId];
    if (!embeddingsModel) {
      throw new Error(
        `Unsupported embedding model ID: ${config.dataConfig.embeddingModelId}. Supported models: ${Object.keys(BEDROCK_FOUNDATION_MODELS).join(', ')}`,
      );
    }

    this.knowledgeBase = new bedrock.VectorKnowledgeBase(
      this,
      'BedrockKnowledgeBase',
      {
        embeddingsModel,
        name: knowledgeBaseName,
        description: `Knowledge Base for ${config.appName}-${config.deploymentStage}`,
        supplementalDataStorageLocations: [
          bedrock.SupplementalDataStorageLocation.s3({
            uri: `s3://${this.knowledgeBaseSupplementalBucket.bucketName}`,
          }),
        ],
      },
    );

    // Add the S3 data source to the knowledge base
    new bedrock.S3DataSource(this, 'BedrockKnowledgeBaseDataSource', {
      bucket: this.knowledgeBaseDataBucket,
      knowledgeBase: this.knowledgeBase,
      chunkingStrategy: bedrock.ChunkingStrategy.FIXED_SIZE,
      dataSourceName: `${knowledgeBaseName}-data-source`,
      ...(config.dataConfig.s3InclusionPrefixes && {
        inclusionPrefixes: config.dataConfig.s3InclusionPrefixes,
      }),
    });

    // Grant the ECS task role access to the new OpenSearch collection and knowledge base
    const taskRole = iam.Role.fromRoleArn(
      this,
      'ImportedTaskRoleForKB',
      taskRoleArn,
    );

    // Grant permissions using the knowledge base's grant method
    this.knowledgeBase.grantRetrieve(taskRole);

    // Add outputs for the new resources
    new cdk.CfnOutput(this, 'KnowledgeBaseName', {
      value: this.knowledgeBase.knowledgeBaseId,
      description: 'ID of the Bedrock Knowledge Base',
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseArn', {
      value: this.knowledgeBase.knowledgeBaseArn,
      description: 'ARN of the Bedrock Knowledge Base',
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseDataBucketName', {
      value: this.knowledgeBaseDataBucket.bucketName,
      description: 'Name of the S3 bucket for Knowledge Base data source',
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseSupplementalBucketName', {
      value: this.knowledgeBaseSupplementalBucket.bucketName,
      description:
        'Name of the S3 bucket for Knowledge Base supplemental data (images)',
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseSupplementalBucketArn', {
      value: this.knowledgeBaseSupplementalBucket.bucketArn,
      description:
        'ARN of the S3 bucket for Knowledge Base supplemental data (images)',
    });
  }
}
