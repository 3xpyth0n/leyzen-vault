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
func ResolveEnvFilePath(path string) (string, error) {
	cleaned := strings.TrimSpace(path)
	if cleaned == "" {
		cleaned = ".env"
	}

	resolved, err := filepath.Abs(cleaned)
	if err != nil {
		return "", fmt.Errorf("resolve env file path: %w", err)
	}

	return resolved, nil
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
