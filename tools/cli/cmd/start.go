package cmd

import (
	"fmt"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	startCmd := &cobra.Command{
		Use:          "start [services...]",
		Short:        "Start the Leyzen Vault Docker stack or specific services",
		Args:         cobra.ArbitraryArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Always regenerate configuration before starting to ensure latest changes are applied
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return fmt.Errorf("failed to generate configuration: %w", err)
			}

			if len(args) > 0 {
				color.HiCyan("Starting services: %s...", strings.Join(args, ", "))
			} else {
				color.HiCyan("Starting Docker stack...")
			}

			composeArgs := append([]string{"up", "-d", "--remove-orphans"}, args...)
			if err := internal.RunCompose(EnvFilePath(), composeArgs...); err != nil {
				return fmt.Errorf("failed to start: %w", err)
			}

			if len(args) > 0 {
				color.HiGreen("Successfully started services")
			} else {
				color.HiGreen("Successfully started Docker stack")
			}
			return nil
		},
	}

	rootCmd.AddCommand(startCmd)
}
