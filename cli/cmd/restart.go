package cmd

import (
	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	restartCmd := &cobra.Command{
		Use:   "restart",
		Short: "Restart the Leyzen Vault Docker stack",
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := internal.RunBuildScript(); err != nil {
				return err
			}
			color.HiCyan("Restarting Docker stack...")
			if err := internal.RunCompose("down"); err != nil {
				return err
			}
			return internal.RunCompose("up", "-d", "--remove-orphans")
		},
	}

	rootCmd.AddCommand(restartCmd)
}
