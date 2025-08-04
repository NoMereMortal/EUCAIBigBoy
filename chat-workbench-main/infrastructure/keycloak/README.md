# Keycloak Authentication for Chat Workbench

This directory contains configuration files and scripts for integrating Keycloak as an authentication provider for the Chat Workbench application.

## Overview

Keycloak is an open-source Identity and Access Management solution that provides features like:

- Single Sign-On (SSO)
- Identity Brokering and Social Login
- User Federation
- Client Adapters
- Admin Console

## Local Development Setup

The Docker Compose configuration automatically sets up Keycloak and configures it for use with the Chat Workbench UI.

### Default Configuration

- **Keycloak Admin Console**: http://localhost:8080/admin
- **Admin Credentials**: admin / admin
- **Realm**: chat-workbench
- **Client ID**: chat-workbench-ui
- **Client Secret**: chat-workbench-secret
- **Test User**: testuser / password

### How It Works

1. The `keycloak` service in `docker-compose.yml` starts a Keycloak server in development mode.
2. The `keycloak-config` service runs the `configure-keycloak.sh` script to:
   - Create a realm called "chat-workbench"
   - Create a client for the UI application
   - Configure the client for OIDC authentication
   - Create a test user

3. The UI application is configured to use Keycloak for authentication via the `env.js` file.

## Manual Configuration

If you need to manually configure Keycloak, follow these steps:

1. Access the Keycloak admin console at http://localhost:8080/admin
2. Log in with admin / admin
3. Create a new realm called "chat-workbench"
4. Create a new client:
   - Client ID: chat-workbench-ui
   - Client Protocol: openid-connect
   - Access Type: confidential
   - Valid Redirect URIs: http://localhost:3000/auth/callback, http://localhost:3000/\*
   - Web Origins: http://localhost:3000

5. Configure the client:
   - Go to the "Credentials" tab and note the client secret
   - Go to the "Client Scopes" tab and ensure "openid", "profile", and "email" are included

6. Create a test user:
   - Username: testuser
   - Email: testuser@example.com
   - First Name: Test
   - Last Name: User
   - Set password: password (disable "Temporary" option)

## UI Integration

The UI uses the `react-oidc-context` library to integrate with Keycloak. The authentication configuration is loaded from the `env.js` file, which is mounted into the UI container.

### Authentication Flow

1. User clicks "Sign In" button
2. User is redirected to Keycloak login page
3. After successful login, user is redirected back to the application
4. The application receives an access token and ID token
5. The application uses the access token for API requests

## Troubleshooting

- If authentication is not working, check the browser console for errors
- Ensure the Keycloak service is running and healthy
- Verify that the UI container has the correct `env.js` file
- Check that the redirect URIs are correctly configured in Keycloak

## Complete Authentication Documentation

This document covers the local Keycloak setup and configuration. For a comprehensive overview of the end-to-end authentication flow, including frontend integration, backend JWT validation, security considerations, and detailed troubleshooting, see the [Authentication Flow Guide](../../docs/guides/AUTHENTICATION_FLOW.md).
