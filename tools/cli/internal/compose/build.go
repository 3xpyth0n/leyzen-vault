package compose

import (
	"fmt"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

// BuildComposeManifest generates the Docker Compose manifest
func BuildComposeManifest(
	env map[string]string,
	webContainers []string,
	sslCertBundlePath string,
	envFilePath string,
) ([]byte, error) {
	manifest := Manifest{
		Services: make(map[string]ServiceDefinition),
		Volumes:  make(map[string]VolumeDefinition),
		Networks: make(map[string]NetworkDefinition),
	}

	orchestratorEnabled := isOrchestratorEnabled(env)

	// PostgreSQL
	postgresService, err := buildPostgresService(env)
	if err != nil {
		return nil, fmt.Errorf("failed to build postgres service: %w", err)
	}
	manifest.Services[PostgresContainerName] = postgresService

	// Vault Services
	vaultServices := buildVaultServices(env, webContainers, envFilePath)
	for name, service := range vaultServices {
		manifest.Services[name] = service
	}

	// Base Services (HAProxy, Orchestrator, etc.)
	baseServices := buildBaseServices(env, webContainers, sslCertBundlePath, orchestratorEnabled, envFilePath)
	for name, service := range baseServices {
		manifest.Services[name] = service
	}

	// Volumes
	postgresVolName := getEnv(env, "POSTGRES_DATA_VOLUME", PostgresDataVolumeName)
	manifest.Volumes[postgresVolName] = VolumeDefinition{Name: "leyzen-vault-postgres-data"}

	manifest.Volumes[VaultDataSourceVolume] = VolumeDefinition{Name: "leyzen-vault-data-source"}

	manifest.Volumes["orchestrator-logs"] = VolumeDefinition{Name: "leyzen-orchestrator-logs"}

	// Networks
	manifest.Networks[VaultNetworkName] = NetworkDefinition{Driver: "bridge", Name: "leyzen-vault-net"}
	manifest.Networks[ControlNetworkName] = NetworkDefinition{Driver: "bridge", Name: "leyzen-control-net"}

	return yaml.Marshal(manifest)
}

func isOrchestratorEnabled(env map[string]string) bool {
	val := strings.ToLower(strings.TrimSpace(env["ORCHESTRATOR_ENABLED"]))
	if val == "" {
		return false
	}
	return val == "true" || val == "1" || val == "yes" || val == "on"
}

func getEnv(env map[string]string, key, defaultVal string) string {
	if val, ok := env[key]; ok && strings.TrimSpace(val) != "" {
		return strings.TrimSpace(val)
	}
	return defaultVal
}

func parsePort(env map[string]string, key string, defaultVal int) int {
	valStr := getEnv(env, key, "")
	if valStr == "" {
		return defaultVal
	}
	val, err := strconv.Atoi(valStr)
	if err != nil {
		return defaultVal
	}
	if val < 1 || val > 65535 {
		return defaultVal
	}
	return val
}

func buildPostgresService(env map[string]string) (ServiceDefinition, error) {
	db := getEnv(env, "POSTGRES_DB", "leyzen_vault")
	user := getEnv(env, "POSTGRES_USER", "leyzen")
	pass := getEnv(env, "POSTGRES_PASSWORD", "")
	port := parsePort(env, "POSTGRES_PORT", PostgresDefaultPort)
	dataVol := getEnv(env, "POSTGRES_DATA_VOLUME", PostgresDataVolumeName)

	if pass == "" {
		return ServiceDefinition{}, fmt.Errorf("POSTGRES_PASSWORD is required in environment")
	}

	return ServiceDefinition{
		Image:         "postgres:16-alpine",
		ContainerName: PostgresContainerName,
		Restart:       "on-failure",
		Environment: map[string]string{
			"POSTGRES_DB":               db,
			"POSTGRES_USER":             user,
			"POSTGRES_PASSWORD":         pass,
			"POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
		},
		Expose: []string{strconv.Itoa(port)},
		Volumes: []string{
			fmt.Sprintf("%s:/var/lib/postgresql/data", dataVol),
			"./infra/postgres/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh:ro",
		},
		HealthCheck: &HealthCheckDefinition{
			Test: []string{
				"CMD-SHELL",
				"pg_isready -U ${POSTGRES_USER:-leyzen} -d postgres || exit 1",
			},
			Interval:    "2s",
			Timeout:     "5s",
			Retries:     10,
			StartPeriod: "30s",
		},
		Networks: []string{VaultNetworkName},
	}, nil
}

func getDatabaseURI(env map[string]string) string {
	db := getEnv(env, "POSTGRES_DB", "leyzen_vault")
	user := getEnv(env, "POSTGRES_USER", "leyzen")
	pass := getEnv(env, "POSTGRES_PASSWORD", "")
	host := PostgresContainerName
	port := parsePort(env, "POSTGRES_PORT", PostgresDefaultPort)
	return fmt.Sprintf("postgresql://%s:%s@%s:%d/%s", user, pass, host, port, db)
}

func buildVaultServices(env map[string]string, containers []string, envFilePath string) map[string]ServiceDefinition {
	services := make(map[string]ServiceDefinition)
	tmpfsSizeRaw := getEnv(env, "VAULT_MAX_TOTAL_SIZE_MB", "1024")
	tmpfsSize, _ := strconv.Atoi(tmpfsSizeRaw)
	if tmpfsSize < 1 {
		tmpfsSize = 1024
	}

	for _, name := range containers {
		services[name] = ServiceDefinition{
			Build: &BuildDefinition{
				Context:    ".",
				Dockerfile: "./infra/vault/Dockerfile",
			},
			Image:         "leyzen/vault:latest",
			ContainerName: name,
			EnvFile:       []string{envFilePath},
			Restart:       "on-failure",
			HealthCheck: &HealthCheckDefinition{
				Test: []string{
					"CMD-SHELL",
					"python3 /app/infra/vault/healthcheck.py || exit 1",
				},
				Interval:    "1s",
				Timeout:     "2s",
				Retries:     1,
				StartPeriod: "3s",
			},
			Tmpfs: []string{
				fmt.Sprintf("/data:size=%dM,noexec,nosuid,nodev", tmpfsSize),
			},
			Volumes: []string{
				fmt.Sprintf("%s:/data-source:rw", VaultDataSourceVolume),
				"./src/common:/common:ro",
			},
			DependsOn: map[string]DependsOnCondition{
				HAProxyContainerName:  {Condition: "service_healthy"},
				PostgresContainerName: {Condition: "service_healthy"},
			},
			Networks:        []string{VaultNetworkName},
			StopGracePeriod: "2s",
		}
	}
	return services
}

func buildBaseServices(
	env map[string]string,
	webContainers []string,
	sslCertPath string,
	orchestratorEnabled bool,
	envFilePath string,
) map[string]ServiceDefinition {
	services := make(map[string]ServiceDefinition)

	// HAProxy
	httpPort := parsePort(env, "HTTP_PORT", 8080)
	httpsPort := parsePort(env, "HTTPS_PORT", 8443)

	haproxyPorts := []string{fmt.Sprintf("%d:80", httpPort)}
	if sslCertPath != "" {
		haproxyPorts = append(haproxyPorts, fmt.Sprintf("%d:443", httpsPort))
	}

	haproxyVols := []string{
		"./infra/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro",
		"./infra/haproxy/404.http:/usr/local/etc/haproxy/errors/404.http:ro",
		"./infra/haproxy/503.http:/usr/local/etc/haproxy/errors/503.http:ro",
	}
	if sslCertPath != "" {
		haproxyVols = append(haproxyVols, fmt.Sprintf("%s:/usr/local/etc/haproxy/ssl/cert.pem:ro", sslCertPath))
	}

	services[HAProxyContainerName] = ServiceDefinition{
		Image:         "haproxy:2.8-alpine",
		ContainerName: HAProxyContainerName,
		Restart:       "always",
		Ports:         haproxyPorts,
		Volumes:       haproxyVols,
		Networks:      []string{VaultNetworkName, ControlNetworkName},
		HealthCheck: &HealthCheckDefinition{
			Test:        []string{"CMD-SHELL", "haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg"},
			Interval:    "5s",
			Timeout:     "3s",
			Retries:     3,
			StartPeriod: "5s",
		},
	}

	// Orchestrator & Docker Proxy (only if enabled)
	if orchestratorEnabled {
		// Docker Proxy
		services["docker-proxy"] = ServiceDefinition{
			Build: &BuildDefinition{
				Context:    "./infra/docker-proxy",
				Dockerfile: "Dockerfile",
			},
			Image:         "leyzen/docker-proxy:latest",
			ContainerName: "docker-proxy",
			EnvFile:       []string{envFilePath},
			Restart:       "unless-stopped",
			Volumes: []string{
				"/var/run/docker.sock:/var/run/docker.sock:ro",
				"./src/common:/srv/common:ro",
			},
			Environment: map[string]string{
				"DOCKER_PROXY_TIMEOUT":   getEnv(env, "DOCKER_PROXY_TIMEOUT", "30"),
				"DOCKER_PROXY_LOG_LEVEL": getEnv(env, "DOCKER_PROXY_LOG_LEVEL", "INFO"),
				"ORCH_WEB_CONTAINERS":    strings.Join(webContainers, ","),
				"PYTHONPATH":             "/srv:/srv/common",
			},
			Networks: []string{ControlNetworkName},
			HealthCheck: &HealthCheckDefinition{
				Test:        []string{"CMD-SHELL", "curl -f http://localhost:2375/healthz || exit 1"},
				Interval:    "2s",
				Timeout:     "10s",
				Retries:     10,
				StartPeriod: "30s",
			},
		}

		// Orchestrator
		services["orchestrator"] = ServiceDefinition{
			Build: &BuildDefinition{
				Context:    "./src/orchestrator",
				Dockerfile: "Dockerfile",
			},
			Image:         "leyzen/orchestrator:latest",
			ContainerName: "orchestrator",
			EnvFile:       []string{envFilePath},
			Environment: map[string]string{
				"ORCH_LOG_DIR":        "/app/logs",
				"ORCH_WEB_CONTAINERS": strings.Join(webContainers, ","),
				"PYTHONPATH":          "/app:/common:/infra",
				"VAULT_DB_URI":        getDatabaseURI(env),
			},
			Restart:         "on-failure",
			StopGracePeriod: "10s",
			HealthCheck: &HealthCheckDefinition{
				Test:        []string{"CMD-SHELL", "curl -f http://localhost/orchestrator/healthz || exit 1"},
				Interval:    "2s",
				Timeout:     "5s",
				Retries:     10,
				StartPeriod: "30s",
			},
			Volumes: []string{
				"./src/orchestrator:/app:ro",
				"./src/common:/common:ro",
				"./src/vault:/infra/vault:ro",
				"orchestrator-logs:/app/logs",
				fmt.Sprintf("%s:/data-source:rw", VaultDataSourceVolume),
			},
			DependsOn: map[string]DependsOnCondition{
				"docker-proxy":        {Condition: "service_healthy"},
				PostgresContainerName: {Condition: "service_healthy"},
			},
			Networks: []string{ControlNetworkName, VaultNetworkName},
		}
	}

	return services
}
