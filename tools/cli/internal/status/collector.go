package status

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	"leyzenctl/internal"
	"syscall"
)

func parseBool(s string, def bool) bool {
	t := strings.TrimSpace(strings.ToLower(s))
	switch t {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	}
	return def
}

func collectBackupsViaApp(container string, timeout time.Duration) (int, int, string, int64) {
	script := `
import json, os, time
from vault.app import create_app
app = create_app()
with app.app_context():
    from vault.services.database_backup_service import DatabaseBackupService
    from vault.services.external_storage_config_service import ExternalStorageConfigService
    from vault.services.external_storage_service import ExternalStorageService
    secret_key = app.config.get("SECRET_KEY","")
    local_count = 0
    s3_count = 0
    s3_bytes = 0
    last_ts = None
    # Try service listing first
    try:
        if secret_key:
            svc = DatabaseBackupService(secret_key, app)
            backups = svc.list_backups()
            for b in backups or []:
                loc = str(b.get("storage_location",""))
                if loc.startswith("s3://"):
                    s3_count += 1
                    s3_bytes += int(b.get("size_bytes",0) or 0)
                else:
                    local_count += 1
                created = b.get("created_at")
                if created:
                    try:
                        from datetime import datetime
                        ts = datetime.fromisoformat(created.replace('Z','+00:00')).timestamp()
                        if (last_ts is None) or (ts>last_ts):
                            last_ts = ts
                    except Exception:
                        pass
    except Exception:
        pass
    # Local fallback scan
    if local_count == 0:
        for d in ['/data-source/backups/database','/data/backups/database']:
            try:
                for f in os.listdir(d):
                    if f.endswith('.dump') and f.startswith('backup_'):
                        local_count += 1
                        p=os.path.join(d,f)
                        ts=os.path.getmtime(p)
                        if (last_ts is None) or (ts>last_ts):
                            last_ts = ts
            except Exception:
                pass
    # S3 fallback scan via app config
    try:
        if secret_key and ExternalStorageConfigService.is_enabled(secret_key, app):
            svc_ext = ExternalStorageService(secret_key, app)
            client = svc_ext._get_client()
            cfg = svc_ext._get_config()
            bname = cfg.get('bucket_name') if cfg else None
            if client and bname:
                paginator = client.get_paginator('list_objects_v2')
                prefix='database-backups/'
                for page in paginator.paginate(Bucket=bname, Prefix=prefix):
                    for obj in page.get('Contents',[]):
                        k=obj.get('Key','')
                        if k.endswith('.dump') and k.split('/')[-1].startswith('backup_'):
                            s3_count += 1
                            s3_bytes += int(obj.get('Size',0) or 0)
                            lm=obj.get('LastModified')
                            if lm:
                                ts = getattr(lm,'timestamp',None)
                                if callable(ts):
                                    ts = ts()
                                elif isinstance(lm,str):
                                    try:
                                        from datetime import datetime
                                        ts = datetime.fromisoformat(lm.replace('Z','+00:00')).timestamp()
                                    except Exception:
                                        ts = None
                                if ts is not None and ((last_ts is None) or (ts>last_ts)):
                                    last_ts = ts
    except Exception:
        pass
    last = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(last_ts)) if last_ts else None
    print(json.dumps({"local":local_count,"s3":s3_count,"last":last,"s3_bytes":s3_bytes}))
`
	out, err := runDockerExec(container, timeout, "python3", "-c", script)
	if err != nil {
		return 0, 0, "", 0
	}
	var p struct {
		Local   int    `json:"local"`
		S3      int    `json:"s3"`
		Last    string `json:"last"`
		S3Bytes int64  `json:"s3_bytes"`
	}
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &p); err != nil {
		return 0, 0, "", 0
	}
	return p.Local, p.S3, p.Last, p.S3Bytes
}
func parseInt(s string, def int) int {
	if v, err := strconv.Atoi(strings.TrimSpace(s)); err == nil {
		return v
	}
	return def
}

func dial(addr string, timeout time.Duration) (int64, bool) {
	start := time.Now()
	conn, err := net.DialTimeout("tcp", addr, timeout)
	if err != nil {
		return int64(time.Since(start).Milliseconds()), false
	}
	_ = conn.Close()
	return int64(time.Since(start).Milliseconds()), true
}

