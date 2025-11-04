package cmd

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	buildCmd := &cobra.Command{
		Use:   "build",
		Short: "Rebuild and start the Leyzen Vault Docker stack",
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to build configuration: %w", err)
			}
			color.HiCyan("Rebuilding Docker stack...")
			if err := internal.RunCompose(EnvFilePath(), "up", "-d", "--build", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to rebuild stack: %w", err)
			}
			color.HiGreen("✓ Successfully rebuilt Docker stack")
			return nil
		},
	}

	rootCmd.AddCommand(buildCmd)
}
