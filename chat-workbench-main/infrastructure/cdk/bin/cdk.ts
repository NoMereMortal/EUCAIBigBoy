#!/usr/bin/env ts-node

// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

// Main app.
import * as fs from 'fs';
import * as path from 'path';

import * as cdk from 'aws-cdk-lib';
import * as yaml from 'js-yaml';

import { ChatWorkbenchStage } from '../lib/chat-workbench-stage';
import { ConfigSchema, type Config } from '../lib/schema';
import { projectRoot } from '../lib/utils';

// Determine configuration file path
// Default to root config.yaml, but allow override with CONFIG_PATH environment variable
let configFilePath = path.join(projectRoot, 'config.yaml');

if (process.env.CONFIG_PATH) {
  const configPathEnv = process.env.CONFIG_PATH;
  // Support both relative and absolute paths
  configFilePath = path.isAbsolute(configPathEnv)
    ? configPathEnv
    : path.resolve(process.cwd(), configPathEnv);
}

// Verify config file exists
if (!fs.existsSync(configFilePath)) {
  console.error(`Configuration file not found: ${configFilePath}`);
  process.exit(1);
}

// Read configuration file
// eslint-disable-next-line
const configFile = yaml.load(fs.readFileSync(configFilePath, 'utf8')) as any;
let configEnv = configFile.env || 'dev';

// Select configuration environment
if (process.env.ENV) {
  configEnv = process.env.ENV;
}
const configData = configFile[configEnv];
if (!configData) {
  throw new Error(`Configuration for environment "${configEnv}" not found.`);
}

console.log(`Loaded config: ${path.basename(configFilePath)} [${configEnv}]`);

// Get profile from command line arguments
const args = process.argv.slice(2);
let profileIndex = args.indexOf('--profile');
if (profileIndex !== -1 && profileIndex + 1 < args.length) {
  const profileValue = args[profileIndex + 1];
  console.log(`Using profile from command line: ${profileValue}`);
  configData.awsProfile = profileValue;
}

// Other command line argument overrides
type EnvMapping = [string, keyof Config];
const mappings: EnvMapping[] = [
  ['AWS_PROFILE', 'awsProfile'],
  ['DEPLOYMENT_NAME', 'deploymentName'],
  ['ACCOUNT_NUMBER', 'accountNumber'],
  ['REGION', 'region'],
];
mappings.forEach(([envVar, configVar]) => {
  const envValue = process.env[envVar];
  if (envValue) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (configData as any)[configVar] = envValue;
  }
});

// Handle deployment flags for UI and API
// Both components are ENABLED BY DEFAULT for a complete deployment
// Set environment variables to 'false' to selectively disable components:
// - UI_DEPLOYMENT=false : Disable UI deployment (CloudFront, S3, UI service)
// - API_DEPLOYMENT=false : Disable API deployment (ECS API service, Docker build)

const deployUI = process.env.UI_DEPLOYMENT !== 'false'; // Default: enabled
const deployAPI = process.env.API_DEPLOYMENT !== 'false'; // Default: enabled

console.log(
  `Deploying: ${configData.deploymentName} (${configEnv}) to ${configData.region}`,
);
console.log(
  `Components: UI=${deployUI ? 'enabled' : 'disabled'}, API=${deployAPI ? 'enabled' : 'disabled'}`,
);

// Validation: At least one component must be deployed
if (!deployUI && !deployAPI) {
  console.error('Error: Both UI and API deployments are disabled.');
  process.exit(1);
}

// Set API_DEPLOYMENT environment variable for use in ApiStack
if (deployAPI) {
  process.env.API_DEPLOYMENT = 'true';
}

// Validate and parse configuration
let config: Config;
try {
  config = ConfigSchema.parse(configData);
} catch (error) {
  if (error instanceof Error) {
    console.error('Error parsing the configuration:', error.message);
  } else {
    console.error('An unexpected error occurred:', error);
  }
  process.exit(1);
}

// Define environment
const env: cdk.Environment = {
  account: config.accountNumber,
  region: config.region,
};

// Application
const app = new cdk.App();

new ChatWorkbenchStage(app, config.deploymentStage, {
  env,
  config,
});

app.synth();
