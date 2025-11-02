package internal

import (
	"fmt"
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
	projectRoot, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("failed to get working directory: %w", err)
	}

	scriptPath := filepath.Join(projectRoot, "compose", "build.py")

	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return err
	}

	cmd := exec.Command("python3", scriptPath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(os.Environ(), fmt.Sprintf("LEYZEN_ENV_FILE=%s", resolvedEnv))

	fmt.Println("🔄 Rebuilding Docker Compose and HAProxy configuration...")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("build.py failed: %w", err)
	}

	fmt.Println("✅ Configuration rebuild completed.")
	return nil
}
