package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

func (m *Model) View() string {
	if !m.ready {
		return m.theme.Title.Render(" Loading Leyzenctl dashboard...")
	}

	header := m.renderHeader()
	status := m.renderStatusPanel()
	logs := m.renderLogPanel()
	help := ""
	if m.helpVisible {
		help = m.renderHelp()
	} else {
		help = m.renderHints()
	}

	layout := lipgloss.JoinVertical(lipgloss.Left, header, status, logs, help)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderHeader() string {
	spinner := ""
	if m.actionRunning {
		spinner = fmt.Sprintf(" %s %s", m.theme.Spinner.Render(m.spinner.View()), m.theme.Accent.Render(strings.ToUpper(string(m.action))))
	}

	subtitle := m.theme.Subtitle.Render(fmt.Sprintf("env: %s", m.envFile))
	title := lipgloss.JoinHorizontal(lipgloss.Left,
		m.theme.Title.Render("Leyzen Vault Control"),
		spinner,
	)

	return lipgloss.JoinVertical(lipgloss.Left, title, subtitle)
}

func (m *Model) renderStatusPanel() string {
	if len(m.statuses) == 0 {
		return m.theme.Pane.Render("No containers running yet. Trigger a start to launch the stack.")
	}

	var rows []string
	header := fmt.Sprintf("%-28s  %-36s  %s", "NAME", "STATUS", "AGE")
	rows = append(rows, m.theme.Accent.Render(header))
	rows = append(rows, strings.Repeat("─", len(header)))

	for _, st := range m.statuses {
		rows = append(rows, fmt.Sprintf("%-28s  %-36s  %s", st.Name, m.formatStatus(st), st.Age))
	}

	return m.theme.Pane.Render(strings.Join(rows, "\n"))
}

func (m *Model) formatStatus(status ContainerStatus) string {
	lower := strings.ToLower(status.RawStatus)
	switch {
	case strings.Contains(lower, "up"):
		return m.theme.ActiveStatus.Render(status.Status)
	case strings.Contains(lower, "exit"), strings.Contains(lower, "dead"), strings.Contains(lower, "unhealthy"):
		return m.theme.ErrorStatus.Render(status.Status)
	default:
		return m.theme.WarningStatus.Render(status.Status)
	}
}

func (m *Model) renderLogPanel() string {
	content := m.viewport.View()
	if strings.TrimSpace(content) == "" {
		content = "No activity yet. Use r to restart or s to stop the stack."
	}
	return m.theme.Pane.Render(content)
}

func (m *Model) renderHints() string {
	hints := []string{
		fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
		fmt.Sprintf("%s Restart", m.theme.HelpKey.Render("r")),
		fmt.Sprintf("%s Start", m.theme.HelpKey.Render("a")),
		fmt.Sprintf("%s Stop", m.theme.HelpKey.Render("s")),
		fmt.Sprintf("%s Rebuild", m.theme.HelpKey.Render("b")),
		fmt.Sprintf("%s Toggle help", m.theme.HelpKey.Render("?")),
	}
	return lipgloss.NewStyle().MarginTop(1).Render(strings.Join(hints, "  ·  "))
}

func (m *Model) renderHelp() string {
	rows := []string{
		fmt.Sprintf("%s Quit the dashboard", m.theme.HelpKey.Render("q")),
		fmt.Sprintf("%s Start the stack (docker compose up)", m.theme.HelpKey.Render("a")),
		fmt.Sprintf("%s Restart the stack", m.theme.HelpKey.Render("r")),
		fmt.Sprintf("%s Stop the stack", m.theme.HelpKey.Render("s")),
		fmt.Sprintf("%s Rebuild configuration", m.theme.HelpKey.Render("b")),
		fmt.Sprintf("%s Toggle this help overlay", m.theme.HelpKey.Render("?")),
		fmt.Sprintf("%s Scroll logs", m.theme.HelpKey.Render("↑/↓")),
	}
	content := lipgloss.JoinVertical(lipgloss.Left, rows...)
	return lipgloss.NewStyle().MarginTop(1).Render(m.theme.Pane.Render(content))
}
