package cmd

import (
	"fmt"
	"os"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal/ui"
)

var (
	envFile string
	rootCmd = &cobra.Command{
		Use:   "leyzenctl",
		Short: "Leyzen Vault management CLI",
		Long:  color.HiCyanString("Leyzenctl orchestrates the Leyzen Vault Docker stack and configuration.\n\n") +
			"Run 'leyzenctl' without arguments to launch the interactive dashboard, or use subcommands like 'start', 'stop', 'status'.",
		RunE: func(cmd *cobra.Command, args []string) error {
			return ui.StartApp(cmd.Context(), EnvFilePath())
		},
	}
)

func init() {
	defaultEnv := ".env"
	if override := os.Getenv("LEYZEN_ENV_FILE"); override != "" {
		defaultEnv = override
	}
	rootCmd.SilenceUsage = true
	rootCmd.PersistentFlags().StringVar(&envFile, "env-file", defaultEnv, "Path to the environment file to use")
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, color.HiRedString("Error: %v", err))
		os.Exit(1)
	}
}

func EnvFilePath() string {
	if envFile == "" {
		return ".env"
	}
	return envFile
}
