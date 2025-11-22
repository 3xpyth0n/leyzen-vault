# API Documentation - Leyzen Vault

All API endpoints are prefixed with `/api` unless otherwise specified.

## Authentication

All requests require an API key in the header:

```
Authorization: Bearer <api_key>
```

### API Keys

You can generate an API key from the admin interface. Navigate to the **API Key** tab in the admin panel to create and manage your API keys.

API keys are required for:

- Automation scripts
- CI/CD pipelines
- Third-party integrations
- Long-running services
- All programmatic access outside the web interface

### Upload and Download

**Important**: Due to end-to-end encryption, file upload and download operations must be performed through the web interface. The API only supports metadata operations (create folders, rename, move, delete, etc.) and does not handle encrypted file data or encryption keys.

## Endpoints

### VaultSpaces

#### GET `/api/vaultspaces`

List all user VaultSpaces.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "vaultspaces": [
    {
      "id": "uuid",
      "name": "My Drive",
      "vaultspace_type": "personal",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### GET `/api/vaultspaces/<vaultspace_id>`

Get a specific VaultSpace.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "vaultspace": {
    "id": "uuid",
    "name": "My Drive",
    "vaultspace_type": "personal",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### POST `/api/vaultspaces`

Create a new VaultSpace.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "name": "New VaultSpace",
  "icon_name": "optional_icon_name"
}
```

**Response:**

```json
{
  "vaultspace": {
    "id": "uuid",
    "name": "New VaultSpace",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### PUT `/api/vaultspaces/<vaultspace_id>`

Update a VaultSpace metadata.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "name": "Updated Name",
  "icon_name": "optional_icon_name"
}
```

**Response:**

```json
{
  "vaultspace": {
    "id": "uuid",
    "name": "Updated Name",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

#### DELETE `/api/vaultspaces/<vaultspace_id>`

Delete a VaultSpace.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "message": "VaultSpace deleted successfully"
}
```

**Note**: VaultSpace key management requires encryption/decryption and must be done through the web interface.

### Files

#### GET `/api/v2/files`

List files in a VaultSpace.

**Authentication**: Required (API Key)

**Query Parameters:**

- `vaultspace_id` (required): VaultSpace ID
- `parent_id` (optional): Parent folder ID
- `page` (optional, default: 1): Page number
- `per_page` (optional, default: 50, max: 100): Items per page

**Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "mime_type": "text/plain",
      "size": 1024,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "is_starred": false
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 100,
    "pages": 2
  }
}
```

#### POST `/api/v2/files/folders`

Create a folder.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "vaultspace_id": "uuid",
  "name": "Folder Name",
  "parent_id": "uuid"
}
```

**Response:**

```json
{
  "folder": {
    "id": "uuid",
    "original_name": "Folder Name",
    "mime_type": "application/x-directory",
    "vaultspace_id": "uuid",
    "parent_id": "uuid"
  }
}
```

#### GET `/api/v2/files/<file_id>`

Get file metadata.

**Authentication**: Required (API Key)

**Query Parameters:**

- `vaultspace_id` (required): VaultSpace ID

**Response:**

```json
{
  "file": {
    "id": "uuid",
    "original_name": "file.txt",
    "mime_type": "text/plain",
    "size": 1024,
    "vaultspace_id": "uuid",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "is_starred": false
  }
}
```

**Note**: Upload and download of files must be done through the web interface due to end-to-end encryption requirements.

#### PUT `/api/v2/files/<file_id>/rename`

Rename a file or folder.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "name": "New Name"
}
```

**Response:**

```json
{
  "file": {
    "id": "uuid",
    "original_name": "New Name",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

#### PUT `/api/v2/files/<file_id>/move`

Move a file or folder to a different parent.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "parent_id": "parent-folder-uuid"
}
```

**Response:**

```json
{
  "file": {
    "id": "uuid",
    "parent_id": "parent-folder-uuid",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

#### DELETE `/api/v2/files/<file_id>`

Delete a file or folder (soft delete).

**Authentication**: Required (API Key)

**Response:**

```json
{
  "message": "File deleted successfully"
}
```

#### POST `/api/v2/files/<file_id>/star`

Star/unstar a file.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "file": {
    "id": "uuid",
    "is_starred": true
  }
}
```

#### GET `/api/v2/files/starred`

List starred files.

**Authentication**: Required (API Key)

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace

**Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "is_starred": true
    }
  ]
}
```

#### GET `/api/v2/files/recent`

List recent files.

**Authentication**: Required (API Key)

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace
- `limit` (optional, default: 50): Maximum number of results
- `days` (optional, default: 30): Number of days

**Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST `/api/v2/files/batch/delete`

Delete multiple files in batch.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "file_ids": ["file-uuid1", "file-uuid2"]
}
```

