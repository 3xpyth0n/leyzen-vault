package internal

import (
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/fatih/color"
)

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

// RunBuildScript executes the Python compose/build.py script to rebuild HAProxy and Compose configuration.
func RunBuildScript(envFile string) error {
	return RunBuildScriptWithWriter(os.Stdout, os.Stderr, envFile)
}

// RunBuildScriptWithWriter executes the Python compose/build.py script streaming output to the provided writers.
func RunBuildScriptWithWriter(stdout, stderr io.Writer, envFile string) error {
	repoRoot, err := FindRepoRoot()
	if err != nil {
		return fmt.Errorf("failed to find repository root: %w", err)
	}

	scriptPath := filepath.Join(repoRoot, "src", "compose", "build.py")

	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return err
	}

	cmd := exec.Command("python3", scriptPath)
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	cmd.Env = append(os.Environ(), fmt.Sprintf("LEYZEN_ENV_FILE=%s", resolvedEnv))

	fmt.Fprintln(stdout, "🔄 Rebuilding Docker Compose and HAProxy configuration...")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("build.py failed: %w", err)
	}

	fmt.Fprintln(stdout, "✅ Configuration rebuild completed.")
	return nil
}
