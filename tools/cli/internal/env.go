package internal

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// EnvEntry represents either a key-value pair or a raw line in an env file.
type EnvEntry struct {
	Key    string
	Value  string
	Raw    string
	IsPair bool
}

// EnvFile models a .env file preserving comments and ordering.
type EnvFile struct {
	Path    string
	Entries []EnvEntry
}

// LoadEnvFile reads an environment file from disk. If the file does not exist,
// an empty representation is returned.
//
// Parser synchronization:
// This Go implementation must maintain compatible behavior with the Python implementation
// in src/common/env.py::read_env_file(). Both parsers are synchronized to ensure identical
// parsing semantics:
//
// - Quote handling: Both strip matching single and double quotes from values
//   - Go: Checks if first and last characters are matching quotes (" or ')
//   - Python: `value[0] == value[-1] and value[0] in {'"', "'"}`
//
// - Comment handling: Both ignore lines starting with #
//   - Go: `strings.HasPrefix(trimmed, "#")`
//   - Python: `line.startswith("#")`
//
// - Empty lines: Both are ignored
//   - Go: `trimmed == ""`
//   - Python: `if not line`
//
// - Whitespace: Both trim keys and values
//   - Go: `strings.TrimSpace(key)`, `strings.TrimSpace(value)`
//   - Python: `key.strip()`, `value.strip()`
//
// - Key-value separation: Both split on first `=` only
//   - Go: `strings.Index(line, "=")` then split
//   - Python: `line.split("=", 1)`
//
// Synchronization rules:
//  1. When modifying parsing logic in this file, update the Python implementation in
//     src/common/env.py::read_env_file() to match
//  2. When modifying parsing logic in Python, update this Go implementation to match
//  3. Test both implementations with the same .env file to verify compatibility
//  4. Document any intentional differences in behavior
//
// This duplication is necessary for linguistic reasons (Python services vs Go CLI)
// but both implementations must stay synchronized to avoid configuration inconsistencies.
func LoadEnvFile(path string) (*EnvFile, error) {
	cleaned := filepath.Clean(path)
	file := &EnvFile{Path: cleaned}

	f, err := os.Open(cleaned)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return file, nil
		}
		return nil, fmt.Errorf("open env file: %w", err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") || !strings.Contains(line, "=") {
			file.Entries = append(file.Entries, EnvEntry{Raw: line})
			continue
		}

		idx := strings.Index(line, "=")
		key := strings.TrimSpace(line[:idx])
		value := strings.TrimSpace(line[idx+1:])
		// Strip matching quotes from value (single or double) to match Python/Docker semantics
		if len(value) >= 2 {
			first := value[0]
			last := value[len(value)-1]
			if (first == '"' && last == '"') || (first == '\'' && last == '\'') {
				value = value[1 : len(value)-1]
			}
		}
		file.Entries = append(file.Entries, EnvEntry{Key: key, Value: value, IsPair: true})
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read env file: %w", err)
	}

	return file, nil
}

// Get returns the value for a key if present.
func (f *EnvFile) Get(key string) (string, bool) {
	for _, entry := range f.Entries {
		if entry.IsPair && entry.Key == key {
			return entry.Value, true
		}
	}
	return "", false
}

// Set inserts or updates a key in the env file representation.
func (f *EnvFile) Set(key, value string) {
	for idx, entry := range f.Entries {
		if entry.IsPair && entry.Key == key {
			f.Entries[idx].Value = value
			return
		}
	}
	f.Entries = append(f.Entries, EnvEntry{Key: key, Value: value, IsPair: true})
}

// Pairs returns a map of all key-value pairs.
func (f *EnvFile) Pairs() map[string]string {
	result := make(map[string]string)
	for _, entry := range f.Entries {
		if entry.IsPair {
			result[entry.Key] = entry.Value
		}
	}
	return result
}

// Write persists the env file to disk.
func (f *EnvFile) Write() error {
	if f.Path == "" {
		return errors.New("env file path is empty")
	}

	var builder strings.Builder
	for idx, entry := range f.Entries {
		if entry.IsPair {
			builder.WriteString(fmt.Sprintf("%s=%s", entry.Key, entry.Value))
		} else {
			builder.WriteString(entry.Raw)
		}
		if idx < len(f.Entries)-1 {
			builder.WriteString("\n")
		}
	}

	if len(f.Entries) == 0 {
		// ensure file ends with newline even if empty
		builder.WriteString("")
	}

	if err := os.WriteFile(f.Path, []byte(builder.String()+"\n"), 0o600); err != nil {
		return fmt.Errorf("write env file: %w", err)
	}
	return nil
}

