package ui

import (
	"sort"
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type ContainerStatus struct {
	Name      string
	Status    string
	Age       string
	RawStatus string
}

type ActionType string

const (
	ActionNone      ActionType = ""
	ActionRestart   ActionType = "restart"
	ActionStart     ActionType = "start"
	ActionStop      ActionType = "stop"
	ActionBuild     ActionType = "build"
	ActionConfigList ActionType = "config-list"
	ActionWizard     ActionType = "wizard"
)

type ViewState string

const (
	ViewDashboard ViewState = "dashboard"
	ViewLogs      ViewState = "logs"
	ViewAction    ViewState = "action"
	ViewConfig    ViewState = "config"
	ViewWizard    ViewState = "wizard"
)

const (
	statusRefreshInterval = 5 * time.Second
	logBufferLimit        = 400
	successMessageDuration = 3 * time.Second
)

type Theme struct {
	Title         lipgloss.Style
	Subtitle      lipgloss.Style
	Pane          lipgloss.Style
	ActiveStatus  lipgloss.Style
	ErrorStatus   lipgloss.Style
	WarningStatus lipgloss.Style
	HelpKey       lipgloss.Style
	HelpDesc      lipgloss.Style
	Spinner       lipgloss.Style
	Accent        lipgloss.Style
	SuccessStatus lipgloss.Style
	Footer        lipgloss.Style
}

type WizardField struct {
	Key       string
	Message   string
	Value     string
	IsPassword bool
	Input     textinput.Model
}

	type Model struct {
	envFile         string
	statuses        []ContainerStatus
	logs            []string
	logsBuffer      []string // Buffer to preserve logs when returning to dashboard
	configPairs     map[string]string // To store configuration pairs
	configShowPasswords map[string]bool // To display/hide passwords in the config view
	viewport        viewport.Model
	spinner         spinner.Model
	width           int
	height          int
	helpVisible     bool
	action          ActionType
	actionRunning   bool
	actionStream    <-chan actionProgressMsg
	runner          *Runner
	theme           Theme
	ready           bool
	pendingRefresh  bool
	viewState       ViewState
	successMessage  string
	successTimer    *time.Timer
	wizardFields    []WizardField
	wizardIndex     int
	wizardError     string
	quitConfirm     bool // Confirmation de sortie
}

func NewModel(envFile string, runner *Runner) *Model {
	sp := spinner.New()
	sp.Spinner = spinner.Dot
	sp.Style = lipgloss.NewStyle().Foreground(lipgloss.Color("205"))

	vp := viewport.New(0, 0)
	vp.MouseWheelEnabled = true

	theme := Theme{
		Title:         lipgloss.NewStyle().Foreground(lipgloss.Color("81")).Bold(true),
		Subtitle:      lipgloss.NewStyle().Foreground(lipgloss.Color("244")),
		Pane:          lipgloss.NewStyle().Padding(1, 2).Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("238")),
		ActiveStatus:  lipgloss.NewStyle().Foreground(lipgloss.Color("42")).Bold(true),
		ErrorStatus:   lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Bold(true),
		WarningStatus: lipgloss.NewStyle().Foreground(lipgloss.Color("214")).Bold(true),
		HelpKey:       lipgloss.NewStyle().Foreground(lipgloss.Color("81")).Bold(true),
		HelpDesc:      lipgloss.NewStyle().Foreground(lipgloss.Color("250")),
		Spinner:       lipgloss.NewStyle().Foreground(lipgloss.Color("213")).Bold(true),
		Accent:        lipgloss.NewStyle().Foreground(lipgloss.Color("45")).Bold(true),
		SuccessStatus: lipgloss.NewStyle().Foreground(lipgloss.Color("42")).Bold(true).Background(lipgloss.Color("235")),
		Footer:        lipgloss.NewStyle().Foreground(lipgloss.Color("240")).MarginTop(1),
	}

	return &Model{
		envFile:            envFile,
		runner:             runner,
		spinner:            sp,
		viewport:           vp,
		theme:              theme,
		viewState:          ViewDashboard,
		configPairs:        make(map[string]string),
		configShowPasswords: make(map[string]bool),
	}
}

func (m *Model) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, fetchStatusesCmd(), scheduleStatusRefresh())
}

func scheduleStatusRefresh() tea.Cmd {
	return tea.Tick(statusRefreshInterval, func(time.Time) tea.Msg {
		return statusTickMsg{}
	})
}

