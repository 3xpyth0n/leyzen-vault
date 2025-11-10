# Developer Documentation - Leyzen Vault

## Architecture

Leyzen Vault is a Flask application with a Vue.js frontend, using PostgreSQL for the database and an end-to-end encryption (E2EE) system.

### Project Structure

```
leyzen-vault/
├── src/
│   ├── vault/              # Main Flask application
│   │   ├── app.py          # Flask entry point
│   │   ├── blueprints/     # API routes
│   │   ├── database/       # Database models and schema
│   │   ├── services/       # Business logic
│   │   ├── middleware/     # Middleware (auth, etc.)
│   │   └── static/         # Vue.js frontend
│   └── orchestrator/       # MTD Orchestrator
├── tests/                  # Unit and integration tests
├── docs/                   # Documentation
└── docker-generated.yml    # Docker configuration (auto-generated)
```

## Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 16
- Docker and Docker Compose

### Installation

1. Clone the repository
2. Install Python dependencies:

```bash
pip install -r infra/vault/requirements.txt
```

3. Install Node.js dependencies:

```bash
cd src/vault/static
npm install
```

4. Configure environment variables:

```bash
cp env.template .env
# Edit .env with your configurations
```

5. Database initialization:

The database is automatically initialized on first startup via `init_db()` which calls `db.create_all()`. No manual migration commands are needed.

### Running in Development

**Backend:**

```bash
flask run --debug
```

**Frontend:**

```bash
cd src/vault/static
npm run dev
```

**With Docker:**

```bash
docker compose -f docker-generated.yml up
```

## Technical Architecture

### End-to-End Encryption

1. **User Master Key**: Derived from password with PBKDF2 (future: Argon2-browser)
2. **VaultSpace Key**: Randomly generated, encrypted with master key
3. **File Key**: Randomly generated, encrypted with VaultSpace key
4. **File Data**: Encrypted with AES-GCM using file key

### Backend Services

#### `AuthService`

Manages authentication and JWT tokens.

#### `AdvancedFileService`

Manages files and folders, CRUD operations, soft delete, starred, recent.

#### `QuotaService`

Manages user quotas.

#### `AdvancedSharingService`

Manages advanced sharing with public links.

#### `ThumbnailService`

Generates and manages thumbnails.

#### `CacheService`

In-memory cache with TTL.

### Data Models

#### `User`

User with email, username, password_hash, roles.

#### `VaultSpace`

Storage space (personal).

#### `File`

File or folder with encrypted metadata, soft delete, starred.

#### `Quota`

Storage and file quotas for users.

#### `PublicShareLink`

Public sharing links with expiration, limits, password.

### API Endpoints

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for complete documentation.

### Frontend

#### Vue.js Structure

- **Components**: Reusable components (FileListView, SearchBar, etc.)
- **Views**: Main pages (Dashboard, VaultSpaceView, etc.)
- **Services**: API clients (api.js, search.js, etc.)
- **Utils**: Utilities (debounce.js, keyManager.js)

#### Client-Side Key Management

The `keyManager.js` file manages:

- Master key derivation from password
- VaultSpace key generation and encryption
- File key generation and encryption
- In-memory key caching

## Tests

### Unit Tests

```bash
pytest tests/test_*.py
```

### Integration Tests

```bash
pytest tests/test_api_integration.py
```

### Security Tests

```bash
pytest tests/test_security_audit.py
```

### Performance Tests

```bash
pytest tests/test_performance.py
```

## Deployment

### Production

1. Configure production environment variables
2. Build Docker images:

```bash
docker compose -f docker-generated.yml build
```

3. Start services:

```bash
docker compose -f docker-generated.yml up -d
```

### Security

- Use HTTPS in production
- Configure security headers (CORS, CSP, etc.)
- Enable rate limiting
- Configure database backups
- Monitor logs and metrics

## Contributing

1. Create a branch for your feature
2. Write tests for your code
3. Ensure all tests pass
4. Submit a pull request

## Debugging

### Logs

Logs are available in:

- Backend: `logs/vault.log`
- Frontend: Browser console

### Database

Access the database:

```bash
psql -U leyzen -d leyzen_vault
```

### Docker

View container logs:

```bash
docker compose -f docker-generated.yml logs -f vault
```

## Future Improvements

- Migration to Argon2-browser for key derivation
- Support for more file types for preview
- Client synchronization (PWA)
- Mobile applications
- Integration with other cloud services
- Improved search with full-text indexing
- Real-time collaboration support

## Support

For any technical questions, open an issue on the GitHub repository.
