package ui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/fatih/color"

	"leyzenctl/internal"
)

type statusMsg struct {
	statuses []ContainerStatus
	err      error
}

type statusTickMsg struct{}

type actionProgressMsg struct {
	Action  ActionType
	Line    string
	LineRaw string // Raw line before cleaning/filtering
	Err     error
	Done    bool
}

type successTimeoutMsg struct{}

type configListMsg struct {
	pairs map[string]string
	err   error
}

type composeServicesMsg struct {
	services []string
	action   ActionType
	err      error
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
		return m, tea.Batch(fetchStatusesCmd(m.envFile), scheduleStatusRefresh())
	case tea.KeyMsg:
		// CTRL+C confirmed: quit
		if msg.String() == "ctrl+c" {
			if m.quitConfirm {
				return m, tea.Quit
			}
			m.quitConfirm = true
			return m, nil
		}
		if m.viewState == ViewWizard && len(m.wizardFields) > 0 {
			if m.quitConfirm {
				m.quitConfirm = false
			}
			return m.handleWizardKey(msg)
		}
		if m.quitConfirm && msg.String() != "ctrl+c" {
			m.quitConfirm = false
		}

		if m.viewState == ViewConfig {
			keyStr := msg.String()
			if keyStr == "up" || keyStr == "down" || keyStr == "pgup" || keyStr == "pgdn" {
				var cmd tea.Cmd
				m.viewport, cmd = m.viewport.Update(msg)
				return m, cmd
			}
		}
		if m.viewState == ViewContainerSelection {
			return m.handleContainerSelectionKey(msg)
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
			errMsg := fmt.Sprintf("[ERROR] failed to load config: %v", msg.err)
			m.appendLog(errMsg, errMsg)
			return m, nil
		}
		m.configPairs = msg.pairs
		if m.viewState == ViewDashboard && len(m.wizardFields) == 0 {
			m.initWizard(msg.pairs)
		}
		return m, nil
	case wizardSaveMsg:
		return m.handleWizardSave(msg)
	case composeServicesMsg:
		return m.handleComposeServices(msg)
	}

	if m.viewState == ViewLogs || m.viewState == ViewAction || m.viewState == ViewConfig {
		var cmd tea.Cmd
		m.viewport, cmd = m.viewport.Update(msg)
		if m.viewState == ViewLogs || m.viewState == ViewAction {
			_, isKeyMsg := msg.(tea.KeyMsg)
			if !isKeyMsg {
				if m.logModeRaw {
					m.viewportYOffsetRaw = m.viewport.YOffset
				} else {
					m.viewportYOffsetNormal = m.viewport.YOffset
				}
			}
		}
		return m, cmd
	}

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
	} else if (m.viewState == ViewLogs || m.viewState == ViewAction) && m.logModeRaw {
		viewportHeight = m.height
	} else {
		// For logs and action views in normal mode, calculate available space
		// header + footer + padding
		viewportHeight = m.height - 8
		if viewportHeight < 6 {
			viewportHeight = 6
		}
	}

	if viewportHeight > 0 {
		if (m.viewState == ViewLogs || m.viewState == ViewAction) && m.logModeRaw {
			m.viewport.Width = m.width
			m.viewport.Height = viewportHeight
		} else {
			m.viewport.Width = m.width - 6
			if m.viewport.Width < 20 {
				m.viewport.Width = 20
			}
			m.viewport.Height = viewportHeight
		}
	}

	if m.viewState == ViewContainerSelection {
		m.containerList.SetWidth(m.width - 6)
		if m.containerList.Width() < 20 {
			m.containerList.SetWidth(20)
		}
		m.containerList.SetHeight(m.height - 10)
		if m.containerList.Height() < 6 {
			m.containerList.SetHeight(6)
		}
	}

	return m, nil
}

func (m *Model) handleStatus(msg statusMsg) (tea.Model, tea.Cmd) {
	if msg.err != nil {
		errMsg := fmt.Sprintf("[ERROR] status refresh failed: %v", msg.err)
		m.appendLog(errMsg, errMsg)
		return m, nil
	}
	m.statuses = msg.statuses
	if m.pendingRefresh {
		m.pendingRefresh = false
	}
	return m, nil
}

