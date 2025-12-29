package cmd

import (
	"fmt"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	restartCmd := &cobra.Command{
		Use:          "restart [services...]",
		Short:        "Restart the Leyzen Vault Docker stack or specific services",
		Args:         cobra.ArbitraryArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				color.HiCyan("Restarting services: %s...", strings.Join(args, ", "))
				// Always regenerate configuration to ensure latest changes are applied
				if err := internal.RunBuildScript(EnvFilePath()); err != nil {
					return fmt.Errorf("failed to generate configuration: %w", err)
				}
				// For individual services, we use stop + up to ensure clean state
				if err := internal.RunCompose(EnvFilePath(), append([]string{"stop"}, args...)...); err != nil {
					return fmt.Errorf("failed to stop services: %w", err)
				}
				if err := internal.RunCompose(EnvFilePath(), append([]string{"up", "-d", "--remove-orphans"}, args...)...); err != nil {
					return fmt.Errorf("failed to start services: %w", err)
				}
				color.HiGreen("Successfully restarted services")
				return nil
			}

			color.HiCyan("Restarting Docker stack...")

			// Promote files to persistent storage before shutdown
			color.HiYellow("Promoting files to persistent storage...")
			if err := internal.PrepareRotation(EnvFilePath()); err != nil {
				// Log warning but don't fail - files may still be in tmpfs
				color.HiYellow("[WARN] Warning: Failed to promote files before restart: %v", err)
				color.HiYellow("  Files in tmpfs will be lost. Continuing with restart...")
			} else {
				color.HiGreen("Files promoted to persistent storage")
			}

			color.HiYellow("Stopping containers...")
			if err := internal.RunCompose(EnvFilePath(), "down", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to stop stack: %w", err)
			}
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to generate configuration: %w", err)
			}
			color.HiYellow("Starting containers...")
			if err := internal.RunCompose(EnvFilePath(), "up", "-d", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to start stack: %w", err)
			}
			color.HiGreen("Successfully restarted Docker stack")
			return nil
		},
	}

	rootCmd.AddCommand(restartCmd)
}
