package internal

import (
	"fmt"
	"os"
	"path/filepath"
)

// FindRepoRoot finds the repository root directory by looking for marker files.
// It searches upward from the current working directory until it finds a directory
// containing both "leyzenctl" and "env.template" files.
//
// This function is used across multiple CLI commands to ensure consistent path resolution
// regardless of the current working directory when the command is executed.
func FindRepoRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("get working directory: %w", err)
	}

	for {
		// Check if we're at the repo root (look for leyzenctl, env.template, etc.)
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
