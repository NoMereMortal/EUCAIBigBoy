// Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
// Terms and the SOW between the parties dated 2025.

/**
 * Utility functions for authentication features
 * This file contains non-React utility functions
 */

/**
 * Check if the code is running on the server (during SSR)
 * This is used to safely handle components that should only run on the client
 */
export function isServerSide(): boolean {
  return typeof window === 'undefined';
}

/**
 * Extract user groups from a profile object, handling different formats
 *
 * @param profile User profile object from auth provider
 * @returns Array of group names
 */
export function extractGroups(profile: any): string[] {
  if (!profile) return [];

  console.log('Extracting groups - Full profile:', profile);
  console.log('Profile keys:', Object.keys(profile));

  // Check multiple potential sources for groups
  const possibleGroupSources = [
    'groups', // Standard OIDC
    'cognito:groups', // AWS Cognito
    'roles', // Some providers use roles
    'realm_access.roles', // Keycloak sometimes uses this
    'resource_access', // Another Keycloak pattern
  ];

  // Log all potential group sources
  possibleGroupSources.forEach((source) => {
    const parts = source.split('.');
    let value = profile;

    // Handle nested properties like 'realm_access.roles'
    for (const part of parts) {
      value = value?.[part];
    }

    console.log(`Groups from source "${source}":`, value);
  });

  // Try to extract groups from various sources
  if (Array.isArray(profile.groups)) {
    console.log('Found groups in profile.groups');
    return profile.groups;
  }

  if (Array.isArray(profile['cognito:groups'])) {
    console.log('Found groups in profile["cognito:groups"]');
    return profile['cognito:groups'];
  }

  if (Array.isArray(profile.roles)) {
    console.log('Found groups in profile.roles');
    return profile.roles;
  }

  if (profile.realm_access && Array.isArray(profile.realm_access.roles)) {
    console.log('Found groups in profile.realm_access.roles');
    return profile.realm_access.roles;
  }

  // Check for Keycloak client roles (resource_access)
  if (profile.resource_access) {
    console.log('Found resource_access, checking for client roles');
    const clientRoles = [];
    for (const client in profile.resource_access) {
      if (
        profile.resource_access[client].roles &&
        Array.isArray(profile.resource_access[client].roles)
      ) {
        console.log(
          `Found roles for client ${client}:`,
          profile.resource_access[client].roles,
        );
        clientRoles.push(...profile.resource_access[client].roles);
      }
    }
    if (clientRoles.length > 0) {
      return clientRoles;
    }
  }

  console.log('No groups found in any standard location');
  return [];
}

/**
 * Helper function to determine if user has admin privileges based on their groups
 * Checks for common admin group naming patterns in both Keycloak and Cognito
 *
 * @param groups Array of user group names
 * @param profile Optional user profile for additional checks
 * @returns Boolean indicating if user is an admin
 */
export function checkIfUserIsAdmin(groups: string[], profile?: any): boolean {
  // Check for admin groups first
  if (groups && groups.length > 0) {
    // Convert to lowercase for case-insensitive comparison
    const lowerCaseGroups = groups.map((group) => group.toLowerCase());

    // Check for common admin group patterns
    const hasAdminGroup = lowerCaseGroups.some(
      (group) =>
        group === 'admin' || // Exact match
        group.includes('admin') || // Contains 'admin'
        group === 'administrator' || // Common alternatives
        group.includes('administrator') ||
        group.startsWith('app-admin') || // Common prefixed patterns
        group.startsWith('system-admin') ||
        group.endsWith('-admin') || // Common suffixed patterns
        group.includes('superuser'), // Other admin-like terms
    );

    if (hasAdminGroup) return true;
  }

  // Fallback to username check if no matching groups found and we have a profile
  if (profile) {
    // Check if the username is "admin"
    const username = profile.preferred_username || profile.username || '';
    if (username.toLowerCase() === 'admin') {
      console.log('Admin access granted based on admin username:', username);
      return true;
    }
  }

  return false;
}

/**
 * Check if the given profile has admin privileges
 *
 * @param profile User profile object
 * @returns Boolean indicating if user is an admin
 */
export function hasAdminRole(profile: any): boolean {
  const groups = extractGroups(profile);
  return checkIfUserIsAdmin(groups, profile);
}
