package internal

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

const apiTimeout = 5 * time.Minute

// PrepareRotation calls the prepare-rotation endpoint on the active vault container
// to promote all files from tmpfs to persistent storage before shutdown.
func PrepareRotation(envFile string) error {
	activeContainer, err := getActiveContainer(envFile)
	if err != nil {
		return fmt.Errorf("failed to find active container: %w", err)
	}

	if activeContainer == "" {
		return nil
	}

	// Verify container state
	checkCtx, checkCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer checkCancel()

	checkCmd := exec.CommandContext(checkCtx, "docker", "inspect", "--format", "{{.State.Status}}", activeContainer)
	if err := checkCmd.Run(); err != nil {
		return fmt.Errorf("container %s is not accessible: %w", activeContainer, err)
	}

	token, err := getInternalAPIToken(envFile)
	if err != nil {
		return fmt.Errorf("failed to get internal API token: %w", err)
	}

	if token == "" {
		token = "placeholder"
	}

	// Use docker exec to call the API from within the vault container using Python
	pythonScript := fmt.Sprintf(`
import sys
import json
try:
    import urllib.request
    import urllib.error

    url = "http://localhost/api/internal/prepare-rotation"
    data = json.dumps({}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        'Authorization': 'Bearer %s',
        'Content-Type': 'application/json'
    })

    with urllib.request.urlopen(req, timeout=300) as response:
        result = json.loads(response.read().decode('utf-8'))
        if not result.get('overall_success', False):
            sys.exit(1)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
`, token)

	ctx, cancel := context.WithTimeout(context.Background(), apiTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", "exec", activeContainer, "python3", "-c", pythonScript)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		if strings.Contains(stderr.String(), "No such container") ||
			strings.Contains(stderr.String(), "is not running") {
			return fmt.Errorf("container %s is not running", activeContainer)
		}
		return fmt.Errorf("prepare-rotation failed: %w - %s", err, stderr.String())
	}

	return nil
}

// getActiveContainer finds the active vault container (running and healthy)
func getActiveContainer(envFile string) (string, error) {
	// Get list of running containers in the project context
	output, err := DockerComposePS(envFile, "--filter", "status=running", "--format", "{{.Name}}")
	if err != nil {
		return "", err
	}

	// Parse container names
	containers := strings.Fields(output)
	for _, name := range containers {
		if strings.HasPrefix(name, "vault_web") {
			return name, nil
		}
	}

	return "", nil // No active container found (not an error)
}

// getInternalAPIToken retrieves the INTERNAL_API_TOKEN from environment or .env file
func getInternalAPIToken(envFile string) (string, error) {
	// First check environment variable
	if token := os.Getenv("INTERNAL_API_TOKEN"); token != "" {
		return token, nil
	}

	// Load from .env file
	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return "", fmt.Errorf("resolve env file path: %w", err)
	}

	envFileData, err := LoadEnvFile(resolvedEnv)
	if err != nil {
		return "", fmt.Errorf("load env file: %w", err)
	}

	token, found := envFileData.Get("INTERNAL_API_TOKEN")
	if !found || token == "" {
		// Token not set - this is not necessarily an error, it may be auto-generated
		return "", nil
	}

	return token, nil
}
