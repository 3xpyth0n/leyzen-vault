package ui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"

	"leyzenctl/internal"
)

type statusMsg struct {
	statuses []ContainerStatus
	err      error
}

type statusTickMsg struct{}

type actionProgressMsg struct {
	Action ActionType
	Line   string
	Err    error
	Done   bool
}

type successTimeoutMsg struct{}

type configListMsg struct {
	pairs map[string]string
	err   error
}

func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		return m.handleWindowSize(msg)
	case statusMsg:
		return m.handleStatus(msg)
	case statusTickMsg:
		if m.actionRunning {
			// Delay refresh until the action completes.
			m.pendingRefresh = true
			return m, scheduleStatusRefresh()
		}
		return m, tea.Batch(fetchStatusesCmd(), scheduleStatusRefresh())
	case tea.KeyMsg:
		// Handle CTRL+C with confirmation
		if msg.String() == "ctrl+c" {
			if m.quitConfirm {
				// Confirmed, quit
				return m, tea.Quit
			}
			// First press: ask for confirmation
			m.quitConfirm = true
			return m, nil
		}
		// 'q' is now used in the wizard for editing, don't quit with it
		// If we're in the wizard, don't go through handleKey which intercepts keys
		if m.viewState == ViewWizard && len(m.wizardFields) > 0 {
			// Cancel confirmation if user presses any key
			if m.quitConfirm {
				m.quitConfirm = false
			}
			return m.handleWizardKey(msg)
		}
		// Cancel confirmation if user presses any key (except CTRL+C)
		if m.quitConfirm && msg.String() != "ctrl+c" {
			m.quitConfirm = false
		}

		// If we're in the config view, let the viewport handle scroll keys
		if m.viewState == ViewConfig {
			keyStr := msg.String()
			if keyStr == "up" || keyStr == "down" || keyStr == "pgup" || keyStr == "pgdn" {
				var cmd tea.Cmd
				m.viewport, cmd = m.viewport.Update(msg)
				return m, cmd
			}
		}
		return m.handleKey(msg)
	case actionProgressMsg:
		return m.handleActionProgress(msg)
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	case successTimeoutMsg:
		m.successMessage = ""
		if m.successTimer != nil {
			m.successTimer = nil
		}
		return m, nil
	case configListMsg:
		if msg.err != nil {
			m.appendLog(fmt.Sprintf("❌ failed to load config: %v", msg.err))
			return m, nil
		}
		m.configPairs = msg.pairs
		// If we're coming from the dashboard and don't have a wizard yet, we might be launching it
		// Initialize the wizard if we don't have one yet
		if m.viewState == ViewDashboard && len(m.wizardFields) == 0 {
			m.initWizard(msg.pairs)
		}
		return m, nil
	case wizardSaveMsg:
		return m.handleWizardSave(msg)
	}

	// Handle viewport only if we're in a view that uses it
	if m.viewState == ViewLogs || m.viewState == ViewAction || m.viewState == ViewConfig {
		var cmd tea.Cmd
		m.viewport, cmd = m.viewport.Update(msg)
		return m, cmd
	}

	// Handle non-keyboard messages from the wizard (already handled for KeyMsg above)
	if m.viewState == ViewWizard && len(m.wizardFields) > 0 {
		if m.wizardIndex < len(m.wizardFields) {
			var cmd tea.Cmd
			m.wizardFields[m.wizardIndex].Input, cmd = m.wizardFields[m.wizardIndex].Input.Update(msg)
			return m, cmd
		}
	}

	return m, nil
}

func (m *Model) handleWindowSize(msg tea.WindowSizeMsg) (tea.Model, tea.Cmd) {
	m.width = msg.Width
	m.height = msg.Height
	m.ready = true

	// Calculate viewport height according to the active view
	var viewportHeight int
	if m.viewState == ViewDashboard {
		// No visible viewport on the dashboard
		viewportHeight = 0
	} else if m.viewState == ViewConfig {
		// For the config view, calculate available space
		// header + footer + pane padding
		viewportHeight = m.height - 10
		if viewportHeight < 6 {
			viewportHeight = 6
		}
	} else {
		// For logs and action views, calculate available space
		// header + footer + padding
		viewportHeight = m.height - 8
		if viewportHeight < 6 {
			viewportHeight = 6
		}
	}

	if viewportHeight > 0 {
		m.viewport.Width = m.width - 6
		if m.viewport.Width < 20 {
			m.viewport.Width = 20
		}
		m.viewport.Height = viewportHeight
	}

	return m, nil
}

