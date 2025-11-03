package ui

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

func (m *Model) View() string {
	if !m.ready {
		return m.theme.Title.Render(" Loading Leyzenctl dashboard...")
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
	// S'assurer qu'on est vraiment sur le dashboard et nettoyer si nécessaire
	if m.viewState != ViewDashboard {
		// Protection : si on appelle renderDashboard mais qu'on n'est pas sur le dashboard,
		// on ne devrait pas arriver ici, mais on force le nettoyage
		m.viewState = ViewDashboard
	}
	
	header := m.renderHeader()
	status := m.renderStatusPanel()
	
	// Message de succès temporaire
	successMsg := ""
	if m.successMessage != "" {
		successMsg = m.renderSuccessMessage()
	}
	
	help := ""
	if m.helpVisible {
		help = m.renderHelp()
	} else {
		help = m.renderHints()
	}
	
	// TOUJOURS utiliser "dashboard" comme contexte pour le footer
	// Forcer explicitement le contexte dashboard pour éviter les hints du wizard
	footer := m.renderFooter("dashboard")

	var parts []string
	parts = append(parts, header)
	if successMsg != "" {
		parts = append(parts, successMsg)
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
	footer := m.renderFooter("logs")

	layout := lipgloss.JoinVertical(lipgloss.Left, header, logs, footer)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderActionView() string {
	header := m.renderHeader()
	logs := m.renderLogPanel()
	footer := m.renderFooter("action")

	layout := lipgloss.JoinVertical(lipgloss.Left, header, logs, footer)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderConfigView() string {
	header := m.renderHeader()
	
	// S'assurer que le viewport est dimensionné
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
	
	// Construire le contenu complet de la config
	configContent := m.buildConfigContent()
	
	// Préserver l'offset Y actuel avant de mettre à jour le contenu
	currentYOffset := m.viewport.YOffset
	
	// Mettre à jour le viewport avec le contenu
	m.viewport.SetContent(configContent)
	
	// Restaurer l'offset Y pour préserver la position de scroll
	m.viewport.SetYOffset(currentYOffset)
	
	// S'assurer que le viewport est synchronisé
	m.viewport.Width = m.width - 6
	if m.viewport.Width < 20 {
		m.viewport.Width = 20
	}
	
	// Rendre le viewport dans le pane
	config := m.theme.Pane.Render(m.viewport.View())
	
	footer := m.renderFooter("config")

	layout := lipgloss.JoinVertical(lipgloss.Left, header, config, footer)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) buildConfigContent() string {
	if len(m.configPairs) == 0 {
		return "No configuration variables set yet. Use 'w' to run the wizard."
	}

	var rows []string
	header := fmt.Sprintf("%-32s  %s", "KEY", "VALUE")
	rows = append(rows, m.theme.Accent.Render(header))
	rows = append(rows, strings.Repeat("─", 80))

	// Organiser les variables par catégorie
	categorized := m.categorizeConfigPairs(m.configPairs)
	
	// Ordre des catégories
	categoryOrder := []string{
		"Vault",
		"Docker Proxy",
		"Filebrowser",
		"Paperless",
		"CSP",
		"Proxy",
		"General",
	}

	hasPasswords := false
	
	// Afficher chaque catégorie
	for _, category := range categoryOrder {
		if vars, ok := categorized[category]; ok && len(vars) > 0 {
			// Titre de catégorie
			if len(rows) > 2 { // S'il y a déjà du contenu, ajouter un espace
				rows = append(rows, "")
			}
			rows = append(rows, m.theme.Subtitle.Render(fmt.Sprintf("── %s ──", category)))
			
			// Variables de cette catégorie
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
				
				// Masquer les valeurs sensibles (mots de passe) sauf si demandé
				if isPassword && !isVisible {
					// Afficher avec un indicateur qu'on peut appuyer dessus
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
	
	// Ajouter une ligne d'aide pour les mots de passe
	if hasPasswords {
		rows = append(rows, "")
		rows = append(rows, m.theme.Subtitle.Render("Press SPACE to toggle password visibility"))
	}

	return strings.Join(rows, "\n")
}

func (m *Model) renderConfigPanel() string {
	// Cette fonction n'est plus utilisée, le contenu est construit via buildConfigContent
	// et affiché via le viewport dans renderConfigView
	return ""
}

// categorizeConfigPairs organise les variables par catégorie logique
func (m *Model) categorizeConfigPairs(pairs map[string]string) map[string][]string {
	categories := make(map[string][]string)
	
	// Ordre logique des clés par catégorie (USER avant PASSWORD, etc.)
	vaultOrder := map[string]int{
		"VAULT_SERVICE":              0,
		"VAULT_USER":                 1,
		"VAULT_PASS":                 2,
		"VAULT_SECRET_KEY":           3,
		"VAULT_ROTATION_INTERVAL":    4,
		"VAULT_WEB_REPLICAS":         5,
		"VAULT_SESSION_COOKIE_SECURE": 6,
	}
	dockerProxyOrder := map[string]int{
		"DOCKER_PROXY_URL":      0,
		"DOCKER_PROXY_TOKEN":    1,
		"DOCKER_PROXY_TIMEOUT":  2,
		"DOCKER_PROXY_LOG_LEVEL": 3,
	}
	filebrowserOrder := map[string]int{
		"FILEBROWSER_VERSION":        0,
		"FILEBROWSER_ADMIN_USER":    1,
		"FILEBROWSER_ADMIN_PASSWORD": 2,
	}
	paperlessOrder := map[string]int{
		"PAPERLESS_URL":        0,
		"PAPERLESS_DBPASS":     1,
		"PAPERLESS_SECRET_KEY": 2,
	}
	cspOrder := map[string]int{
		"CSP_REPORT_MAX_SIZE":   0,
		"CSP_REPORT_RATE_LIMIT": 1,
	}
	proxyOrder := map[string]int{
		"PROXY_TRUST_COUNT": 0,
	}
	
	// Collecter toutes les clés
	allKeys := make([]string, 0, len(pairs))
	for k := range pairs {
		allKeys = append(allKeys, k)
	}
	
	// Catégoriser chaque clé
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
	
	// Trier chaque catégorie selon l'ordre défini
	for category, keys := range categories {
		var orderMap map[string]int
		
		// Déterminer la map d'ordre selon la catégorie
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
			// Trier selon l'ordre défini, puis alphabétiquement pour les autres
			sort.Slice(keys, func(i, j int) bool {
				orderI, hasOrderI := orderMap[keys[i]]
				orderJ, hasOrderJ := orderMap[keys[j]]
				
				if hasOrderI && hasOrderJ {
					return orderI < orderJ
				}
				if hasOrderI {
					return true // i a un ordre, i vient avant
				}
				if hasOrderJ {
					return false // j a un ordre, j vient avant
				}
				// Les deux n'ont pas d'ordre, trier alphabétiquement
				return keys[i] < keys[j]
			})
		} else {
			// Pour General, trier alphabétiquement
			sort.Strings(keys)
		}
		
		categories[category] = keys
	}
	
	return categories
}

func (m *Model) renderWizardView() string {
	header := m.renderHeader()
	wizard := m.renderWizardPanel()
	footer := m.renderFooter("wizard")

	layout := lipgloss.JoinVertical(lipgloss.Left, header, wizard, footer)
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, layout)
}

func (m *Model) renderWizardPanel() string {
	if len(m.wizardFields) == 0 {
		return m.theme.Pane.Render("No configuration variables found. Use 'c' to view config first.")
	}

	var rows []string
	
	// Titre
	rows = append(rows, m.theme.Accent.Render("Interactive Configuration Wizard"))
	
	// Progression (ex: "Variable 1 sur 10")
	progress := fmt.Sprintf("Variable %d sur %d", m.wizardIndex+1, len(m.wizardFields))
	rows = append(rows, m.theme.Subtitle.Render(progress))
	rows = append(rows, "")
	
	// Afficher UN SEUL champ à la fois
	field := m.wizardFields[m.wizardIndex]
	label := field.Key
	if field.IsPassword {
		label += " (password, hidden)"
	}
	
	labelText := m.theme.Accent.Bold(true).Render(fmt.Sprintf("%s:", label))
	rows = append(rows, labelText)
	rows = append(rows, "")
	
	// Input field avec focus
	inputStyle := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("81")).
		Padding(0, 1).
		Width(60)
	
	inputView := field.Input.View()
	rows = append(rows, inputStyle.Render(inputView))
	rows = append(rows, "")
	
	// Message d'aide
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
	
	// Boutons de navigation et d'action
	rows = append(rows, "")
	rows = append(rows, strings.Repeat("─", 60))
	rows = append(rows, "")
	
	// Bouton Précédent (gauche)
	prevDisabled := m.wizardIndex == 0
	var prevButton string
	if prevDisabled {
		prevButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("238")).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("238")).
			Render("← Précédent")
	} else {
		prevButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("81")).
			Bold(true).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("81")).
			Render("← Précédent (←)")
	}
	
	// Bouton Suivant (droite)
	nextDisabled := m.wizardIndex >= len(m.wizardFields)-1
	var nextButton string
	if nextDisabled {
		nextButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("238")).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("238")).
			Render("Suivant → (→)")
	} else {
		nextButton = lipgloss.NewStyle().
			Foreground(lipgloss.Color("81")).
			Bold(true).
			Padding(0, 2).
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("81")).
			Render("Suivant → (→)")
	}
	
	// Bouton Sauvegarder
	saveButton := lipgloss.NewStyle().
		Foreground(lipgloss.Color("42")).
		Bold(true).
		Padding(0, 2).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("42")).
		Render("✓ Sauvegarder (Ctrl+S)")
	
	// Bouton Annuler
	cancelButton := lipgloss.NewStyle().
		Foreground(lipgloss.Color("240")).
		Bold(true).
		Padding(0, 2).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("240")).
		Render("✗ Annuler (Esc)")
	
	// Première ligne : Précédent et Suivant
	navButtons := lipgloss.JoinHorizontal(lipgloss.Left, prevButton, "  ", nextButton)
	rows = append(rows, navButtons)
	rows = append(rows, "")
	
	// Deuxième ligne : Sauvegarder et Annuler
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
	// Ne pas afficher de logs si on est sur le dashboard (ne devrait jamais arriver)
	if m.viewState == ViewDashboard {
		return m.theme.Pane.Render("No activity yet. Use r to restart or s to stop the stack.")
	}
	
	content := m.viewport.View()
	if strings.TrimSpace(content) == "" {
		content = "No activity yet. Use r to restart or s to stop the stack."
	}
	return m.theme.Pane.Render(content)
}

