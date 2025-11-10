package internal

import (
	"fmt"
	"strconv"
	"strings"
)

const (
	// Minimum secret length required for cryptographic secrets
	// This aligns with Python validation in:
	// - src/vault/config.py::load_settings() (requires 32 characters)
	// - src/orchestrator/config.py::load_settings() (requires 32 characters)
	minSecretLength = 32
)

type valueValidator func(string) (string, error)

var keyValidators = map[string]valueValidator{
	"WEB_REPLICAS":         validatePositiveInt,
	"ORCH_PASS":            validatePassword,
	"ROTATION_INTERVAL":    validatePositiveInt,
	"SECRET_KEY":           validateSecretLength,
	// DOCKER_PROXY_TOKEN is auto-generated from SECRET_KEY and no longer required
	// "DOCKER_PROXY_TOKEN":   validateSecretLength,
}

// ValidateEnvValue validates and sanitizes a value for the given key.
// Empty values are now allowed (optional fields).
func ValidateEnvValue(key, value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	// If a specific validation exists for this key, use it
	if validator, ok := keyValidators[key]; ok {
		// If the value is empty and we have a validator, still allow it (optional field)
		if trimmed == "" {
			return "", nil // Empty value allowed
		}
		return validator(trimmed)
	}
	// Otherwise, just trim - empty values allowed
	return trimmed, nil
}

func validateNonEmpty(value string) (string, error) {
	// Allow empty values (optional fields)
	return strings.TrimSpace(value), nil
}

func validatePositiveInt(value string) (string, error) {
	// Allow empty values (optional fields)
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", nil
	}
	// If a value is provided, it must be a positive integer
	n, err := strconv.Atoi(trimmed)
	if err != nil || n < 1 {
		return "", fmt.Errorf("value must be a positive integer")
	}
	return strconv.Itoa(n), nil
}

func validatePassword(value string) (string, error) {
	// No length limit - let the user choose
	return strings.TrimSpace(value), nil
}

// validateSecretLength validates that a cryptographic secret meets minimum length requirements.
// This aligns with the Python validation in:
// - src/vault/config.py::load_settings() (requires 32 characters via validate_secret_entropy)
// - src/orchestrator/config.py::load_settings() (requires 32 characters via validate_secret_entropy)
// Both Python implementations use validate_secret_entropy() with min_length=32.
func validateSecretLength(value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", nil // Empty value allowed (optional field)
	}
	if len(trimmed) < minSecretLength {
		return "", fmt.Errorf("secret must be at least %d characters long (got %d characters). Generate with: openssl rand -hex 32", minSecretLength, len(trimmed))
	}
	return trimmed, nil
}

// SurveyValidator wraps ValidateEnvValue for use with survey prompts.
func SurveyValidator(key string) func(interface{}) error {
	return func(ans interface{}) error {
		str, ok := ans.(string)
		if !ok {
			return fmt.Errorf("unexpected answer type")
		}
		_, err := ValidateEnvValue(key, str)
		return err
	}
}
