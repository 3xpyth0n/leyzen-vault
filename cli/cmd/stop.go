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
			if err := internal.RunBuildScript(); err != nil {
				return err
			}
			color.HiCyan("Stopping Docker stack...")
			return internal.RunCompose("down")
		},
	}

	rootCmd.AddCommand(stopCmd)
}
