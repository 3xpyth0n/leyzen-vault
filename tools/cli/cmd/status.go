package cmd

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

const (
	nameWidth   = 28
	statusWidth = 36
	ageHeader   = "AGE"
)

// regex to remove ANSI escape sequences
var ansiRegex = regexp.MustCompile(`\x1b\[[0-9;]*m`)

func visibleLen(s string) int {
	return len(ansiRegex.ReplaceAllString(s, ""))
}

func padRightColored(s string, width int) string {
	visible := visibleLen(s)
	if visible >= width {
		return s
	}
	return s + strings.Repeat(" ", width-visible)
}

func init() {
	statusCmd := &cobra.Command{
		Use:          "status",
		Short:        "Show the status of Leyzen Vault containers",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Ensure docker-generated.yml exists before checking status
			if err := internal.EnsureDockerGeneratedFileWithWriter(cmd.OutOrStdout(), cmd.ErrOrStderr(), EnvFilePath()); err != nil {
				return fmt.Errorf("failed to initialize configuration: %w", err)
			}

			projectStatuses, err := internal.GetProjectStatuses(EnvFilePath())
			if err != nil {
				return err
			}

			if len(projectStatuses) == 0 {
				fmt.Fprintln(cmd.OutOrStdout(), color.HiYellowString("No services defined in configuration."))
				return nil
			}

			// Define table column widths
			const (
				nameWidth   = 28
				statusWidth = 36
			)

			// Print header
			fmt.Fprintf(cmd.OutOrStdout(), "%s  %s  %s\n",
				internal.PadRightVisible(color.HiCyanString("NAME"), nameWidth),
				internal.PadRightVisible(color.HiCyanString("STATUS"), statusWidth),
				color.HiCyanString("AGE"),
			)
			fmt.Fprintf(cmd.OutOrStdout(), "%s  %s  %s\n",
				strings.Repeat("─", nameWidth),
				strings.Repeat("─", statusWidth),
				strings.Repeat("─", 10),
			)

			for _, st := range projectStatuses {
				status := internal.FormatStatusColor(st.Status)
				fmt.Fprintf(cmd.OutOrStdout(), "%s  %s  %s\n",
					internal.PadRightVisible(st.Name, nameWidth),
					internal.PadRightVisible(status, statusWidth),
					st.Age,
				)
			}

			return nil
		},
	}

	rootCmd.AddCommand(statusCmd)
}