func (m *Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.quitConfirm {
		m.quitConfirm = false
	}

	keyStr := msg.String()
	if len(keyStr) == 1 && ((keyStr >= "A" && keyStr <= "Z") || (keyStr >= "a" && keyStr <= "z")) {
		keyStr = strings.ToLower(keyStr)
	}

	switch keyStr {
	case "ctrl+c":
		if m.quitConfirm {
			// Confirmed, quit
			return m, tea.Quit
		}
		// First press: ask for confirmation
		m.quitConfirm = true
		return m, nil
	case "esc":
		if m.viewState == ViewLogs || m.viewState == ViewConfig || m.viewState == ViewWizard {
			m.switchToDashboard()
			return m, nil
		}
		if m.viewState == ViewAction && !m.actionRunning {
			m.switchToDashboard()
			return m, nil
		}
		return m, nil
	case "r":
		if m.viewState == ViewConfig {
			return m, fetchConfigListCmd(m.envFile)
		}
		if m.viewState == ViewDashboard {
			return m, fetchComposeServicesCmd(m.envFile, ActionRestart)
		}
		return m, nil
	case "?":
		if m.viewState == ViewDashboard {
			m.helpVisible = !m.helpVisible
		}
		return m, nil
	case "l":
		if m.viewState == ViewDashboard {
			m.switchToLogs()
			return m, nil
		}
		return m, nil
	case "c":
		if m.viewState == ViewDashboard {
			m.switchToConfig()
			return m, fetchConfigListCmd(m.envFile)
		}
		return m, nil
	case " ":
		if m.viewState == ViewConfig {
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
		if m.viewState == ViewDashboard {
			if len(m.configPairs) == 0 {
				return m, fetchConfigListCmd(m.envFile)
			}
			m.initWizard(m.configPairs)
			return m, nil
		}
		return m, nil
	case "s":
		if m.viewState == ViewDashboard {
			return m, fetchComposeServicesCmd(m.envFile, ActionStop)
		}
		return m, nil
	case "b":
		if m.viewState == ViewDashboard {
			return m, fetchComposeServicesCmd(m.envFile, ActionBuild)
		}
		return m, nil
	case "a":
		if m.viewState == ViewDashboard {
			return m, fetchComposeServicesCmd(m.envFile, ActionStart)
		}
		return m, nil
	case "v":
		if m.viewState == ViewLogs || m.viewState == ViewAction {
			if m.logModeRaw {
				m.viewportYOffsetRaw = m.viewport.YOffset
			} else {
				m.viewportYOffsetNormal = m.viewport.YOffset
			}

			m.logModeRaw = !m.logModeRaw

			var logsToDisplay []string
			if m.logModeRaw {
				logsToDisplay = m.logsRaw
				m.viewport.Width = m.width
				m.viewport.Height = m.height
			} else {
				logsToDisplay = m.logs
				viewportHeight := m.height - 8
				if viewportHeight < 6 {
					viewportHeight = 6
				}
				m.viewport.Height = viewportHeight
				m.viewport.Width = m.width - 6
				if m.viewport.Width < 20 {
					m.viewport.Width = 20
				}
			}

			m.viewport.SetContent(strings.Join(logsToDisplay, "\n"))

			if m.logModeRaw {
				if m.viewportYOffsetRaw > 0 {
					m.viewport.SetYOffset(m.viewportYOffsetRaw)
				} else {
					m.viewport.GotoBottom()
					m.viewportYOffsetRaw = m.viewport.YOffset
				}
			} else {
				if m.viewportYOffsetNormal > 0 {
					m.viewport.SetYOffset(m.viewportYOffsetNormal)
				} else {
					m.viewport.GotoBottom()
					m.viewportYOffsetNormal = m.viewport.YOffset
				}
			}
		}
		return m, nil
	case "up", "down", "pgup", "pgdn", "home", "end":
		// Navigation in viewport for logs/action/config views
		if m.viewState == ViewLogs || m.viewState == ViewAction || m.viewState == ViewConfig {
			var cmd tea.Cmd
			m.viewport, cmd = m.viewport.Update(msg)
			// Save scroll position after manual navigation in logs/action views
			if m.viewState == ViewLogs || m.viewState == ViewAction {
				if m.logModeRaw {
					m.viewportYOffsetRaw = m.viewport.YOffset
				} else {
					m.viewportYOffsetNormal = m.viewport.YOffset
				}
			}
			return m, cmd
		}
		return m, nil
	}
	return m, nil
}

func (m *Model) handleContainerSelectionKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	key := msg.String()

	switch key {
	case "esc":
		// Cancel and return to dashboard
		m.switchToDashboard()
		return m, nil
	case " ":
		// Toggle selection
		if len(m.containerItems) == 0 {
			return m, nil
		}
		idx := m.containerIndex
		if idx < 0 || idx >= len(m.containerItems) {
			return m, nil
		}

		item := &m.containerItems[idx]
		item.Selected = !item.Selected

		if item.IsAllOption && item.Selected {
			for i := range m.containerItems {
				if i != idx {
					m.containerItems[i].Selected = false
				}
			}
		} else if item.Selected {
			if len(m.containerItems) > 0 && m.containerItems[0].IsAllOption {
				m.containerItems[0].Selected = false
			}
		}
		return m, nil
	case "enter":
		// Confirm selection and execute action
		selectedServices := []string{}
		allSelected := false

		for _, item := range m.containerItems {
			if item.Selected {
				if item.IsAllOption {
					// "All" selected - use empty list to mean all services
					allSelected = true
					selectedServices = []string{}
					break
				} else {
					selectedServices = append(selectedServices, item.Name)
				}
			}
		}

		if len(selectedServices) == 0 && !allSelected {
			selectedServices = []string{}
		}

		// Save pending action before any state changes
		pendingAction := m.pendingAction

		// Clean up container selection view state without calling switchToDashboard
		// (which would reset pendingAction)
		m.containerItems = nil
		m.containerIndex = 0
		m.availableServices = nil

		// Execute action with selected services
		return m.startActionWithServices(pendingAction, selectedServices)
	case "up", "down":
		// Handle navigation manually
		if key == "up" {
			if m.containerIndex > 0 {
				m.containerIndex--
			} else {
				m.containerIndex = len(m.containerItems) - 1
			}
		} else {
			if m.containerIndex < len(m.containerItems)-1 {
				m.containerIndex++
			} else {
				m.containerIndex = 0
			}
		}
		return m, nil
	default:
		return m, nil
	}
}

