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
		if len(value) >= 2 {
			first := value[0]
			last := value[len(value)-1]
			if (first == '"' && last == '"') || (first == '\'' && last == '\'') || (first == '`' && last == '`') {
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
		builder.WriteString("")
	}

	if err := os.WriteFile(f.Path, []byte(builder.String()+"\n"), 0o600); err != nil {
		return fmt.Errorf("write env file: %w", err)
	}
	return nil
}

// ResolveEnvFilePath returns an absolute path for the provided env file, defaulting to .env when empty.
func ResolveEnvFilePath(path string) (string, error) {
	repoRoot, err := FindRepoRoot()
	if err != nil {
		return "", fmt.Errorf("find repository root: %w", err)
	}

	cleaned := strings.TrimSpace(path)

	if cleaned == "" {
		if override := os.Getenv("LEYZEN_ENV_FILE"); override != "" {
			cleaned = strings.TrimSpace(override)
		} else {
			cleaned = ".env"
		}
	}

	expanded := cleaned
	if strings.HasPrefix(cleaned, "~") {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", fmt.Errorf("get user home directory: %w", err)
		}
		expanded = strings.Replace(cleaned, "~", homeDir, 1)
	}

	var resolved string
	if filepath.IsAbs(expanded) {
		resolved = expanded
	} else {
		resolved = filepath.Join(repoRoot, expanded)
	}

	abs, err := filepath.Abs(resolved)
	if err != nil {
		return "", fmt.Errorf("resolve env file path: %w", err)
	}

	return abs, nil
}

// LoadEnvTemplate loads variables from env.template file located in the project root.
func LoadEnvTemplate(envFilePath string) (map[string]string, error) {
	resolvedEnvPath, err := ResolveEnvFilePath(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("resolve env file path: %w", err)
	}

	envDir := filepath.Dir(resolvedEnvPath)
	templatePath := filepath.Join(envDir, "env.template")

	if _, err := os.Stat(templatePath); os.IsNotExist(err) {
		parentTemplatePath := filepath.Join(filepath.Dir(envDir), "env.template")
		if _, err := os.Stat(parentTemplatePath); os.IsNotExist(err) {
			return make(map[string]string), nil
		}
		templatePath = parentTemplatePath
	}

	templateFile, err := LoadEnvFile(templatePath)
	if err != nil {
		return nil, fmt.Errorf("load env template: %w", err)
	}

	return templateFile.Pairs(), nil
}

// InitializeEnvFromTemplate initializes an empty env file with variables from env.template.
// Returns the merged variables.
func InitializeEnvFromTemplate(envFilePath string) (map[string]string, error) {
	envFile, err := LoadEnvFile(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load env file: %w", err)
	}

	if len(envFile.Pairs()) == 0 {
		templatePairs, err := LoadEnvTemplate(envFilePath)
		if err != nil {
			return nil, fmt.Errorf("load template: %w", err)
		}

		if len(templatePairs) > 0 {
			for key, value := range templatePairs {
				envFile.Set(key, value)
			}

			if err := envFile.Write(); err != nil {
				return nil, fmt.Errorf("write initialized env file: %w", err)
			}
		}

		return envFile.Pairs(), nil
	}

	return envFile.Pairs(), nil
}

// LoadAllEnvVariables loads all environment variables by merging env.template with .env.
// Values from .env take priority over template values.
func LoadAllEnvVariables(envFilePath string) (map[string]string, error) {
	templatePairs, err := LoadEnvTemplate(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load template: %w", err)
	}

	envFile, err := LoadEnvFile(envFilePath)
	if err != nil {
		return nil, fmt.Errorf("load env file: %w", err)
	}

	envPairs := envFile.Pairs()

	result := make(map[string]string)
	for key, value := range templatePairs {
		result[key] = value
	}
	for key, value := range envPairs {
		result[key] = value
	}

	return result, nil
}

// EnvDoc represents documentation for an environment variable parsed from the template.
type EnvDoc struct {
	Name        string
	Summary     string
	Description string
}

// FindEnvTemplatePath locates the env.template file relative to the given env file path.
func FindEnvTemplatePath(envFilePath string) (string, error) {
	resolvedEnvPath, err := ResolveEnvFilePath(envFilePath)
	if err != nil {
		return "", fmt.Errorf("resolve env file path: %w", err)
	}

	envDir := filepath.Dir(resolvedEnvPath)
	templatePath := filepath.Join(envDir, "env.template")

	if _, err := os.Stat(templatePath); os.IsNotExist(err) {
		parentTemplatePath := filepath.Join(filepath.Dir(envDir), "env.template")
		if _, err := os.Stat(parentTemplatePath); os.IsNotExist(err) {
			return "", os.ErrNotExist
		}
		templatePath = parentTemplatePath
	}
	return templatePath, nil
}

// LoadEnvDocumentation parses comments from env.template to create variable documentation.
func LoadEnvDocumentation(envFilePath string) (map[string]EnvDoc, error) {
	templatePath, err := FindEnvTemplatePath(envFilePath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return make(map[string]EnvDoc), nil
		}
		return nil, fmt.Errorf("find env template: %w", err)
	}

	f, err := os.Open(templatePath)
	if err != nil {
		return nil, fmt.Errorf("open template: %w", err)
	}
	defer f.Close()

	docs := make(map[string]EnvDoc)
	var currentComments []string

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		trimmed := strings.TrimSpace(line)

		if trimmed == "" {
			currentComments = nil
			continue
		}

		if strings.HasPrefix(trimmed, "#") {
			content := strings.TrimPrefix(trimmed, "#")
			content = strings.TrimSpace(content)

			if idx := strings.Index(content, "="); idx != -1 {
				key := strings.TrimSpace(content[:idx])
				if key != "" && !strings.Contains(key, " ") {
					if len(currentComments) > 0 {
						doc := EnvDoc{
							Name:        key,
							Summary:     currentComments[0],
							Description: strings.Join(currentComments, "\n"),
						}
						if _, exists := docs[key]; !exists {
							docs[key] = doc
						}
					}
					currentComments = nil
					continue
				}
			}

			currentComments = append(currentComments, content)
			continue
		}

		if idx := strings.Index(trimmed, "="); idx != -1 {
			if len(currentComments) > 0 {
				key := strings.TrimSpace(trimmed[:idx])

				if key == "" {
					currentComments = nil
					continue
				}

				doc := EnvDoc{
					Name:        key,
					Summary:     currentComments[0],
					Description: strings.Join(currentComments, "\n"),
				}
				docs[key] = doc
			}
			currentComments = nil
		} else {
			currentComments = nil
		}
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("scan template: %w", err)
	}

	return docs, nil
}