// ResolveEnvFilePath returns an absolute path for the provided env file, defaulting to .env when empty.
// This function aligns with the Python implementation in src/common/env.py::load_env_with_override():
// - If LEYZEN_ENV_FILE is set and non-empty, use that file
// - Relative paths are resolved relative to the repository root (not current working directory)
// - Absolute paths are used as-is
// - If no path is provided and LEYZEN_ENV_FILE is not set, default to .env in repository root
func ResolveEnvFilePath(path string) (string, error) {
	repoRoot, err := FindRepoRoot()
	if err != nil {
		return "", fmt.Errorf("find repository root: %w", err)
	}

	cleaned := strings.TrimSpace(path)

	// Check for LEYZEN_ENV_FILE override (same as Python logic)
	if cleaned == "" {
		if override := os.Getenv("LEYZEN_ENV_FILE"); override != "" {
			cleaned = strings.TrimSpace(override)
		} else {
			cleaned = ".env"
		}
	}

	// Expand user home directory (~)
	expanded := cleaned
	if strings.HasPrefix(cleaned, "~") {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("get user home directory: %w", err)
		}
		expanded = strings.Replace(cleaned, "~", homeDir, 1)
	}

	// Resolve path: if absolute, use as-is; if relative, resolve from repo root
	var resolved string
	if filepath.IsAbs(expanded) {
		resolved = expanded
	} else {
		resolved = filepath.Join(repoRoot, expanded)
	}

	// Make absolute path canonical
	abs, err := filepath.Abs(resolved)
	if err != nil {
		return "", fmt.Errorf("resolve env file path: %w", err)
	}

	return abs, nil
}

// LoadEnvTemplate loads variables from env.template file located in the project root.
// It finds env.template by looking for it relative to the provided env file path.
func LoadEnvTemplate(envFilePath string) (map[string]string, error) {
	// Resolve the env file path to get its directory
	resolvedEnvPath, err := ResolveEnvFilePath(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("resolve env file path: %w", err)
	}

	envDir := filepath.Dir(resolvedEnvPath)

	// Try to find env.template in the same directory or parent directory
	templatePath := filepath.Join(envDir, "env.template")

	// If not found, try parent directory (project root)
	if _, err := os.Stat(templatePath); os.IsNotExist(err) {
		parentTemplatePath := filepath.Join(filepath.Dir(envDir), "env.template")
		if _, err := os.Stat(parentTemplatePath); os.IsNotExist(err) {
			// Template not found anywhere, return empty map
			return make(map[string]string), nil
		}
		templatePath = parentTemplatePath
	}

	// Try to load the template
	templateFile, err := LoadEnvFile(templatePath)
	if err != nil {
		return nil, fmt.Errorf("load env template: %w", err)
	}

	return templateFile.Pairs(), nil
}

// InitializeEnvFromTemplate initializes an empty env file with variables from env.template.
// Returns the merged variables.
func InitializeEnvFromTemplate(envFilePath string) (map[string]string, error) {
	// Load current env file
	envFile, err := LoadEnvFile(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load env file: %w", err)
	}

	// Check if file is empty (no key-value pairs)
	if len(envFile.Pairs()) == 0 {
		// Load template
		templatePairs, err := LoadEnvTemplate(envFilePath)
		if err != nil {
			return nil, fmt.Errorf("load template: %w", err)
		}

		// If template has variables, copy them to env file
		if len(templatePairs) > 0 {
			// Copy all template variables to env file
			for key, value := range templatePairs {
				envFile.Set(key, value)
			}

			// Save the initialized file
			if err := envFile.Write(); err != nil {
				return nil, fmt.Errorf("write initialized env file: %w", err)
			}
		}

		return envFile.Pairs(), nil
	}

	// File already has variables, return them
	return envFile.Pairs(), nil
}

// LoadAllEnvVariables loads all environment variables by merging env.template with .env.
// Values from .env take priority over template values.
// This function is used to display all available variables in the Config view and Wizard,
// even if they are not yet set in the .env file.
func LoadAllEnvVariables(envFilePath string) (map[string]string, error) {
	// Load template first (all available variables)
	templatePairs, err := LoadEnvTemplate(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load template: %w", err)
	}

	// Load current .env file
	envFile, err := LoadEnvFile(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load env file: %w", err)
	}

	envPairs := envFile.Pairs()

	// Merge: start with template, then override with .env values
	result := make(map[string]string)
	for key, value := range templatePairs {
		result[key] = value
	}
	// Override with .env values (they take priority)
	for key, value := range envPairs {
		result[key] = value
	}

	return result, nil
}
