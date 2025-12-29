from __future__ import annotations


class SecretString:
    """A string that masks its value in logs and repr()."""

    def __init__(self, value: str):
        self._value = value

    def get_secret_value(self) -> str:
        """Return the actual secret value."""
        return self._value

    def __str__(self) -> str:
        return "**********"

    def __repr__(self) -> str:
        return "SecretString('**********')"