**Response:**

```json
{
  "deleted": ["file-uuid1", "file-uuid2"],
  "failed": []
}
```

#### POST `/api/v2/files/batch/move`

Move multiple files to a new parent in batch.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "file_ids": ["file-uuid1", "file-uuid2"],
  "new_parent_id": "parent-folder-uuid"
}
```

**Response:**

```json
{
  "moved": ["file-uuid1", "file-uuid2"],
  "failed": []
}
```

#### POST `/api/v2/files/batch/rename`

Rename multiple files in batch.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "file_renames": [
    { "file_id": "file-uuid1", "new_name": "New Name 1" },
    { "file_id": "file-uuid2", "new_name": "New Name 2" }
  ]
}
```

**Response:**

```json
{
  "renamed": ["file-uuid1", "file-uuid2"],
  "failed": []
}
```

### Trash

#### GET `/api/v2/trash`

List files in trash.

**Authentication**: Required (API Key)

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace

**Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "deleted_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

#### POST `/api/v2/trash/<file_id>/restore`

Restore a file from trash.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "file": {
    "id": "uuid",
    "original_name": "file.txt",
    "deleted_at": null
  },
  "message": "File restored successfully"
}
```

#### DELETE `/api/v2/trash/<file_id>/permanent`

Permanently delete a file from trash (cannot be undone).

**Authentication**: Required (API Key)

**Response:**

```json
{
  "message": "File permanently deleted"
}
```

### Sharing

#### POST `/api/v2/sharing/public-links`

Create a public share link.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "resource_id": "uuid",
  "resource_type": "file",
  "password": "optional_password",
  "expires_in_days": 7,
  "max_downloads": 10,
  "max_access_count": 100,
  "allow_download": true,
  "permission_type": "read"
}
```

**Response:**

```json
{
  "share_link": {
    "id": "uuid",
    "token": "share_token",
    "expires_at": "2024-01-08T00:00:00Z",
    "max_downloads": 10,
    "download_count": 0
  },
  "share_url": "/share/share_token"
}
```

#### GET `/api/v2/sharing/public-links`

List public links created by the user.

**Authentication**: Required (API Key)

**Query Parameters:**

- `resource_id` (optional): Filter by resource ID

**Response:**

```json
{
  "share_links": [
    {
      "id": "uuid",
      "token": "share_token",
      "resource_id": "uuid",
      "resource_type": "file",
      "expires_at": "2024-01-08T00:00:00Z"
    }
  ],
  "total": 1
}
```

#### GET `/api/v2/sharing/public-links/<token>`

Get a public link by token (public endpoint, no auth required).

**Query Parameters:**

- `password` (optional): Password if required
- `download` (optional): Set to "true" to download directly

**Response:**

```json
{
  "share_link": {
    "id": "uuid",
    "token": "share_token",
    "resource_id": "uuid",
    "expires_at": "2024-01-08T00:00:00Z"
  },
  "resource": {
    "id": "uuid",
    "original_name": "file.txt"
  }
}
```

#### PUT `/api/v2/sharing/public-links/<link_id>`

Update a public link.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "expires_in_days": 7,
  "max_downloads": 10,
  "max_access_count": 100,
  "allow_download": true
}
```

**Response:**

```json
{
  "share_link": {
    "id": "uuid",
    "expires_at": "2024-01-08T00:00:00Z",
    "max_downloads": 10
  }
}
```

#### DELETE `/api/v2/sharing/public-links/<link_id>`

Revoke a public link.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "message": "Share link revoked successfully"
}
```

#### POST `/api/v2/sharing/public-links/<token>/verify`

Verify a password-protected public link.

**Request Body:**

```json
{
  "password": "password"
}
```

**Response:**

```json
{
  "share_link": {
    "id": "uuid",
    "token": "share_token",
    "can_access": true
  }
}
```

#### POST `/api/v2/sharing/public-links/<token>/access`

Access a resource via a public link (increments access count).

**Request Body:**

```json
{
  "password": "optional-password"
}
```

**Response:**

```json
{
  "share_link": {
    "id": "uuid",
    "token": "share_token",
    "access_count": 1
  },
  "resource": {
    "id": "uuid",
    "original_name": "file.txt"
  }
}
```

