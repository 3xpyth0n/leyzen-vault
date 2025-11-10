# Changelog

All notable changes to this project will be documented in this file.

The Leyzen Vault project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
