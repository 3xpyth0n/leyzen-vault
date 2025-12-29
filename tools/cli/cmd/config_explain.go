package cmd

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/spf13/cobra"

	"leyzenctl/internal"
)

var (
	docTitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FAFAFA")).
			Background(lipgloss.Color("#004225")).
			Padding(0, 1)

	docSubtitleStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#A49FA5")).
				MarginTop(1)

	docBodyStyle = lipgloss.NewStyle().
			MarginTop(1).
			MarginBottom(1)
)

type item struct {
	title, desc string
	doc         internal.EnvDoc
}

func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title + " " + i.desc }

type model struct {
	list     list.Model
	viewport viewport.Model
	view     string // "list" or "detail"
	selected item
	ready    bool
	width    int
	height   int
}

func (m model) Init() tea.Cmd {
	return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.ready = true

		m.list.SetWidth(msg.Width)
		m.list.SetHeight(msg.Height)

		headerHeight := lipgloss.Height(m.headerView())
		footerHeight := lipgloss.Height(m.footerView())
		verticalMarginHeight := headerHeight + footerHeight

		if !m.ready {
			m.viewport = viewport.New(msg.Width, msg.Height-verticalMarginHeight)
			m.viewport.YPosition = headerHeight
		} else {
			m.viewport.Width = msg.Width
			m.viewport.Height = msg.Height - verticalMarginHeight
		}

	case tea.KeyMsg:
		if m.view == "list" {
			switch msg.String() {
			case "ctrl+c":
				return m, tea.Quit
			case "enter":
				if i, ok := m.list.SelectedItem().(item); ok {
					m.selected = i
					m.view = "detail"
					m.viewport.SetContent(m.renderDetailContent(i))
					m.viewport.GotoTop()
					return m, nil
				}
			}
		}
		if m.view == "detail" {
			switch msg.String() {
			case "esc", "q":
				m.view = "list"
				return m, nil
			case "ctrl+c":
				return m, tea.Quit
			}
			var vpCmd tea.Cmd
			m.viewport, vpCmd = m.viewport.Update(msg)
			cmds = append(cmds, vpCmd)
			return m, tea.Batch(cmds...)
		}
	}

	if m.view == "list" {
		m.list, cmd = m.list.Update(msg)
		cmds = append(cmds, cmd)
	}

	return m, tea.Batch(cmds...)
}

func (m model) View() string {
	if !m.ready {
		return "\n  Initializing..."
	}

	if m.view == "list" {
		return m.list.View()
	}

	return fmt.Sprintf("%s\n%s\n%s", m.headerView(), m.viewport.View(), m.footerView())
}

func (m model) headerView() string {
	title := docTitleStyle.Render(m.selected.title)
	line := strings.Repeat("─", max(0, m.viewport.Width-lipgloss.Width(title)))
	return lipgloss.JoinHorizontal(lipgloss.Center, title, line)
}

func (m model) footerView() string {
	info := docSubtitleStyle.Render("Press Esc or q to go back")
	line := strings.Repeat("─", max(0, m.viewport.Width-lipgloss.Width(info)))
	return lipgloss.JoinHorizontal(lipgloss.Center, line, info)
}

func (m model) renderDetailContent(i item) string {
	return fmt.Sprintf("\n%s",
		docBodyStyle.Render(i.doc.Description),
	)
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

var explainCmd = &cobra.Command{
	Use:                   "explain",
	Short:                 "Interactive guide for environment variables",
	Long:                  "Explore and understand Leyzen Vault configuration variables interactively.",
	DisableFlagsInUseLine: true,
	Args:                  cobra.NoArgs,
	RunE: func(cmd *cobra.Command, args []string) error {
		// Load documentation
		envPath := EnvFilePath()
		docs, err := internal.LoadEnvDocumentation(envPath)
		if err != nil {
			return err
		}

		if len(docs) == 0 {
			fmt.Println("No documentation found in env.template")
			return nil
		}

		// Convert to list items
		var items []list.Item
		var keys []string
		for k := range docs {
			keys = append(keys, k)
		}
		sort.Strings(keys)

		for _, k := range keys {
			doc := docs[k]
			items = append(items, item{
				title: k,
				desc:  doc.Summary,
				doc:   doc,
			})
		}

		// Initialize list
		delegate := list.NewDefaultDelegate()
		delegate.Styles.SelectedTitle = delegate.Styles.SelectedTitle.
			BorderLeftForeground(lipgloss.Color("#004225")).
			Foreground(lipgloss.Color("#004225"))
		delegate.Styles.SelectedDesc = delegate.Styles.SelectedDesc.
			BorderLeftForeground(lipgloss.Color("#004225")).
			Foreground(lipgloss.Color("#006638")) // Slightly lighter green for description

		l := list.New(items, delegate, 0, 0)
		l.Title = "Leyzen Vault Configuration"
		l.SetShowStatusBar(false)
		l.SetFilteringEnabled(true)
		l.Styles.Title = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FAFAFA")).
			Background(lipgloss.Color("#004225")).
			Padding(0, 1)

		l.Filter = func(term string, targets []string) []list.Rank {
			var ranks []list.Rank
			term = strings.ToLower(term)

			for i, target := range targets {
				lowerTarget := strings.ToLower(target)
				idx := strings.Index(lowerTarget, term)
				if idx != -1 {
					matchedIndexes := make([]int, len(term))
					for j := 0; j < len(term); j++ {
						matchedIndexes[j] = idx + j
					}

					ranks = append(ranks, list.Rank{
						Index:          i,
						MatchedIndexes: matchedIndexes,
					})
				}
			}
			return ranks
		}

		// Run program
		p := tea.NewProgram(model{
			list: l,
			view: "list",
		}, tea.WithAltScreen())

		if _, err := p.Run(); err != nil {
			return err
		}

		return nil
	},
}

func init() {
	configCmd.AddCommand(explainCmd)
}