func httpGet(url string, timeout time.Duration) (int64, int, error) {
	client := &http.Client{Timeout: timeout}
	start := time.Now()
	resp, err := client.Get(url)
	if err != nil {
		return int64(time.Since(start).Milliseconds()), 0, err
	}
	defer resp.Body.Close()
	return int64(time.Since(start).Milliseconds()), resp.StatusCode, nil
}

func cpuLoadPercent() float64 {
	b, err := os.ReadFile("/proc/loadavg")
	if err != nil {
		return 0
	}
	fields := strings.Fields(string(b))
	if len(fields) == 0 {
		return 0
	}
	val, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return 0
	}
	cpus := runtime.NumCPU()
	if cpus <= 0 {
		cpus = 1
	}
	return (val / float64(cpus)) * 100.0
}

func memUsedPercent() float64 {
	b, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0
	}
	lines := strings.Split(string(b), "\n")
	var total, available float64
	for _, ln := range lines {
		if strings.HasPrefix(ln, "MemTotal:") {
			parts := strings.Fields(ln)
			if len(parts) >= 2 {
				if v, err := strconv.ParseFloat(parts[1], 64); err == nil {
					total = v * 1024.0
				}
			}
		} else if strings.HasPrefix(ln, "MemAvailable:") {
			parts := strings.Fields(ln)
			if len(parts) >= 2 {
				if v, err := strconv.ParseFloat(parts[1], 64); err == nil {
					available = v * 1024.0
				}
			}
		}
	}
	if total <= 0 {
		return 0
	}
	used := total - available
	return (used / total) * 100.0
}

func fsStats(path string) (StorageStats, error) {
	var s StorageStats
	s.Path = path
	var st syscall.Statfs_t
	if err := syscall.Statfs(path, &st); err != nil {
		return s, err
	}
	total := int64(st.Blocks) * int64(st.Bsize)
	avail := int64(st.Bavail) * int64(st.Bsize)
	used := total - avail
	s.TotalBytes = total
	s.UsedBytes = used
	if total > 0 {
		s.Percent = float64(used) * 100.0 / float64(total)
	}
	return s, nil
}

