package cmd

import (
	"fmt"
	"sort"
	"strings"

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

			keys := make([]string, 0, len(pairs))
			for key := range pairs {
				keys = append(keys, key)
			}
			sort.Strings(keys)

			maxKey := 0
			for _, key := range keys {
				if len(key) > maxKey {
					maxKey = len(key)
				}
			}

			header := fmt.Sprintf("%-*s %s", maxKey, color.HiBlueString("KEY"), color.HiBlueString("VALUE"))
			fmt.Println(header)
			fmt.Println(strings.Repeat("-", len(header)))

			for _, key := range keys {
				value := pairs[key]
				fmt.Printf("%-*s %s\n", maxKey, color.HiGreenString(key), value)
			}
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
			if err := internal.RunBuildScript(); err != nil {
    			fmt.Println("⚠️ Failed to rebuild configuration:", err)
			}
			color.HiGreen("%s updated", key)
			return nil
		},
	}

	configCmd.AddCommand(listCmd, setCmd)
}
