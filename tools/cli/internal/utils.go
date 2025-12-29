package internal

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/fatih/color"
)

// ansiRegex matches ANSI escape sequences.
var ansiRegex = regexp.MustCompile(`\x1b\[[0-9;]*m`)

// VisibleLen returns the length of a string excluding ANSI escape sequences.
func VisibleLen(s string) int {
	return len(ansiRegex.ReplaceAllString(s, ""))
}

// PadRightVisible pads a string with spaces to the right, accounting for invisible ANSI sequences.
func PadRightVisible(s string, width int) string {
	visible := VisibleLen(s)
	if visible >= width {
		return s
	}
	return s + strings.Repeat(" ", width-visible)
}

func ensureBinaryAvailable(name string) error {
	if _, err := exec.LookPath(name); err != nil {
		return fmt.Errorf("%s is required but was not found in PATH", name)
	}
	return nil
}

// FormatStatusColor returns a colored version of the Docker container status.
func FormatStatusColor(status string) string {
	lower := strings.ToLower(status)
	switch {
	case strings.Contains(lower, "up"):
		return color.HiGreenString(status)
	case strings.Contains(lower, "exit") || strings.Contains(lower, "dead"):
		return color.HiRedString(status)
	default:
		return color.HiYellowString(status)
	}
}

// FormatKeyValue renders a key/value pair with colored key for better readability.
func FormatKeyValue(key, value string) string {
	return fmt.Sprintf("%s: %s", color.HiBlueString(key), value)
}

// RunBuildScript executes the internal Go generator to rebuild HAProxy and Compose configuration.
func RunBuildScript(envFile string) error {
	return GenerateConfig(os.Stdout, os.Stderr, envFile)
}

// RunBuildScriptWithWriter is deprecated but kept for compatibility.
func RunBuildScriptWithWriter(stdout, stderr io.Writer, envFile string) error {
	// Add header with green color
	fmt.Fprintln(stdout, color.HiGreenString("[CONFIG] Generating configuration..."))
	fmt.Fprintln(stdout, color.HiGreenString("----------------------------------------------------------------"))

	if err := GenerateConfig(stdout, stderr, envFile); err != nil {
		return err
	}

	// Add visual separation
	fmt.Fprintln(stdout, color.HiGreenString("----------------------------------------------------------------"))
	return nil
}

// EnsureDockerGeneratedFile ensures that docker-generated.yml exists in the repository root.
func EnsureDockerGeneratedFile(envFile string) error {
	return EnsureDockerGeneratedFileWithWriter(os.Stdout, os.Stderr, envFile)
}

// EnsureDockerGeneratedFileWithWriter ensures that docker-generated.yml exists in the repository root.
// Output is streamed to the provided writers.
func EnsureDockerGeneratedFileWithWriter(stdout, stderr io.Writer, envFile string) error {
	repoRoot, err := FindRepoRoot()
	if err != nil {
		return fmt.Errorf("failed to find repository root: %w", err)
	}

	dockerGeneratedPath := filepath.Join(repoRoot, "docker-generated.yml")

	if _, err := os.Stat(dockerGeneratedPath); err == nil {
		return nil
	}

	if err := RunBuildScriptWithWriter(stdout, stderr, envFile); err != nil {
		return fmt.Errorf("failed to generate docker-generated.yml: %w", err)
	}

	return nil
}