func getServiceStatusMap(envFile string) map[string]string {
	out := make(map[string]string)
	psOutput, err := internal.DockerComposePS(envFile, "--format", "{{.Service}}\t{{.Status}}")
	if err != nil || psOutput == "" {
		return out
	}
	for _, line := range strings.Split(psOutput, "\n") {
		parts := strings.Split(line, "\t")
		if len(parts) >= 2 {
			out[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
		}
	}
	return out
}

func Collect(envFile string, timeout time.Duration) (Result, error) {
	var res Result
	env, err := internal.LoadAllEnvVariables(envFile)
	if err != nil {
		return res, err
	}

	version := os.Getenv("LEYZENCTL_VERSION")
	if version == "" {
		version = "dev"
	}
	res.Summary.Version = version
	res.Summary.Timestamp = time.Now()

	httpPort := parseInt(env["HTTP_PORT"], 8080)
	httpsPort := parseInt(env["HTTPS_PORT"], 8443)
	enableHTTPS := parseBool(env["ENABLE_HTTPS"], false)

	res.PortStats = append(res.PortStats, PortStat{Name: "HTTP", Port: httpPort, Protocol: "tcp"})
	if enableHTTPS {
		res.PortStats = append(res.PortStats, PortStat{Name: "HTTPS", Port: httpsPort, Protocol: "tcp"})
	}
	res.Performance.CPULoadPercent = cpuLoadPercent()
	res.Performance.MemoryUsedPercent = memUsedPercent()

	var endpoints []string
	webContainers, _ := resolveWebContainersForStatus(env)
	for range webContainers {
		endpoints = append(endpoints, fmt.Sprintf("http://localhost:%d/healthz", httpPort))
		break
	}

	appUp := 0
	var appEndpoints []Endpoint
	for _, url := range endpoints {
		lat, code, err := httpGet(url, timeout)
		ep := Endpoint{Name: "vault_web", Address: url, LatencyMs: lat}
		if err == nil && code == 200 {
			ep.Reachable = true
			ep.Status = "ok"
			appUp++
		} else {
			ep.Reachable = false
			ep.Status = "degraded"
			if err != nil {
				ep.Message = err.Error()
			}
		}
		appEndpoints = append(appEndpoints, ep)
	}
	res.App.Endpoints = appEndpoints
	res.App.ReplicasTotal = len(webContainers)
	res.App.ReplicasUp = appUp
	res.App.Status = "ok"
	if appUp == 0 {
		res.App.Status = "critical"
		res.App.Message = "all replicas down"
	}

	latHTTP, upHTTP := dial(fmt.Sprintf("localhost:%d", httpPort), time.Duration(timeout))
	res.Infra.HAProxyHTTPUp = upHTTP
	res.Infra.LatencyMs = latHTTP
	if enableHTTPS {
		latHTTPS, upHTTPS := dial(fmt.Sprintf("localhost:%d", httpsPort), time.Duration(timeout))
		res.Infra.HAProxyHTTPSUp = upHTTPS
		if latHTTPS > 0 {
			res.Infra.LatencyMs = latHTTPS
		}
	}
	res.Infra.Status = "ok"
	if !upHTTP {
		res.Infra.Status = "degraded"
	}

	s3Endpoint := strings.TrimSpace(env["VAULT_S3_ENDPOINT_URL"])
	s3Bucket := strings.TrimSpace(env["VAULT_S3_BUCKET_NAME"])
	useSSL := parseBool(env["VAULT_S3_USE_SSL"], true)
	res.S3.Endpoint = s3Endpoint
	res.S3.Bucket = s3Bucket
	if s3Endpoint != "" {
		host, port := parseHostPortFromURL(s3Endpoint, useSSL)
		latS3, upS3 := dial(net.JoinHostPort(host, port), time.Duration(timeout))
		res.S3.LatencyMs = latS3
		res.S3.Reachable = upS3
		res.S3.Status = "ok"
		if !upS3 {
			res.S3.Status = "degraded"
			res.S3.Message = "endpoint unreachable"
		}
	} else {
		res.S3.Status = "unknown"
		res.S3.Message = "not configured"
	}

	dbHost := strings.TrimSpace(env["POSTGRES_HOST"])
	if dbHost == "" {
		dbHost = "postgres"
	}
	dbPort := parseInt(env["POSTGRES_PORT"], 5432)
	// Prefer docker health status; fall back to TCP dial if not available
	serviceStatuses := getServiceStatusMap(envFile)
	var dbServiceStatus string
	if s, ok := serviceStatuses["postgres"]; ok {
		dbServiceStatus = s
	} else {
		// try best-effort lookup
		for k, v := range serviceStatuses {
			if strings.Contains(strings.ToLower(k), "postgres") {
				dbServiceStatus = v
				break
			}
		}
	}
	if dbServiceStatus != "" {
		lower := strings.ToLower(dbServiceStatus)
		isUp := strings.Contains(lower, "up")
		isHealthy := strings.Contains(lower, "healthy")
		res.DB.Reachable = isUp || isHealthy
		if res.DB.Reachable {
			res.DB.Status = "ok"
		} else {
			res.DB.Status = "degraded"
			res.DB.Message = dbServiceStatus
		}
		// leave latency empty for docker-based check
	} else {
		latDB, upDB := dial(net.JoinHostPort(dbHost, strconv.Itoa(dbPort)), time.Duration(timeout))
		res.DB.LatencyMs = latDB
		res.DB.Reachable = upDB
		res.DB.Status = "ok"
		if !upDB {
			res.DB.Status = "degraded"
			res.DB.Message = "unreachable"
		}
	}

	repoRoot, _ := internal.FindRepoRoot()
	dataPath := repoRoot
	st, err := fsStats(dataPath)
	if err == nil {
		res.Storage.Data = st
		res.Storage.Status = "ok"
	} else {
		res.Storage.Status = "unknown"
		res.Storage.Message = "filesystem stats unavailable"
	}

	res.Backup.Status = "unknown"
	res.Backup.Message = "metadata unavailable"

	// Container storage and backups via docker exec (vault_app preferred)
	container := detectVaultContainer(envFile)
	if container != "" {
		if cs, ok := collectContainerStorage(container, timeout); ok {
			res.Storage.Data = cs
			res.Storage.Status = "ok"
		}
		// Prefer app-aware listing for accurate summary
		lc2, sc2, last2, s3b2 := collectBackupsViaApp(container, timeout)
		if lc2 > 0 || sc2 > 0 {
			res.Backup.LocalCount = lc2
			res.Backup.S3Count = sc2
			if last2 != "" {
				res.Backup.LastSuccessAt = last2
			}
			if sc2 > 0 {
				res.S3.ObjectCount = sc2
			}
			if s3b2 > 0 {
				res.S3.TotalBytes = s3b2
			}
		} else {
			// Fallback to raw scans
			lc, lts := collectLocalBackups(container, timeout)
			res.Backup.LocalCount = lc
			if lts != "" {
				res.Backup.LastSuccessAt = lts
			}
			sc, s3bytes, s3last := collectS3Backups(container, timeout)
			res.Backup.S3Count = sc
			if sc > 0 {
				res.S3.ObjectCount = sc
			}
			if s3bytes > 0 {
				res.S3.TotalBytes = s3bytes
			}
			if s3last != "" {
				res.S3.LastBackupAt = s3last
				if res.Backup.LastSuccessAt == "" {
					res.Backup.LastSuccessAt = s3last
				}
			}
		}
		if res.Backup.LocalCount > 0 || res.Backup.S3Count > 0 {
			res.Backup.Status = "ok"
			res.Backup.Message = ""
		}
	}

	overall := "ok"
	var critical []string
	if res.App.Status == "critical" {
		overall = "critical"
		critical = append(critical, "app")
	}
	if res.DB.Status == "degraded" && overall != "critical" {
		overall = "degraded"
	}
	res.Summary.OverallStatus = overall
	res.Summary.CriticalFailures = critical

	{
		ps, _ := internal.GetProjectStatuses(envFile)
		for _, s := range ps {
			res.Containers = append(res.Containers, ContainerStatus{
				Name:   s.Name,
				Status: s.Status,
				Age:    s.Age,
			})
		}
	}

	return res, nil
}

func MarshalJSON(res Result) ([]byte, error) {
	return json.MarshalIndent(res, "", "  ")
}

func resolveWebContainersForStatus(env map[string]string) ([]string, string) {
	if strings.TrimSpace(env["ORCHESTRATOR_ENABLED"]) == "true" {
		val := strings.TrimSpace(env["ORCH_WEB_CONTAINERS"])
		if val != "" {
			names := strings.Split(val, ",")
			var out []string
			for _, n := range names {
				n = strings.TrimSpace(n)
				if n != "" {
					out = append(out, n)
				}
			}
			if len(out) > 0 {
				return out, val
			}
		}
		replicas := parseInt(env["WEB_REPLICAS"], 3)
		var names []string
		for i := 0; i < replicas; i++ {
			names = append(names, fmt.Sprintf("vault_web%d", i+1))
		}
		return names, strings.Join(names, ",")
	}
	return []string{"vault_app"}, "vault_app"
}

func runDockerExec(container string, timeout time.Duration, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, "docker", append([]string{"exec", container}, args...)...)
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(out), nil
}

