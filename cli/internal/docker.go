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

const commandTimeout = 10 * time.Minute

// RunCompose executes `docker compose` with the provided arguments and streams the output.
func RunCompose(args ...string) error {
	fullArgs := append([]string{"compose"}, args...)
	return runStreaming(fullArgs)
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

func runStreaming(args []string) error {
	if err := ensureBinaryAvailable("docker"); err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), commandTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("docker %s: %w", strings.Join(args, " "), err)
	}
	return nil
}
