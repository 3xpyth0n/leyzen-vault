package cmd

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	restartCmd := &cobra.Command{
		Use:   "restart",
		Short: "Restart the Leyzen Vault Docker stack",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			color.HiCyan("Restarting Docker stack...")

			// Promote files to persistent storage before shutdown
			color.HiYellow("Promoting files to persistent storage...")
			if err := internal.PrepareRotation(EnvFilePath()); err != nil {
				// Log warning but don't fail - files may still be in tmpfs
				color.HiYellow("⚠ Warning: Failed to promote files before restart: %v", err)
				color.HiYellow("  Files in tmpfs will be lost. Continuing with restart...")
			} else {
				color.HiGreen("✓ Files promoted to persistent storage")
			}

			color.HiYellow("Stopping containers...")
			if err := internal.RunCompose(EnvFilePath(), "down", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to stop stack: %w", err)
			}
			color.HiYellow("Rebuilding configuration...")
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to build configuration: %w", err)
			}
			color.HiYellow("Starting containers...")
			if err := internal.RunCompose(EnvFilePath(), "up", "-d", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to start stack: %w", err)
			}
			color.HiGreen("✓ Successfully restarted Docker stack")
			return nil
		},
	}

	rootCmd.AddCommand(restartCmd)
}