func detectVaultContainer(envFile string) string {
	m := getServiceStatusMap(envFile)
	if _, ok := m["vault_app"]; ok {
		return "vault_app"
	}
	for name := range m {
		if strings.HasPrefix(name, "vault_web") {
			return name
		}
	}
	return ""
}

func collectContainerStorage(container string, timeout time.Duration) (StorageStats, bool) {
	out, err := runDockerExec(container, timeout, "python3", "-c",
		"import shutil,json; t,u,f=shutil.disk_usage('/data'); print(json.dumps({'total':t,'used':u,'free':f}))")
	if err != nil {
		return StorageStats{}, false
	}
	type payload struct {
		Total int64 `json:"total"`
		Used  int64 `json:"used"`
		Free  int64 `json:"free"`
	}
	var p payload
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &p); err != nil {
		return StorageStats{}, false
	}
	return StorageStats{Path: "/data", UsedBytes: p.Used, TotalBytes: p.Total, Percent: percent(p.Used, p.Total)}, true
}

func percent(used, total int64) float64 {
	if total <= 0 {
		return 0
	}
	return float64(used) * 100.0 / float64(total)
}

func collectLocalBackups(container string, timeout time.Duration) (int, string) {
	out, err := runDockerExec(container, timeout, "python3", "-c",
		"import os,json,time; dirs=['/data-source/backups/database','/data/backups/database']; files=[];"+
			"\\n"+`
for d in dirs:
    try:
        for f in os.listdir(d):
            if f.endswith('.dump'):
                files.append((os.path.join(d,f), os.path.getmtime(os.path.join(d,f))))
    except Exception:
        pass
cnt=len(files)
latest=None
if files:
    latest_ts=max(files, key=lambda x:x[1])[1]
    latest=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(latest_ts))
print(json.dumps({'count':cnt,'latest':latest}))`)
	if err != nil {
		return 0, ""
	}
	var p struct {
		Count  int    `json:"count"`
		Latest string `json:"latest"`
	}
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &p); err != nil {
		return 0, ""
	}
	return p.Count, p.Latest
}

