package ui

import (
	"fmt"
	"time"
	"strings"

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
		// Toujours permettre 'q' pour quitter, même dans le wizard
		if msg.String() == "q" || msg.String() == "ctrl+c" {
			return m, tea.Quit
		}
		// Si on est dans le wizard, ne pas passer par handleKey qui intercepte les touches
		if m.viewState == ViewWizard && len(m.wizardFields) > 0 {
			return m.handleWizardKey(msg)
		}
		// Si on est dans la vue config, laisser le viewport gérer les touches de scroll
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
		// Si on vient du dashboard et qu'on n'a pas encore de wizard, on est peut-être en train de le lancer
		// Initialiser le wizard si on n'en a pas encore
		if m.viewState == ViewDashboard && len(m.wizardFields) == 0 {
			m.initWizard(msg.pairs)
		}
		return m, nil
	case wizardSaveMsg:
		return m.handleWizardSave(msg)
	}

	// Gérer le viewport seulement si on est dans une vue qui l'utilise
	if m.viewState == ViewLogs || m.viewState == ViewAction || m.viewState == ViewConfig {
		var cmd tea.Cmd
		m.viewport, cmd = m.viewport.Update(msg)
		return m, cmd
	}
	
	// Gérer les messages non-clavier du wizard (déjà géré pour KeyMsg ci-dessus)
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

	// Calculer la hauteur du viewport selon la vue active
	var viewportHeight int
	if m.viewState == ViewDashboard {
		// Pas de viewport visible sur le dashboard
		viewportHeight = 0
	} else if m.viewState == ViewConfig {
		// Pour la vue config, calculer l'espace disponible
		// header + footer + padding du pane
		viewportHeight = m.height - 10
		if viewportHeight < 6 {
			viewportHeight = 6
		}
	} else {
		// Pour les vues logs et action, calculer l'espace disponible
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
	switch msg.String() {
	case "ctrl+c", "q":
		return m, tea.Quit
	case "esc":
		// Retour au dashboard depuis n'importe quelle vue
		if m.viewState == ViewLogs || m.viewState == ViewConfig || m.viewState == ViewWizard {
			m.switchToDashboard()
			return m, nil
		}
		// Si une action est en cours, on permet quand même de revenir au dashboard
		// mais on continue d'afficher les logs en arrière-plan
		if m.viewState == ViewAction && !m.actionRunning {
			m.switchToDashboard()
			return m, nil
		}
		return m, nil
	case "r":
		// Rafraîchir la config si on est dans la vue config
		if m.viewState == ViewConfig {
			return m, fetchConfigListCmd(m.envFile)
		}
		// Sinon, redémarrer depuis le dashboard
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
		// Basculer vers la vue logs depuis le dashboard
		if m.viewState == ViewDashboard {
			m.switchToLogs()
			return m, nil
		}
		return m, nil
	case "c":
		// Afficher la configuration depuis le dashboard
		if m.viewState == ViewDashboard {
			m.switchToConfig()
			return m, fetchConfigListCmd(m.envFile)
		}
		return m, nil
	case " ":
		// Espace pour toggle l'affichage des mots de passe dans la vue config
		if m.viewState == ViewConfig {
			// Toggle TOUS les mots de passe, secrets, tokens
			// Utiliser la même logique de détection que dans buildConfigContent
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
		// Lancer le wizard depuis le dashboard
		if m.viewState == ViewDashboard {
			// Charger la config existante pour pré-remplir les champs
			// Utiliser les valeurs déjà chargées ou charger si nécessaire
			if len(m.configPairs) == 0 {
				// Charger la config puis initialiser le wizard
				return m, fetchConfigListCmd(m.envFile)
			}
			// Si on a déjà les valeurs, initialiser directement
			// Mais s'il n'y a vraiment rien dans le .env, on devrait quand même permettre d'ajouter des variables
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
		// Navigation dans le viewport pour les vues logs/action/config
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
		
		// Retour au dashboard après erreur
		m.switchToDashboard()
		
		// Pas de message de succès pour les erreurs
		return m, fetchStatusesCmd()
	}

	if msg.Done {
		actionName := string(msg.Action)
		m.appendLog(fmt.Sprintf("✅ %s completed", actionName))
		m.actionRunning = false
		m.action = ActionNone
		m.actionStream = nil

		// Afficher le message de succès et retourner au dashboard après un délai
		m.successMessage = fmt.Sprintf("%s completed successfully", actionName)
		
		// Programmer le retour au dashboard et la suppression du message de succès
		cmd := tea.Sequence(
			fetchStatusesCmd(),
			tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} }),
		)
		
		// Retour automatique au dashboard après le succès
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
		// Sauvegarder toutes les modifications
		return m.saveWizard()
	case "esc":
		// Annuler et retourner au dashboard
		m.switchToDashboard()
		return m, nil
	case "right", "→":
		// Passer au champ suivant (Suivant)
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
		// Passer au champ précédent (Précédent)
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
		// Enter : passer au champ suivant (comme "Suivant")
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
		// Toutes les autres touches (lettres, chiffres, etc.) : passer à l'input actif
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
	
	// Tous les champs sont optionnels - validation optionnelle seulement
	// Si la valeur est vide, c'est OK
	if value == "" {
		return nil
	}
	
	// Si on a une valeur, valider (mais pas obligatoire)
	_, err := internal.ValidateEnvValue(field.Key, value)
	if err != nil {
		// Si la validation échoue, retourner l'erreur
		// Mais seulement si on a une valeur (pas si vide)
		return err
	}
	
	return nil
}

