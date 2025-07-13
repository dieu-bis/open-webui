# Atlassian OAuth 2.0 Integration

This document describes how to set up and use the Atlassian OAuth 2.0 integration in Open WebUI.

## Overview

The Atlassian integration allows users to connect their Atlassian accounts (Jira and Confluence) to Open WebUI, enabling them to:

- Import Confluence pages and spaces
- Access Jira issues and projects
- Search across Atlassian content
- Use secure OAuth 2.0 authentication with refresh tokens

## Prerequisites

1. **Atlassian Developer Account**: You need access to the [Atlassian Developer Console](https://developer.atlassian.com/)
2. **OAuth 2.0 App**: Create an OAuth 2.0 (3LO) app in the Atlassian Developer Console

## Setting up Atlassian OAuth App

### 1. Create OAuth 2.0 App

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/)
2. Click "Create" and select "OAuth 2.0 (3LO)"
3. Fill in your app details:
   - **App name**: e.g., "Open WebUI Integration"
   - **Description**: "AI-powered chat interface with Atlassian integration"

### 2. Configure OAuth Settings

1. In your app, go to **Authorization** → **OAuth 2.0 (3LO)** → **Configure**
2. Set the **Callback URL** to: `https://your-domain.com/settings/connections`
   - For development: `http://localhost:3000/settings/connections`
3. Click **Save changes**

### 3. Add API Permissions

1. Go to **Permissions** in the left menu
2. Add the APIs you want to use:
   - **Jira API**: Add for Jira integration
   - **Confluence API**: Add for Confluence integration
3. For each API, configure the required scopes:
   - **Jira**: `read:jira-user`, `read:jira-work`, `write:jira-work`
   - **Confluence**: `read:confluence-content.all`, `write:confluence-content`
   - **General**: `offline_access` (for refresh tokens)

### 4. Get Credentials

1. Go to **Settings** in your app
2. Copy the **Client ID** and **Secret**

## Environment Configuration

Set the following environment variables in your Open WebUI deployment:

```bash
# Enable Atlassian integration
ENABLE_ATLASSIAN_INTEGRATION=true

# OAuth credentials from your Atlassian app
ATLASSIAN_CLIENT_ID=your_client_id_here
ATLASSIAN_CLIENT_SECRET=your_client_secret_here

# OAuth configuration
ATLASSIAN_OAUTH_SCOPE="read:jira-user read:jira-work read:confluence-content.all offline_access"
ATLASSIAN_REDIRECT_URI=https://your-domain.com/settings/connections

# For development
# ATLASSIAN_REDIRECT_URI=http://localhost:3000/settings/connections
```

## Database Migration

The integration includes a database migration to create the `atlassian_connections` table. This will run automatically when you start Open WebUI.

## User Experience

### Connecting an Account

1. Users navigate to **Settings** → **Connections**
2. Click **Connect Atlassian** button
3. They are redirected to Atlassian's OAuth consent screen
4. After granting permissions, they return to Open WebUI
5. The connection is established and refresh tokens are stored securely

### Using the Integration

Once connected, users can:

- View their connected Atlassian sites
- See available scopes and permissions
- Access content from Jira and Confluence (implementation pending)
- Disconnect their account at any time

### Connection Management

- **Automatic Token Refresh**: Access tokens are automatically refreshed using stored refresh tokens
- **Token Expiration**: Refresh tokens are valid for 90 days of inactivity, 365 days absolute
- **Security**: All tokens are stored encrypted in the database
- **Multi-site Support**: Users can access multiple Atlassian sites with a single connection

## API Endpoints

The integration provides the following API endpoints:

### User Endpoints

- `GET /api/v1/atlassian/connection/status` - Get connection status
- `POST /api/v1/atlassian/connection/callback` - Handle OAuth callback
- `DELETE /api/v1/atlassian/connection` - Disconnect account
- `GET /api/v1/atlassian/sites` - Get accessible sites

### Admin Endpoints

- `GET /api/v1/atlassian/admin/connections` - List all connections
- `DELETE /api/v1/atlassian/admin/connections/{user_id}` - Remove user connection

## Security Considerations

1. **OAuth State Parameter**: Used to prevent CSRF attacks
2. **Refresh Token Rotation**: Tokens are rotated on each use
3. **Scope Limitation**: Only request necessary permissions
4. **Secure Storage**: Tokens encrypted in database
5. **Token Expiration**: Automatic cleanup of expired tokens

## Troubleshooting

### Common Issues

1. **Invalid Redirect URI**: Ensure the callback URL in your Atlassian app matches the `ATLASSIAN_REDIRECT_URI` environment variable

2. **Scope Permissions**: Make sure your Atlassian app has the required scopes enabled

3. **Token Refresh Failures**: Check if the user's Atlassian account password has changed (this invalidates refresh tokens)

4. **Connection Not Found**: The user may need to reconnect if their refresh token has expired

### Debug Information

Enable debug logging to see OAuth flow details:

```bash
LOG_LEVEL=DEBUG
```

This will log OAuth requests, token exchanges, and API calls for troubleshooting.

## Future Enhancements

- Content picker for Confluence pages
- Jira issue import functionality
- Search integration across Atlassian content
- Webhook support for real-time updates
- Support for Atlassian Data Center/Server (not just Cloud)

## References

- [Atlassian OAuth 2.0 Documentation](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)
- [Atlassian API Documentation](https://developer.atlassian.com/cloud/)
- [OAuth 2.0 RFC](https://tools.ietf.org/html/rfc6749)