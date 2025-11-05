#!/usr/bin/env python3
"""Validate Leyzen Vault environment configuration.

This script checks that all required environment variables are set correctly
and warns about common security misconfigurations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    """Main validation function."""
    # Determine .env file location
    repo_root = Path(__file__).resolve().parent.parent
    env_file_override = os.environ.get("LEYZEN_ENV_FILE")
    if env_file_override:
        env_path = Path(env_file_override).expanduser().resolve()
        if not env_path.is_absolute():
            env_path = repo_root / env_path
    else:
        env_path = repo_root / ".env"

    if not env_path.exists():
        print(f"❌ ERROR: .env file not found at {env_path}")
        print(f"   Create it by copying env.template: cp env.template .env")
        return 1

    # Load environment variables from .env file
    env_vars: dict[str, str] = {}
    with env_path.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_vars[key] = value

    errors: list[str] = []
    warnings: list[str] = []

    # Check required variables
    required_vars = [
        "VAULT_USER",
        "VAULT_PASS",
        "ORCH_USER",
        "ORCH_PASS",
        "SECRET_KEY",
        "DOCKER_PROXY_TOKEN",
    ]

    for var in required_vars:
        if not env_vars.get(var):
            errors.append(f"{var} is required but not set")

    # Check environment mode
    env_mode = env_vars.get("LEYZEN_ENVIRONMENT", "prod").strip().lower()
    is_production = env_mode in {"prod", "production", "1", "true"}

    # Check for default credentials in production
    if is_production:
        if env_vars.get("VAULT_USER", "").strip() == "admin":
            errors.append(
                "VAULT_USER cannot be 'admin' in production mode. "
                "Set LEYZEN_ENVIRONMENT=dev for development, or change VAULT_USER."
            )
        if env_vars.get("VAULT_PASS", "").strip() == "admin":
            errors.append(
                "VAULT_PASS cannot be 'admin' in production mode. "
                "Set LEYZEN_ENVIRONMENT=dev for development, or change VAULT_PASS."
            )
        if env_vars.get("ORCH_USER", "").strip() == "admin":
            errors.append(
                "ORCH_USER cannot be 'admin' in production mode. "
                "Set LEYZEN_ENVIRONMENT=dev for development, or change ORCH_USER."
            )
        if env_vars.get("ORCH_PASS", "").strip() == "admin":
            errors.append(
                "ORCH_PASS cannot be 'admin' in production mode. "
                "Set LEYZEN_ENVIRONMENT=dev for development, or change ORCH_PASS."
            )

    # Check secret lengths
    secret_key = env_vars.get("SECRET_KEY", "")
    if secret_key and len(secret_key) < 12:
        errors.append(
            f"SECRET_KEY must be at least 12 characters long (got {len(secret_key)})"
        )

    docker_token = env_vars.get("DOCKER_PROXY_TOKEN", "")
    if docker_token and len(docker_token) < 12:
        errors.append(
            f"DOCKER_PROXY_TOKEN must be at least 12 characters long (got {len(docker_token)})"
        )

    # Check WEB_REPLICAS
    web_replicas = env_vars.get("WEB_REPLICAS", "3")
    try:
        replicas = int(web_replicas)
        if replicas < 2:
            errors.append(
                f"WEB_REPLICAS must be at least 2 for rotation (got {replicas})"
            )
    except ValueError:
        warnings.append(f"WEB_REPLICAS is not a valid integer: {web_replicas}")

    # Check PROXY_TRUST_COUNT
    proxy_trust = env_vars.get("PROXY_TRUST_COUNT", "1")
    try:
        trust_count = int(proxy_trust)
        if trust_count < 0:
            warnings.append("PROXY_TRUST_COUNT should be >= 0")
    except ValueError:
        warnings.append(f"PROXY_TRUST_COUNT is not a valid integer: {proxy_trust}")

    # Check VAULT_AUDIT_RETENTION_DAYS if set
    retention_days = env_vars.get("VAULT_AUDIT_RETENTION_DAYS")
    if retention_days:
        try:
            days = int(retention_days)
            if days < 1:
                warnings.append(
                    f"VAULT_AUDIT_RETENTION_DAYS should be >= 1 (got {days})"
                )
        except ValueError:
            warnings.append(
                f"VAULT_AUDIT_RETENTION_DAYS is not a valid integer: {retention_days}"
            )

    # Print results
    if errors:
        print("❌ VALIDATION FAILED:")
        for error in errors:
            print(f"   • {error}")
        print()
        print("Fix the errors above before deploying to production.")
        return 1

    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   • {warning}")
        print()

    print("✅ Validation passed! All required variables are set correctly.")
    if is_production:
        print("   Production mode detected - credentials validated.")
    else:
        print(f"   Development mode detected (LEYZEN_ENVIRONMENT={env_mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
