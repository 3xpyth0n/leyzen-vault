package cmd

import (
	"fmt"

	survey "github.com/AlecAivazis/survey/v2"
	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

func init() {
	wizardCmd := &cobra.Command{
		Use:   "wizard",
		Short: "Interactive environment configuration",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			envFile, err := internal.LoadEnvFile(EnvFilePath())
			if err != nil {
				return err
			}

			prompts := []struct {
				Key      string
				Message  string
				Password bool
			}{
				{Key: "WEB_REPLICAS", Message: "Number of Vault replicas"},
				{Key: "ORCH_PASS", Message: "Orchestrator admin password", Password: true},
				{Key: "ROTATION_INTERVAL", Message: "Rotation interval (seconds)"},
			}

			responses := make(map[string]string)
			for _, prompt := range prompts {
				existing, _ := envFile.Get(prompt.Key)
				var answer string
				var question survey.Prompt
				if prompt.Password {
					question = &survey.Password{Message: prompt.Message}
				} else {
					question = &survey.Input{Message: prompt.Message, Default: existing}
				}

				var askOptions []survey.AskOpt
				if prompt.Password {
					askOptions = append(askOptions, survey.WithValidator(func(ans interface{}) error {
						str, _ := ans.(string)
						if str == "" && existing != "" {
							return nil
						}
						_, err := internal.ValidateEnvValue(prompt.Key, str)
						return err
					}))
				} else {
					askOptions = append(askOptions, survey.WithValidator(internal.SurveyValidator(prompt.Key)))
				}

				if err := survey.AskOne(question, &answer, askOptions...); err != nil {
					return fmt.Errorf("wizard aborted: %w", err)
				}

				if prompt.Password && answer == "" && existing != "" {
					responses[prompt.Key] = existing
					continue
				}

				sanitized, err := internal.ValidateEnvValue(prompt.Key, answer)
				if err != nil {
					return err
				}
				responses[prompt.Key] = sanitized
			}

			for key, value := range responses {
				envFile.Set(key, value)
			}

			if err := envFile.Write(); err != nil {
				return err
			}
			if err := internal.RunBuildScript(EnvFilePath()); err != nil {
				fmt.Println("⚠️ Failed to rebuild configuration:", err)
			}
			color.HiGreen("Configuration saved to %s", envFile.Path)
			return nil
		},
	}

	configCmd.AddCommand(wizardCmd)
}
