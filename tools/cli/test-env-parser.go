// +build ignore

// test-env-parser.go is a minimal helper program to verify that the Go env parser
// matches the Python parser behavior.
//
// Usage: go run test-env-parser.go <path-to-env-file>
// Output: JSON object with key-value pairs parsed from the env file

package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/3xpyth0n/leyzen-vault/tools/cli/internal"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <env-file-path>\n", os.Args[0])
		os.Exit(1)
	}

	envFile, err := internal.LoadEnvFile(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading env file: %v\n", err)
		os.Exit(1)
	}

	pairs := envFile.Pairs()
	jsonBytes, err := json.Marshal(pairs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(jsonBytes))
}

