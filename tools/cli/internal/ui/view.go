package ui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

func (m *Model) View() string {
	if !m.ready {
		return m.theme.Title.Render(" Loading Leyzenctl dashboard...\n") +
			m.theme.Subtitle.Render(" Loading configuration...\n") +
			m.theme.Subtitle.Render(" Connecting to Docker...")
	}

	switch m.viewState {
	case ViewDashboard:
		return m.renderDashboard()
	case ViewLogs:
		return m.renderLogsView()
	case ViewAction:
		return m.renderActionView()
	case ViewConfig:
		return m.renderConfigView()
	case ViewWizard:
		return m.renderWizardView()
	default:
		return m.renderDashboard()
	}
}

func (m *Model) renderDashboard() string {
	// Ensure we're really on the dashboard and clean up if necessary
	if m.viewState != ViewDashboard {
		// Protection: if we call renderDashboard but we're not on the dashboard,
		// we shouldn't get here, but force cleanup anyway
		m.viewState = ViewDashboard
	}

	header := m.renderHeader()
	status := m.renderStatusPanel()

	// Temporary success message
	successMsg := ""
	if m.successMessage != "" {
		successMsg = m.renderSuccessMessage()
	}

	// Quit confirmation message
	quitMsg := ""
	if m.quitConfirm {
		quitMsg = m.renderQuitConfirmation()
	}

	help := ""
	if m.helpVisible {
		help = m.renderHelp()
	} else {
		help = m.renderHints()
	}

	// ALWAYS use "dashboard" as context for the footer
	// Explicitly force dashboard context to avoid wizard hints
	footer := m.renderFooter("dashboard")

	var parts []string
	parts = append(parts, header)
	if successMsg != "" {
		parts = append(parts, successMsg)
	}
	if quitMsg != "" {
		parts = append(parts, quitMsg)
	}
	parts = append(parts, status)
	parts = append(parts, help)
	parts = append(parts, footer)

	layout := lipgloss.JoinVertical(lipgloss.Left, parts...)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderLogsView() string {
	header := m.renderHeader()
	logs := m.renderLogPanel()

	quitMsg := ""
	if m.quitConfirm {
		quitMsg = m.renderQuitConfirmation()
	}

	footer := m.renderFooter("logs")

	var parts []string
	parts = append(parts, header)
	if quitMsg != "" {
		parts = append(parts, quitMsg)
	}
	parts = append(parts, logs)
	parts = append(parts, footer)

	layout := lipgloss.JoinVertical(lipgloss.Left, parts...)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderActionView() string {
	header := m.renderHeader()
	logs := m.renderLogPanel()

	quitMsg := ""
	if m.quitConfirm {
		quitMsg = m.renderQuitConfirmation()
	}

	footer := m.renderFooter("action")

	var parts []string
	parts = append(parts, header)
	if quitMsg != "" {
		parts = append(parts, quitMsg)
	}
	parts = append(parts, logs)
	parts = append(parts, footer)

	layout := lipgloss.JoinVertical(lipgloss.Left, parts...)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderConfigView() string {
	header := m.renderHeader()

	// Ensure the viewport is sized
	if m.viewport.Height == 0 && m.height > 0 {
		viewportHeight := m.height - 10
		if viewportHeight < 6 {
			viewportHeight = 6
		}
		m.viewport.Width = m.width - 6
		if m.viewport.Width < 20 {
			m.viewport.Width = 20
		}
		m.viewport.Height = viewportHeight
	}

	// Build the complete config content
	configContent := m.buildConfigContent()

	// Preserve current Y offset before updating content
	currentYOffset := m.viewport.YOffset

	// Update the viewport with the content
	m.viewport.SetContent(configContent)

	// Restore Y offset to preserve scroll position
	m.viewport.SetYOffset(currentYOffset)

	// Ensure the viewport is synchronized
	m.viewport.Width = m.width - 6
	if m.viewport.Width < 20 {
		m.viewport.Width = 20
	}

	// Render the viewport in the pane
	config := m.theme.Pane.Render(m.viewport.View())

	quitMsg := ""
	if m.quitConfirm {
		quitMsg = m.renderQuitConfirmation()
	}

	footer := m.renderFooter("config")

	var parts []string
	parts = append(parts, header)
	if quitMsg != "" {
		parts = append(parts, quitMsg)
	}
	parts = append(parts, config)
	parts = append(parts, footer)

	layout := lipgloss.JoinVertical(lipgloss.Left, parts...)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) buildConfigContent() string {
	if len(m.configPairs) == 0 {
		return "No configuration variables set yet. Use 'w' to run the wizard."
	}

	var rows []string
	
	// Show password toggle hint at the top
	hasPasswords := false
	for key := range m.configPairs {
		keyLower := strings.ToLower(key)
		if strings.Contains(keyLower, "password") ||
			strings.Contains(keyLower, "secret") ||
			strings.Contains(keyLower, "pass") ||
			strings.Contains(keyLower, "token") {
			hasPasswords = true
			break
		}
	}
	if hasPasswords {
		rows = append(rows, m.theme.Subtitle.Render("💡 Press SPACE to toggle password visibility"))
		rows = append(rows, "")
	}
	
	header := fmt.Sprintf("%-32s  %s", "KEY", "VALUE")
	rows = append(rows, m.theme.Accent.Render(header))
	rows = append(rows, strings.Repeat("─", 80))

	// Organize variables by category
	categorized := m.categorizeConfigPairs(m.configPairs)

	// Category order
	categoryOrder := []string{
		"Vault",
		"Docker Proxy",
		"Filebrowser",
		"Paperless",
		"CSP",
		"Proxy",
		"General",
	}

	// Display each category
	for _, category := range categoryOrder {
		if vars, ok := categorized[category]; ok && len(vars) > 0 {
			// Category title
			if len(rows) > 2 { // If there's already content, add a space
				rows = append(rows, "")
			}
			rows = append(rows, m.theme.Subtitle.Render(fmt.Sprintf("── %s ──", category)))

			// Variables in this category
			for _, key := range vars {
				value := m.configPairs[key]
				isPassword := strings.Contains(strings.ToLower(key), "password") ||
					strings.Contains(strings.ToLower(key), "secret") ||
					strings.Contains(strings.ToLower(key), "pass") ||
					strings.Contains(strings.ToLower(key), "token")
				isVisible := m.configShowPasswords[key]

				if isPassword {
					hasPasswords = true
				}

				// Hide sensitive values (passwords) unless requested
				if isPassword && !isVisible {
					// Display with an indicator that it can be clicked
					maskedValue := strings.Repeat("•", len(value))
					if len(value) == 0 {
						maskedValue = "(empty)"
					}
					value = m.theme.WarningStatus.Render(maskedValue)
				} else if isPassword && isVisible {
					value = m.theme.SuccessStatus.Render(value)
				}
				rows = append(rows, fmt.Sprintf("%-32s  %s", m.theme.Accent.Render(key), value))
			}
		}
	}

	return strings.Join(rows, "\n")
}

func (m *Model) renderConfigPanel() string {
	// This function is no longer used, content is built via buildConfigContent
	// and displayed via the viewport in renderConfigView
	return ""
}

// categorizeConfigPairs organizes variables by logical category
func (m *Model) categorizeConfigPairs(pairs map[string]string) map[string][]string {
	categories := make(map[string][]string)

	// Logical order of keys by category (USER before PASSWORD, etc.)
	vaultOrder := map[string]int{
		"VAULT_SERVICE":               0,
		"VAULT_USER":                  1,
		"VAULT_PASS":                  2,
		"VAULT_SECRET_KEY":            3,
		"VAULT_ROTATION_INTERVAL":     4,
		"VAULT_WEB_REPLICAS":          5,
		"VAULT_SESSION_COOKIE_SECURE": 6,
	}
	dockerProxyOrder := map[string]int{
		"DOCKER_PROXY_URL":       0,
		"DOCKER_PROXY_TOKEN":     1,
		"DOCKER_PROXY_TIMEOUT":   2,
		"DOCKER_PROXY_LOG_LEVEL": 3,
	}
	filebrowserOrder := map[string]int{
		"FILEBROWSER_VERSION":        0,
		"FILEBROWSER_ADMIN_USER":     1,
		"FILEBROWSER_ADMIN_PASSWORD": 2,
	}
	paperlessOrder := map[string]int{
		"PAPERLESS_URL":        0,
		"PAPERLESS_DBPASS":     1,
		"PAPERLESS_SECRET_KEY": 2,
	}
	cspOrder := map[string]int{
		"VAULT_CSP_REPORT_MAX_SIZE":   0,
		"VAULT_CSP_REPORT_RATE_LIMIT": 1,
		// Deprecated keys: These are kept for backward compatibility with old .env files
		// that may still use the old naming convention (without VAULT_ prefix).
		// New configurations should use VAULT_CSP_REPORT_MAX_SIZE and VAULT_CSP_REPORT_RATE_LIMIT.
		// TODO: Remove these deprecated keys in a future major version (e.g., v2.0.0) after ensuring
		//       all deployments have migrated to the VAULT_ prefixed versions. This is a breaking
		//       change that should be tracked in CHANGELOG.md when implemented.
		"CSP_REPORT_MAX_SIZE":   0, // Deprecated: use VAULT_CSP_REPORT_MAX_SIZE
		"CSP_REPORT_RATE_LIMIT": 1, // Deprecated: use VAULT_CSP_REPORT_RATE_LIMIT
	}
	proxyOrder := map[string]int{
		"PROXY_TRUST_COUNT": 0,
	}

	// Collect all keys
	allKeys := make([]string, 0, len(pairs))
	for k := range pairs {
		allKeys = append(allKeys, k)
	}

	// Categorize each key
	for _, key := range allKeys {
		category := ""

		if strings.HasPrefix(key, "VAULT_") {
			category = "Vault"
		} else if strings.HasPrefix(key, "DOCKER_PROXY_") {
			category = "Docker Proxy"
		} else if strings.HasPrefix(key, "FILEBROWSER_") {
			category = "Filebrowser"
		} else if strings.HasPrefix(key, "PAPERLESS_") {
			category = "Paperless"
		} else if strings.HasPrefix(key, "VAULT_CSP_") {
			category = "CSP"
		} else if strings.HasPrefix(key, "CSP_") {
			category = "CSP"
		} else if strings.HasPrefix(key, "PROXY_") {
			category = "Proxy"
		} else {
			category = "General"
		}

		if categories[category] == nil {
			categories[category] = make([]string, 0)
		}

		categories[category] = append(categories[category], key)
	}

	// Sort each category according to the defined order
	for category, keys := range categories {
		var orderMap map[string]int

		// Determine the order map according to the category
		if category == "Vault" {
			orderMap = vaultOrder
		} else if category == "Docker Proxy" {
			orderMap = dockerProxyOrder
		} else if category == "Filebrowser" {
			orderMap = filebrowserOrder
		} else if category == "Paperless" {
			orderMap = paperlessOrder
		} else if category == "CSP" {
			orderMap = cspOrder
		} else if category == "Proxy" {
			orderMap = proxyOrder
		} else {
			orderMap = nil
		}

		if orderMap != nil {
			// Sort according to defined order, then alphabetically for others
			sort.Slice(keys, func(i, j int) bool {
				orderI, hasOrderI := orderMap[keys[i]]
				orderJ, hasOrderJ := orderMap[keys[j]]

				if hasOrderI && hasOrderJ {
					return orderI < orderJ
				}
				if hasOrderI {
					return true // i has an order, i comes before
				}
				if hasOrderJ {
					return false // j has an order, j comes before
				}
				// Both have no order, sort alphabetically
				return keys[i] < keys[j]
			})
		} else {
			// For General, sort alphabetically
			sort.Strings(keys)
		}

		categories[category] = keys
	}

	return categories
}

func (m *Model) renderWizardView() string {
	header := m.renderHeader()
	wizard := m.renderWizardPanel()

	quitMsg := ""
	if m.quitConfirm {
		quitMsg = m.renderQuitConfirmation()
	}

	footer := m.renderFooter("wizard")

	var parts []string
	parts = append(parts, header)
	if quitMsg != "" {
		parts = append(parts, quitMsg)
	}
	parts = append(parts, wizard)
	parts = append(parts, footer)

	layout := lipgloss.JoinVertical(lipgloss.Left, parts...)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderWizardPanel() string {
	if len(m.wizardFields) == 0 {
		return m.theme.Pane.Render("No configuration variables found. Use 'c' to view config first.")
	}

	var rows []string

	// Title
	rows = append(rows, m.theme.Accent.Render("Interactive Configuration Wizard"))

	// Progress (e.g., "Variable 1 of 10")
	progress := fmt.Sprintf("Variable %d of %d", m.wizardIndex+1, len(m.wizardFields))
	rows = append(rows, m.theme.Subtitle.Render(progress))
	rows = append(rows, "")

	// Display ONE field at a time
	field := m.wizardFields[m.wizardIndex]
	label := field.Key
	if field.IsPassword {
		label += " (password, hidden)"
	}

	labelText := m.theme.Accent.Bold(true).Render(fmt.Sprintf("%s:", label))
	rows = append(rows, labelText)
	
	// Add helpful hint based on field name
	hint := m.getWizardHint(field.Key)
	if hint != "" {
		rows = append(rows, m.theme.Subtitle.Render(fmt.Sprintf("💡 %s", hint)))
	}
	rows = append(rows, "")

	// Input field with focus
	inputStyle := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("81")).
		Padding(0, 1).
		Width(60)

	inputView := field.Input.View()
	rows = append(rows, inputStyle.Render(inputView))
	rows = append(rows, "")

	// Help message
	if field.IsPassword {
		rows = append(rows, m.theme.Subtitle.Render("This is a password field. Your input will be hidden."))
		rows = append(rows, "")
	}

	rows = append(rows, m.theme.Subtitle.Render("All fields are optional. Leave empty to keep existing value."))
	rows = append(rows, "")

	if m.wizardError != "" {
		rows = append(rows, m.theme.ErrorStatus.Render("❌ "+m.wizardError))
		rows = append(rows, "")
	}

	// Navigation and action buttons
	rows = append(rows, "")
	rows = append(rows, strings.Repeat("─", 60))
	rows = append(rows, "")

	// Previous button (left)
	prevDisabled := m.wizardIndex == 0
	var prevButton string
	if prevDisabled {
		prevButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("240")).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240")).
			Render("← Previous (disabled)")
	} else {
		prevButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("81")).
			Bold(true).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("81")).
			Render("← Previous (←)")
	}

	// Next button (right)
	nextDisabled := m.wizardIndex >= len(m.wizardFields)-1
	var nextButton string
	if nextDisabled {
		nextButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("240")).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("240")).
			Render("Next → (disabled)")
	} else {
		nextButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("81")).
			Bold(true).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("81")).
			Render("Next → (→)")
	}

	// Save button
	saveButton := lipgloss.NewStyle().
		Foreground(lipgloss.Color("42")).
		Bold(true).
		Padding(0, 2).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("42")).
		Render("✓ Save (Ctrl+S)")

	// Cancel button
	cancelButton := lipgloss.NewStyle().
		Foreground(lipgloss.Color("240")).
		Bold(true).
		Padding(0, 2).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("240")).
		Render("✗ Cancel (Esc)")

	// First line: Previous and Next
	navButtons := lipgloss.JoinHorizontal(lipgloss.Left, prevButton, "  ", nextButton)
	rows = append(rows, navButtons)
	rows = append(rows, "")

	// Second line: Save and Cancel
	actionButtons := lipgloss.JoinHorizontal(lipgloss.Left, saveButton, "  ", cancelButton)
	rows = append(rows, actionButtons)

	return m.theme.Pane.Render(strings.Join(rows, "\n"))
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
		return m.theme.Pane.Render("No containers running. Press 'a' to start the stack or 'w' to configure.")
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
	// Don't display logs if we're on the dashboard (should never happen)
	if m.viewState == ViewDashboard {
		return m.theme.Pane.Render("No activity yet. Use r to restart or s to stop the stack.")
	}

	content := m.viewport.View()
	if strings.TrimSpace(content) == "" {
		content = "No activity yet. Use r to restart or s to stop the stack."
	}
	return m.theme.Pane.Render(content)
}

