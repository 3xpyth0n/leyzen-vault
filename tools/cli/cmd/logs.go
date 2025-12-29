package cmd

import (
	"fmt"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	logsCmd := &cobra.Command{
		Use:   "logs [services...]",
		Short: "View output from services",
		Long:  "Display logs from all services or specific ones. Use --tail to limit output.",
		Args:  cobra.ArbitraryArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			tail, _ := cmd.Flags().GetString("tail")
			follow, _ := cmd.Flags().GetBool("follow")

			composeArgs := []string{"logs"}
			if follow {
				composeArgs = append(composeArgs, "-f")
			}
			if tail != "" {
				composeArgs = append(composeArgs, "--tail", tail)
			}
			composeArgs = append(composeArgs, args...)

			if len(args) > 0 {
				color.HiCyan("Showing logs for: %s...", strings.Join(args, ", "))
			} else {
				color.HiCyan("Showing logs for all services...")
			}

			if err := internal.RunCompose(EnvFilePath(), composeArgs...); err != nil {
				return fmt.Errorf("failed to get logs: %w", err)
			}
			return nil
		},
	}

	logsCmd.Flags().String("tail", "all", "Number of lines to show from the end of the logs for each container")
	logsCmd.Flags().BoolP("follow", "f", false, "Follow log output")

	rootCmd.AddCommand(logsCmd)
}
