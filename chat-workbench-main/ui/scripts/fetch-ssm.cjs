#!/usr/bin/env node

const fs = require('fs');
const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');
const os = require('os');

const environment = process.env.NODE_ENV || 'development';
const isDev = environment === 'development';
const isProd = environment === 'production';

// Basic AWS configuration logging (safe for production)
console.log('AWS Configuration:');
console.log('- Region:', process.env.AWS_REGION || 'us-east-1');
if (isDev) {
  console.log('- Profile:', process.env.AWS_PROFILE || 'default');
  console.log('- Access Key ID:', process.env.AWS_ACCESS_KEY_ID ? '[REDACTED]' : 'not set');
  console.log('- Secret Access Key:', process.env.AWS_SECRET_ACCESS_KEY ? '[REDACTED]' : 'not set');
  console.log('- Session Token:', process.env.AWS_SESSION_TOKEN ? '[REDACTED]' : 'not set');

  // Check if AWS credentials file exists (only in dev mode)
  const awsCredentialsPath = `${os.homedir()}/.aws/credentials`;
  const awsConfigPath = `${os.homedir()}/.aws/config`;

  console.log('AWS Credentials File Check:');
  try {
    console.log(`- Credentials file exists: ${fs.existsSync(awsCredentialsPath)}`);
    console.log(`- Config file exists: ${fs.existsSync(awsConfigPath)}`);

    // Log container information in dev mode only
    console.log('Container Information:');
    console.log('- User ID:', process.getuid ? process.getuid() : 'N/A');
    console.log('- Group ID:', process.getgid ? process.getgid() : 'N/A');
    console.log('- Current directory:', process.cwd());
    console.log('- Home directory:', os.homedir());
  } catch (err) {
    console.log(`- Error checking AWS credentials files: ${err.message}`);
  }
}

// Create an SSM client with appropriate logging level
console.log('Creating SSM client with region:', process.env.AWS_REGION || 'us-east-1');
const ssmClient = new SSMClient({
  region: process.env.AWS_REGION || 'us-east-1',
  ...(isDev && {
    logger: {
      debug: (...args) => console.log('AWS SDK DEBUG:', ...args),
      info: (...args) => console.log('AWS SDK INFO:', ...args),
      warn: (...args) => console.log('AWS SDK WARN:', ...args),
      error: (...args) => console.log('AWS SDK ERROR:', ...args)
    }
  })
});

// Define the parameter name
const paramName = process.env.SSM_PARAM_NAME || '/chatworkbench/dev/ui-config';
console.log('SSM Parameter Name:', paramName);

