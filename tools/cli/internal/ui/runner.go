package ui

import (
	"context"
	"fmt"
	"io"
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

	// Ensure docker-generated.yml exists at startup (silently, no logs)
	if err := internal.EnsureDockerGeneratedFileWithWriter(io.Discard, io.Discard, resolvedEnv); err != nil {
		return fmt.Errorf("failed to initialize docker-generated.yml: %w", err)
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
	return r.RunWithServices(action, []string{})
}

func (r *Runner) RunWithServices(action ActionType, services []string) (<-chan actionProgressMsg, error) {
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
			err = r.restartWithServices(writer, services)
		case ActionStart:
			err = r.startWithServices(writer, services)
		case ActionStop:
			err = r.stopWithServices(writer, services)
		case ActionBuild:
			err = r.buildWithServices(writer, services)
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
	return r.restartWithServices(writer, []string{})
}

func (r *Runner) restartWithServices(writer *actionWriter, services []string) error {
	writer.emit("🔄 [RESTART] Restarting Leyzen Vault...")
	if err := r.stopWithServices(writer, services); err != nil {
		return err
	}
	if err := r.buildWithServices(writer, services); err != nil {
		return err
	}
	if err := r.startWithServices(writer, services); err != nil {
		return err
	}
	return nil
}

func (r *Runner) start(writer *actionWriter) error {
	return r.startWithServices(writer, []string{})
}

func (r *Runner) startWithServices(writer *actionWriter, services []string) error {
	if len(services) == 0 {
		writer.emit("▶ [START] Starting Docker stack...")
		return internal.RunComposeWithWriter(writer, writer, r.envFile, "up", "-d", "--remove-orphans")
	}
	writer.emit(fmt.Sprintf("▶ [START] Starting services: %s", strings.Join(services, ", ")))
	args := []string{"up", "-d", "--remove-orphans"}
	args = append(args, services...)
	return internal.RunComposeWithWriter(writer, writer, r.envFile, args...)
}

func (r *Runner) stop(writer *actionWriter) error {
	return r.stopWithServices(writer, []string{})
}

func (r *Runner) stopWithServices(writer *actionWriter, services []string) error {
	if len(services) == 0 {
		writer.emit("⏹ [STOP] Stopping Docker stack...")
		return internal.RunComposeWithWriter(writer, writer, r.envFile, "down", "--remove-orphans")
	}
	writer.emit(fmt.Sprintf("⏹ [STOP] Stopping services: %s", strings.Join(services, ", ")))
	// For stop, we need to use 'stop' command instead of 'down' for specific services
	args := []string{"stop"}
	args = append(args, services...)
	return internal.RunComposeWithWriter(writer, writer, r.envFile, args...)
}

func (r *Runner) build(writer *actionWriter) error {
	return r.buildWithServices(writer, []string{})
}

func (r *Runner) buildWithServices(writer *actionWriter, services []string) error {
	if err := internal.RunBuildScriptWithWriter(writer, writer, r.envFile); err != nil {
		return err
	}
	if len(services) == 0 {
		writer.emit("🔨 [BUILD] Rebuilding Docker stack...")
		return internal.RunComposeWithWriter(writer, writer, r.envFile, "up", "-d", "--build", "--remove-orphans")
	}
	writer.emit(fmt.Sprintf("🔨 [BUILD] Rebuilding services: %s", strings.Join(services, ", ")))
	// Build only the specified services
	buildArgs := []string{"build"}
	buildArgs = append(buildArgs, services...)
	if err := internal.RunComposeWithWriter(writer, writer, r.envFile, buildArgs...); err != nil {
		return err
	}
	// Then start the specified services
	upArgs := []string{"up", "-d", "--remove-orphans"}
	upArgs = append(upArgs, services...)
	return internal.RunComposeWithWriter(writer, writer, r.envFile, upArgs...)
}

func (r *Runner) wizard(writer *actionWriter) error {
	// The wizard is now handled directly in the TUI via ViewWizard
	// This function should no longer be called, but we keep it for compatibility
	writer.emit("⚠️  Wizard should be initiated from dashboard (press 'w')")
	return fmt.Errorf("wizard not available as action - use dashboard")
}

func fetchConfigListCmd(envFile string) tea.Cmd {
	return func() tea.Msg {
		// Load all variables from template + .env (template values are defaults, .env values take priority)
		pairs, err := internal.LoadAllEnvVariables(envFile)
		if err != nil {
			return configListMsg{err: err}
		}
		return configListMsg{pairs: pairs}
	}
}

func fetchComposeServicesCmd(envFile string, action ActionType) tea.Cmd {
	return func() tea.Msg {
		// Ensure docker-generated.yml exists before fetching services (silently, no logs)
		if err := internal.EnsureDockerGeneratedFileWithWriter(io.Discard, io.Discard, envFile); err != nil {
			return composeServicesMsg{err: err, action: action}
		}
		services, err := internal.GetComposeServices(envFile)
		if err != nil {
			return composeServicesMsg{err: err, action: action}
		}
		return composeServicesMsg{services: services, action: action}
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
			// No newline found, keep in buffer for next write
			w.buf.WriteString(data)
			break
		}

		line := strings.TrimSuffix(data[:idx], "\r")
		// Clean the line of control characters
		line = strings.Trim(line, "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")
		// Trim whitespace but preserve intentional spaces
		line = strings.TrimSpace(line)

		// Ignore empty lines
		if line == "" {
			data = data[idx+1:]
			continue
		}

		// Filter isolated single characters that are likely artifacts
		// These are usually control characters or terminal escape sequence remnants
		if len(line) == 1 {
			// Allow only valid special characters that might appear alone
			validSingleChars := map[string]bool{
				"[": true,
				"]": true,
				"(": true,
				")": true,
				"{": true,
				"}": true,
			}
			// Filter out isolated letters, numbers, and other single characters
			if !validSingleChars[line] {
				// Ignore isolated characters like "d", "C", "B", etc.
				data = data[idx+1:]
				continue
			}
		}

		// Filter out lines that are just single lowercase letters (common artifacts)
		if len(line) == 1 && line >= "a" && line <= "z" {
			data = data[idx+1:]
			continue
		}

		w.stream <- actionProgressMsg{Action: w.action, Line: line}
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

	line := w.buf.String()
	// Clean the line of control characters
	line = strings.Trim(line, "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")
	line = strings.TrimSpace(line)
	
	// Filter out isolated single characters
	if line != "" {
		if len(line) == 1 {
			validSingleChars := map[string]bool{
				"[": true,
				"]": true,
				"(": true,
				")": true,
				"{": true,
				"}": true,
			}
			if !validSingleChars[line] {
				// Ignore isolated characters
				w.buf.Reset()
				return
			}
		}
		// Filter out single lowercase letters
		if len(line) == 1 && line >= "a" && line <= "z" {
			w.buf.Reset()
			return
		}
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