func (m *Model) appendLog(line string) {
	if line == "" {
		return
	}
	
	// DO NOT add logs if we're on the dashboard (they should not be displayed)
	if m.viewState == ViewDashboard {
		return
	}
	
	// Clean the line: remove control characters and leading/trailing spaces
	line = strings.TrimSpace(line)
	// Filter empty lines after cleaning
	if line == "" {
		return
	}
	// Filter lines with only an isolated character (formatting artifacts)
	// Unless it's a valid special character
	if len(line) == 1 {
		// Allow only certain valid special characters
		validSingleChars := map[string]bool{
			"[": true,
			"]": true,
			"(": true,
			")": true,
		}
		if !validSingleChars[line] {
			// Ignore isolated characters like "C", "B", etc.
			return
		}
	}
	
	// Filter lines that start with an isolated character followed by a newline
	// (e.g., "C\n" or "B\n")
	if len(line) > 1 && (line[0] == 'C' || line[0] == 'B') && line[1] == '\n' {
		return
	}
	
	m.logs = append(m.logs, line)
	if len(m.logs) > logBufferLimit {
		diff := len(m.logs) - logBufferLimit
		m.logs = m.logs[diff:]
	}
	// Only update viewport if we're in a view that displays logs
	if m.viewState == ViewLogs || m.viewState == ViewAction {
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	}
}

func (m *Model) switchToDashboard() {
	// Save current logs in buffer if coming from a view with logs
	if m.viewState == ViewLogs || m.viewState == ViewAction {
		m.logsBuffer = make([]string, len(m.logs))
		copy(m.logsBuffer, m.logs)
	}
	
	// If coming from wizard, completely clean up state
	if m.viewState == ViewWizard {
		// Reset wizard fields to avoid display remnants
		m.wizardFields = nil
		m.wizardIndex = 0
		m.wizardError = ""
	}
	
	// COMPLETELY CLEAN: logs, viewport, action, quit confirmation
	// Logs should not be displayed on the dashboard
	m.logs = nil
	m.viewport.SetContent("")
	m.viewport.GotoTop()
	m.actionRunning = false
	m.action = ActionNone
	m.actionStream = nil
	m.quitConfirm = false
	
	// Change state AFTER cleanup
	m.viewState = ViewDashboard
}

func (m *Model) switchToLogs() {
	// Restore logs from buffer if necessary
	if len(m.logsBuffer) > 0 {
		m.logs = make([]string, len(m.logsBuffer))
		copy(m.logs, m.logsBuffer)
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	} else if len(m.logs) > 0 {
		// If no buffer but we have logs, display them
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	}
	m.viewState = ViewLogs
	// Recalculate viewport size for this view
	if m.ready && m.height > 0 {
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
}

func (m *Model) switchToAction() {
	m.viewState = ViewAction
	// Recalculate viewport size for this view
	if m.ready && m.height > 0 {
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
}

func (m *Model) switchToConfig() {
	m.viewState = ViewConfig
	// Initialize config viewport size if window is already sized
	if m.ready && m.height > 0 {
		viewportHeight := m.height - 10
		if viewportHeight < 6 {
			viewportHeight = 6
		}
		m.viewport.Width = m.width - 6
		if m.viewport.Width < 20 {
			m.viewport.Width = 20
		}
		m.viewport.Height = viewportHeight
		// Reset scroll to top
		m.viewport.SetYOffset(0)
	}
}

func (m *Model) initWizard(existing map[string]string) {
	// Load ALL variables from .env
	// If existing is empty, wizard will display a message
	// Automatically detect passwords (containing "password" or "secret")
	keys := make([]string, 0, len(existing))
	for k := range existing {
		keys = append(keys, k)
	}
	
	// Sort keys for consistent display
	sort.Strings(keys)
	
	m.wizardFields = make([]WizardField, len(keys))
	for i, key := range keys {
		existingValue := existing[key]
		isPassword := strings.Contains(strings.ToLower(key), "password") || 
		             strings.Contains(strings.ToLower(key), "secret") ||
		             strings.Contains(strings.ToLower(key), "token") ||
		             strings.Contains(strings.ToLower(key), "key")
		
		ti := textinput.New()
		ti.Placeholder = fmt.Sprintf("Value for %s", key)
		ti.CharLimit = 512 // Increase the limit
		ti.Width = 60
		if isPassword {
			ti.EchoMode = textinput.EchoPassword
			ti.EchoCharacter = '•'
		}
		// Pre-fill with existing value
		if existingValue != "" {
			ti.SetValue(existingValue)
		}
		
		m.wizardFields[i] = WizardField{
			Key:        key,
			Message:    key,
			Value:      existingValue,
			IsPassword: isPassword,
			Input:      ti,
		}
	}
	
	// Focus on first field and blur others
	m.wizardIndex = 0
	if len(m.wizardFields) > 0 {
		for i := range m.wizardFields {
			if i == 0 {
				m.wizardFields[i].Input.Focus()
				m.wizardFields[i].Input.CursorEnd()
			} else {
				m.wizardFields[i].Input.Blur()
			}
		}
	}
	m.wizardError = ""
	m.viewState = ViewWizard
}

func (m *Model) switchToWizard() {
	m.viewState = ViewWizard
}
