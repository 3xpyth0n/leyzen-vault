package status

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"

	"leyzenctl/internal"

	"github.com/fatih/color"
)

func row(w io.Writer, width int, s string) {
	p := internal.PadRightVisible(s, width-4)
	fmt.Fprintf(w, "│ %s │\n", p)
}

func rowSplit(w io.Writer, width int, left, right string) {
	content := width - 4
	lv := internal.VisibleLen(left)
	rv := internal.VisibleLen(right)
	space := content - lv - rv
	if space < 1 {
		space = 1
	}
	fmt.Fprintf(w, "│ %s%s%s │\n", left, strings.Repeat(" ", space), right)
}

func rowHeader(w io.Writer, width int, left, center, right string) {
	content := width - 4
	lv := internal.VisibleLen(left)
	cv := internal.VisibleLen(center)
	rv := internal.VisibleLen(right)
	centerStart := (content - cv) / 2
	spaceAfterLeft := centerStart - lv
	if spaceAfterLeft < 1 {
		spaceAfterLeft = 1
	}
	maxSpaceAfterLeft := content - (lv + cv + rv) - 1
	if maxSpaceAfterLeft < 1 {
		maxSpaceAfterLeft = 1
	}
	if spaceAfterLeft > maxSpaceAfterLeft {
		spaceAfterLeft = maxSpaceAfterLeft
	}
	spaceBeforeRight := content - (lv + spaceAfterLeft + cv + rv)
	if spaceBeforeRight < 1 {
		spaceBeforeRight = 1
	}
	fmt.Fprintf(w, "│ %s%s%s%s%s │\n",
		left,
		strings.Repeat(" ", spaceAfterLeft),
		center,
		strings.Repeat(" ", spaceBeforeRight),
		right,
	)
}

func wrapSingle(s string, width int) []string {
	if internal.VisibleLen(s) <= width {
		return []string{s}
	}
	var lines []string
	current := ""
	for _, word := range strings.Fields(s) {
		sep := ""
		if current != "" {
			sep = " "
		}
		next := current + sep + word
		if internal.VisibleLen(next) > width {
			if current != "" {
				lines = append(lines, current)
				current = word
				if internal.VisibleLen(current) > width {
					// Hard cut if single word exceeds width
					runes := []rune(current)
					if len(runes) > width {
						lines = append(lines, string(runes[:width]))
						current = string(runes[width:])
						continue
					}
				}
			} else {
				runes := []rune(word)
				if len(runes) > width {
					lines = append(lines, string(runes[:width]))
					current = string(runes[width:])
				} else {
					current = word
				}
			}
		} else {
			current = next
		}
	}
	if current != "" {
		lines = append(lines, current)
	}
	return lines
}

func wrapLines(inputs []string, width int) []string {
	var out []string
	for _, s := range inputs {
		for _, ln := range wrapSingle(s, width) {
			out = append(out, ln)
		}
	}
	return out
}

func grid3(w io.Writer, width int, colsA, colsB, colsC []string) {
	contentWidth := width - 4
	sepCount := 2
	colWidth := (contentWidth - sepCount) / 3
	colsA = wrapLines(colsA, colWidth)
	colsB = wrapLines(colsB, colWidth)
	colsC = wrapLines(colsC, colWidth)
	maxLines := len(colsA)
	if len(colsB) > maxLines {
		maxLines = len(colsB)
	}
	if len(colsC) > maxLines {
		maxLines = len(colsC)
	}
	for i := 0; i < maxLines; i++ {
		a := ""
		b := ""
		c := ""
		if i < len(colsA) {
			a = colsA[i]
		}
		if i < len(colsB) {
			b = colsB[i]
		}
		if i < len(colsC) {
			c = colsC[i]
		}
		left := internal.PadRightVisible(a, colWidth)
		mid := internal.PadRightVisible(b, colWidth)
		right := internal.PadRightVisible(c, colWidth)
		fmt.Fprintf(w, "│ %s│%s│%s │\n", left, mid, right)
	}
}

func badge(s string) string {
	switch s {
	case "ok":
		return color.HiGreenString("OK")
	case "degraded":
		return color.HiYellowString("DEGRADED")
	case "critical":
		return color.HiRedString("CRITICAL")
	default:
		return color.HiBlueString(strings.ToUpper(s))
	}
}

func RenderHuman(w io.Writer, r Result) {
	left := color.HiCyanString("Leyzen Vault")
	center := fmt.Sprintf("%s %s", "Cluster Status:", badge(r.Summary.OverallStatus))
	right := color.HiMagentaString("Version: " + r.Summary.Version)
	width := 72
	fmt.Fprintln(w, "┌"+strings.Repeat("─", width-2)+"┐")
	rowHeader(w, width, left, center, right)
	fmt.Fprintln(w, "├"+strings.Repeat("─", width-2)+"┤")

	row(w, width, color.HiCyanString("Containers"))
	if len(r.Containers) > 0 {
		header := "  " +
			internal.PadRightVisible("Service", 18) + " " +
			internal.PadRightVisible("Status", 28) + " " +
			internal.PadRightVisible("Age", 12)
		row(w, width, header)
		for _, c := range r.Containers {
			line := "  " +
				internal.PadRightVisible(c.Name, 18) + " " +
				internal.PadRightVisible(internal.FormatStatusColor(c.Status), 28) + " " +
				internal.PadRightVisible(c.Age, 12)
			row(w, width, line)
		}
	} else {
		row(w, width, "  No services found")
	}
	fmt.Fprintln(w, "├"+strings.Repeat("─", width-2)+"┤")

	var proxyLines []string
	proxyLines = append(proxyLines, color.HiCyanString("Proxy"))
	proxyLines = append(proxyLines, fmt.Sprintf("HTTP %t", r.Infra.HAProxyHTTPUp))
	proxyLines = append(proxyLines, fmt.Sprintf("HTTPS %t", r.Infra.HAProxyHTTPSUp))
	if r.Infra.LatencyMs > 0 {
		proxyLines = append(proxyLines, fmt.Sprintf("Latency %dms", r.Infra.LatencyMs))
	}

	var portsLines []string
	portsLines = append(portsLines, color.HiCyanString("Network Ports"))
	if len(r.PortStats) == 0 {
		portsLines = append(portsLines, "none")
	} else {
		for _, p := range r.PortStats {
			portsLines = append(portsLines, fmt.Sprintf("%s %d/%s", p.Name, p.Port, p.Protocol))
		}
	}

	var perfLines []string
	perfLines = append(perfLines, color.HiCyanString("Server Performance"))
	perfLines = append(perfLines, fmt.Sprintf("CPU %0.1f%%", r.Performance.CPULoadPercent))
	perfLines = append(perfLines, fmt.Sprintf("Memory %0.1f%%", r.Performance.MemoryUsedPercent))

	grid3(w, width, proxyLines, portsLines, perfLines)

	fmt.Fprintln(w, "└"+strings.Repeat("─", width-2)+"┘")
}

func RenderJSON(w io.Writer, r Result) error {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(w, string(b))
	return err
}

func humanGB(b int64) string {
	if b <= 0 {
		return "0 GB"
	}
	gb := float64(b) / 1_000_000_000.0
	return fmt.Sprintf("%0.2f GB", gb)
}

func shortenURL(u string) string {
	s := strings.TrimSpace(u)
	s = strings.TrimPrefix(s, "https://")
	s = strings.TrimPrefix(s, "http://")
	if i := strings.IndexByte(s, '/'); i >= 0 {
		return s[:i]
	}
	return s
}
