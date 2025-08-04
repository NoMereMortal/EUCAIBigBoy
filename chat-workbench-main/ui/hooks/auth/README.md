# Authentication System

This directory contains the core authentication services for the application, implementing a robust OIDC-based authentication flow.

## Architecture

The authentication system follows these key principles:

1. **OIDC-first**: The primary authentication mechanism uses OpenID Connect through `react-oidc-context`.
2. **Decoupled state**: Auth state is managed by the OIDC provider, not the application store.
3. **Progressive enhancement**: Components gracefully handle server-side rendering.
4. **Centralized utilities**: Shared functions for error handling, SSR detection, etc.

## Key Components

### Provider

- `use-auth-provider.tsx` - Main auth context provider that implements OIDC auth
- `use-auth-config.ts` - Configuration for the auth provider

### Guards

- `AuthGuard` - Protects routes that require authentication
- `AdminGuard` - Protects routes that require admin privileges

### UI Components

- `LoginButton` - Button to initiate the login flow
- `LogoutButton` - Button to initiate the logout flow
- `AuthInitializer` - Component that initializes auth state on app load

## Usage

### Protecting Routes

Wrap any route that requires authentication with the `AuthGuard`:

```tsx
export default function ProtectedPage() {
  return (
    <AuthGuard>
      <YourProtectedContent />
    </AuthGuard>
  );
}
```

For admin-only routes, use the `AdminGuard`:

```tsx
export default function AdminPage() {
  return (
    <AdminGuard fallback={<NotAuthorizedMessage />}>
      <YourAdminContent />
    </AdminGuard>
  );
}
```

### Accessing Auth State

Use the `useAuth` hook to access authentication state in components:

```tsx
export function ProfileButton() {
  const { isAuthenticated, userProfile } = useAuth();

  if (!isAuthenticated) return null;

  return <Button>{userProfile?.firstName}</Button>;
}
```

## Auth Flow

1. User visits protected route → redirected to login page
2. User authenticates with OIDC provider
3. OIDC provider redirects back to `/auth/callback`
4. Callback page processes auth response and redirects to original destination
5. Token refresh happens automatically in the background

## Deprecated Components

The Zustand-based auth store (`auth-slice.ts`) is being phased out in favor of the OIDC provider. It remains as a compatibility layer for existing components but should not be used in new code.
