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
	logsBuffer      []string // Buffer pour conserver les logs lors du retour au dashboard
	configPairs     map[string]string // Pour stocker les paires de configuration
	configShowPasswords map[string]bool // Pour afficher/masquer les mots de passe dans la vue config
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
	
	// NE PAS ajouter de logs si on est sur le dashboard (ils ne doivent pas s'afficher)
	if m.viewState == ViewDashboard {
		return
	}
	
	// Nettoyer la ligne : supprimer les caractères de contrôle et les espaces en début/fin
	line = strings.TrimSpace(line)
	// Filtrer les lignes vides après nettoyage
	if line == "" {
		return
	}
	// Filtrer les lignes avec seulement un caractère isolé (artefacts de formatage)
	// Sauf si c'est un caractère spécial valide
	if len(line) == 1 {
		// Autoriser seulement certains caractères spéciaux valides
		validSingleChars := map[string]bool{
			"[": true,
			"]": true,
			"(": true,
			")": true,
		}
		if !validSingleChars[line] {
			// Ignorer les caractères isolés comme "C", "B", etc.
			return
		}
	}
	
	// Filtrer les lignes qui commencent par un caractère isolé suivi d'un saut de ligne
	// (ex: "C\n" ou "B\n")
	if len(line) > 1 && (line[0] == 'C' || line[0] == 'B') && line[1] == '\n' {
		return
	}
	
	m.logs = append(m.logs, line)
	if len(m.logs) > logBufferLimit {
		diff := len(m.logs) - logBufferLimit
		m.logs = m.logs[diff:]
	}
	// Ne mettre à jour le viewport que si on est dans une vue qui affiche les logs
	if m.viewState == ViewLogs || m.viewState == ViewAction {
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	}
}

func (m *Model) switchToDashboard() {
	// Sauvegarder les logs actuels dans le buffer si on vient d'une vue avec logs
	if m.viewState == ViewLogs || m.viewState == ViewAction {
		m.logsBuffer = make([]string, len(m.logs))
		copy(m.logsBuffer, m.logs)
	}
	
	// Si on vient du wizard, nettoyer complètement l'état
	if m.viewState == ViewWizard {
		// Réinitialiser les champs du wizard pour éviter les restes d'affichage
		m.wizardFields = nil
		m.wizardIndex = 0
		m.wizardError = ""
	}
	
	// NETTOYER COMPLÈTEMENT : logs, viewport, action
	// Les logs ne doivent pas s'afficher sur le dashboard
	m.logs = nil
	m.viewport.SetContent("")
	m.viewport.GotoTop()
	m.actionRunning = false
	m.action = ActionNone
	m.actionStream = nil
	
	// Changer l'état APRÈS le nettoyage
	m.viewState = ViewDashboard
}

func (m *Model) switchToLogs() {
	// Restaurer les logs depuis le buffer si nécessaire
	if len(m.logsBuffer) > 0 {
		m.logs = make([]string, len(m.logsBuffer))
		copy(m.logs, m.logsBuffer)
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	} else if len(m.logs) > 0 {
		// Si pas de buffer mais qu'on a des logs, les afficher
		m.viewport.SetContent(strings.Join(m.logs, "\n"))
		m.viewport.GotoBottom()
	}
	m.viewState = ViewLogs
	// Recalculer la taille du viewport pour cette vue
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
	// Recalculer la taille du viewport pour cette vue
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
	// Initialiser la taille du viewport config si la fenêtre est déjà dimensionnée
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
		// Réinitialiser le scroll en haut
		m.viewport.SetYOffset(0)
	}
}

func (m *Model) initWizard(existing map[string]string) {
	// Charger TOUTES les variables du .env
	// Si existing est vide, le wizard affichera un message
	// Détecter automatiquement les mots de passe (contenant "password" ou "secret")
	keys := make([]string, 0, len(existing))
	for k := range existing {
		keys = append(keys, k)
	}
	
	// Trier les clés pour un affichage cohérent
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
		ti.CharLimit = 512 // Augmenter la limite
		ti.Width = 60
		if isPassword {
			ti.EchoMode = textinput.EchoPassword
			ti.EchoCharacter = '•'
		}
		// Pré-remplir avec la valeur existante
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
	
	// Focus sur le premier champ et blur les autres
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
