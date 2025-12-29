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
- Verifying cryptographic secrets meet minimum length requirements (≥32 characters)`,
	SilenceUsage: true,
	RunE:         runValidate,
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

	templateVars, requiredVars, secretVars, err := parseTemplate(templatePath)
	if err != nil {
		return fmt.Errorf("failed to parse env.template: %w", err)
	}

	envVars, err := parseEnv(envPath)
	if err != nil {
		return fmt.Errorf("failed to parse .env: %w", err)
	}

	errors := []string{}
	warnings := []string{}

	orchestratorEnabled := true
	if val, exists := envVars["ORCHESTRATOR_ENABLED"]; exists {
		val = strings.ToLower(strings.TrimSpace(val))
		orchestratorEnabled = val == "true" || val == "1" || val == "yes" || val == "on"
	}

	if orchestratorEnabled {
		requiredVars = append(requiredVars, "ORCH_USER", "ORCH_PASS")
	}

	for _, reqVar := range requiredVars {
		value, exists := envVars[reqVar]
		if !exists || strings.TrimSpace(value) == "" {
			errors = append(errors, fmt.Sprintf("Missing or empty required variable: %s", reqVar))
		}
	}

	for _, secretVar := range secretVars {
		value, exists := envVars[secretVar]
		if exists && strings.TrimSpace(value) != "" {
			if len(value) < 32 {
				errors = append(errors, fmt.Sprintf(
					"Secret %s must be at least 32 characters long (got %d characters). Generate with: openssl rand -hex 32",
					secretVar, len(value),
				))
			}
		}
	}

	for templateVar := range templateVars {
		if _, exists := envVars[templateVar]; !exists {
			if !templateVars[templateVar].optional {
				warnings = append(warnings, fmt.Sprintf("Missing variable from template: %s", templateVar))
			}
		}
	}

	for envVar := range envVars {
		if _, exists := templateVars[envVar]; !exists {
			warnings = append(warnings, fmt.Sprintf("Variable not in template: %s", envVar))
		}
	}

	if len(errors) > 0 {
		fmt.Println("[ERROR] Validation failed with errors:")
		for _, err := range errors {
			fmt.Printf("  - %s\n", err)
		}
	}

	if len(warnings) > 0 {
		fmt.Println("\n[WARN] Warnings:")
		for _, warn := range warnings {
			fmt.Printf("  - %s\n", warn)
		}
	}

	if len(errors) == 0 && len(warnings) == 0 {
		fmt.Println("Configuration validation passed!")
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

	varPattern := regexp.MustCompile(`^#?\s*([A-Z_][A-Z0-9_]*)\s*=`)

	for _, line := range lines {
		line = strings.TrimSpace(line)

		if line == "" {
			continue
		}

		match := varPattern.FindStringSubmatch(line)
		if len(match) > 1 {
			varName := match[1]
			isCommented := strings.HasPrefix(line, "#")
			isOptional := strings.Contains(line, "# Optional") || strings.Contains(line, "[WARN] Advanced") ||
				isCommented

			vars[varName] = varInfo{optional: isOptional}

			if varName == "SECRET_KEY" {
				secrets = append(secrets, varName)
			}
		}
	}

	required := []string{
		"SECRET_KEY",
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

		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}

		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			value = strings.Trim(value, `"'`)
			vars[key] = value
		}
	}

	return vars, nil
}
