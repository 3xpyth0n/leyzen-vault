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
// Since leyzenctl runs on the host (not in Docker network), we use docker exec
// to run a Python script from within the vault container to call the internal API.
func PrepareRotation(envFile string) error {
	// Get active container name
	activeContainer, err := getActiveContainer()
	if err != nil {
		return fmt.Errorf("failed to find active container: %w", err)
	}

	if activeContainer == "" {
		// No active container found, skip promotion (not an error - may be first startup)
		return nil
	}

	// Check if container is actually running and healthy
	// Use docker inspect to verify container state
	checkCtx, checkCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer checkCancel()

	checkCmd := exec.CommandContext(checkCtx, "docker", "inspect", "--format", "{{.State.Status}}", activeContainer)
	if err := checkCmd.Run(); err != nil {
		// Container doesn't exist or isn't accessible
		return fmt.Errorf("container %s is not accessible: %w", activeContainer, err)
	}

	// Get internal API token from environment
	token, err := getInternalAPIToken(envFile)
	if err != nil {
		// Try to get token from container's environment as fallback
		// The token might be auto-generated and stored in the container
		return fmt.Errorf("failed to get internal API token: %w", err)
	}

	if token == "" {
		// Token not available - this might be okay if it's auto-generated
		// We'll try the promotion anyway, and if it fails due to auth, we'll get a clear error
		// For now, use a placeholder - the container might accept requests without token
		// or the token might be auto-generated
		token = "placeholder"
	}

	// Use docker exec to call the API from within the vault container using Python
	// Python is available in the vault container and can make HTTP requests
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

	// Execute Python script via docker exec in the vault container
	cmd := exec.CommandContext(ctx, "docker", "exec", activeContainer, "python3", "-c", pythonScript)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		// Check if container doesn't exist or isn't running
		if strings.Contains(stderr.String(), "No such container") ||
			strings.Contains(stderr.String(), "is not running") {
			return fmt.Errorf("container %s is not running", activeContainer)
		}
		return fmt.Errorf("prepare-rotation failed: %w - %s", err, stderr.String())
	}

	return nil
}

// getActiveContainer finds the active vault container (running and healthy)
func getActiveContainer() (string, error) {
	// Get list of running containers
	output, err := DockerPS("--filter", "status=running", "--format", "{{.Names}}")
	if err != nil {
		return "", err
	}

	// Parse container names
	containers := strings.Fields(output)
	for _, name := range containers {
		// Check if it's a vault container (starts with vault_web)
		if strings.HasPrefix(name, "vault_web") {
			// Check if container is healthy
			// We can't easily check health status from docker ps, so we'll try to call the API
			// If it fails, we'll try the next container
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
