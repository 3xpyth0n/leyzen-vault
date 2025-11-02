package internal

import (
	"fmt"
	"strconv"
	"strings"
)

type valueValidator func(string) (string, error)

var keyValidators = map[string]valueValidator{
	"VAULT_PLUGIN":                validateNonEmpty,
	"VAULT_REPLICAS":              validatePositiveInt,
	"VAULT_ORCHESTRATOR_PASSWORD": validatePassword,
	"VAULT_ROTATION_INTERVAL":     validatePositiveInt,
	"VAULT_DOCKER_NETWORK":        validateNonEmpty,
}

// ValidateEnvValue validates and sanitizes a value for the given key.
func ValidateEnvValue(key, value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if validator, ok := keyValidators[key]; ok {
		return validator(trimmed)
	}
	if trimmed == "" {
		return "", fmt.Errorf("value for %s cannot be empty", key)
	}
	return trimmed, nil
}

func validateNonEmpty(value string) (string, error) {
	if strings.TrimSpace(value) == "" {
		return "", fmt.Errorf("value cannot be empty")
	}
	return value, nil
}

func validatePositiveInt(value string) (string, error) {
	n, err := strconv.Atoi(value)
	if err != nil || n < 1 {
		return "", fmt.Errorf("value must be a positive integer")
	}
	return strconv.Itoa(n), nil
}

func validatePassword(value string) (string, error) {
	if len(value) < 8 {
		return "", fmt.Errorf("password must be at least 8 characters long")
	}
	return value, nil
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