func (m *Model) handleStatus(msg statusMsg) (tea.Model, tea.Cmd) {
	if msg.err != nil {
		m.appendLog(fmt.Sprintf("❌ status refresh failed: %v", msg.err))
		return m, nil
	}
	m.statuses = msg.statuses
	if m.pendingRefresh {
		m.pendingRefresh = false
	}
	return m, nil
}

func (m *Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Cancel confirmation if user presses any key (except CTRL+C which is handled in Update)
	if m.quitConfirm {
		m.quitConfirm = false
	}

	switch msg.String() {
	case "ctrl+c":
		if m.quitConfirm {
			// Confirmed, quit
			return m, tea.Quit
		}
		// First press: ask for confirmation
		m.quitConfirm = true
		return m, nil
	case "esc":
		// Return to dashboard from any view
		if m.viewState == ViewLogs || m.viewState == ViewConfig || m.viewState == ViewWizard {
			m.switchToDashboard()
			return m, nil
		}
		// If an action is in progress, we still allow returning to the dashboard
		// but we continue to display logs in the background
		if m.viewState == ViewAction && !m.actionRunning {
			m.switchToDashboard()
			return m, nil
		}
		return m, nil
	case "r":
		// Refresh config if we're in the config view
		if m.viewState == ViewConfig {
			return m, fetchConfigListCmd(m.envFile)
		}
		// Otherwise, restart from the dashboard
		if m.viewState == ViewDashboard {
			return m.startAction(ActionRestart)
		}
		return m, nil
	case "?":
		if m.viewState == ViewDashboard {
			m.helpVisible = !m.helpVisible
		}
		return m, nil
	case "l":
		// Switch to logs view from the dashboard
		if m.viewState == ViewDashboard {
			m.switchToLogs()
			return m, nil
		}
		return m, nil
	case "c":
		// Display configuration from the dashboard
		if m.viewState == ViewDashboard {
			m.switchToConfig()
			return m, fetchConfigListCmd(m.envFile)
		}
		return m, nil
	case " ":
		// Space to toggle password display in the config view
		if m.viewState == ViewConfig {
			// Toggle ALL passwords, secrets, tokens
			// Use the same detection logic as in buildConfigContent
			for key := range m.configPairs {
				keyLower := strings.ToLower(key)
				if strings.Contains(keyLower, "password") ||
					strings.Contains(keyLower, "secret") ||
					strings.Contains(keyLower, "pass") ||
					strings.Contains(keyLower, "token") {
					m.configShowPasswords[key] = !m.configShowPasswords[key]
				}
			}
			return m, nil
		}
		return m, nil
	case "w":
		// Launch wizard from the dashboard
		if m.viewState == ViewDashboard {
			// Load existing config to pre-fill fields
			// Use already loaded values or load if necessary
			if len(m.configPairs) == 0 {
				// Load config then initialize wizard
				return m, fetchConfigListCmd(m.envFile)
			}
			// If we already have values, initialize directly
			// But if there's really nothing in .env, we should still allow adding variables
			m.initWizard(m.configPairs)
			return m, nil
		}
		return m, nil
	case "s":
		if m.viewState == ViewDashboard {
			return m.startAction(ActionStop)
		}
		return m, nil
	case "b":
		if m.viewState == ViewDashboard {
			return m.startAction(ActionBuild)
		}
		return m, nil
	case "a":
		if m.viewState == ViewDashboard {
			return m.startAction(ActionStart)
		}
		return m, nil
	case "up", "down", "pgup", "pgdn", "home", "end":
		// Navigation in viewport for logs/action/config views
		if m.viewState == ViewLogs || m.viewState == ViewAction || m.viewState == ViewConfig {
			var cmd tea.Cmd
			m.viewport, cmd = m.viewport.Update(msg)
			return m, cmd
		}
		return m, nil
	}
	return m, nil
}

