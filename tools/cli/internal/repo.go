package internal

import (
	"fmt"
	"os"
	"path/filepath"
)

// FindRepoRoot finds the repository root directory by looking for marker files.
func FindRepoRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("get working directory: %w", err)
	}

	for {
		if _, err := os.Stat(filepath.Join(dir, "leyzenctl")); err == nil {
			if _, err := os.Stat(filepath.Join(dir, "env.template")); err == nil {
				return dir, nil
			}
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf("repository root not found")
		}
		dir = parent
	}
}
