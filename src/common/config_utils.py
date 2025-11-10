"""Common configuration utility functions shared across Leyzen Vault components."""

from __future__ import annotations

from common.exceptions import ConfigurationError


_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def parse_bool(value: str | None, *, default: bool) -> bool:
    """Parse a boolean environment variable.

    Args:
        value: String value to parse
        default: Default value if parsing fails or value is None

    Returns:
        Parsed boolean value or default
    """
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    return default


def parse_int_env_var(
    name: str,
    default: int,
    env: dict[str, str],
    min_value: int | None = None,
    max_value: int | None = None,
    *,
    strip_quotes: bool = False,
) -> int:
    """Parse an integer environment variable with optional min/max constraints.

    Args:
        name: Environment variable name
        default: Default value if variable is missing or invalid
        env: Dictionary containing environment variables
        min_value: Minimum value if specified (inclusive), None otherwise
        max_value: Maximum value if specified (inclusive), None otherwise
        strip_quotes: If True, strip matching quotes from the value

    Returns:
        Parsed integer value, or default if parsing fails
    """
    raw_value = env.get(name, str(default)).strip()
    if strip_quotes:
        raw_value = raw_value.strip('"').strip("'")
    try:
        value = int(raw_value)
        if min_value is not None:
            value = max(min_value, value)
        if max_value is not None:
            value = min(max_value, value)
        return value
    except ValueError:
        return default


def validate_secret_entropy(
    secret: str, min_length: int = 32, secret_name: str = "SECRET"
) -> None:
    """Validate secret has sufficient entropy and length.

    Args:
        secret: The secret value to validate
        min_length: Minimum required length (default: 32)
        secret_name: Name of the secret for error messages

    Raises:
        ConfigurationError: If the secret does not meet requirements
    """
    if len(secret) < min_length:
        raise ConfigurationError(
            f"{secret_name} must be at least {min_length} characters long "
            f"(generate with: openssl rand -hex 32)"
        )

    # Basic entropy calculation
    unique_chars = len(set(secret))
    if unique_chars < 8:
        raise ConfigurationError(
            f"{secret_name} has insufficient entropy (too few unique characters, got {unique_chars})"
        )

    # Reject obvious patterns
    if secret == secret[0] * len(secret):
        raise ConfigurationError(f"{secret_name} cannot be a repeating pattern")

    # Reject common weak values
    weak_values = {
        "admin",
        "password",
        "secret",
        "123456789012",
        "12345678901234567890123456789012",
    }
    if secret.lower() in weak_values:
        raise ConfigurationError(f"{secret_name} cannot be a common weak value")


def validate_default_credentials(
    username: str, password: str, env_values: dict[str, str]
) -> None:
    """Validate that default credentials are only allowed in explicit dev mode.

    This function checks if the provided credentials match default values (admin/admin)
    and ensures they are only used in development mode. In production, default
    credentials are rejected for security.

    Args:
        username: The username to validate
        password: The password to validate
        env_values: Dictionary containing environment variables (must include LEYZEN_ENVIRONMENT)

    Raises:
        ConfigurationError: If default credentials are detected without explicit dev mode

    Example:
        >>> env = {"LEYZEN_ENVIRONMENT": "prod"}
        >>> validate_default_credentials("admin", "admin", env)
        ConfigurationError: Default credentials are not allowed in production
    """
    leylen_env = env_values.get("LEYZEN_ENVIRONMENT", "").strip().lower()
    is_dev_mode = leylen_env in ("dev", "development")

    DEFAULT_USERNAME = "admin"
    DEFAULT_PASSWORD = "admin"

    errors = []
    if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
        if not is_dev_mode:
            errors.append(
                f"Default credentials ({DEFAULT_USERNAME}/{DEFAULT_PASSWORD}) are not allowed. "
                "Set LEYZEN_ENVIRONMENT=dev explicitly for development only, "
                "or use secure credentials for production."
            )

    if errors:
        raise ConfigurationError(
            "Security validation failed:\n  " + "\n  ".join(errors)
        )


__all__ = [
    "parse_bool",
    "parse_int_env_var",
    "validate_secret_entropy",
    "validate_default_credentials",
]
