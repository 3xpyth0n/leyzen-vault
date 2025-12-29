package cmd

import (
	"fmt"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	buildCmd := &cobra.Command{
		Use:          "build [services...]",
		Short:        "Rebuild and start the Leyzen Vault Docker stack or specific services",
		Args:         cobra.ArbitraryArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if len(args) > 0 {
				color.HiCyan("Rebuilding services: %s...", strings.Join(args, ", "))
				// Always regenerate configuration to ensure latest changes are applied
				if err := internal.RunBuildScript(EnvFilePath()); err != nil {
					return fmt.Errorf("failed to generate configuration: %w", err)
				}
				composeArgs := append([]string{"up", "-d", "--build", "--remove-orphans"}, args...)
				if err := internal.RunCompose(EnvFilePath(), composeArgs...); err != nil {
					return fmt.Errorf("failed to rebuild services: %w", err)
				}
				color.HiGreen("✓ Successfully rebuilt services")
				return nil
			}

			// Stop containers before building
			color.HiYellow("Stopping Docker stack...")
			if err := internal.RunCompose(EnvFilePath(), "down", "--remove-orphans"); err != nil {
				return fmt.Errorf("failed to stop stack: %w", err)
			}
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
