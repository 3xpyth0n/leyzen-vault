package cmd

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"leyzenctl/internal"
	"leyzenctl/internal/status"
)

func init() {
	statusCmd := &cobra.Command{
		Use:          "status",
		Aliases:      []string{"status=json"},
		Short:        "Show the status of Leyzen Vault",
		Long:         "Show Leyzen Vault status. Use --json, 'json' positional, or alias 'status=json' for JSON output.",
		Args:         cobra.ArbitraryArgs,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			jsonOut, _ := cmd.Flags().GetBool("json")
			if !jsonOut {
				for _, a := range args {
					if strings.EqualFold(strings.TrimSpace(a), "json") {
						jsonOut = true
						break
					}
				}
			}
			if err := internal.EnsureDockerGeneratedFileWithWriter(cmd.OutOrStdout(), cmd.ErrOrStderr(), EnvFilePath()); err != nil {
				return fmt.Errorf("failed to initialize configuration: %w", err)
			}

			if jsonOut {
				res, err := status.Collect(EnvFilePath(), 800*time.Millisecond)
				if err != nil {
					return err
				}
				b, err := status.MarshalJSON(res)
				if err != nil {
					return err
				}
				fmt.Fprintln(cmd.OutOrStdout(), string(b))
				if res.Summary.OverallStatus == "critical" {
					os.Exit(1)
				}
				return nil
			}

			res, err := status.Collect(EnvFilePath(), 800*time.Millisecond)
			if err != nil {
				return err
			}
			status.RenderHuman(cmd.OutOrStdout(), res)
			if res.Summary.OverallStatus == "critical" {
				os.Exit(1)
			}
			return nil
		},
	}

	statusCmd.PersistentFlags().Bool("json", false, "Output status as JSON")
	statusCmd.FParseErrWhitelist.UnknownFlags = true

	rootCmd.AddCommand(statusCmd)
}
