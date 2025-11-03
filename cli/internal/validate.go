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
// Les valeurs vides sont maintenant permises (champs optionnels).
func ValidateEnvValue(key, value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	// Si une validation spécifique existe pour cette clé, l'utiliser
	if validator, ok := keyValidators[key]; ok {
		// Si la valeur est vide et qu'on a un validator, permettre quand même (champ optionnel)
		if trimmed == "" {
			return "", nil // Valeur vide permise
		}
		return validator(trimmed)
	}
	// Sinon, juste trimmer - valeurs vides permises
	return trimmed, nil
}

func validateNonEmpty(value string) (string, error) {
	// Permettre les valeurs vides (champs optionnels)
	return strings.TrimSpace(value), nil
}

func validatePositiveInt(value string) (string, error) {
	// Permettre les valeurs vides (champs optionnels)
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return "", nil
	}
	// Si une valeur est fournie, elle doit être un entier positif
	n, err := strconv.Atoi(trimmed)
	if err != nil || n < 1 {
		return "", fmt.Errorf("value must be a positive integer")
	}
	return strconv.Itoa(n), nil
}

func validatePassword(value string) (string, error) {
	// Pas de limite de longueur - laisser l'utilisateur choisir
	return strings.TrimSpace(value), nil
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
