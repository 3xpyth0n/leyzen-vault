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
			color.HiCyan("Restarting Docker stack...")
			if err := internal.RunCompose(EnvFilePath(), "down", "--remove-orphans"); err != nil {
				return err
			}
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				return err
			}
			return internal.RunCompose(EnvFilePath(), "up", "-d", "--remove-orphans")
		},
	}

	rootCmd.AddCommand(restartCmd)
}