**Note**: Downloading files requires decryption and must be done through the web interface.

### Quotas

#### GET `/api/v2/quota`

Get quota information for the current user.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "max_storage_bytes": 1073741824,
  "used_storage_bytes": 52428800,
  "max_files": 10000,
  "used_files": 150,
  "usage_percentage": 4.88
}
```

#### POST `/api/v2/quota/check`

Check if user has enough quota for additional storage.

**Authentication**: Required (API Key)

**Request Body:**

```json
{
  "additional_bytes": 1024
}
```

**Response:**

```json
{
  "has_quota": true,
  "max_storage_bytes": 1073741824,
  "used_storage_bytes": 52428800,
  "available_bytes": 1021313024
}
```

### Search

#### GET `/api/search/files`

Search files.

**Authentication**: Required (API Key)

**Query Parameters:**

- `q` (optional): Search term (filename)
- `vaultspace_id` (optional): Filter by VaultSpace
- `mime_type` (optional): Filter by MIME type
- `min_size` (optional): Minimum size in bytes
- `max_size` (optional): Maximum size in bytes
- `created_after` (optional): ISO date
- `created_before` (optional): ISO date
- `updated_after` (optional): ISO date
- `updated_before` (optional): ISO date
- `files_only` (optional): true/false (default: false)
- `folders_only` (optional): true/false (default: false)
- `sort_by` (optional): Sort field (relevance, name, date, size, default: relevance)
- `sort_order` (optional): Order (asc, desc, default: desc)
- `limit` (optional): Maximum number of results (default: 100)
- `offset` (optional): Offset for pagination (default: 0)
  **Response:**

```json
{
  "files": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "mime_type": "text/plain",
      "relevance_score": 0.95
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

#### GET `/api/search/recent`

Get recently accessed or modified files.

**Authentication**: Required (API Key)

**Query Parameters:**

- `days` (optional): Number of days to look back (default: 7)
- `limit` (optional): Maximum results (default: 50)

**Response:**

```json
{
  "results": [
    {
      "id": "uuid",
      "original_name": "file.txt",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 10
}
```

**Note**: Advanced search operations that require encryption/decryption (such as encrypted tags search) must be done through the web interface.

### Thumbnails

#### GET `/api/v2/thumbnails/<file_id>`

Get a thumbnail.

**Authentication**: Required (API Key)

**Query Parameters:**

- `size` (optional, default: 256x256): Size (64x64, 128x128, 256x256) in format WIDTHxHEIGHT

**Response:** Binary stream (JPEG image)

**Note**: Thumbnail generation requires decrypted file data and must be done through the web interface.

#### DELETE `/api/v2/thumbnails/<file_id>`

Delete thumbnails for a file.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "message": "Thumbnails deleted successfully"
}
```

### SSO

#### GET `/api/sso/providers`

List all active SSO providers (public endpoint).

**Response:**

```json
{
  "providers": [
    {
      "id": "uuid",
      "name": "Google SSO",
      "provider_type": "oidc",
      "is_active": true,
      "config": {
        "authorization_url": "https://accounts.google.com/oauth2/v2/auth",
        "issuer_url": "https://accounts.google.com"
      }
    }
  ]
}
```

### Administration

#### GET `/api/admin/users`

List all users with search and filters (admin only).

**Authentication**: Required (API Key with admin role)

**Query Parameters:**

- `page` (optional, default: 1): Page number
- `per_page` (optional, default: 50): Items per page
- `query` (optional): Search query (email, username)
- `role` (optional): Filter by role (user, admin, superadmin)

**Response:**

```json
{
  "users": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "global_role": "user"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 100,
    "pages": 2
  }
}
```

#### GET `/api/admin/users/<user_id>`

Get detailed user information (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "global_role": "user",
    "created_at": "2024-01-01T00:00:00Z"
  },
  "statistics": {
    "total_files": 150,
    "total_storage": 52428800
  }
}
```

#### PUT `/api/admin/users/<user_id>`

Update user (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "email": "newemail@example.com",
  "password": "newpassword"
}
```

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "email": "newemail@example.com"
  }
}
```

#### PUT `/api/admin/users/<user_id>/role`

Update user global role (admin or superadmin).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "global_role": "admin"
}
```

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "global_role": "admin"
  }
}
```

#### DELETE `/api/admin/users/<user_id>`

