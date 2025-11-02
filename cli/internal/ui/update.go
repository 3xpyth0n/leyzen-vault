package ui

import (
	"fmt"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
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
		return m.handleKey(msg)
	case actionProgressMsg:
		return m.handleActionProgress(msg)
	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	}

	var cmd tea.Cmd
	m.viewport, cmd = m.viewport.Update(msg)
	return m, cmd
}

func (m *Model) handleWindowSize(msg tea.WindowSizeMsg) (tea.Model, tea.Cmd) {
	m.width = msg.Width
	m.height = msg.Height
	m.ready = true

	viewportHeight := m.height - 11 // header + status panes + padding
	if viewportHeight < 6 {
		viewportHeight = 6
	}
	m.viewport.Width = m.width - 6
	if m.viewport.Width < 20 {
		m.viewport.Width = 20
	}
	m.viewport.Height = viewportHeight
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
	switch msg.String() {
	case "ctrl+c", "q":
		return m, tea.Quit
	case "?":
		m.helpVisible = !m.helpVisible
		return m, nil
	case "r":
		return m.startAction(ActionRestart)
	case "s":
		return m.startAction(ActionStop)
	case "b":
		return m.startAction(ActionBuild)
	case "a":
		return m.startAction(ActionStart)
	case "up", "down", "pgup", "pgdn", "home", "end":
		var cmd tea.Cmd
		m.viewport, cmd = m.viewport.Update(msg)
		return m, cmd
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
		m.appendLog(fmt.Sprintf("❌ %s failed: %v", msg.Action, msg.Err))
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil
		return m, nil
	}

	if msg.Done {
		m.appendLog(fmt.Sprintf("✅ %s completed", msg.Action))
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		if m.pendingRefresh {
			m.pendingRefresh = false
			return m, fetchStatusesCmd()
		}
		return m, fetchStatusesCmd()
	}

	return m, waitForActionProgress(m.actionStream)
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
