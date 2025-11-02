package cmd

import (
	"fmt"
	"os"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
)

var (
	envFile string
	rootCmd = &cobra.Command{
		Use:   "leyzenctl",
		Short: "Leyzen Vault management CLI",
		Long:  color.HiCyanString("Leyzenctl orchestrates the Leyzen Vault Docker stack and configuration."),
	}
)

func init() {
	rootCmd.PersistentFlags()
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, color.HiRedString("Error: %v", err))
		os.Exit(1)
	}
}

func EnvFilePath() string {
	return envFile
}
