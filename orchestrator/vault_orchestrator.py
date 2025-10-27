#!/usr/bin/python3

import time
import random
import traceback
from datetime import datetime, timedelta
from threading import Thread
import logging
import json
from typing import Any, Dict, Optional
from flask import (
    Flask,
    render_template,
    send_from_directory,
    jsonify,
    request,
    redirect,
    url_for,
    session,
    abort,
)
from functools import wraps
import os
import signal
import sys
import pytz
from collections import defaultdict, deque
import requests

from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf

# ------------------------------
# Timezone
# ------------------------------
LOCAL_TZ = pytz.timezone(os.getenv("TIMEZONE", "UTC"))

# ------------------------------
# Environment
# ------------------------------
WEB_CONTAINERS = os.environ.get("VAULT_WEB_CONTAINERS").split(",")
USERNAME = os.environ.get("VAULT_USER", "admin")
PASSWORD = os.environ.get("VAULT_PASS", None)

# Ensure required vars
required_vars = ["VAULT_USER", "VAULT_PASS", "VAULT_SECRET_KEY", "DOCKER_PROXY_TOKEN"]
for var in required_vars:
    if not os.environ.get(var):
        raise EnvironmentError(f"Missing {var} variable in .env")

# ------------------------------
# Paths
# ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "vault_orchestrator.log")
HTML_DIR = os.path.join(os.path.dirname(__file__))

# ------------------------------
# Docker proxy / rotation config
# ------------------------------


class DockerProxyError(RuntimeError):
    """Base error for controlled Docker proxy failures."""


class DockerProxyNotFound(DockerProxyError):
    """Raised when a container is not present on the proxy side."""


