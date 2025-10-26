#!/usr/bin/python3

import docker
import time
import random
import traceback
from datetime import datetime, timedelta
from threading import Thread
import logging
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
WEB_CONTAINERS = os.environ.get("VAULT_WEB_CONTAINERS", "paperless_web1").split(",")
USERNAME = os.environ.get("VAULT_USER", "admin")
PASSWORD = os.environ.get("VAULT_PASS", None)

# Ensure required vars
required_vars = ["VAULT_USER", "VAULT_PASS", "VAULT_SECRET_KEY"]
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
# Docker / rotation config
# ------------------------------
client = docker.from_env()
web_containers = [c.strip() for c in WEB_CONTAINERS if c.strip()]
interval = int(str(os.environ.get("VAULT_ROTATION_INTERVAL", "90")).strip('"'))

rotation_count = 0
rotation_active = True  # default: running
rotation_resuming = False
last_active_container = None
stop_requested = False
last_rotation_time = None

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
        cont = client.containers.get(name)
        cont.reload()
        return cont
    except docker.errors.NotFound:
        log(f"[ERROR] Container {name} not found")
        return None
    except Exception as e:
        log(f"[ERROR] Error getting container {name}: {e}")
        return None


def wait_until_healthy(container, check_interval=2, log_interval=30):
    last_log = time.time()
    name = getattr(container, "name", "<unknown>")

    while True:
        try:
            container.reload()
        except docker.errors.NotFound:
            log(f"[WAIT ERROR] Container {name} disappeared during warmup")
            return False
        except Exception as e:
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
    except Exception as e:
        log(f"[STOP ERROR] Failed to reload {name} before stop: {e}")

    status = getattr(cont, "status", None)
    if status == "paused":
        try:
            cont.unpause()
            cont.reload()
            status = cont.status
        except Exception as e:
            log(f"[STOP ERROR] Failed to unpause {name}: {e}")

    if status not in ("running", "restarting"):
        return False

    try:
        cont.stop(timeout=timeout)
        try:
            cont.wait(timeout=timeout)
        except Exception:
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
    except Exception as e:
        log(f"[START ERROR] Failed to reload {name} before start: {e}")

    status = getattr(cont, "status", None)
    if status == "paused":
        try:
            cont.unpause()
            cont.reload()
            status = cont.status
        except Exception as e:
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


def is_blocked(ip):
    attempts = login_attempts[ip]
    now = datetime.now()
    # remove old attempts
    while attempts and now - attempts[0] > BLOCK_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_ATTEMPTS


def register_failed_attempt(ip):
    login_attempts[ip].append(datetime.now())


# ------------------------------
# Orchestrator loop (rotation)
# ------------------------------
def orchestrator_loop():
    global rotation_count, last_rotation_time, last_active_container
    if not web_containers:
        log("[WARN] No web containers configured for rotation.")
        return

    managed_containers = []
    for name in web_containers:
        if get_container_safe(name):
            managed_containers.append(name)
        else:
            log(f"[ERROR] Container {name} declared but not found. It will be skipped.")

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
    while True:
        try:
            if rotation_resuming:
                next_switch_time = datetime.now(LOCAL_TZ) + timedelta(seconds=interval)
                time.sleep(1)
                continue

            if not rotation_active:
                next_switch_time = datetime.now(LOCAL_TZ) + timedelta(seconds=interval)
                time.sleep(1)
                continue

            now = datetime.now(LOCAL_TZ)
            if now < next_switch_time:
                time.sleep(1)
                continue

            if len(managed_containers) == 1:
                next_switch_time = now + timedelta(seconds=interval)
                continue

            rotated = False
            attempts = 0
            total_containers = len(managed_containers)

            while (
                attempts < total_containers - 1
            ):  # exclude current active from attempts
                next_index = (active_index + 1 + attempts) % total_containers
                next_name = managed_containers[next_index]
                if next_name == active_name:
                    attempts += 1
                    continue

                next_cont = start_container(next_name, reason="preparing for rotation")
                if not next_cont:
                    attempts += 1
                    continue

                if not wait_until_healthy(next_cont):
                    log(
                        f"[WARNING] {next_name} failed to reach a healthy state — stopping container."
                    )
                    stop_container(next_name, reason="failed rotation health check")
                    attempts += 1
                    continue

                log(
                    f"{next_name} marked ACTIVE at {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}"
                )
                mark_active(next_name)
                elapsed = accumulate_and_clear_active(active_name)
                if elapsed > 0:
                    total_s = container_total_active_seconds.get(active_name, 0)
                    log(f"Accumulated {elapsed}s for {active_name} (total={total_s}s)")

                stop_container(active_name, reason="rotation completed")
                active_name = next_name
                active_index = next_index
                ensure_single_active(active_name, managed_containers)

                rotation_count += 1
                last_rotation_time = datetime.now(LOCAL_TZ)
                last_active_container = active_name

                log(f"Rotation #{rotation_count}: {active_name} is now active")
                rotated = True
                break

            if not rotated:
                log(
                    f"[WARNING] Rotation skipped — no healthy candidates available. {active_name} remains active."
                )

            next_switch_time = datetime.now(LOCAL_TZ) + timedelta(seconds=interval)
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
                except Exception as e:
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
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        # take the first IP in the list (the original client)
        client_ip = client_ip.split(",")[0].strip()

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

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

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
        "report-uri /csp-violation-report-endpoint; "
    )
    return response


@app.route("/orchestrator/csp-violation-report-endpoint", methods=["POST"])
@login_required
def csp_violation_report():
    print("[CSP VIOLATION]", request.json)
    return "", 204


# ------------------------------
# Server-Sent Events (SSE) Stream
# ------------------------------
from flask import Response
import json


@app.route("/orchestrator/api/stream", strict_slashes=False)
@login_required
def api_stream():
    import json
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

                data = {
                    "containers": containers,
                    "rotation_count": rotation_count,
                    "last_rotation": (
                        last_rotation_time.strftime("%Y-%m-%d %H:%M:%S")
                        if last_rotation_time
                        else None
                    ),
                    "rotation_active": rotation_active,
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
