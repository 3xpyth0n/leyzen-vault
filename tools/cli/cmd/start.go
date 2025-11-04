package cmd

import (
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
				return err
			}
			color.HiCyan("Starting Docker stack...")
			return internal.RunCompose(EnvFilePath(), "up", "-d", "--remove-orphans")
		},
	}

	rootCmd.AddCommand(startCmd)
}