class DockerProxyClient:
    """Minimal wrapper around the docker-proxy API with ACL enforcement."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or "http://docker-proxy:2375").rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        request_timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = self._session.request(
                method,
                url,
                timeout=request_timeout,
                headers=headers,
                **kwargs,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise DockerProxyError(
                f"Failed to reach docker proxy at {self.base_url}: {exc}"
            ) from exc

        if response.status_code == 404:
            raise DockerProxyNotFound(f"Container not found for path {path}")

        if not response.ok:
            raise DockerProxyError(
                f"Proxy error {response.status_code}: {response.text.strip()}"
            )

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise DockerProxyError("Invalid JSON received from proxy") from exc

    def inspect(self, name: str) -> Dict[str, Any]:
        data = self._request("GET", f"containers/{name}/json")
        if not isinstance(data, dict):
            data = {}

        state = data.get("State", {}).get("Status")
        return {"status": state, "attrs": data}

    def start(self, name: str) -> None:
        self._request("POST", f"containers/{name}/start")

    def stop(self, name: str, timeout: Optional[int] = None) -> None:
        params = {"t": timeout} if timeout is not None else None
        self._request("POST", f"containers/{name}/stop", params=params)

    def wait(self, name: str, timeout: Optional[int] = None) -> None:
        request_timeout = timeout if timeout is not None else self.timeout
        self._request("POST", f"containers/{name}/wait", timeout=request_timeout)

    def unpause(self, name: str) -> None:
        self._request("POST", f"containers/{name}/unpause")


class ProxyContainer:
    """Container facade backed by DockerProxyClient responses."""

    def __init__(self, client: DockerProxyClient, name: str, payload: Dict[str, Any]):
        self._client = client
        self.name = name
        self._payload = payload

    def reload(self) -> None:
        self._payload = self._client.inspect(self.name)

    @property
    def status(self) -> Optional[str]:
        status = self._payload.get("status")
        if status:
            return status
        attrs = self.attrs
        if isinstance(attrs, dict):
            return attrs.get("State", {}).get("Status")
        return None

    @property
    def attrs(self) -> Dict[str, Any]:
        attrs = self._payload.get("attrs")
        if isinstance(attrs, dict):
            return attrs
        return {}

    def start(self) -> None:
        self._client.start(self.name)
        self.reload()

    def stop(self, timeout: Optional[int] = None) -> None:
        self._client.stop(self.name, timeout=timeout)
        self.reload()

    def wait(self, timeout: Optional[int] = None) -> None:
        self._client.wait(self.name, timeout=timeout)

    def unpause(self) -> None:
        self._client.unpause(self.name)
        self.reload()


client = DockerProxyClient(
    base_url=os.environ.get("DOCKER_PROXY_URL"),
    token=os.environ.get("DOCKER_PROXY_TOKEN"),
)
web_containers = [c.strip() for c in WEB_CONTAINERS if c.strip()]
interval = int(str(os.environ.get("VAULT_ROTATION_INTERVAL", "90")).strip('"'))

rotation_count = 0
rotation_active = True  # default: running
rotation_resuming = False
last_active_container = None
stop_requested = False
last_rotation_time = None
next_rotation_eta = None

container_total_active_seconds = {name: 0 for name in web_containers}
container_active_since = {name: None for name in web_containers}


# ------------------------------
# Logging
# ------------------------------
def log(msg):
    timestamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def handle_shutdown(sig, frame):
    log(f"=== Orchestrator stopped (signal {sig}) ===")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# ------------------------------
# Docker helpers
# ------------------------------
def get_container_safe(name):
    try:
        payload = client.inspect(name)
        return ProxyContainer(client, name, payload)
    except DockerProxyNotFound:
        log(f"[ERROR] Container {name} not found")
        return None
    except DockerProxyError as e:
        log(f"[ERROR] Error getting container {name}: {e}")
        return None


def wait_until_healthy(container, check_interval=2, log_interval=30):
    last_log = time.time()
    name = getattr(container, "name", "<unknown>")

    while True:
        try:
            container.reload()
        except DockerProxyNotFound:
            log(f"[WAIT ERROR] Container {name} disappeared during warmup")
            return False
        except DockerProxyError as e:
            log(f"[WAIT ERROR] Failed to reload {name}: {e}")
            time.sleep(check_interval)
            continue

        health = container.attrs.get("State", {}).get("Health", {}).get("Status")
        status = container.status

        if status == "running" and (health is None or health == "healthy"):
            return True

        if status in {"exited", "dead"}:
            log(
                f"[WAIT ERROR] {name} stopped while warming up (status={status}, health={health})"
            )
            return False

        now = time.time()
        if now - last_log >= log_interval:
            log(
                f"[WAIT] Waiting for {name} to become healthy "
                f"(status={status}, health={health})"
            )
            last_log = now

        time.sleep(check_interval)


def mark_active(name):
    container_active_since[name] = datetime.now(LOCAL_TZ)


def accumulate_and_clear_active(name):
    start_ts = container_active_since.get(name)
    if not start_ts:
        return 0
    if start_ts:
        elapsed = int((datetime.now(LOCAL_TZ) - start_ts).total_seconds())
        container_total_active_seconds[name] = (
            container_total_active_seconds.get(name, 0) + elapsed
        )
        container_active_since[name] = None
        return elapsed


def stop_container(name, reason=None, timeout=30):
    cont = get_container_safe(name)
    if not cont:
        return False

    try:
        cont.reload()
    except DockerProxyError as e:
        log(f"[STOP ERROR] Failed to reload {name} before stop: {e}")

    status = getattr(cont, "status", None)
    if status == "paused":
        try:
            cont.unpause()
            cont.reload()
            status = cont.status
        except DockerProxyError as e:
            log(f"[STOP ERROR] Failed to unpause {name}: {e}")

    if status not in ("running", "restarting"):
        return False

    try:
        cont.stop(timeout=timeout)
        try:
            cont.wait(timeout=timeout)
        except DockerProxyError:
            # `wait` may fail for some drivers once the container is stopped – best effort only.
            pass
        log_reason = f" ({reason})" if reason else ""
        log(f"[ACTION] Stopped {name}{log_reason}")
        return True
    except Exception as e:
        log(f"[STOP ERROR] Failed to stop {name}: {e}")
        return False


def start_container(name, reason=None):
    cont = get_container_safe(name)
    if not cont:
        return None

    try:
        cont.reload()
    except DockerProxyError as e:
        log(f"[START ERROR] Failed to reload {name} before start: {e}")

    status = getattr(cont, "status", None)
    if status == "paused":
        try:
            cont.unpause()
            cont.reload()
            status = cont.status
        except DockerProxyError as e:
            log(f"[START ERROR] Failed to unpause {name}: {e}")

    if status == "running":
        return cont

    try:
        cont.start()
        log_reason = f" ({reason})" if reason else ""
        log(f"[ACTION] Started {name}{log_reason}")
    except Exception as e:
        log(f"[START ERROR] Failed to start {name}: {e}")
        return None

    # Reload to provide an up-to-date handle
    return get_container_safe(name)


def ensure_single_active(active_name, managed_names):
    for name in managed_names:
        if name == active_name:
            continue
        cont = get_container_safe(name)
        if cont and cont.status == "running":
            stop_container(name, reason="enforcing single active container")


# ------------------------------
# In-memory password hash
# ------------------------------
if not PASSWORD:
    raise EnvironmentError("VAULT_PASS must be set to initialize password hash.")
PASSWORD_HASH = generate_password_hash(PASSWORD)
# Remove plain text password and save the hash
del PASSWORD


TRUSTED_PROXY_IPS = {
    ip.strip()
    for ip in os.environ.get("TRUSTED_PROXY_IPS", "").split(",")
    if ip.strip()
}


def verify_credentials(username, password):
    if username != USERNAME:
        return False
    try:
        return check_password_hash(PASSWORD_HASH, password)
    except Exception:
        log("[ERROR] check_password_hash failure")
        return False


# ------------------------------
# Anti-bruteforce system (5 tries / 5 min per IP)
# ------------------------------
login_attempts = defaultdict(lambda: deque(maxlen=10))  # store timestamps per IP
MAX_ATTEMPTS = 5
BLOCK_WINDOW = timedelta(minutes=5)


def is_blocked(ip, current_time=None):
    attempts = login_attempts[ip]
    now = current_time or datetime.now()
    # remove old attempts
    while attempts and now - attempts[0] > BLOCK_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_ATTEMPTS


def register_failed_attempt(ip, attempt_time=None):
    login_attempts[ip].append(attempt_time or datetime.now())


def get_client_ip():
    remote_addr = request.remote_addr

    if remote_addr in TRUSTED_PROXY_IPS:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

    return remote_addr


# ------------------------------
# Orchestrator loop (rotation)
# ------------------------------
def orchestrator_loop():
    global rotation_count, last_rotation_time, last_active_container, next_rotation_eta
    if not web_containers:
        log("[WARN] No web containers configured for rotation.")
        return

    managed_containers = []
    for name in web_containers:
        if get_container_safe(name):
            managed_containers.append(name)
        else:
            log(f"[ERROR] Container {name} declared but not found. It will be skipped.")

    # randomize the baseline order so we don't bias toward the first declared entry
    if len(managed_containers) > 1:
        random.shuffle(managed_containers)

    if not managed_containers:
        log("[ERROR] No valid container found to manage.")
        return

    # --- Clean startup: stop all containers to ensure single active ---
    log("[INIT] Stopping all containers before rotation startup...")
    for name in managed_containers:
        stop_container(name, reason="initial cleanup")

    # choose an initial active container that can become healthy
    active_index = None
    active_name = None
    for idx, name in enumerate(managed_containers):
        candidate = start_container(name, reason="initial activation")
        if not candidate:
            continue
        if wait_until_healthy(candidate):
            active_index = idx
            active_name = name
            break
        else:
            log(
                f"[WARNING] {name} failed to reach a healthy state during startup — stopping container."
            )
            stop_container(name, reason="failed startup health check")

    if active_name is None:
        log("[ERROR] Unable to find a healthy container to start rotation.")
        return

    ensure_single_active(active_name, managed_containers)
    mark_active(active_name)
    last_active_container = active_name

    rotation_count = 0
    last_rotation_time = datetime.now(LOCAL_TZ)
    log(f"Initial rotation: {active_name} active")

    next_switch_time = datetime.now(LOCAL_TZ) + timedelta(seconds=interval)
    next_rotation_eta = interval
    while True:
        try:
            now = datetime.now(LOCAL_TZ)

            if rotation_resuming:
                next_switch_time = now + timedelta(seconds=interval)
                next_rotation_eta = None
                time.sleep(1)
                continue

            if not rotation_active:
                next_switch_time = now + timedelta(seconds=interval)
                next_rotation_eta = None
                time.sleep(1)
                continue

            remaining = (next_switch_time - now).total_seconds()
            next_rotation_eta = max(0, int(remaining))
            if now < next_switch_time:
                time.sleep(1)
                continue

            if len(managed_containers) == 1:
                next_switch_time = now + timedelta(seconds=interval)
                next_rotation_eta = interval
                continue

            rotated = False
            total_containers = len(managed_containers)
            candidate_indices = [
                idx for idx in range(total_containers) if idx != active_index
            ]
            random.shuffle(candidate_indices)

            for next_index in candidate_indices:
                next_name = managed_containers[next_index]

                released = stop_container(
                    active_name, reason="releasing shared database for rotation"
                )
                elapsed = accumulate_and_clear_active(active_name)
                if elapsed > 0:
                    total_s = container_total_active_seconds.get(active_name, 0)
                    log(
                        f"Accumulated {elapsed}s for {active_name} (total={total_s}s) before rotation"
                    )

                if not released:
                    log(
                        f"[WARNING] Failed to stop {active_name} prior to rotation; will retry later."
                    )
                    mark_active(active_name)
                    time.sleep(2)
                    continue

                next_cont = start_container(next_name, reason="preparing for rotation")
                if not next_cont:
                    restore = start_container(
                        active_name, reason="restoring active after failed candidate"
                    )
                    if restore and wait_until_healthy(restore):
                        mark_active(active_name)
                        ensure_single_active(active_name, managed_containers)
                    else:
                        log(
                            f"[ERROR] Unable to restart {active_name} after {next_name} failed to launch."
                        )
                    continue

                if not wait_until_healthy(next_cont):
                    log(
                        f"[WARNING] {next_name} failed to reach a healthy state — stopping container."
                    )
                    stop_container(next_name, reason="failed rotation health check")
                    restore = start_container(
                        active_name, reason="restoring active after failed candidate"
                    )
                    if restore and wait_until_healthy(restore):
                        mark_active(active_name)
                        ensure_single_active(active_name, managed_containers)
                    else:
                        log(
                            f"[ERROR] Unable to restore {active_name} after unhealthy rotation candidate {next_name}."
                        )
                    continue

                log(
                    f"{next_name} marked ACTIVE at {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}"
                )
                mark_active(next_name)
                active_name = next_name
                active_index = next_index
                ensure_single_active(active_name, managed_containers)

                rotation_count += 1
                last_rotation_time = datetime.now(LOCAL_TZ)
                next_rotation_eta = interval
                last_active_container = active_name

                log(f"Rotation #{rotation_count}: {active_name} is now active")
                rotated = True
                break

            if not rotated:
                log(
                    f"[WARNING] Rotation skipped — no healthy candidates available. {active_name} remains active."
                )

            next_switch_time = datetime.now(LOCAL_TZ) + timedelta(seconds=interval)
            next_rotation_eta = interval
        except Exception:
            log(f"Exception in orchestrator loop:\n{traceback.format_exc()}")
            time.sleep(5)


def uptime_tracker_loop():
    while True:
        try:
            now = datetime.now(LOCAL_TZ)

            for name in web_containers:
                cont = get_container_safe(name)
                if not cont:
                    continue

                try:
                    cont.reload()
                except DockerProxyError as e:
                    log(f"[UPTIME ERROR] Failed to reload {name}: {e}")
                    continue

                status = cont.status
                health = cont.attrs.get("State", {}).get("Health", {}).get("Status")

                # Case 1 — container is healthy
                if status == "running" and (health is None or health == "healthy"):
                    if not container_active_since.get(name):
                        container_active_since[name] = now

                # Case 2 — container is not healthy
                else:
                    if container_active_since.get(name):
                        elapsed = int(
                            (now - container_active_since[name]).total_seconds()
                        )
                        container_total_active_seconds[name] = (
                            container_total_active_seconds.get(name, 0) + elapsed
                        )
                        log(
                            f"[UPTIME] {name} paused (+{elapsed}s, total={container_total_active_seconds[name]}s)"
                        )
                        container_active_since[name] = None

            time.sleep(1)
        except Exception as e:
            log(f"[UPTIME TRACKER ERROR] {e}")
            time.sleep(2)


# ------------------------------
# Flask app + CSRF + session cookies
# ------------------------------
app = Flask(__name__, template_folder=HTML_DIR, static_folder=HTML_DIR)
app.secret_key = os.environ.get("VAULT_SECRET_KEY")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # ↩️ pass to True when HTTPS
)

# CSRF
csrf = CSRFProtect(app)

logging.getLogger("werkzeug").setLevel(logging.ERROR)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/orchestrator/login", methods=["GET", "POST"])
def login():
    error = None

    client_ip = get_client_ip()

    if request.method == "POST":
        # Check if IP is temporarily blocked
        if is_blocked(client_ip):
            log(f"[AUTH BLOCKED] Too many attempts from {client_ip}")
            error = "Too many attempts, try again later."
            return render_template("login.html", error=error), 429

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if verify_credentials(username, password):
            session["logged_in"] = True
            session.permanent = False
            log(f"[AUTH SUCCESS] {username} from {client_ip}")
            return redirect(request.args.get("next") or url_for("dashboard"))
        else:
            register_failed_attempt(client_ip)
            log(f"[AUTH FAIL] login attempt for user={username} from {client_ip}")
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/orchestrator/logout", methods=["GET"])
def logout():
    session["logged_in"] = False
    return redirect(url_for("login"))


@app.route("/orchestrator", strict_slashes=False)
@login_required
def dashboard():
    vault_rotation_interval = int(os.getenv("VAULT_ROTATION_INTERVAL", "90"))
    return render_template(
        "index.html",
        vault_rotation_interval=vault_rotation_interval,
        csrf_token=generate_csrf(),
    )


@app.route("/orchestrator/api/control", methods=["POST"])
@login_required
def api_control():
    global rotation_active

    # Try to parse JSON
    try:
        data = request.get_json(force=True)
    except Exception:
        log("[CONTROL ERROR] Invalid JSON body received")
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

    action = (data.get("action") or "").strip().lower()

    # Guard rails (server-side logic)
    if action == "start" and rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Already running",
                    "rotation_active": rotation_active,
                }
            ),
            400,
        )

    if action == "stop" and not rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Already stopped",
                    "rotation_active": rotation_active,
                }
            ),
            400,
        )

    if action == "kill" and rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Stop orchestrator before kill",
                    "rotation_active": rotation_active,
                }
            ),
            400,
        )

    client_ip = get_client_ip()

    log(f"[CONTROL] Received action '{action}' from {client_ip}")

    if action == "stop":
        rotation_active = False
        log("[ORCH] Rotation paused by user")
        return jsonify(
            {
                "status": "ok",
                "message": "Rotation stopped.",
                "rotation_active": rotation_active,
            }
        )

    elif action == "start":
        global rotation_resuming, last_active_container
        rotation_resuming = True
        rotation_active = True

        try:
            if last_active_container and last_active_container in web_containers:
                active_name = last_active_container
            else:
                active_name = random.choice(web_containers)
                log(
                    f"[RESUME WARN] No previous active container found, selecting {active_name}"
                )

            log(
                f"[RESUME] Cleaning state before rotation — keeping {active_name} active"
            )

            for name in web_containers:
                cont = get_container_safe(name)
                if not cont:
                    continue

                if name == active_name:
                    if cont.status != "running":
                        try:
                            cont.start()
                            log(f"[RESUME] Started {name} as active container")
                        except Exception as e:
                            log(f"[RESUME ERROR] Failed to start {name}: {e}")
                    continue
                else:
                    if cont.status == "running":
                        try:
                            cont.stop()
                            log(
                                f"[RESUME] Stopped {name} to enforce single-active policy"
                            )
                        except Exception as e:
                            log(f"[RESUME ERROR] Failed to stop {name}: {e}")

            log(
                f"[ORCH] Rotation resumed with {active_name} as initial active container"
            )

        except Exception as e:
            log(f"[RESUME ERROR] Failed during resume: {e}")

        finally:
            rotation_resuming = False

        return jsonify(
            {
                "status": "ok",
                "message": "Rotation resumed with clean state.",
                "rotation_active": rotation_active,
            }
        )

    elif action == "kill":
        stopped = []
        for name in web_containers:
            try:
                cont = get_container_safe(name)
                if cont and cont.status == "running":
                    cont.stop()
                    stopped.append(name)
                    log(f"[CONTROL] Killed container: {name}")
            except Exception as e:
                log(f"[CONTROL ERROR] Failed to kill {name}: {e}")
        return jsonify(
            {
                "status": "ok",
                "message": f"Killed containers: {', '.join(stopped) or 'none'}",
                "rotation_active": rotation_active,
            }
        )

    else:
        return (
            jsonify({"status": "error", "message": f"Unknown action '{action}'"}),
            400,
        )


@app.route("/orchestrator/logs", strict_slashes=False)
@login_required
def logs():
    try:
        with open(LOG_FILE, "r") as f:
            content = f.read()
        return render_template("logs.html", log_content=content)
    except Exception as e:
        return f"Error reading logs: {e}", 500


@app.route("/orchestrator/logs/raw", strict_slashes=False)
@login_required
def logs_raw():
    try:
        with open(LOG_FILE, "r") as f:
            return f.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as e:
        return f"Error reading logs: {e}", 500


@app.route("/orchestrator/js/<path:filename>", strict_slashes=False)
@login_required
def serve_js(filename):
    response = send_from_directory(
        os.path.join(os.path.dirname(__file__), "js"), filename
    )
    response.headers["Cache-Control"] = "public, max-age=3600, immutable"
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return response


# Tailwind compiled CSS
@app.route("/orchestrator/static/<path:filename>")
def orchestrator_static(filename):
    return send_from_directory("static", filename)


@app.route("/orchestrator/favicon.png", strict_slashes=False)
def favicon():
    return send_from_directory(os.path.join(os.path.dirname(__file__)), "favicon.png")


# Content Security Policy
@app.after_request
def add_csp_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://cdn.jsdelivr.net;"
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "report-uri /orchestrator/csp-violation-report-endpoint; "
    )
    return response


@app.route("/orchestrator/csp-violation-report-endpoint", methods=["POST"])
@csrf.exempt
def csp_violation_report():
    report = request.get_json(silent=True)

    if report is None and request.data:
        try:
            report = json.loads(request.data.decode("utf-8"))
        except ValueError:
            report = {"raw": request.data.decode("utf-8", errors="replace")}

    if report is None:
        report = {"message": "No report payload received"}

    csp_payload = report
    if isinstance(report, dict) and "csp-report" in report:
        csp_payload = report["csp-report"]

    if not isinstance(csp_payload, dict):
        csp_payload = {}

    document_uri = csp_payload.get("document-uri") or csp_payload.get("source-file")
    directive = csp_payload.get("effective-directive") or csp_payload.get(
        "violated-directive"
    )
    blocked_uri = csp_payload.get("blocked-uri")

    violation_type = "unknown"
    if isinstance(directive, str) and directive:
        violation_type = directive.split("-")[0]

    filtered_report = {
        "document_uri": document_uri or "unknown",
        "violation_type": violation_type or "unknown",
        "blocked_uri": blocked_uri or "unknown",
    }

    log(f"[CSP VIOLATION] {json.dumps(filtered_report, ensure_ascii=False)}")
    return "", 204


# ------------------------------
# Server-Sent Events (SSE) Stream
# ------------------------------
from flask import Response


@app.route("/orchestrator/api/stream", strict_slashes=False)
@login_required
def api_stream():
    import sys

    def event_stream():
        """Send container status as SSE"""
        while True:
            try:
                now = datetime.now(LOCAL_TZ)
                containers = {}
                for name in web_containers:
                    cont = get_container_safe(name)
                    state = cont.status if cont else "not found"
                    health = (
                        cont.attrs.get("State", {}).get("Health", {}).get("Status")
                        if cont
                        else None
                    )
                    total = container_total_active_seconds.get(name, 0)
                    start_ts = container_active_since.get(name)
                    if start_ts:
                        total += (now - start_ts).total_seconds()
                    containers[name] = {
                        "state": state,
                        "health": health,
                        "uptime": round(total, 1),
                    }

                eta = next_rotation_eta
                data = {
                    "containers": containers,
                    "rotation_count": rotation_count,
                    "last_rotation": (
                        last_rotation_time.strftime("%Y-%m-%d %H:%M:%S")
                        if last_rotation_time
                        else None
                    ),
                    "rotation_active": rotation_active,
                    "next_rotation_eta": (
                        int(eta) if isinstance(eta, (int, float)) and eta >= 0 else None
                    ),
                }

                chunk = f"data: {json.dumps(data)}\n\n"
                yield chunk
                sys.stdout.flush()
                time.sleep(0.9)
            except GeneratorExit:
                break
            except Exception as e:
                log(f"[SSE ERROR] {e}")
                time.sleep(0.9)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = (
        "no"  # disable proxy buffering (nginx/haproxy)
    )
    response.headers["Connection"] = "keep-alive"
    return response


# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    log("=== Orchestrator started ===")
    Thread(target=orchestrator_loop, daemon=True).start()
    Thread(target=uptime_tracker_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8081, debug=False)
