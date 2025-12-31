package cmd

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"leyzenctl/internal/ui"
	"leyzenctl/internal/version"
)

var (
	envFile     string
	versionFlag string
	rootCmd     = &cobra.Command{
		Use:   "leyzenctl",
		Short: "Leyzen Vault management CLI",
		Long: color.HiCyanString("Leyzenctl orchestrates the Leyzen Vault Docker stack and configuration.\n\n") +
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
	rootCmd.SilenceErrors = true
	rootCmd.PersistentFlags().StringVar(&envFile, "env-file", defaultEnv, "Path to the environment file to use")
	rootCmd.PersistentFlags().StringVarP(&versionFlag, "version", "v", "", "Print version information and exit; use 'json' for JSON output")
	if f := rootCmd.PersistentFlags().Lookup("version"); f != nil {
		f.NoOptDefVal = "text"
	}
	rootCmd.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
		if cmd.Flags().Changed("version") {
			if (versionFlag == "" || versionFlag == "text") && len(args) > 0 && args[0] == "json" {
				versionFlag = "json"
			}
			printVersion(versionFlag)
			os.Exit(0)
		}
		return nil
	}
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

func printVersion(format string) {
	v := version.Version
	c := version.Commit
	d := version.Date
	channel := "stable"
	latest := ""
	if v == "nightly" {
		channel = "nightly"
		latest = latestStable()
	}
	if format == "json" {
		type payload struct {
			Version      string `json:"version"`
			Channel      string `json:"channel"`
			LatestStable string `json:"latestStable,omitempty"`
			Commit       string `json:"commit"`
			Date         string `json:"date"`
		}
		p := payload{Version: v, Channel: channel, Commit: c, Date: d}
		if channel == "nightly" {
			if latest == "" {
				p.LatestStable = "unknown"
			} else {
				p.LatestStable = latest
			}
		}
		b, _ := json.Marshal(p)
		fmt.Println(string(b))
		return
	}
	if channel == "nightly" {
		if latest == "" {
			fmt.Printf("leyzenctl nightly (latest stable: unknown) (commit %s, built %s)\n", c, d)
		} else {
			fmt.Printf("leyzenctl nightly (latest stable: %s) (commit %s, built %s)\n", latest, c, d)
		}
		return
	}
	fmt.Printf("leyzenctl %s (commit %s, built %s)\n", v, c, d)
}

func latestStable() string {
	client := &http.Client{Timeout: 3 * time.Second}
	req, err := http.NewRequest("GET", "https://api.github.com/repos/3xpyth0n/leyzen-vault/releases/latest", nil)
	if err != nil {
		return ""
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return ""
	}
	type latestResp struct {
		TagName string `json:"tag_name"`
	}
	var lr latestResp
	if err := json.NewDecoder(resp.Body).Decode(&lr); err != nil {
		return ""
	}
	if lr.TagName == "" {
		return ""
	}
	return lr.TagName
}