func (m *Model) saveWizard() (tea.Model, tea.Cmd) {
	// Valider toutes les valeurs avant de sauvegarder (optionnel - juste avertir)
	hasErrors := false
	for i := range m.wizardFields {
		value := m.wizardFields[i].Input.Value()
		if err := m.validateWizardField(i, value); err != nil {
			m.wizardError = fmt.Sprintf("Error in %s: %v", m.wizardFields[i].Key, err)
			hasErrors = true
			break
		}
		// Sauvegarder la valeur dans le champ
		m.wizardFields[i].Value = value
	}
	
	if hasErrors {
		// Ne pas sauvegarder si erreur
		return m, nil
	}
	
	// Pas d'erreur - sauvegarder
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
	// Charger le fichier env
	envFileObj, err := internal.LoadEnvFile(envFile)
	if err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to load env file: %w", err)}
	}
	
	// Sauvegarder chaque champ (valeurs vides permises)
	for _, field := range fields {
		value := field.Value // Utiliser la valeur sauvegardée dans le champ
		
		// Toutes les valeurs sont optionnelles
		// Si la valeur est vide, on la sauvegarde quand même (peut être supprimée)
		sanitized := strings.TrimSpace(value)
		
		// Si validation échoue mais valeur non vide, retourner erreur
		if sanitized != "" {
			validated, err := internal.ValidateEnvValue(field.Key, sanitized)
			if err != nil {
				return wizardSaveMsg{err: fmt.Errorf("%s: %w", field.Key, err)}
			}
			sanitized = validated
		}
		
		// Sauvegarder (même si vide)
		envFileObj.Set(field.Key, sanitized)
	}
	
	// Sauvegarder
	if err := envFileObj.Write(); err != nil {
		return wizardSaveMsg{err: fmt.Errorf("failed to write env file: %w", err)}
	}
	
	// Rebuild - écrire dans un buffer silencieux pour ne pas polluer le TUI
	// Les logs du rebuild ne doivent pas s'afficher sur le dashboard
	var silentBuffer strings.Builder
	if err := internal.RunBuildScriptWithWriter(&silentBuffer, &silentBuffer, envFile); err != nil {
		// Retourner l'erreur mais ne pas afficher les logs
		return wizardSaveMsg{err: fmt.Errorf("failed to rebuild: %w", err)}
	}
	
	return wizardSaveMsg{err: nil}
}

func (m *Model) handleWizardSave(msg wizardSaveMsg) (tea.Model, tea.Cmd) {
	m.actionRunning = false
	m.action = ActionNone
	
	// D'abord, retourner au dashboard pour nettoyer l'état
	m.switchToDashboard()
	
	if msg.err != nil {
		// Pour les erreurs, on peut ajouter un message mais seulement si on n'est pas sur le dashboard
		// Ici, on est déjà sur le dashboard, donc on ne fait rien avec les logs
		m.successMessage = fmt.Sprintf("❌ Configuration save failed: %v", msg.err)
		// Programmer la suppression du message d'erreur
		cmd := tea.Tick(successMessageDuration, func(time.Time) tea.Msg { return successTimeoutMsg{} })
		return m, cmd
	}
	
	// Succès
	m.successMessage = "Configuration saved successfully"
	
	// Rafraîchir la config
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
