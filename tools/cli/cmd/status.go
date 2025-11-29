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
		Use:   "status",
		Short: "Show the status of Leyzen Vault containers",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			output, err := internal.DockerPS("--format", "{{.Names}}\t{{.Status}}\t{{.RunningFor}}")
			if err != nil {
				return err
			}
			if output == "" {
				color.HiYellow("No containers are currently running.")
				return nil
			}

			// Calculate the maximum width for the AGE column
			ageWidth := len(ageHeader)
			lines := strings.Split(strings.TrimSpace(output), "\n")
			for _, line := range lines {
				parts := strings.Split(line, "\t")
				if len(parts) == 3 {
					if len(parts[2]) > ageWidth {
						ageWidth = len(parts[2])
					}
				}
			}

			// headers
			fmt.Printf("%s  %s  %s\n",
				padRightColored(color.HiBlueString("NAME"), nameWidth),
				padRightColored(color.HiBlueString("STATUS"), statusWidth),
				color.HiBlueString(ageHeader),
			)

			fmt.Printf("%s  %s  %s\n",
				strings.Repeat("─", nameWidth),
				strings.Repeat("─", statusWidth),
				strings.Repeat("─", ageWidth),
			)

			// rows
			for _, line := range lines {
				parts := strings.Split(line, "\t")
				if len(parts) != 3 {
					continue
				}

				name := parts[0]
				status := internal.FormatStatusColor(parts[1])
				age := parts[2]

				fmt.Printf("%s  %s  %s\n",
					padRightColored(name, nameWidth),
					padRightColored(status, statusWidth),
					age,
				)
			}

			return nil
		},
	}

	rootCmd.AddCommand(statusCmd)
}
