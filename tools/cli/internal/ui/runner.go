package ui

import (
	"context"
	"fmt"
	"strings"
	"sync"

	tea "github.com/charmbracelet/bubbletea"

	"leyzenctl/internal"
)

type Runner struct {
	envFile string
}

func NewRunner(envFile string) *Runner {
	return &Runner{envFile: envFile}
}

func StartApp(ctx context.Context, envFile string) error {
	resolvedEnv, err := internal.ResolveEnvFilePath(envFile)
	if err != nil {
		return err
	}

	runner := NewRunner(resolvedEnv)
	model := NewModel(resolvedEnv, runner)

	options := []tea.ProgramOption{tea.WithAltScreen()}
	if ctx != nil {
		options = append(options, tea.WithContext(ctx))
	}

	program := tea.NewProgram(model, options...)
	if _, err := program.Run(); err != nil {
		return err
	}
	return nil
}

func (r *Runner) Run(action ActionType) (<-chan actionProgressMsg, error) {
	if action == ActionNone {
		return nil, fmt.Errorf("no action requested")
	}

	stream := make(chan actionProgressMsg, 64)

	go func() {
		defer close(stream)
		writer := newActionWriter(action, stream)

		var err error
		switch action {
		case ActionRestart:
			err = r.restart(writer)
		case ActionStart:
			err = r.start(writer)
		case ActionStop:
			err = r.stop(writer)
		case ActionBuild:
			err = r.build(writer)
		case ActionWizard:
			err = r.wizard(writer)
		default:
			err = fmt.Errorf("unknown action %s", action)
		}

		writer.flush()

		if err != nil {
			stream <- actionProgressMsg{Action: action, Err: err}
			return
		}

		stream <- actionProgressMsg{Action: action, Done: true}
	}()

	return stream, nil
}

func (r *Runner) restart(writer *actionWriter) error {
	writer.emit("🔄 [RESTART] Restarting Leyzen Vault...")
	if err := r.stop(writer); err != nil {
		return err
	}
	if err := r.build(writer); err != nil {
		return err
	}
	if err := r.start(writer); err != nil {
		return err
	}
	return nil
}

func (r *Runner) start(writer *actionWriter) error {
	writer.emit("▶ [START] Starting Docker stack...")
	return internal.RunComposeWithWriter(writer, writer, r.envFile, "up", "-d", "--remove-orphans")
}

func (r *Runner) stop(writer *actionWriter) error {
	writer.emit("⏹ [STOP] Stopping Docker stack...")
	return internal.RunComposeWithWriter(writer, writer, r.envFile, "down", "--remove-orphans")
}

func (r *Runner) build(writer *actionWriter) error {
	if err := internal.RunBuildScriptWithWriter(writer, writer, r.envFile); err != nil {
		return err
	}
	writer.emit("🔨 [BUILD] Rebuilding Docker stack...")
	return internal.RunComposeWithWriter(writer, writer, r.envFile, "up", "-d", "--build", "--remove-orphans")
}

func (r *Runner) wizard(writer *actionWriter) error {
	// The wizard is now handled directly in the TUI via ViewWizard
	// This function should no longer be called, but we keep it for compatibility
	writer.emit("⚠️  Wizard should be initiated from dashboard (press 'w')")
	return fmt.Errorf("wizard not available as action - use dashboard")
}

func fetchConfigListCmd(envFile string) tea.Cmd {
	return func() tea.Msg {
		// Initialize from template if file is empty
		pairs, err := internal.InitializeEnvFromTemplate(envFile)
		if err != nil {
			return configListMsg{err: err}
		}
		return configListMsg{pairs: pairs}
	}
}

type actionWriter struct {
	action ActionType
	stream chan<- actionProgressMsg
	mu     sync.Mutex
	buf    strings.Builder
}

func newActionWriter(action ActionType, stream chan<- actionProgressMsg) *actionWriter {
	return &actionWriter{action: action, stream: stream}
}

func (w *actionWriter) emit(line string) {
	if strings.TrimSpace(line) == "" {
		return
	}
	w.stream <- actionProgressMsg{Action: w.action, Line: line}
}

func (w *actionWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	w.buf.Write(p)
	data := w.buf.String()
	w.buf.Reset()

	for {
		idx := strings.IndexByte(data, '\n')
		if idx == -1 {
			w.buf.WriteString(data)
			break
		}

		line := strings.TrimSpace(strings.TrimSuffix(data[:idx], "\r"))
		// Clean the line of control characters
		line = strings.Trim(line, "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")

		// Ignore empty lines or problematic isolated characters
		if line != "" {
			// Filter isolated characters that are likely artifacts
			if len(line) == 1 {
				// Allow only valid special characters
				validSingleChars := map[string]bool{
					"[": true,
					"]": true,
					"(": true,
					")": true,
				}
				if !validSingleChars[line] {
					// Ignore isolated characters like "C", "B", etc.
					data = data[idx+1:]
					continue
				}
			}
			w.stream <- actionProgressMsg{Action: w.action, Line: line}
		}
		data = data[idx+1:]
	}

	return len(p), nil
}

func (w *actionWriter) flush() {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.buf.Len() == 0 {
		return
	}

	line := strings.TrimSpace(w.buf.String())
	if line != "" {
		w.stream <- actionProgressMsg{Action: w.action, Line: line}
	}
	w.buf.Reset()
}

func fetchStatusesCmd() tea.Cmd {
	return func() tea.Msg {
		output, err := internal.DockerPS("--format", "{{.Names}}\t{{.Status}}\t{{.RunningFor}}")
		if err != nil {
			return statusMsg{err: err}
		}
		return statusMsg{statuses: parseStatuses(output)}
	}
}

func parseStatuses(output string) []ContainerStatus {
	output = strings.TrimSpace(output)
	if output == "" {
		return nil
	}
	var statuses []ContainerStatus
	for _, line := range strings.Split(output, "\n") {
		parts := strings.Split(line, "\t")
		if len(parts) != 3 {
			continue
		}
		statuses = append(statuses, ContainerStatus{
			Name:      parts[0],
			Status:    parts[1],
			RawStatus: parts[1],
			Age:       parts[2],
		})
	}
	return statuses
}
