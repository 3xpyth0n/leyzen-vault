package ui

import (
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/spinner"
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
	ActionNone    ActionType = ""
	ActionRestart ActionType = "restart"
	ActionStart   ActionType = "start"
	ActionStop    ActionType = "stop"
	ActionBuild   ActionType = "build"
)

const (
	statusRefreshInterval = 5 * time.Second
	logBufferLimit        = 400
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
}

type Model struct {
	envFile        string
	statuses       []ContainerStatus
	logs           []string
	viewport       viewport.Model
	spinner        spinner.Model
	width          int
	height         int
	helpVisible    bool
	action         ActionType
	actionRunning  bool
	actionStream   <-chan actionProgressMsg
	runner         *Runner
	theme          Theme
	ready          bool
	pendingRefresh bool
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
	}

	return &Model{
		envFile:  envFile,
		runner:   runner,
		spinner:  sp,
		viewport: vp,
		theme:    theme,
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
	m.logs = append(m.logs, line)
	if len(m.logs) > logBufferLimit {
		diff := len(m.logs) - logBufferLimit
		m.logs = m.logs[diff:]
	}
	m.viewport.SetContent(strings.Join(m.logs, "\n"))
	m.viewport.GotoBottom()
}
