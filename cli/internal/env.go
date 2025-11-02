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
