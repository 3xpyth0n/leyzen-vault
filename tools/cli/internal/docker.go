package internal

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
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

// DockerPS executes `docker ps` with the provided arguments and returns its output.
func DockerPS(args ...string) (string, error) {
	if err := ensureBinaryAvailable("docker"); err != nil {
		return "", err
	}

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", append([]string{"ps"}, args...)...)
	var stdout bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("docker ps: %w", err)
	}

	return strings.TrimSpace(stdout.String()), nil
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
