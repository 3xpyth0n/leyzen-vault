package compose

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// PrepareSSLCertificateBundle ensures HAProxy has access to a PEM file that includes the cert and key.
func PrepareSSLCertificateBundle(
	enableHTTPS bool,
	certPath string,
	keyPath string,
	rootDir string,
	outputPath string,
) (string, []string, error) {
	if !enableHTTPS || certPath == "" {
		return "", nil, nil
	}

	warnings := []string{}

	certFile := resolvePath(certPath, rootDir)

	pemTarget := outputPath
	if pemTarget == "" {
		pemTarget = filepath.Join(rootDir, "infra", "haproxy", "haproxy.pem")
	}

	writePEM := func(target string, content string) error {
		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return fmt.Errorf("could not create directory for PEM bundle: %w", err)
		}

		if !strings.HasSuffix(content, "\n") {
			content += "\n"
		}

		if err := os.WriteFile(target, []byte(content), 0644); err != nil {
			return fmt.Errorf("could not write PEM bundle to %s: %w", target, err)
		}
		return nil
	}

	certContent, err := os.ReadFile(certFile)
	if err != nil {
		warnings = append(warnings, fmt.Sprintf("SSL certificate file is not readable: %v", err))
		return "", warnings, nil
	}
	certText := string(certContent)

	if keyPath != "" {
		keyFile := resolvePath(keyPath, rootDir)
		keyContent, err := os.ReadFile(keyFile)
		if err != nil {
			warnings = append(warnings, fmt.Sprintf("SSL key file is not readable: %v", err))
			return "", warnings, nil
		}
		keyText := string(keyContent)

		combined := strings.TrimRight(certText, "\n") + "\n" + strings.TrimSpace(keyText) + "\n"
		if err := writePEM(pemTarget, combined); err != nil {
			warnings = append(warnings, err.Error())
			return "", warnings, nil
		}
		return pemTarget, warnings, nil
	}

	if !strings.Contains(certText, "PRIVATE KEY") {
		warnings = append(warnings, "SSL certificate file must contain the private key when SSL_KEY_PATH is not provided")
		return "", warnings, nil
	}

	if certFile == pemTarget {
		return certFile, warnings, nil
	}

	if err := writePEM(pemTarget, certText); err != nil {
		warnings = append(warnings, err.Error())
		return "", warnings, nil
	}

	return pemTarget, warnings, nil
}

func resolvePath(pathStr string, rootDir string) string {
	if filepath.IsAbs(pathStr) {
		return pathStr
	}
	return filepath.Join(rootDir, pathStr)
}