// Function to fetch the parameter
async function fetchParameter() {
  try {
    // Create the GetParameterCommand with the parameter name
    const command = new GetParameterCommand({
      Name: paramName,
      WithDecryption: false
    });

    try {
      // Send the command to AWS SSM
      const response = await ssmClient.send(command);

      const config = JSON.parse(response.Parameter.Value);

      if (!config.COGNITO || !config.COGNITO.authority) {
        console.error('FATAL: Invalid configuration - missing COGNITO.authority');
        process.exit(1);
      }

      console.log(config);

      // Format the env.js content with proper indentation and ensure all auth fields
      const envJs = `window.env = {
  "API_URI": "${config.API_URI || ''}",
  "API_VERSION": "${config.API_VERSION || 'v1'}",
  "UI_TITLE": "${config.UI_TITLE || ''}",
  "COGNITO": {
    "authority": "${config.COGNITO ? config.COGNITO.authority || '' : ''}",
    "client_id": "${config.COGNITO ? config.COGNITO.client_id || '' : ''}",
    "redirect_uri": "${config.COGNITO ? config.COGNITO.redirect_uri || config.API_URI || '' : ''}",
    "post_logout_redirect_uri": "${config.COGNITO ? config.COGNITO.post_logout_redirect_uri || config.API_URI || '' : ''}",
    "scope": "${config.COGNITO ? config.COGNITO.scope || 'openid' : 'openid'}",
    "response_type": "${config.COGNITO ? config.COGNITO.response_type || 'code' : 'code'}",
    "loadUserInfo": ${config.COGNITO ? config.COGNITO.loadUserInfo !== false : true},
    "metadata": {
      "authorization_endpoint": "${config.COGNITO && config.COGNITO.metadata ? config.COGNITO.metadata.authorization_endpoint || '' : ''}",
      "token_endpoint": "${config.COGNITO && config.COGNITO.metadata ? config.COGNITO.metadata.token_endpoint || '' : ''}",
      "userinfo_endpoint": "${config.COGNITO && config.COGNITO.metadata ? config.COGNITO.metadata.userinfo_endpoint || '' : ''}",
      "end_session_endpoint": "${config.COGNITO && config.COGNITO.metadata ? config.COGNITO.metadata.end_session_endpoint || '' : ''}"
    }
  }
};`;

      console.log(envJs);

      // Write to both public directory and out directory (if it exists)
      fs.writeFileSync('/app/public/env.js', envJs);

      // Also write to the out directory if it exists (for static exports)
      if (fs.existsSync('/app/out')) {
        fs.writeFileSync('/app/out/env.js', envJs);
        console.log('Wrote env.js to static export directory');
      }

      console.log('Successfully fetched and wrote configuration');
    } catch (ssmError) {
      // Log error details in a simple format to avoid syntax issues
      console.error('SSM Error Details:');
      console.error('Message:', ssmError.message);
      console.error('Code:', ssmError.code);
      console.error('Region:', process.env.AWS_REGION);
      console.error('Parameter Name:', paramName);

      // Log detailed error information only in development mode
      if (isDev) {
        // Log metadata if available
        if (ssmError.$metadata) {
          console.error('Request ID:', ssmError.$metadata.requestId || 'N/A');
          console.error('Status Code:', ssmError.$metadata.httpStatusCode || 'N/A');
        }

        // Log stack trace if available
        if (ssmError.stack) {
          console.error('Stack Trace:', ssmError.stack);
        }

        // Log additional AWS SDK error information
        console.error('Error Type:', ssmError.name);
        console.error('Error Constructor:', ssmError.constructor ? ssmError.constructor.name : 'Unknown');
        console.error('Is AWS SDK Error:', ssmError.$service ? 'Yes' : 'No');
      }

      if (isProd) {
        console.error('FATAL: Cannot fetch production configuration from SSM');
        console.error('Production deployments require valid SSM parameter configuration');
        process.exit(1);
      }

      console.log('Development environment detected, using local Keycloak configuration');
      const devEnv = `window.env = {
  "API_URI": "http://localhost:8000",
  "API_VERSION": "v1",
  "UI_TITLE": "",
  "COGNITO": {
    "authority": "http://localhost:8080/realms/chat-workbench",
    "client_id": "chat-workbench-ui",
    "redirect_uri": "http://localhost:3000/auth/callback",
    "post_logout_redirect_uri": "http://localhost:3000",
    "scope": "openid profile email",
    "response_type": "code",
    "loadUserInfo": true,
    "metadata": {
      "authorization_endpoint": "http://localhost:8080/realms/chat-workbench/protocol/openid-connect/auth",
      "token_endpoint": "http://localhost:8080/realms/chat-workbench/protocol/openid-connect/token",
      "userinfo_endpoint": "http://localhost:8080/realms/chat-workbench/protocol/openid-connect/userinfo",
      "end_session_endpoint": "http://localhost:8080/realms/chat-workbench/protocol/openid-connect/logout"
    }
  }
};`;
      console.log(devEnv)
      fs.writeFileSync('/app/public/env.js', devEnv);
    }
  } catch (error) {
    console.error('Error in fetch operation:', error.message);

    if (isDev) {
      console.error('Error Type:', error.name);
      console.error('Error Message:', error.message);
      if (error.stack) {
        console.error('Stack Trace:', error.stack);
      }
    }

    if (isProd) {
      console.error('FATAL: Critical error in production configuration fetch');
      process.exit(1);
    }

    console.log('Using empty configuration for development');
    fs.writeFileSync('/app/public/env.js', 'window.env = {};');
  }
}

// Run the function
fetchParameter()
  .then(() => console.log('Configuration setup complete'))
  .catch((err) => console.error('Fatal error:', err));
