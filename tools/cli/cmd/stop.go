package cmd

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	stopCmd := &cobra.Command{
		Use:   "stop",
		Short: "Stop the Leyzen Vault Docker stack",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Ensure docker-generated.yml exists before stopping
			if err := internal.EnsureDockerGeneratedFile(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to ensure docker-generated.yml exists: %w", err)
			}
			color.HiCyan("Stopping Docker stack...")
			if err := internal.RunCompose(EnvFilePath(), "down", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to stop stack: %w", err)
			}
			color.HiGreen("✓ Successfully stopped Docker stack")
			return nil
		},
	}

	rootCmd.AddCommand(stopCmd)
}
