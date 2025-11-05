package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"leyzenctl/internal"

	"github.com/spf13/cobra"
)

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate .env configuration file",
	Long: `Validate the .env configuration file by:
- Comparing with env.template for missing or extra variables
- Checking that required variables are present and non-empty
- Verifying cryptographic secrets meet minimum length requirements (≥12 characters)`,
	RunE: runValidate,
}

func init() {
	configCmd.AddCommand(validateCmd)
}

func runValidate(cmd *cobra.Command, args []string) error {
	repoRoot, err := internal.FindRepoRoot()
	if err != nil {
		return fmt.Errorf("failed to find repository root: %w", err)
	}

	envPath := filepath.Join(repoRoot, ".env")
	templatePath := filepath.Join(repoRoot, "env.template")

	// Read env.template to get expected variables
	templateVars, requiredVars, secretVars, err := parseTemplate(templatePath)
	if err != nil {
		return fmt.Errorf("failed to parse env.template: %w", err)
	}

	// Read .env file
	envVars, err := parseEnv(envPath)
	if err != nil {
		return fmt.Errorf("failed to parse .env: %w", err)
	}

	errors := []string{}
	warnings := []string{}

	// Check required variables
	for _, reqVar := range requiredVars {
		value, exists := envVars[reqVar]
		if !exists || strings.TrimSpace(value) == "" {
			errors = append(errors, fmt.Sprintf("Missing or empty required variable: %s", reqVar))
		}
	}

	// Check cryptographic secrets length (≥12 characters)
	for _, secretVar := range secretVars {
		value, exists := envVars[secretVar]
		if exists && strings.TrimSpace(value) != "" {
			if len(value) < 12 {
				errors = append(errors, fmt.Sprintf(
					"Secret %s must be at least 12 characters long (got %d characters)",
					secretVar, len(value),
				))
			}
		}
	}

	// Check for missing variables from template (warnings, not errors)
	for templateVar := range templateVars {
		if _, exists := envVars[templateVar]; !exists {
			// Only warn if it's not marked as optional/advanced
			if !templateVars[templateVar].optional {
				warnings = append(warnings, fmt.Sprintf("Missing variable from template: %s", templateVar))
			}
		}
	}

	// Check for extra variables not in template (warnings)
	for envVar := range envVars {
		if _, exists := templateVars[envVar]; !exists {
			warnings = append(warnings, fmt.Sprintf("Variable not in template: %s", envVar))
		}
	}

	// Print results
	if len(errors) > 0 {
		fmt.Println("❌ Validation failed with errors:")
		for _, err := range errors {
			fmt.Printf("  - %s\n", err)
		}
	}

	if len(warnings) > 0 {
		fmt.Println("\n⚠️  Warnings:")
		for _, warn := range warnings {
			fmt.Printf("  - %s\n", warn)
		}
	}

	if len(errors) == 0 && len(warnings) == 0 {
		fmt.Println("✅ Configuration validation passed!")
		return nil
	}

	if len(errors) > 0 {
		return fmt.Errorf("validation failed with %d error(s)", len(errors))
	}

	return nil
}

type varInfo struct {
	optional bool
}

func parseTemplate(path string) (map[string]varInfo, []string, []string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, nil, err
	}

	vars := make(map[string]varInfo)
	secrets := []string{}

	lines := strings.Split(string(content), "\n")

	// Regular expressions to extract variable names (including commented lines)
	// This pattern matches both commented (# VAR=value) and uncommented (VAR=value) lines
	varPattern := regexp.MustCompile(`^#?\s*([A-Z_][A-Z0-9_]*)\s*=`)

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Skip empty lines only
		if line == "" {
			continue
		}

		// Extract variable name (works for both commented and uncommented lines)
		match := varPattern.FindStringSubmatch(line)
		if len(match) > 1 {
			varName := match[1]
			isCommented := strings.HasPrefix(line, "#")
			// A variable is optional if:
			// - It's explicitly marked as optional/advanced in comments
			// - It's commented out (has a default value)
			isOptional := strings.Contains(line, "# Optional") || strings.Contains(line, "⚠️ Advanced") ||
				isCommented

			vars[varName] = varInfo{optional: isOptional}

			// Only SECRET_KEY and DOCKER_PROXY_TOKEN are secrets, check explicitly
			if varName == "SECRET_KEY" || varName == "DOCKER_PROXY_TOKEN" {
				secrets = append(secrets, varName)
			}
		}
	}

	// Synchronize with Python validation in:
	// - src/vault/config.py::load_settings() (requires VAULT_USER, VAULT_PASS, SECRET_KEY)
	// - src/orchestrator/config.py::_ensure_required_variables() (requires ORCH_USER, ORCH_PASS, SECRET_KEY, DOCKER_PROXY_TOKEN)
	// These variables are required at runtime and must be present and non-empty.
	// When modifying this list, update the Python implementations to match.
	// We only use this explicit list to avoid false positives from conditional "REQUIRED if ..." comments.
	required := []string{
		"VAULT_USER",
		"VAULT_PASS",
		"ORCH_USER",
		"ORCH_PASS",
		"SECRET_KEY",
		"DOCKER_PROXY_TOKEN",
	}

	return vars, required, secrets, nil
}

func parseEnv(path string) (map[string]string, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	vars := make(map[string]string)
	lines := strings.Split(string(content), "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)

		// Skip comments and empty lines
		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}

		// Parse KEY=VALUE
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			// Remove quotes if present
			value = strings.Trim(value, `"'`)
			vars[key] = value
		}
	}

	return vars, nil
}
