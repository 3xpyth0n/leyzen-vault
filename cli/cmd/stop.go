package cmd

import (
	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	stopCmd := &cobra.Command{
		Use:   "stop",
		Short: "Stop the Leyzen Vault Docker stack",
		RunE: func(cmd *cobra.Command, args []string) error {
			color.HiCyan("Stopping Docker stack...")
			return internal.RunCompose(EnvFilePath(), "down", "--remove-orphans")
		},
	}

	rootCmd.AddCommand(stopCmd)
}