Permanently delete user and all associated data (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "User and all associated data deleted successfully"
}
```

#### GET `/api/admin/stats`

Get comprehensive system statistics (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "users": {
    "total": 100,
    "active": 95,
    "admins": 5
  },
  "storage": {
    "total_bytes": 1073741824,
    "used_bytes": 52428800
  },
  "files": {
    "total": 10000,
    "deleted": 500
  }
}
```

#### GET `/api/admin/quotas`

List all quotas with user storage usage (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "quotas": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "user_email": "user@example.com",
      "max_storage_bytes": 1073741824,
      "used_storage_bytes": 52428800,
      "max_files": 10000,
      "used_files": 150
    }
  ]
}
```

#### POST `/api/admin/quotas`

Create or update quota (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "user_id": "uuid",
  "max_storage_bytes": 1073741824,
  "max_files": 10000
}
```

**Response:**

```json
{
  "quota": {
    "id": "uuid",
    "user_id": "uuid",
    "max_storage_bytes": 1073741824,
    "max_files": 10000
  }
}
```

#### GET `/api/admin/api-keys`

List all API keys (admin and superadmin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "api_keys": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "N8N Integration",
      "created_at": "2024-01-01T00:00:00Z",
      "last_used_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

#### POST `/api/admin/api-keys`

Generate a new API key (admin and superadmin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "user_id": "uuid",
  "name": "API Key Name"
}
```

**Response:**

```json
{
  "api_key": {
    "id": "uuid",
    "user_id": "uuid",
    "name": "API Key Name"
  },
  "key": "plaintext_api_key_here"
}
```

**Important**: The plaintext key is shown only once. Save it securely.

#### DELETE `/api/admin/api-keys/<key_id>`

Revoke (delete) an API key (admin and superadmin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "API key revoked successfully"
}
```

#### GET `/api/admin/api-keys/user/<user_id>`

List all API keys for a specific user (admin and superadmin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "api_keys": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "API Key Name",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### GET `/api/admin/audit-logs`

Get audit logs with filters (admin only).

**Authentication**: Required (API Key with admin role)

**Query Parameters:**

- `limit` (optional, default: 100): Maximum number of logs
- `action` (optional): Filter by action
- `file_id` (optional): Filter by file ID
- `success` (optional): Filter by success (true/false)
- `user_ip` (optional): Filter by user IP

**Response:**

```json
{
  "logs": [
    {
      "id": "uuid",
      "action": "upload",
      "user_ip": "192.168.1.1",
      "success": true,
      "timestamp": "2024-01-01T00:00:00Z"
    }
  ],
  "count": 100
}
```

#### GET `/api/admin/audit-logs/export/csv`

Export audit logs to CSV (admin only).

**Authentication**: Required (API Key with admin role)

**Query Parameters:**

- `limit` (optional, default: 1000): Maximum number of logs to export

**Response:** CSV file download

#### GET `/api/admin/audit-logs/export/json`

Export audit logs to JSON (admin only).

**Authentication**: Required (API Key with admin role)

**Query Parameters:**

- `limit` (optional, default: 1000): Maximum number of logs to export

**Response:** JSON file download

#### GET `/api/admin/sso-providers`

List all SSO providers (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "providers": [
    {
      "id": "uuid",
      "name": "Google SSO",
      "provider_type": "oidc",
      "is_active": true
    }
  ]
}
```

#### POST `/api/admin/sso-providers`

Create a new SSO provider (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "name": "Google SSO",
  "provider_type": "oidc",
  "config": {
    "issuer_url": "https://accounts.google.com",
    "client_id": "client_id",
    "client_secret": "client_secret"
  },
  "is_active": true
}
```

**Response:**

```json
{
  "provider": {
    "id": "uuid",
    "name": "Google SSO",
    "provider_type": "oidc",
    "is_active": true
  }
}
```

#### GET `/api/admin/sso-providers/<provider_id>`

Get a specific SSO provider (admin only).

**Authentication**: Required (API Key with admin role)

#### PUT `/api/admin/sso-providers/<provider_id>`

Update an SSO provider (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "name": "Updated Name",
  "config": {},
  "is_active": false
}
```

#### DELETE `/api/admin/sso-providers/<provider_id>`

Delete an SSO provider (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "SSO provider deleted successfully"
}
```

#### GET `/api/admin/domain-rules`

List domain rules (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "rules": [
    {
      "id": "uuid",
      "domain_pattern": "@example.com",
      "sso_provider_id": "uuid",
      "is_active": true
    }
  ]
}
```

#### POST `/api/admin/domain-rules`

Create a domain rule (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "domain_pattern": "@example.com",
  "sso_provider_id": "uuid",
  "is_active": true
}
```

#### PUT `/api/admin/domain-rules/<rule_id>`

Update a domain rule (admin only).

**Authentication**: Required (API Key with admin role)

#### DELETE `/api/admin/domain-rules/<rule_id>`

Delete a domain rule (admin only).

**Authentication**: Required (API Key with admin role)

#### GET `/api/admin/settings`

Get system settings (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "settings": {
    "allow_signup": "true",
    "password_authentication_enabled": "true"
  }
}
```

#### PUT `/api/admin/settings`

Update system settings (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "allow_signup": false,
  "password_authentication_enabled": true
}
```

#### GET `/api/admin/storage/reconcile`

Get storage reconciliation report (find orphaned files) (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "primary_orphans": ["file-id-1", "file-id-2"],
  "source_orphans": [],
  "primary_orphans_count": 2,
  "source_orphans_count": 0,
  "db_records": 1000,
  "primary_files": 998,
  "source_files": 1000
}
```

#### POST `/api/admin/storage/cleanup`

Clean up orphaned files from storage (superadmin only).

**Authentication**: Required (API Key with superadmin role)

**Request Body:**

```json
{
  "dry_run": true
}
```

**Response:**

```json
{
  "dry_run": true,
  "deleted_primary": ["file-id-1"],
  "deleted_source": [],
  "deleted_primary_count": 1,
  "deleted_source_count": 0,
  "failed_count": 0,
  "failed": [],
  "stats": {
    "primary_orphans": ["file-id-1"],
    "source_orphans": []
  }
}
```

#### POST `/api/admin/test-smtp`

Test SMTP configuration by sending a test email to the current admin user (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "success": true,
  "message": "Test email sent successfully to admin@example.com"
}
```

#### POST `/api/admin/users/<user_id>/send-verification`

Resend verification email to user (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "Verification email sent"
}
```

#### GET `/api/admin/invitations`

List invitations (admin only).

**Authentication**: Required (API Key with admin role)

**Query Parameters:**

- `invited_by` (optional): Filter by inviter user ID
- `status` (optional): Filter by status (pending, accepted, expired)
- `page` (optional, default: 1): Page number
- `per_page` (optional, default: 50): Items per page

**Response:**

```json
{
  "invitations": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 10,
    "pages": 1
  }
}
```

#### POST `/api/admin/invitations`

Create an invitation (admin only).

**Authentication**: Required (API Key with admin role)

**Request Body:**

```json
{
  "email": "user@example.com"
}
```

**Response:**

```json
{
  "invitation": {
    "id": "uuid",
    "email": "user@example.com",
    "token": "invitation-token",
    "status": "pending"
  }
}
```

#### POST `/api/admin/invitations/<invitation_id>/resend`

Resend invitation email (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "Invitation resent successfully"
}
```

#### DELETE `/api/admin/invitations/<invitation_id>`

Cancel an invitation (admin only).

**Authentication**: Required (API Key with admin role)

**Response:**

```json
{
  "message": "Invitation cancelled successfully"
}
```

### Security

#### GET `/security/api/stats`

Get security and storage statistics.

**Authentication**: Required (API Key)

**Response:**

```json
{
  "storage": {
    "total_files": 1000,
    "total_size": 1073741824,
    "total_encrypted_size": 1431634944,
    "average_size": 1073741,
    "files_by_type": {
      "pdf": 100,
      "jpg": 200,
      "png": 150
    }
  },
  "activity": {
    "recent_actions": 500,
    "successful_actions": 480,
    "failed_actions": 20,
    "by_action": {
      "upload": 200,
      "download": 150,
      "delete": 50
    }
  },
  "recent_logs": [
    {
      "id": "uuid",
      "action": "upload",
      "user_ip": "192.168.1.1",
      "success": true,
      "timestamp": "2024-01-01T00:00:00Z"
    }
  ]
}
```

## HTTP Status Codes

- `200`: Success
- `201`: Created
- `400`: Invalid request
- `401`: Unauthenticated
- `403`: Forbidden
- `404`: Not found
- `500`: Server error

## Error Handling

Errors are returned in the format:

```json
{
  "error": "Descriptive error message"
}
```

## Pagination

List endpoints support pagination with `page` and `per_page` parameters. The response includes pagination information:

```json
{
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 100,
    "pages": 2
  }
}
```
