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
		RunE: func(cmd *cobra.Command, args []string) error {
			color.HiCyan("Restarting Docker stack...")
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
