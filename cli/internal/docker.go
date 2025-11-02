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

	fullArgs := []string{"compose"}
	if resolvedEnv != "" {
		fullArgs = append(fullArgs, "--env-file", resolvedEnv)
	}
	fullArgs = append(fullArgs, args...)
	return runStreaming(stdout, stderr, fullArgs)
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