func (m *Model) startAction(action ActionType) (tea.Model, tea.Cmd) {
	return m.startActionWithServices(action, []string{})
}

func (m *Model) startActionWithServices(action ActionType, services []string) (tea.Model, tea.Cmd) {
	if action == ActionNone {
		return m, nil
	}
	if m.actionRunning {
		warnMsg := color.HiYellowString("[WARN] another action is currently running; please wait...")
		m.appendLog(warnMsg, warnMsg)
		return m, nil
	}

	if m.viewState == ViewContainerSelection {
		m.viewState = ViewDashboard
		m.pendingAction = ActionNone
	}

	stream, err := m.runner.RunWithServices(action, services)
	if err != nil {
		errMsg := color.HiRedString(fmt.Sprintf("[ERROR] failed to start %s: %v", action, err))
		m.appendLog(errMsg, errMsg)
		return m, nil
	}

	m.actionStream = stream
	m.action = action
	m.actionRunning = true
	m.switchToAction()

	return m, tea.Batch(waitForActionProgress(stream), m.spinner.Tick)
}

func (m *Model) handleActionProgress(msg actionProgressMsg) (tea.Model, tea.Cmd) {
	if msg.Action != m.action {
		return m, nil
	}

	if msg.Line != "" {
		// Use raw line if available, otherwise use cleaned line
		lineRaw := msg.LineRaw
		if lineRaw == "" {
			lineRaw = msg.Line
		}
		m.appendLog(msg.Line, lineRaw)
	}

	if msg.Err != nil {
		actionName := string(msg.Action)
		errMsg := color.HiRedString(fmt.Sprintf("[ERROR] %s failed: %v", actionName, msg.Err))
		m.appendLog(errMsg, errMsg)
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		return m, fetchStatusesCmd(m.envFile)
	}

	if msg.Done {
		actionName := string(msg.Action)
		doneMsg := color.HiGreenString(fmt.Sprintf("%s completed", actionName))
		m.appendLog(doneMsg, doneMsg)
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		m.successMessage = fmt.Sprintf("%s completed successfully", actionName)

		cmd := tea.Sequence(
			fetchStatusesCmd(m.envFile),
			tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} }),
		)

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
		return m.saveWizard()
	case "esc":
		m.switchToDashboard()
		return m, nil
	case "right", "→":
		m.wizardFields[m.wizardIndex].Input.Blur()
		m.wizardIndex++
		if m.wizardIndex >= len(m.wizardFields) {
			m.wizardIndex = 0
		}
		if m.wizardIndex < len(m.wizardFields) {
			field := &m.wizardFields[m.wizardIndex]
			field.Input.Focus()
			field.Input.CursorEnd()
		}
		m.wizardError = ""
		return m, nil
	case "left", "←":
		m.wizardFields[m.wizardIndex].Input.Blur()
		m.wizardIndex--
		if m.wizardIndex < 0 {
			m.wizardIndex = len(m.wizardFields) - 1
		}
		if m.wizardIndex >= 0 {
			field := &m.wizardFields[m.wizardIndex]
			field.Input.Focus()
			field.Input.CursorEnd()
		}
		m.wizardError = ""
		return m, nil
	case "enter":
		m.wizardFields[m.wizardIndex].Input.Blur()
		m.wizardIndex++
		if m.wizardIndex >= len(m.wizardFields) {
			m.wizardIndex = 0
		}
		if m.wizardIndex < len(m.wizardFields) {
			field := &m.wizardFields[m.wizardIndex]
			field.Input.Focus()
			field.Input.CursorEnd()
		}
		m.wizardError = ""
		return m, nil
	default:
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

	if value == "" {
		return nil
	}

	_, err := internal.ValidateEnvValue(field.Key, value)
	if err != nil {
		return err
	}

	return nil
}