func (m *Model) renderSuccessMessage() string {
	return m.theme.SuccessStatus.Padding(0, 1).Render(fmt.Sprintf("✅ %s", m.successMessage))
}

func (m *Model) renderFooter(context string) string {
	var hints []string
	
	switch context {
	case "dashboard":
		hints = []string{
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
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
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
			fmt.Sprintf("%s Refresh", m.theme.HelpKey.Render("r")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
			fmt.Sprintf("%s Toggle passwords", m.theme.HelpKey.Render("Space")),
		}
	case "wizard":
		hints = []string{
			fmt.Sprintf("%s Précédent", m.theme.HelpKey.Render("←")),
			fmt.Sprintf("%s Suivant", m.theme.HelpKey.Render("→")),
			fmt.Sprintf("%s Sauvegarder", m.theme.HelpKey.Render("Ctrl+S")),
			fmt.Sprintf("%s Annuler", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quitter", m.theme.HelpKey.Render("q")),
		}
	case "logs":
		hints = []string{
			fmt.Sprintf("%s Back", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
		}
	case "action":
		hints = []string{
			fmt.Sprintf("%s Back (wait for completion)", m.theme.HelpKey.Render("Esc")),
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
			fmt.Sprintf("%s Scroll", m.theme.HelpKey.Render("↑/↓")),
		}
	default:
		hints = []string{
			fmt.Sprintf("%s Quit", m.theme.HelpKey.Render("q")),
		}
	}
	
	separator := m.theme.HelpDesc.Render(" • ")
	return m.theme.Footer.Render(strings.Join(hints, separator))
}

func (m *Model) renderHints() string {
	// Les hints sont maintenant dans le footer, cette méthode peut être simplifiée ou supprimée
	// On la garde pour la compatibilité avec renderHelp() qui l'utilise encore
	return ""
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
