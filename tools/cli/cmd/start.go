package cmd

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	startCmd := &cobra.Command{
		Use:   "start",
		Short: "Start the Leyzen Vault Docker stack",
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to build configuration: %w", err)
			}
			color.HiCyan("Starting Docker stack...")
			if err := internal.RunCompose(EnvFilePath(), "up", "-d", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to start stack: %w", err)
			}
			color.HiGreen("✓ Successfully started Docker stack")
			return nil
		},
	}

	rootCmd.AddCommand(startCmd)
}