func (m *Model) startAction(action ActionType) (tea.Model, tea.Cmd) {
	if action == ActionNone {
		return m, nil
	}
	if m.actionRunning {
		m.appendLog("⚠️ another action is currently running; please wait...")
		return m, nil
	}

	stream, err := m.runner.Run(action)
	if err != nil {
		m.appendLog(fmt.Sprintf("❌ failed to start %s: %v", action, err))
		return m, nil
	}

	m.actionStream = stream
	m.action = action
	m.actionRunning = true
	m.switchToAction()
	m.appendLog(fmt.Sprintf("🚀 starting %s...", action))

	return m, tea.Batch(waitForActionProgress(stream), m.spinner.Tick)
}

func (m *Model) handleActionProgress(msg actionProgressMsg) (tea.Model, tea.Cmd) {
	if msg.Action != m.action {
		// Ignore outdated messages from previous action.
		return m, nil
	}

	if msg.Line != "" {
		m.appendLog(msg.Line)
	}

	if msg.Err != nil {
		actionName := string(msg.Action)
		m.appendLog(fmt.Sprintf("❌ %s failed: %v", actionName, msg.Err))
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		// Return to dashboard after error
		m.switchToDashboard()

		// No success message for errors
		return m, fetchStatusesCmd()
	}

	if msg.Done {
		actionName := string(msg.Action)
		m.appendLog(fmt.Sprintf("✅ %s completed", actionName))
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		// Display success message and return to dashboard after a delay
		m.successMessage = fmt.Sprintf("%s completed successfully", actionName)

		// Schedule return to dashboard and success message removal
		cmd := tea.Sequence(
			fetchStatusesCmd(),
			tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} }),
		)

		// Automatic return to dashboard after success
		m.switchToDashboard()

		if m.pendingRefresh {
			m.pendingRefresh = false
		}
		return m, cmd
	}

	return m, waitForActionProgress(m.actionStream)
}

func (m *Model) handleWizardKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	key := msg.String()

	switch key {
	case "ctrl+s", "ctrl+S":
		// Save all modifications
		return m.saveWizard()
	case "esc":
		// Cancel and return to dashboard
		m.switchToDashboard()
		return m, nil
	case "right", "→":
		// Move to next field (Next)
		if m.wizardIndex < len(m.wizardFields)-1 {
			m.wizardFields[m.wizardIndex].Input.Blur()
			m.wizardIndex++
			if m.wizardIndex < len(m.wizardFields) {
				m.wizardFields[m.wizardIndex].Input.Focus()
				m.wizardFields[m.wizardIndex].Input.CursorEnd()
			}
			m.wizardError = ""
		}
		return m, nil
	case "left", "←":
		// Move to previous field (Previous)
		if m.wizardIndex > 0 {
			m.wizardFields[m.wizardIndex].Input.Blur()
			m.wizardIndex--
			if m.wizardIndex >= 0 {
				m.wizardFields[m.wizardIndex].Input.Focus()
				m.wizardFields[m.wizardIndex].Input.CursorEnd()
			}
			m.wizardError = ""
		}
		return m, nil
	case "enter":
		// Enter: move to next field (like "Next")
		if m.wizardIndex < len(m.wizardFields)-1 {
			m.wizardFields[m.wizardIndex].Input.Blur()
			m.wizardIndex++
			if m.wizardIndex < len(m.wizardFields) {
				m.wizardFields[m.wizardIndex].Input.Focus()
				m.wizardFields[m.wizardIndex].Input.CursorEnd()
			}
			m.wizardError = ""
		}
		return m, nil
	default:
		// All other keys (letters, numbers, etc.): pass to active input
		if m.wizardIndex < len(m.wizardFields) {
			var cmd tea.Cmd
			m.wizardFields[m.wizardIndex].Input, cmd = m.wizardFields[m.wizardIndex].Input.Update(msg)
			return m, cmd
		}
	}
	return m, nil
}

