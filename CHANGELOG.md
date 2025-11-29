# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Preview support for video, audio, text, and markdown files ([#12](https://github.com/3xpyth0n/leyzen-vault/issues/12)).
- Email verification is now mandatory for all users except the superadmin.
- Conflict resolution modal for file and folder name conflicts with options to replace, keep both (auto-rename), or skip ([#13](https://github.com/3xpyth0n/leyzen-vault/issues/13)).
- VaultSpace pinning feature allowing users to pin frequently used VaultSpaces to the sidebar for quick access ([#14](https://github.com/3xpyth0n/leyzen-vault/issues/14)).
- Dynamic icon system using Lucide Icons library with searchable IconPicker for VaultSpace customization.

### Changed

- Improved Docker container isolation, excluded Python caches from builds, and minimized write permissions for each container.
- Migrated from hardcoded SVG icons to Lucide Icons library, providing access to 1000+ modern icons. The IconPicker now includes search functionality allowing users to find icons by name.
- Optimized build code splitting to reduce chunk sizes below 100 kB by separating vendor dependencies and component chunks.

### Fixed

- Increased `api_keys.key_prefix` column capacity and added automatic migration to prevent API key creation failures caused by truncation.
- Invited accounts now default to the `user` role to avoid missing-role errors during signup completion.
- HAProxy now accepts either combined PEM files or separate certificate/key inputs by validating and generating a single bundle automatically.
- HTTPS detection now honors custom HTTP/HTTPS ports and tunnel frontends, preventing CSP errors and redirect loops when overriding `HTTP_PORT`/`HTTPS_PORT`.
- Fixed setup endpoint redirecting to dashboard without master key initialization. The `/setup` endpoint now follows the same flow as `/signup`, requiring email verification and redirecting to login page instead of automatically authenticating users.
- Fixed SharingManager initialization failure on browsers without Trusted Types support (e.g., Firefox) by implementing DOM API fallback for modal creation.
- Fixed MIME type detection priority: extension-based detection now takes precedence over file-magic, preventing `application/octet-stream` for files with known extensions. Added migration script and frontend normalization for WEBP and other formats.

## [2.2.1] - 2025-11-23

### Fixed - Critical Installation Issues

#### Fresh Installation Fixes

- **Database Initialization**: Fixed critical issue where `users` table and other required tables (28 tables total) were not created when `db.create_all()` raised duplicate errors. Added comprehensive table verification and individual table creation for missing tables using explicit SQL commands (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN`) with retry logic and detailed logging.
- **JWT jti Column Migration**: Enhanced migration logic to ensure `jti` column is always created in `jwt_blacklist` table, even when database objects already exist. Added explicit SQL commands and retry mechanisms with comprehensive logging to prevent startup blocking.
- **SSO Token Generation**: Fixed SSO authentication failures by adding required `jti` claim to JWT tokens generated for OAuth2 and OIDC providers. Tokens now include `jti`, `typ`, and `iss` claims for consistency with password-based authentication tokens and production security requirements.
- **Session Cookie Security**: Fixed CAPTCHA session expiration when accessing via IP addresses (e.g., `http://192.168.1.36:8080`) by dynamically adjusting `SESSION_COOKIE_SECURE` based on request security context (`request.is_secure`). Session cookies now work correctly in HTTP contexts while maintaining security for HTTPS.
- **Web Crypto API**: Added robust error handling and context detection for `crypto.subtle` availability, with clear error messages for non-secure contexts (HTTP on IP addresses). Prevents "Cannot read properties of undefined" errors during master key derivation.
- **Static Assets HTTPS Upgrade**: Removed `upgrade-insecure-requests` directive from Content Security Policy when using HTTP, and disabled security headers that force HTTPS for private IP addresses. Prevents `ERR_SSL_PROTOCOL_ERROR` when accessing via HTTP.

### Security

- **SSO Token Security**: All SSO-generated JWT tokens now include `jti`, `typ`, and `iss` claims for consistency with password-based authentication tokens and production security requirements.
- **Internal API Token**: Random token generation with automatic storage in encrypted `system_secrets` table. Removed deprecated `derive_internal_api_token()` function.
- **JWT Replay Protection**: Automatic `jti` column migration with retry logic. Application no longer blocks startup if column missing.
- **Rate Limiting**: Enforced fail-closed behavior. All rate limiting errors result in request denial, even in development.
- **Argon2-browser Key Derivation**: Replaced PBKDF2 with Argon2-browser for client-side master key derivation. Uses Argon2id with optimized parameters providing enhanced protection against brute-force and GPU attacks while maintaining browser compatibility.
- **Internal API Hardening**: IP whitelist, strict rate limiting (60 req/min), detailed logging, User-Agent validation.
- **Origin Validation**: Never completely disabled, even in development. Permissive but active validation in dev mode.
- **JSON DoS Protection**: Safe JSON parsing with size and depth limits across all endpoints.
- **API Key Prefix**: Configurable or random per-instance prefix to prevent predictability.
- **TOTP Security**: Zero-tolerance window, code reuse protection with cache.
- **Log Sanitization**: Enhanced masking of tokens (4 chars only), secrets, full paths. Safe logging utility.
- **File Validation**: Magic bytes validation for whitelisted files to detect tampering.
- **Error Standardization**: Unique error codes (ERR\_\*) to prevent information leakage.

### Added

#### Share Link Email Sending

- **Email Share Links**: Send share links via email directly from the `/shared` page. Email modal with recipient address validation and styled HTML email template.
- **Decryption Key Validation**: Automatic validation ensures the share link contains the decryption key before sending. Error modal displayed if key is missing.
- **Email Template**: Styled HTML email template with share link, file name, and security information. Includes plain text fallback for email clients.

#### Recursive File Search

- **File and Folder Search**: Recursive search functionality for files and folders with pattern matching across all subfolders.
- **Full Path Display**: Search results display complete file paths for location clarity.
- **Advanced Filters**: Filtering by file type, size range, and file/folder toggle with automatic application. Sort by relevance, name, date, or size.
- **Search Panel**: Dropdown results panel with pagination support that auto-closes after file selection.
- **Backend Optimization**: Whoosh full-text search index with fuzzy matching and SQL ILIKE fallback, including relevance scoring.

### Changed

- **Database Schema**: Improved `init_db()` function to verify and create all required tables individually, ensuring complete database initialization even on partial failures or duplicate errors.
- **CORS Configuration**: Changed from blocking to warning in production to allow application startup.

### Important Notes

⚠️ **Critical for Fresh Installations**: Previous releases (v1.0.0 through v2.2.0) may fail on fresh installations due to database initialization issues. **All users performing fresh installations must use v2.2.1 or later.**

If you already have a working installation from a previous version, you can safely upgrade to v2.2.1 without issues.

## [2.2.0] - 2025-11-22

### Added

#### Two-Factor Authentication (2FA)

- **TOTP-Based Authentication**: Optional two-factor authentication using Time-based One-Time Password (TOTP) compliant with RFC 6238. Users can enable 2FA through the Account Settings page.
- **Authenticator App Support**: Compatible with popular authenticator apps including Google Authenticator, Authy, 1Password, Microsoft Authenticator, and other TOTP-compatible applications.
- **QR Code Setup**: Automatic QR code generation for easy 2FA setup. Users can scan the QR code with their authenticator app for instant configuration.
- **Backup Recovery Codes**: 8-character backup codes generated during 2FA setup for emergency account access. Users can regenerate backup codes at any time through their account settings.

#### Other Features

- **Automatic Storage Cleanup**: Implemented background worker in orchestrator that periodically detects and removes orphaned files from storage, ensuring disk space is properly reclaimed from deleted files.
- **Chunked File Upload**: Added chunked upload system for large files. Files larger than 5MB are automatically split into chunks and uploaded sequentially, preventing memory issues and enabling upload of files of any size.
- **Encryption Overlay for SSO Users**: Added glassmorphic encryption overlay that appears when SSO-authenticated users access encrypted VaultSpaces. The overlay prevents unexpected logout and provides a clear interface for password entry to decrypt files.
- **Configurable Gunicorn Workers**: Added `VAULT_WORKERS` environment variable to configure the number of Gunicorn worker processes for the vault service, with a default value of 2 workers.
- **Automatic Thumbnail Generation**: Lazy-loaded thumbnail generation for images displayed in grid view with automatic detection and generation on scroll.

#### Moving Target Defense (MTD) Enhancements

- **Enhanced File Validation and Promotion**: Improved MTD rotation process with streamlined file validation and promotion system.
  - Files in temporary storage are validated against database whitelist before promotion to persistent storage.
  - Only legitimate files are preserved during container rotation.
  - Invalid files are automatically removed, enhancing security and preventing malware persistence.

### Changed

- **Orchestrator UI Style**: Updated orchestrator UI styling to match the vault's design system for consistent user experience across the application.
- **Authentication Migration**: Migrated from hybrid session/CSRF authentication to JWT-only authentication. CSRF protection has been removed as JWT tokens in Authorization headers are already protected by Same-Origin Policy. This provides a cleaner and more secure authentication approach for API endpoints while maintaining defense-in-depth security through Origin/Referer header validation and Content-Type validation.
- **File Promotion Service**: File promotion is now a common service shared between vault and orchestrator, rather than being reserved to the orchestrator. Files are automatically promoted to persistent storage after each upload, ensuring persistence even without orchestrator rotation.

### Security

- **SSRF Vulnerability Protection**: Fixed critical Server-Side Request Forgery (SSRF) vulnerabilities in SSO and Webhook services that could allow attackers to access internal services or cloud metadata APIs (AWS, GCP, Azure).
  - Implemented comprehensive URL validation blocking private networks (RFC 1918), localhost, link-local addresses, and cloud metadata service (169.254.169.254)
  - Added DNS resolution checking to prevent DNS rebinding attacks
  - Disabled HTTP redirects on all external requests
  - Enforced strict validation of all URLs in SSO provider configurations (OAuth2, OIDC, SAML) and webhook endpoints
  - All vulnerabilities resolved with 28 unit tests providing comprehensive coverage

### Fixed

- **Permanent File Deletion**: Fixed issue where permanently deleted files were removed from database but remained on disk, causing orphaned files accumulation. Physical files are now properly deleted from both primary and source storage locations.
- **File List Synchronization**: Fixed critical issues with file list synchronization where deleted files would reappear, files would appear duplicated after copy/move operations, and files in trash would still appear in recent/starred views. The fix includes proper filtering of deleted files in all operations, improved cache invalidation, and forced cache-busting refresh in frontend views.
- **Modal Display After Page Refresh**: Fixed issue where confirmation modals (logout, delete, etc.) would not appear after page refresh. The issue was caused by CSS conflicts where global styles were hiding modal overlays.
- **SSO User Unexpected Logout**: Fixed issue where SSO-authenticated users were automatically logged out when canceling the password modal. Users can now cancel the password entry without being disconnected, with the encryption overlay remaining visible until they unlock their files.
- **View Synchronization**: Synchronized file view functionality across VaultSpaceView, StarredView, and RecentView by implementing a shared composable for selection management, view mode switching, and encryption overlay handling, ensuring consistent behavior across all views.
- **Origin Validation Security**: Strengthened origin validation to block unauthorized origins and explicitly reject "null" origin in production mode, preventing CSRF attacks.
- **Timing Attack Protection**: Implemented constant-time comparisons for password and token verification to prevent timing-based enumeration attacks.

## [2.1.0] - 2025-11-15

### Added

#### UI Enhancements

- **ZIP Archive Icon**: Added dedicated ZIP archive icon for ZIP files and the "Zip Folder" menu option. ZIP files now display a distinctive archive icon instead of the generic file icon, making them easily identifiable in file listings and context menus.

#### Share Link Password Protection

- **Password-Protected Share Links**: Users can now protect share links with a password when creating them. The password is optional and can be set via a checkbox in the share link creation modal.
- **Password Validation on Download**: When accessing a password-protected share link, users are required to enter the password before downloading the file. The password is validated server-side before file access is granted.
- **Password Error Handling**: Comprehensive error handling for invalid passwords with clear error messages. Users receive feedback when the password is incorrect or missing.
- **Backend Password Support**: Full backend support for password-protected share links using secure password hashing (Argon2). The `has_password` flag is included in all API responses to indicate password protection status.

#### ZIP Folder Functionality

- **Folder Zipping**: Users can now zip entire folders (including all subfolders and files) to create a single ZIP file. The ZIP file preserves the original folder structure and is encrypted like any other file in the system. The ZIP file can be shared via share links.
- **ZIP Extraction**: Users can upload ZIP files and extract them to recreate the folder structure with all contained files. Each file is individually encrypted and uploaded to the VaultSpace.
- **Client-Side Processing**: All ZIP operations (creation and extraction) are performed client-side. Files are decrypted, processed, and re-encrypted entirely in the browser for maximum security.
- **Progress Tracking**: Real-time progress indicators for both zipping and extraction operations, showing current file being processed and overall progress.
- **Error Handling**: Comprehensive error handling for quota limits, network errors, corrupted ZIP files, and missing encryption keys with user-friendly error messages.

#### Password Change with Automatic Key Re-encryption

- **Automatic VaultSpace Key Re-encryption**: Password change now automatically re-encrypts all VaultSpace keys with the new master key before updating the password. This ensures that all encrypted files remain accessible after password change.
- **Password Verification**: Added verification step to ensure the current password can decrypt at least one VaultSpace key before proceeding with password change. Prevents password change with incorrect password.

#### Admin Dashboard Enhancements

- **Enhanced Dashboard Statistics**: Improved admin dashboard with enriched statistics including user role breakdown, storage usage progress bars, and average metrics per user. Added visual indicators for disk storage usage with percentage display and color-coded warnings.
- **Recent Activity Overview**: New "Recent Activity" section displaying the 3 most recent audit log entries with success/failure indicators, timestamps, and quick access to full audit logs.
- **Top Users by Storage**: New "Top Users by Storage" card showing the 3 users with highest storage consumption, including visual progress bars and quick navigation to user management.
- **Quota Alerts**: New "Quota Alerts" section displaying users approaching their storage limits (≥80% usage) with visual warnings and percentage indicators for proactive quota management.
- **Quick Stats Cards**: Added clickable quick stats cards for API Keys and SSO Providers with summary information and direct navigation to respective management sections.
- **Dashboard Refresh**: Added manual refresh button and last update timestamp indicator for real-time statistics monitoring.
- **Improved UX**: Enhanced user experience with clickable cards, better visual hierarchy, and responsive grid layout for better information density.

#### Admin Panel Migration

- **User Management Migration**: Migrated all user management functionalities from `/account` page to the Admin Panel's "Users" tab..
- **User Invitations Migration**: Migrated invitation management system from `/account` page to the Admin Panel's "Users" tab. Admins can now create, view, resend, and cancel user invitations directly from the centralized admin interface.
- **Domain Rules Migration**: Migrated domain rules management from `/account` page to the Admin Panel's "Authentication" tab. Domain rules for SSO authentication are now managed alongside SSO provider configuration for better organization and workflow.
- **Centralized Admin Interface**: Removed the "Administration" section from the `/account` page, centralizing all administrative actions in the dedicated Admin Panel for improved organization and user experience. All admin functionalities are now accessible through the Admin Panel's dedicated tabs.

#### Single Sign-On (SSO)

- **SSO Provider Management**: Complete SSO provider management system with support for multiple provider types (Google, Microsoft Entra, Slack, Discord, GitLab, OIDC Generic, SAML Generic, Email Magic Link). Admins can create, edit, activate/deactivate, and delete SSO providers through the admin panel.
- **Provider Type Presets**: Intuitive provider creation with predefined configurations for popular SSO providers, simplifying setup with provider-specific fields and automatic endpoint configuration.
- **Email Magic Link Authentication**: Passwordless authentication via email magic links. Users receive a secure link via email to authenticate without a password. Includes link expiry management.
- **Provider Validation**: Comprehensive validation system ensuring provider name uniqueness and preventing multiple active providers of the same preset type (e.g., only one active Google provider at a time).
- **Password Authentication Toggle**: System-wide toggle to disable password authentication and CAPTCHA. When disabled, requires at least one active SSO provider (including Email Magic Link). Existing users can authenticate via SSO providers that map to their email address.
- **SSO Callback Handling**: Robust callback handling for all SSO provider types with proper error handling and user feedback. Automatic redirect to dashboard on successful authentication.
- **SMTP Configuration Testing**: Built-in SMTP configuration testing for Email Magic Link providers with detailed error feedback and status indicators in the admin panel.

### Changed

- **Account Page Simplification**: Removed the "Administration" section from the `/account` page. All administrative functionalities (user management, invitations, domain rules) have been moved to the dedicated Admin Panel for better organization and separation of concerns. The account page now focuses solely on user account settings and profile management.

### Fixed

- **API Key Permissions**: Fixed security issue where admins could create API keys for any user, including super admins. Admins can now only create API keys for themselves, while super admins can create API keys for any user.
- **SSO Error Handling**: Fixed SSO authentication error display on login page. Errors from SSO callbacks are now properly displayed to users with automatic URL cleanup.
- **VaultSpace Name Duplicate Check**: Fixed VaultSpace name duplicate check to validate duplicates per owner instead of globally. Users can now create VaultSpaces with the same name as other users' VaultSpaces, but cannot create duplicate names within their own VaultSpaces.
- **File Reappearance After Deletion**: Fixed issue where deleted or moved files would reappear after page refresh. Improved cache invalidation mechanism to invalidate all cache entries for a vaultspace and user after any modifying operation (delete, move, rename, create folder), ensuring all pages and parent folders are properly refreshed.
- **POST Buttons Malfunction After Container Restart**: Fixed issue where all POST request buttons (move, copy, delete, logout) would stop functioning after container rebuild or restart. Implemented automatic JWT token refresh mechanism that attempts to refresh expired tokens before redirecting to login, preventing UI elements from becoming unresponsive due to expired JWTs.

---

## [2.0.0] - 2025-11-10

### Added

#### Architecture & Infrastructure

- **PostgreSQL Database**: Complete migration to PostgreSQL for all data storage (users, files, metadata, audit logs, share links, vaultspaces). Schema is automatically created on first startup using SQLAlchemy ORM.
- **Vue.js Single Page Application (SPA)**: Complete frontend rewrite with Vue.js 3, Vite, Vue Router, and Pinia for state management. Modern, responsive UI with client-side routing.
- **REST API v2**: Comprehensive RESTful API with JWT authentication for all operations. Full API documentation available in `docs/API_DOCUMENTATION.md`.
- **Service Layer Architecture**: Refactored codebase with dedicated services for each major feature (30+ new services).

#### Core Features

- **VaultSpaces**: Workspace system with personal spaces. Each VaultSpace has its own encryption keys.
- **Advanced Sharing**: Enhanced sharing system with link expiration, download limits, and password protection.
- **Folders & Hierarchy**: Full folder structure support with nested folders and hierarchical organization.
- **Search**: Encrypted search functionality with searchable encryption for secure, privacy-preserving file search.
- **Trash System**: File deletion with trash/recycle bin functionality for recovery.
- **Device Management**: Device registration and management for enhanced security.
- **User Invitations**: Admin-controlled user invitation system with email verification.
- **Email Verification**: Email verification system for new user accounts.
- **Account Management**: Comprehensive user account management with profile settings.

#### Enterprise Features

- **Single Sign-On (SSO)**: Domain-based SSO rules and SSO configuration.
- **Admin Dashboard**: Comprehensive admin dashboard with user management, system settings, and analytics.
- **Quota Management**: Complete quota management system with real-time usage tracking. Admins can view all users with their actual storage and file usage, set storage and file limits per user, and monitor quota usage with visual indicators. Quota enforcement prevents uploads when limits are exceeded with user-friendly error modals.
- **API Key Management**: Admin panel for generating and revoking API keys for automation and external integrations (e.g., n8n). API keys use Argon2 hashing and support Bearer token authentication alongside JWT tokens.
- **Audit Logging**: Enhanced audit logging with PostgreSQL storage, automatic cleanup, and detailed activity tracking.
- **Behavioral Analysis**: Behavioral analysis service for security monitoring and anomaly detection.
- **Zero Trust**: Zero Trust security service for advanced threat detection and prevention.
- **Backup Service**: Automated backup service for data protection and disaster recovery.
- **Template System**: VaultSpace templates for quick workspace creation and standardization.

#### Security Enhancements

- **JWT Authentication**: JWT-based authentication for API endpoints with token refresh and blacklist support.
- **Master Key Derivation**: PBKDF2-based master key derivation with per-user salts for enhanced security.
- **VaultSpace Key Management**: Hierarchical key management with VaultSpace keys and file keys, all encrypted with user master keys.
- **Searchable Encryption**: Privacy-preserving encrypted search without exposing file contents.
- **Enhanced Rate Limiting**: Improved rate limiting with IP-based tracking and configurable limits.
- **Trusted Types**: Content Security Policy enhancements with Trusted Types for XSS prevention.
- **Email Service**: SMTP integration for email notifications, verification, and invitations.
- **Password Security**: Enhanced password security with PBKDF2 hashing and strength validation.

#### Developer Experience

- **API Documentation**: Complete API documentation in `docs/API_DOCUMENTATION.md`.
- **Developer Guide**: Comprehensive developer guide in `docs/DEVELOPER_GUIDE.md`.
- **Authentication Documentation**: Detailed authentication architecture documentation in `docs/AUTHENTICATION.md`.
- **Database Schema**: Complete database schema with SQLAlchemy models and automatic migrations.
- **Common Services**: Shared services and utilities in `src/common/services/` for code reuse.
- **Middleware System**: Middleware system for authentication, authorization, and request processing.
- **Validation System**: Comprehensive validation system with custom validators for all inputs.

#### User Interface

- **Modern UI/UX**: Complete UI redesign with modern design principles, animations, and responsive layout.
- **Container selection in TUI**: Added interactive container selection for Start, Stop, Restart, and Build actions in `leyzenctl` TUI. Users can select "All" containers or choose specific services with multi-selection support.
- **Keyboard Shortcuts**: Comprehensive keyboard shortcuts for power users.
- **Drag & Drop**: File upload with drag-and-drop support.
- **Context Menu**: Right-click context menus for files and folders.
- **Virtual List**: Virtual scrolling for large file lists with performance optimization.
- **Service Worker**: Service worker for offline support and performance optimization.
- **Notifications**: In-app notification system for user feedback.
- **Animations**: Smooth animations and transitions for better user experience.

### Changed

#### Architecture

- **Database**: Migrated from file-based storage to PostgreSQL for all metadata, users, and system data.
- **Frontend**: Migrated from server-rendered templates to Vue.js SPA with client-side routing.
- **Authentication**: Enhanced authentication system with JWT tokens for API and session-based auth for web interface.
- **File Storage**: Enhanced file storage system with support for persistent storage and tmpfs volumes.
- **API Structure**: Complete API restructuring with RESTful endpoints and consistent response formats.
- **Service Architecture**: Refactored to service-oriented architecture with dedicated services for each feature.

#### Configuration

- **Environment Variables**: Extended `env.template` with 100+ new configuration options for all new features.
- **PostgreSQL Configuration**: Added PostgreSQL connection configuration with `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- **SMTP Configuration**: Added SMTP configuration for email services (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, etc.).
- **Security Configuration**: Enhanced security configuration with email verification, device management, and behavioral analysis settings.

#### Dependencies

- **Python Dependencies**: Added Flask-SQLAlchemy, psycopg2-binary, PyJWT, and other dependencies for new features.
- **Node.js Dependencies**: Added Vue.js 3, Vite, Vue Router, Pinia, Axios, and other frontend dependencies.
- **Database**: PostgreSQL 16 is now required for deployments.

### Fixed

- **Database Connection**: Fixed database connection handling with proper error messages and fallback modes.
- **File Upload**: Improved file upload handling with better error messages and validation.
- **Authentication Flow**: Fixed authentication flow for both web and API interfaces.
- **Session Management**: Improved session management with proper cookie settings and security headers.
- **Rate Limiting**: Fixed rate limiting for unknown IPs with conservative default limits.
- **CSP Headers**: Enhanced CSP headers with Trusted Types and proper nonce generation.
- **Error Handling**: Improved error handling with consistent error responses and proper logging.
- **Configuration Validation**: Enhanced configuration validation with comprehensive checks and clear error messages.

### Security

- **JWT Security**: Implemented JWT authentication with secure token generation, validation, and blacklist support.
- **Password Security**: Enhanced password security with PBKDF2 hashing and per-user salts.
- **Key Management**: Improved key management with hierarchical key structure and secure key derivation.
- **Email Verification**: Added email verification requirement for new user accounts.
- **Device Management**: Added device registration and management for enhanced security.
- **Audit Logging**: Enhanced audit logging with PostgreSQL storage and automatic cleanup.
- **Rate Limiting**: Improved rate limiting with IP-based tracking and configurable limits.
- **XSS Prevention**: Enhanced XSS prevention with Trusted Types and proper input sanitization.
- **CSRF Protection**: Improved CSRF protection with token validation and secure cookie settings.
- **SQL Injection Prevention**: Prevented SQL injection with parameterized queries and ORM usage.
- **Secrets Management**: Removed all hardcoded secrets and require environment variables for all sensitive data.
- **Production Mode**: Enhanced production mode with strict validation and rejection of default credentials.

### Deprecated

- **File-based Storage**: File-based metadata storage is deprecated in favor of PostgreSQL.
- **Server-rendered Templates**: Server-rendered templates are deprecated in favor of Vue.js SPA.
- **Session-based API Auth**: Session-based API authentication is deprecated in favor of JWT tokens (still supported for web interface).
- **Legacy Share Service**: Legacy share service (`src/vault/services/share_service.py`) is removed and replaced with `ShareLinkService` and `AdvancedSharingService`.
- **Legacy Logging Service**: Legacy logging services (`src/vault/services/logging.py`, `src/orchestrator/services/logging.py`) are removed and replaced with `common/services/logging.py`.
- **Python Validation Script**: Python validation script (`tools/validate-env.py`) is removed and replaced with Go-based validation in `leyzenctl`.

---

## [1.0.0] - 2025-11-05

## Initial Release

This is the first official release of Leyzen Vault (Initial Release). Leyzen Vault is a modular moving-target defense orchestrator that automates ephemeral container rotation for a secure file storage system.

This initial release includes:

- End-to-end encryption (E2EE) with client-side encryption using Web Crypto API
- Dynamic stack composition with Docker Compose and HAProxy artifact generation
- Rotation-aware control plane with SSE telemetry
- Defense-in-depth defaults with CAPTCHA authentication, CSP reporting, and proxy trust limits
- Hardened Flask orchestrator with Docker lifecycle coordination
- HAProxy front-end with strict security headers

Licensed under the Business Source License 1.1 (BSL 1.1).
