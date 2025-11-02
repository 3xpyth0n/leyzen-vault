package cmd

import (
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
				return err
			}
			color.HiCyan("Rebuilding Docker stack...")
			return internal.RunCompose(EnvFilePath(), "up", "-d", "--build", "--remove-orphans")
		},
	}

	rootCmd.AddCommand(buildCmd)
}
