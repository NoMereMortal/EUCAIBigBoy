#!/usr/bin/env node

const fs = require('fs');

// Create mock configuration for development environment
const mockEnvJs = `window.env = {
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

// Write to public directory
fs.writeFileSync('/app/public/env.js', mockEnvJs);

// Also write to the out directory if it exists
if (fs.existsSync('/app/out')) {
  fs.writeFileSync('/app/out/env.js', mockEnvJs);
  console.log('Wrote mock env.js to static export directory');
}

console.log('Created mock auth configuration for development');
