package cmd

import (
	"fmt"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Manage Leyzen Vault environment configuration",
}

func init() {
	rootCmd.AddCommand(configCmd)

	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List configured environment variables",
		RunE: func(cmd *cobra.Command, args []string) error {
			envFilePath := EnvFilePath()
			envFile, err := internal.LoadEnvFile(envFilePath)
			if err != nil {
				return err
			}

			pairs := envFile.Pairs()
			if len(pairs) == 0 {
				color.HiYellow("No environment variables configured yet (%s)", envFilePath)
				return nil
			}

			// Collect and sort keys
			keys := make([]string, 0, len(pairs))
			for k := range pairs {
				keys = append(keys, k)
			}
			sort.Strings(keys)

			// Compute max visible lengths (raw text, no ANSI)
			maxKey := utf8.RuneCountInString("KEY")
			maxVal := utf8.RuneCountInString("VALUE")
			for _, k := range keys {
				if l := utf8.RuneCountInString(k); l > maxKey {
					maxKey = l
				}
				if l := utf8.RuneCountInString(pairs[k]); l > maxVal {
					maxVal = l
				}
			}

			// One-space padding on each side inside cells
			keyWidth := maxKey + 2   // visible width of key cell content (including internal spaces)
			valWidth := maxVal + 2   // visible width of value cell content (including internal spaces)

			// Frame lines
			topBorder := "╭" + strings.Repeat("─", keyWidth) + "┬" + strings.Repeat("─", valWidth) + "╮"
			midBorder := "├" + strings.Repeat("─", keyWidth) + "┼" + strings.Repeat("─", valWidth) + "┤"
			botBorder := "╰" + strings.Repeat("─", keyWidth) + "┴" + strings.Repeat("─", valWidth) + "╯"

			// Print header row (headers colored but width computed from raw)
			fmt.Println(topBorder)
			fmt.Print("│")
			fmt.Print(padCell("KEY", keyWidth, color.HiBlueString("KEY")))
			fmt.Print("│")
			fmt.Print(padCell("VALUE", valWidth, color.HiBlueString("VALUE")))
			fmt.Println("│")
			fmt.Println(midBorder)

			// Print data rows (keys colored, values plain)
			for _, k := range keys {
				v := pairs[k]
				fmt.Print("│")
				fmt.Print(padCell(k, keyWidth, color.HiGreenString(k)))
				fmt.Print("│")
				fmt.Print(padCell(v, valWidth, v))
				fmt.Println("│")
			}

			fmt.Println(botBorder)
			return nil
		},
	}

	setCmd := &cobra.Command{
		Use:   "set <KEY> <VALUE>",
		Short: "Set an environment variable",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			key := args[0]
			rawValue := args[1]

			sanitized, err := internal.ValidateEnvValue(key, rawValue)
			if err != nil {
				return err
			}

			envFile, err := internal.LoadEnvFile(EnvFilePath())
			if err != nil {
				return err
			}
			envFile.Set(key, sanitized)
			if err := envFile.Write(); err != nil {
				return err
			}

			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				fmt.Println("⚠️ Failed to rebuild configuration:", err)
			}

			color.HiGreen("%s updated", key)
			return nil
		},
	}

	configCmd.AddCommand(listCmd, setCmd)
}

func padCell(raw string, visibleWidth int, colored string) string {
	rawLen := utf8.RuneCountInString(raw)
	used := 1 + rawLen // 1 leading space + content visible length
	if used < visibleWidth {
		return " " + colored + strings.Repeat(" ", visibleWidth-used)
	}
	return " " + colored
}

