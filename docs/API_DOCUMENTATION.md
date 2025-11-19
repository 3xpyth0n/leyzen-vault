# API Documentation - Leyzen Vault

## Base URL

```
http://localhost:8080/api
```

## Authentication

All requests (except `/auth/register` and `/auth/login`) require an API key in the header:

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

## Endpoints

### Authentication

#### POST `/auth/register`

Create a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "username"
}
```

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  }
}
```

#### POST `/auth/login`

Login.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username"
  }
}
```

### VaultSpaces

#### GET `/vaultspaces`

List all user VaultSpaces.

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

#### GET `/vaultspaces/:id`

Get a specific VaultSpace.

#### POST `/vaultspaces`

Create a new VaultSpace.

**Request Body:**

```json
{
  "name": "New VaultSpace",
  "vaultspace_type": "personal"
}
```

### Files

#### GET `/v2/files`

List files in a VaultSpace.

**Query Parameters:**

- `vaultspace_id` (required): VaultSpace ID
- `parent_id` (optional): Parent folder ID
- `page` (optional, default: 1): Page number
- `per_page` (optional, default: 50): Items per page

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

#### POST `/v2/files`

Upload a file or create a folder.

**Request Body (file):**

```json
{
  "vaultspace_id": "uuid",
  "original_name": "file.txt",
  "encrypted_data": "base64_encrypted_data",
  "encrypted_key": "base64_encrypted_key",
  "iv": "base64_iv",
  "mime_type": "text/plain",
  "size": 1024,
  "parent_id": "uuid"
}
```

**Request Body (folder):**

```json
{
  "vaultspace_id": "uuid",
  "name": "folder_name",
  "mime_type": "application/x-directory",
  "parent_id": "uuid"
}
```

#### GET `/v2/files/:id`

Get file details.

#### PUT `/v2/files/:id`

Update a file (rename, move).

**Request Body:**

```json
{
  "original_name": "new_name.txt",
  "parent_id": "uuid"
}
```

#### DELETE `/v2/files/:id`

Delete a file (soft delete).

#### POST `/v2/files/:id/star`

Star/unstar a file.

#### GET `/v2/files/starred`

List starred files.

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace

#### GET `/v2/files/recent`

List recent files.

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace
- `limit` (optional, default: 50): Maximum number of results
- `days` (optional, default: 30): Number of days

### Trash

#### GET `/v2/trash`

List files in trash.

**Query Parameters:**

- `vaultspace_id` (optional): Filter by VaultSpace

#### POST `/v2/trash/:id/restore`

Restore a file from trash.

#### DELETE `/v2/trash/:id`

Permanently delete a file.

### Sharing

#### POST `/v2/sharing/public-links`

Create a public share link.

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
  "public_link": {
    "id": "uuid",
    "token": "share_token",
    "expires_at": "2024-01-08T00:00:00Z",
    "max_downloads": 10,
    "download_count": 0
  }
}
```

#### GET `/v2/sharing/public-links`

List public links created by the user.

#### GET `/v2/sharing/public-links/:token`

Get a public link by token.

#### PUT `/v2/sharing/public-links/:id`

Update a public link.

#### DELETE `/v2/sharing/public-links/:id`

Revoke a public link.

#### GET `/v2/sharing/public-links/:token/access`

Access a resource via a public link.

**Query Parameters:**

- `password` (optional): Password if required

#### GET `/v2/sharing/public-links/:token/download`

Download a resource via a public link.

### Quotas

#### GET `/v2/quotas/me`

Get user quota.

**Response:**

```json
{
  "quota": {
    "max_storage_bytes": 1073741824,
    "used_storage_bytes": 52428800,
    "max_files": 10000,
    "used_files": 150,
    "usage_percentage": 4.88
  }
}
```

### Search

#### GET `/search/files`

Search files.

**Query Parameters:**

- `q` (required): Search term
- `vaultspace_id` (optional): Filter by VaultSpace
- `mime_type` (optional): Filter by MIME type
- `min_size` (optional): Minimum size in bytes
- `max_size` (optional): Maximum size in bytes
- `created_after` (optional): ISO date
- `created_before` (optional): ISO date
- `sort_by` (optional): Sort field (relevance, name, date, size)
- `sort_order` (optional): Order (asc, desc)
- `limit` (optional): Maximum number of results
- `offset` (optional): Offset for pagination

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

### Thumbnails

#### GET `/v2/thumbnails/:file_id`

Get a thumbnail.

**Query Parameters:**

- `size` (optional, default: 256x256): Size (64x64, 128x128, 256x256)

#### POST `/v2/thumbnails/:file_id/generate`

Generate thumbnails for a file.

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