func (m *Model) validateWizardField(index int, value string) error {
	if index >= len(m.wizardFields) {
		return fmt.Errorf("invalid field index")
	}
	field := m.wizardFields[index]

	// All fields are optional - optional validation only
	// If the value is empty, that's OK
	if value == "" {
		return nil
	}

	// If we have a value, validate (but not required)
	_, err := internal.ValidateEnvValue(field.Key, value)
	if err != nil {
		// If validation fails, return the error
		// But only if we have a value (not if empty)
		return err
	}

	return nil
}

func (m *Model) saveWizard() (tea.Model, tea.Cmd) {
	// Validate all values before saving (optional - just warn)
	hasErrors := false
	for i := range m.wizardFields {
		value := m.wizardFields[i].Input.Value()
		if err := m.validateWizardField(i, value); err != nil {
			m.wizardError = fmt.Sprintf("Error in %s: %v", m.wizardFields[i].Key, err)
			hasErrors = true
			break
		}
		// Save the value in the field
		m.wizardFields[i].Value = value
	}

	if hasErrors {
		// Don't save if error
		return m, nil
	}

	// No error - save
	m.wizardError = ""
	m.switchToAction()
	m.action = ActionWizard
	m.actionRunning = true

	return m, tea.Batch(
		saveWizardCmd(m.envFile, m.wizardFields),
		m.spinner.Tick,
	)
}

type wizardSaveMsg struct {
	err error
}

func saveWizardCmd(envFile string, fields []WizardField) tea.Cmd {
	return func() tea.Msg {
		return saveWizard(envFile, fields)
	}
}

func saveWizard(envFile string, fields []WizardField) tea.Msg {
	// Load the env file
	envFileObj, err := internal.LoadEnvFile(envFile)
	if err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to load env file: %w", err)}
	}

	// Save each field (empty values allowed)
	for _, field := range fields {
		value := field.Value // Use the value saved in the field

		// All values are optional
		// If the value is empty, we still save it (can be removed)
		sanitized := strings.TrimSpace(value)

		// If validation fails but value is not empty, return error
		if sanitized != "" {
			validated, err := internal.ValidateEnvValue(field.Key, sanitized)
			if err != nil {
				return wizardSaveMsg{err: fmt.Errorf("%s: %w", field.Key, err)}
			}
			sanitized = validated
		}

		// Save (even if empty)
		envFileObj.Set(field.Key, sanitized)
	}

	// Save
	if err := envFileObj.Write(); err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to write env file: %w", err)}
	}

	// Rebuild - write to a silent buffer to avoid polluting the TUI
	// Rebuild logs should not be displayed on the dashboard
	var silentBuffer strings.Builder
	if err := internal.RunBuildScriptWithWriter(&silentBuffer, &silentBuffer, envFile); err != nil {
		// Return the error but don't display logs
		return wizardSaveMsg{err: fmt.Errorf("failed to rebuild: %w", err)}
	}

	return wizardSaveMsg{err: nil}
}

func (m *Model) handleWizardSave(msg wizardSaveMsg) (tea.Model, tea.Cmd) {
	m.actionRunning = false
	m.action = ActionNone

	// First, return to dashboard to clean up state
	m.switchToDashboard()

	if msg.err != nil {
		// For errors, we can add a message but only if we're not on the dashboard
		// Here, we're already on the dashboard, so we don't do anything with logs
		m.successMessage = fmt.Sprintf("❌ Configuration save failed: %v", msg.err)
		// Schedule error message removal
		cmd := tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} })
		return m, cmd
	}

	// Success
	m.successMessage = "Configuration saved successfully"

	// Refresh config
	cmd := tea.Sequence(
		fetchConfigListCmd(m.envFile),
		fetchStatusesCmd(),
		tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} }),
	)

	return m, cmd
}

func waitForActionProgress(stream <-chan actionProgressMsg) tea.Cmd {
	return func() tea.Msg {
		msg, ok := <-stream
		if !ok {
			return actionProgressMsg{Done: true}
		}
		return msg
	}
}

// Additional update helpers are defined in runner.go and view.go.
