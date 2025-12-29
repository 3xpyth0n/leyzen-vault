package internal

import (
	"fmt"
	"strconv"
	"strings"
)

const (
	// Minimum secret length required for cryptographic secrets
	minSecretLength = 32
)

type valueValidator func(string) (string, error)

var keyValidators = map[string]valueValidator{
	"WEB_REPLICAS":      validatePositiveInt,
	"ORCH_PASS":         validatePassword,
	"ROTATION_INTERVAL": validatePositiveInt,
	"SECRET_KEY":        validateSecretLength,
}

// ValidateEnvValue validates and sanitizes a value for the given key.
func ValidateEnvValue(key, value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if validator, ok := keyValidators[key]; ok {
		if trimmed == "" {
			return "", nil
		}
		return validator(trimmed)
	}
	return trimmed, nil
}

func validateNonEmpty(value string) (string, error) {
	return strings.TrimSpace(value), nil
}

func validatePositiveInt(value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", nil
	}
	n, err := strconv.Atoi(trimmed)
	if err != nil || n < 1 {
		return "", fmt.Errorf("value must be a positive integer")
	}
	return strconv.Itoa(n), nil
}

func validatePassword(value string) (string, error) {
	return strings.TrimSpace(value), nil
}

// validateSecretLength validates that a cryptographic secret meets minimum length requirements.
func validateSecretLength(value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", nil
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