func (m *Model) saveWizard() (tea.Model, tea.Cmd) {
	hasErrors := false
	for i := range m.wizardFields {
		value := m.wizardFields[i].Input.Value()
		if err := m.validateWizardField(i, value); err != nil {
			m.wizardError = fmt.Sprintf("Error in %s: %v", m.wizardFields[i].Key, err)
			hasErrors = true
			break
		}
		m.wizardFields[i].Value = value
	}

	if hasErrors {
		return m, nil
	}

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
	envFileObj, err := internal.LoadEnvFile(envFile)
	if err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to load env file: %w", err)}
	}

	for _, field := range fields {
		value := field.Value
		sanitized := strings.TrimSpace(value)

		if sanitized != "" {
			validated, err := internal.ValidateEnvValue(field.Key, sanitized)
			if err != nil {
				return wizardSaveMsg{err: fmt.Errorf("%s: %w", field.Key, err)}
			}
			sanitized = validated
		}

		envFileObj.Set(field.Key, sanitized)
	}

	if err := envFileObj.Write(); err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to write env file: %w", err)}
	}

	var silentBuffer strings.Builder
	if err := internal.RunBuildScriptWithWriter(&silentBuffer, &silentBuffer, envFile); err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to rebuild: %w", err)}
	}

	return wizardSaveMsg{err: nil}
}

func (m *Model) handleWizardSave(msg wizardSaveMsg) (tea.Model, tea.Cmd) {
	m.actionRunning = false
	m.action = ActionNone

	m.switchToDashboard()

	if msg.err != nil {
		m.successMessage = fmt.Sprintf("[ERROR] Configuration save failed: %v", msg.err)
		cmd := tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} })
		return m, cmd
	}

	m.successMessage = "Configuration saved successfully"

	cmd := tea.Sequence(
		fetchConfigListCmd(m.envFile),
		fetchStatusesCmd(m.envFile),
		tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} }),
	)

	return m, cmd
}

func (m *Model) handleComposeServices(msg composeServicesMsg) (tea.Model, tea.Cmd) {
	if msg.err != nil {
		errMsg := fmt.Sprintf("[ERROR] failed to load services: %v", msg.err)
		m.appendLog(errMsg, errMsg)
		return m, nil
	}
	m.initContainerSelection(msg.services, msg.action)
	return m, nil
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
