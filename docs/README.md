# Leyzen Vault Documentation

This directory contains developer documentation and policies for the Leyzen Vault project. For user-facing and operational documentation, see the [official documentation](https://docs.leyzen.com).

## Documentation Map

### Core Documentation

- **[AGENTS.md](AGENTS.md)** - Code style and architecture guidelines for AI assistants and contributors
  - Repository structure and organization
  - Python and Go coding guidelines
  - Flask blueprints and templates
  - Front-end assets and styling
  - Service startup order
  - Dockerfile patterns
  - Environment variable naming conventions
  - Authentication differences

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and component communication
  - High-level architecture overview
  - Service components and responsibilities
  - Startup order and dependencies
  - Container rotation flow
  - Inter-component communication
  - Network and volume management

- **[AUTHENTICATION.md](AUTHENTICATION.md)** - Authentication architecture and differences
  - Differences between Vault and Orchestrator authentication
  - `login_required()` decorator implementations
  - CAPTCHA and CSRF token handling
  - Authentication flows
  - Best practices for adding authentication

### Security Documentation

- **[SECURITY.md](SECURITY.md)** - Security policy and vulnerability reporting
  - Supported versions
  - Vulnerability reporting process
  - Response expectations
  - Automated security scanning
  - Secret rotation procedures

- **[SECURITY_RUNTIME.md](SECURITY_RUNTIME.md)** - Runtime security controls
  - Content Security Policy (CSP) implementation
  - CAPTCHA and CSRF protection
  - Proxy trust configuration
  - Docker proxy allowlisting
  - Session security

### Contribution and Policies

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution workflow and conventions
  - How to contribute
  - Commit message conventions
  - Pull request process
  - Code review guidelines

- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** - Community standards
  - Code of conduct
  - Expected behavior
  - Reporting guidelines

### API and Technical Documentation

- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - API endpoint documentation
  - Vault API endpoints
  - Orchestrator API endpoints
  - Request/response formats
  - Authentication requirements

- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Developer setup and workflow
  - Development environment setup
  - Building and testing
  - Debugging tips
  - Common issues and solutions

### Legal and Licensing

- **[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)** - Third-party licenses
  - Licenses for dependencies
  - Attribution requirements

- **[TRADEMARKS.md](TRADEMARKS.md)** - Trademark usage guidelines
  - Trademark policy
  - Usage guidelines

## Documentation Organization

### Official Documentation (User & Operational Guides)

The [official documentation](https://docs.leyzen.com) contains user-facing and operational documentation:

- Quickstart guides
- Installation instructions
- Configuration guides
- CLI usage (`leyzenctl`)
- Architecture overview (user-friendly)
- Security model
- Telemetry and monitoring
- CI/CD procedures
- FAQ

### Repository `docs/` Directory (Developer & Code Documentation)

This directory contains developer-focused documentation:

- Code style and architecture guidelines
- Security policies and procedures
- Contribution guidelines
- API documentation
- Technical implementation details

## Documentation Maintenance

### When to Update Documentation

- **User-facing changes**: Update official documentation and README.md
- **Code changes**: Update AGENTS.md, ARCHITECTURE.md, or API_DOCUMENTATION.md
- **Security changes**: Update SECURITY.md or SECURITY_RUNTIME.md
- **Process changes**: Update CONTRIBUTING.md or CODE_OF_CONDUCT.md

### Documentation Standards

- Use clear, concise language
- Include code examples where appropriate
- Keep documentation up to date with code changes
- Cross-reference related documentation
- Use consistent formatting and structure

### Adding New Documentation

1. Create the documentation file in `docs/`
2. Add an entry to this README.md
3. Update relevant cross-references
4. Update the main README.md if it's user-facing
5. Update the official documentation if it's operational documentation

## Quick Links

- [Official Documentation](https://docs.leyzen.com)
- [Main README](../README.md)
- [CHANGELOG](../CHANGELOG.md)
- [License](../LICENSE)

## Contributing to Documentation

When contributing to documentation:

1. Follow the existing documentation style and format
2. Use clear, concise language
3. Include code examples where helpful
4. Cross-reference related documentation
5. Update this README.md if adding new documentation files
6. Keep documentation synchronized with code changes

For questions or suggestions about documentation, please open an issue or pull request on GitHub.