func (m *Model) renderQuitConfirmation() string {
	message := fmt.Sprintf(
		"⚠️  Quit application? Press %s again to confirm quit, or any other key to cancel",
		m.theme.HelpKey.Render("CTRL+C"),
	)
	return m.theme.WarningStatus.
		Padding(0, 2).
		MarginBottom(1).
		Render(message)
}

func (m *Model) renderSuccessMessage() string {
	return m.theme.SuccessStatus.Padding(0, 1).Render(fmt.Sprintf("✅ %s", m.successMessage))
}

func (m *Model) renderFooter(context string) string {
	var hints []string

	switch context {
	case "dashboard":
		hints = []string{
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
			fmt.Sprintf("%s Start", m.theme.HelpKey.Render("a")),
			fmt.Sprintf("%s Restart", m.theme.HelpKey.Render("r")),
			fmt.Sprintf("%s Stop", m.theme.HelpKey.Render("s")),
			fmt.Sprintf("%s Rebuild", m.theme.HelpKey.Render("b")),
			fmt.Sprintf("%s Config", m.theme.HelpKey.Render("c")),
			fmt.Sprintf("%s Wizard", m.theme.HelpKey.Render("w")),
			fmt.Sprintf("%s Logs", m.theme.HelpKey.Render("l")),
			fmt.Sprintf("%s Help", m.theme.HelpKey.Render("?")),
		}
	case "config":
		hints = []string{
			fmt.Sprintf("%s Back", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
			fmt.Sprintf("%s Refresh", m.theme.HelpKey.Render("r")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
			fmt.Sprintf("%s Toggle passwords", m.theme.HelpKey.Render("Space")),
		}
	case "wizard":
		hints = []string{
			fmt.Sprintf("%s Previous", m.theme.HelpKey.Render("←")),
			fmt.Sprintf("%s Next", m.theme.HelpKey.Render("→")),
			fmt.Sprintf("%s Save", m.theme.HelpKey.Render("Ctrl+S")),
			fmt.Sprintf("%s Cancel", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
		}
	case "logs":
		hints = []string{
			fmt.Sprintf("%s Back", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
		}
	case "action":
		hints = []string{
			fmt.Sprintf("%s Back (wait for completion)", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
		}
	default:
		hints = []string{
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("Ctrl+C")),
		}
	}

	separator := m.theme.HelpDesc.Render(" • ")
	return m.theme.Footer.Render(strings.Join(hints, separator))
}

func (m *Model) renderHints() string {
	// Hints are now in the footer, this method can be simplified or removed
	// We keep it for compatibility with renderHelp() which still uses it
	return ""
}

func (m *Model) renderHelp() string {
	rows := []string{
		m.theme.Accent.Render("Actions:"),
		fmt.Sprintf("%s Quit the dashboard (press twice to confirm)", m.theme.HelpKey.Render("Ctrl+C")),
		fmt.Sprintf("%s Start the stack (docker compose up)", m.theme.HelpKey.Render("a")),
		fmt.Sprintf("%s Restart the stack", m.theme.HelpKey.Render("r")),
		fmt.Sprintf("%s Stop the stack", m.theme.HelpKey.Render("s")),
		fmt.Sprintf("%s Rebuild configuration", m.theme.HelpKey.Render("b")),
		fmt.Sprintf("%s Toggle this help overlay", m.theme.HelpKey.Render("?")),
		"",
		m.theme.Accent.Render("Navigation:"),
		fmt.Sprintf("%s Return to dashboard", m.theme.HelpKey.Render("Esc")),
		fmt.Sprintf("%s View logs", m.theme.HelpKey.Render("l")),
		fmt.Sprintf("%s View configuration", m.theme.HelpKey.Render("c")),
		fmt.Sprintf("%s Run wizard", m.theme.HelpKey.Render("w")),
		fmt.Sprintf("%s Scroll logs/config", m.theme.HelpKey.Render("↑/↓")),
	}
	content := lipgloss.JoinVertical(lipgloss.Left, rows...)
	return lipgloss.NewStyle().MarginTop(1).Render(m.theme.Pane.Render(content))
}

// getWizardHint returns a helpful hint for a configuration field
func (m *Model) getWizardHint(key string) string {
	hints := map[string]string{
		"VAULT_USER":                  "Username for Vault authentication",
		"VAULT_PASS":                  "Password for Vault authentication",
		"VAULT_SECRET_KEY":            "Secret key used for encryption",
		"VAULT_ROTATION_INTERVAL":     "Time in seconds between container rotations",
		"VAULT_WEB_REPLICAS":         "Number of web container replicas",
		"DOCKER_PROXY_URL":           "URL of the Docker proxy service",
		"DOCKER_PROXY_TOKEN":         "Authentication token for Docker proxy",
		"FILEBROWSER_ADMIN_USER":     "Admin username for Filebrowser",
		"FILEBROWSER_ADMIN_PASSWORD": "Admin password for Filebrowser",
		"PAPERLESS_URL":              "URL of the Paperless service",
		"PAPERLESS_DBPASS":           "Database password for Paperless",
	}
	if hint, ok := hints[key]; ok {
		return hint
	}
	return ""
}