func collectS3Backups(container string, timeout time.Duration) (int, int64, string) {
	out, err := runDockerExec(container, timeout, "python3", "-c",
		"import json,os; import boto3; from botocore.config import Config;"+
			"e=os.environ.get('VAULT_S3_ENDPOINT_URL'); b=os.environ.get('VAULT_S3_BUCKET_NAME');"+
			"ak=os.environ.get('VAULT_S3_ACCESS_KEY_ID'); sk=os.environ.get('VAULT_S3_SECRET_ACCESS_KEY');"+
			"rg=os.environ.get('VAULT_S3_REGION','auto'); use_ssl=os.environ.get('VAULT_S3_USE_SSL','true').lower() in ('1','true','yes');"+
			"if not e or not b or not ak or not sk: print(json.dumps({'count':0,'bytes':0,'latest':None})); exit(0);"+
			"cfg={'region_name':rg};"+
			"if e: cfg['endpoint_url']=e;"+
			"client=boto3.client('s3',**cfg,aws_access_key_id=ak,aws_secret_access_key=sk,config=Config(s3={'addressing_style':'path'}));"+
			"prefix='database-backups/';"+
			"paginator=client.get_paginator('list_objects_v2');"+
			"names=set(); bytes=0; latest=None;"+
			"for page in paginator.paginate(Bucket=b, Prefix=prefix):"+
			"  for obj in page.get('Contents',[]):"+
			"    k=obj['Key'];"+
			"    fname=k.split('/')[-1];"+
			"    if fname.startswith('backup_') and (fname.endswith('.dump') or fname.endswith('.metadata.json')):"+
			"      base=fname.split('.')[0];"+
			"      names.add(base);"+
			"      if fname.endswith('.dump'): bytes+=obj.get('Size',0);"+
			"      lm=obj.get('LastModified');"+
			"      if lm and (latest is None or lm>latest): latest=lm;"+
			"print(json.dumps({'count':len(names),'bytes':bytes,'latest':latest.isoformat() if latest else None}))")
	if err != nil {
		return 0, 0, ""
	}
	var p struct {
		Count  int    `json:"count"`
		Bytes  int64  `json:"bytes"`
		Latest string `json:"latest"`
	}
	if err := json.Unmarshal([]byte(strings.TrimSpace(out)), &p); err != nil {
		return 0, 0, ""
	}
	return p.Count, p.Bytes, p.Latest
}
func parseHostPortFromURL(raw string, ssl bool) (string, string) {
	u := strings.TrimSpace(raw)
	u = strings.TrimPrefix(u, "http://")
	u = strings.TrimPrefix(u, "https://")
	host := u
	port := "443"
	if !ssl {
		port = "80"
	}
	if idx := strings.Index(host, "/"); idx != -1 {
		host = host[:idx]
	}
	if strings.Contains(host, ":") {
		parts := strings.Split(host, ":")
		host = parts[0]
		port = parts[1]
	}
	return host, port
}
