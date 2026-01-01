package status

import "time"

type Summary struct {
	OverallStatus    string            `json:"overall_status"`
	Timestamp        time.Time         `json:"timestamp"`
	Version          string            `json:"version"`
	CriticalFailures []string          `json:"critical_failures"`
	Meta             map[string]string `json:"meta,omitempty"`
}

type Endpoint struct {
	Name      string            `json:"name"`
	Address   string            `json:"address"`
	LatencyMs int64             `json:"latency_ms"`
	Reachable bool              `json:"reachable"`
	Status    string            `json:"status"`
	Message   string            `json:"message,omitempty"`
	Extra     map[string]string `json:"extra,omitempty"`
}

type AppSection struct {
	ReplicasTotal int        `json:"replicas_total"`
	ReplicasUp    int        `json:"replicas_up"`
	Endpoints     []Endpoint `json:"endpoints"`
	Status        string     `json:"status"`
	Message       string     `json:"message,omitempty"`
}

type S3Section struct {
	Endpoint     string `json:"endpoint"`
	Bucket       string `json:"bucket"`
	Reachable    bool   `json:"reachable"`
	LatencyMs    int64  `json:"latency_ms"`
	ObjectCount  int    `json:"object_count"`
	TotalBytes   int64  `json:"total_bytes"`
	LastBackupAt string `json:"last_backup_at,omitempty"`
	Status       string `json:"status"`
	Message      string `json:"message,omitempty"`
}

type BackupSection struct {
	LastSuccessAt     string `json:"last_success_at,omitempty"`
	LastDurationMs    int64  `json:"last_duration_ms,omitempty"`
	LastArtifactSizeB int64  `json:"last_artifact_size_bytes,omitempty"`
	LocalCount        int    `json:"local_count"`
	S3Count           int    `json:"s3_count"`
	Status            string `json:"status"`
	Message           string `json:"message,omitempty"`
}

type DBSection struct {
	Reachable bool   `json:"reachable"`
	LatencyMs int64  `json:"latency_ms"`
	Status    string `json:"status"`
	Message   string `json:"message,omitempty"`
}

type InfraSection struct {
	HAProxyHTTPUp  bool   `json:"haproxy_http_up"`
	HAProxyHTTPSUp bool   `json:"haproxy_https_up"`
	LatencyMs      int64  `json:"latency_ms"`
	Status         string `json:"status"`
	Message        string `json:"message,omitempty"`
}

type StorageStats struct {
	Path       string  `json:"path"`
	UsedBytes  int64   `json:"used_bytes"`
	TotalBytes int64   `json:"total_bytes"`
	Percent    float64 `json:"percent"`
}

type StorageSection struct {
	Data    StorageStats `json:"data_dir"`
	Status  string       `json:"status"`
	Message string       `json:"message,omitempty"`
}

type PortStat struct {
	Name     string `json:"name"`
	Port     int    `json:"port"`
	Protocol string `json:"protocol"`
}

type PerformanceStats struct {
	CPULoadPercent    float64 `json:"cpu_load_percent"`
	MemoryUsedPercent float64 `json:"memory_used_percent"`
}

type Result struct {
	Summary     Summary           `json:"summary"`
	App         AppSection        `json:"app"`
	S3          S3Section         `json:"s3"`
	Backup      BackupSection     `json:"backup"`
	DB          DBSection         `json:"db"`
	Infra       InfraSection      `json:"infra"`
	Storage     StorageSection    `json:"storage"`
	Containers  []ContainerStatus `json:"containers"`
	PortStats   []PortStat        `json:"port_stats,omitempty"`
	Performance PerformanceStats  `json:"performance,omitempty"`
}

type ContainerStatus struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	Age    string `json:"age"`
}
