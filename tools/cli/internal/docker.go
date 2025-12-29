package internal

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"
)

const commandTimeout = 10 * time.Minute

// RunCompose executes `docker compose` with the provided arguments and streams the output.
func RunCompose(envFile string, args ...string) error {
	return RunComposeWithWriter(os.Stdout, os.Stderr, envFile, args...)
}

// RunComposeWithWriter executes `docker compose` with the provided arguments, streaming output to the supplied writers.
func RunComposeWithWriter(stdout, stderr io.Writer, envFile string, args ...string) error {
	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return err
	}

	repoRoot, err := FindRepoRoot()
	if err != nil {
		return fmt.Errorf("failed to find repository root: %w", err)
	}

	fullArgs := []string{"compose", "-f", "docker-generated.yml"}
	fullArgs = append(fullArgs, args...)

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", fullArgs...)
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	cmd.Dir = repoRoot // Set working directory to repo root

	// Set LEYZEN_ENV_FILE environment variable if env file is specified
	if resolvedEnv != "" {
		env := os.Environ()
		env = append(env, fmt.Sprintf("LEYZEN_ENV_FILE=%s", resolvedEnv))
		cmd.Env = env
	}

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("docker %s: %w", strings.Join(fullArgs, " "), err)
	}
	return nil
}

// DockerComposePS executes `docker compose ps` with the provided arguments and returns its output.
func DockerComposePS(envFile string, args ...string) (string, error) {
	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return "", err
	}

	if err := ensureBinaryAvailable("docker"); err != nil {
		return "", err
	}

	repoRoot, err := FindRepoRoot()
	if err != nil {
		return "", fmt.Errorf("failed to find repository root: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	fullArgs := []string{"compose", "-f", "docker-generated.yml", "ps", "-a"}
	fullArgs = append(fullArgs, args...)

	cmd := exec.CommandContext(ctx, "docker", fullArgs...)
	cmd.Dir = repoRoot // Set working directory to repo root

	// Set LEYZEN_ENV_FILE environment variable if env file is specified
	if resolvedEnv != "" {
		env := os.Environ()
		env = append(env, fmt.Sprintf("LEYZEN_ENV_FILE=%s", resolvedEnv))
		cmd.Env = env
	}

	var stdout bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("docker compose ps: %w", err)
	}

	return strings.TrimSpace(stdout.String()), nil
}

// ProjectStatus represents the status of a service in the project.
type ProjectStatus struct {
	Name   string
	Status string
	Age    string
}

// GetProjectStatuses retrieves the status of all services defined in the compose file.
func GetProjectStatuses(envFile string) ([]ProjectStatus, error) {
	// 1. Get all services defined in the YAML
	services, err := GetComposeServices(envFile)
	if err != nil {
		return nil, fmt.Errorf("failed to get services: %w", err)
	}

	// 2. Get statuses of existing containers
	psOutput, err := DockerComposePS(envFile, "--format", "{{.Service}}\t{{.Status}}\t{{.RunningFor}}")
	if err != nil {
		// If ps fails, we still want to show the services but with unknown status
		psOutput = ""
	}

	// Parse ps output into a map of service name -> status info
	containerStatuses := make(map[string]ProjectStatus)
	if psOutput != "" {
		for _, line := range strings.Split(psOutput, "\n") {
			parts := strings.Split(line, "\t")
			if len(parts) >= 2 {
				serviceName := parts[0]
				status := parts[1]
				age := ""
				if len(parts) >= 3 {
					age = parts[2]
				}
				containerStatuses[serviceName] = ProjectStatus{
					Name:   serviceName,
					Status: status,
					Age:    age,
				}
			}
		}
	}

	// 3. Merge services and statuses
	var results []ProjectStatus
	for _, serviceName := range services {
		if st, ok := containerStatuses[serviceName]; ok {
			results = append(results, st)
		} else {
			// Service defined in YAML but no container exists in Docker
			results = append(results, ProjectStatus{
				Name:   serviceName,
				Status: "Not created",
				Age:    "-",
			})
		}
	}

	// 4. Sort results alphabetically by Name
	sort.Slice(results, func(i, j int) bool {
		return results[i].Name < results[j].Name
	})

	return results, nil
}

// GetComposeServices retrieves the list of services from docker-compose configuration.
func GetComposeServices(envFile string) ([]string, error) {
	resolvedEnv, err := ResolveEnvFilePath(envFile)
	if err != nil {
		return nil, err
	}

	if err := ensureBinaryAvailable("docker"); err != nil {
		return nil, err
	}

	repoRoot, err := FindRepoRoot()
	if err != nil {
		return nil, fmt.Errorf("failed to find repository root: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	fullArgs := []string{"compose", "-f", "docker-generated.yml", "config", "--services"}

	cmd := exec.CommandContext(ctx, "docker", fullArgs...)
	cmd.Dir = repoRoot // Set working directory to repo root

	// Set LEYZEN_ENV_FILE environment variable if env file is specified
	if resolvedEnv != "" {
		env := os.Environ()
		env = append(env, fmt.Sprintf("LEYZEN_ENV_FILE=%s", resolvedEnv))
		cmd.Env = env
	}

	var stdout bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("docker compose config --services: %w", err)
	}

	output := strings.TrimSpace(stdout.String())
	if output == "" {
		return []string{}, nil
	}

	services := strings.Split(output, "\n")
	// Remove empty strings
	var result []string
	for _, s := range services {
		s = strings.TrimSpace(s)
		if s != "" {
			result = append(result, s)
		}
	}

	return result, nil
}

func runStreaming(stdout, stderr io.Writer, args []string) error {
	if err := ensureBinaryAvailable("docker"); err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", args...)
	cmd.Stdout = stdout
	cmd.Stderr = stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("docker %s: %w", strings.Join(args, " "), err)
	}
	return nil
}
