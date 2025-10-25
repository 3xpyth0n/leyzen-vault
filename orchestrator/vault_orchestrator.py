#!/usr/bin/python3

import docker
import time
import random
import traceback
from datetime import datetime, timedelta
from threading import Thread
import logging
from flask import (
    Flask, render_template, send_from_directory, jsonify,
    request, redirect, url_for, session, abort
)
from functools import wraps
import os
import signal
import sys
import pytz
from collections import defaultdict, deque

from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf import CSRFProtect

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
        raise EnvironmentError(f"Variable {var} manquante dans .env")

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
health_timeout = int(str(os.environ.get("VAULT_HEALTH_TIMEOUT", "30")).strip('"'))

rotation_count = 0
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

def wait_until_healthy(container, check_interval=2, timeout=health_timeout):
    start = time.time()
    while True:
        try:
            container.reload()
            health = container.attrs.get("State", {}).get("Health", {}).get("Status")
            status = container.status
            if status == "running" and (health is None or health == "healthy"):
                return True
        except Exception as e:
            log(f"[ERROR] while checking health: {e}")
        if time.time() - start > timeout:
            return False
        time.sleep(check_interval)

def mark_active(name):
    container_active_since[name] = datetime.now(LOCAL_TZ)

def accumulate_and_clear_active(name):
    start_ts = container_active_since.get(name)
    if not start_ts:
        return 0
    if start_ts:
        elapsed = int((datetime.now(LOCAL_TZ) - start_ts).total_seconds())
        container_total_active_seconds[name] = container_total_active_seconds.get(name, 0) + elapsed
        container_active_since[name] = None
        return elapsed

# ------------------------------
# In-memory password hash
# ------------------------------
if not PASSWORD:
    raise EnvironmentError("VAULT_PASS must be set to initialize password hash.")
PASSWORD_HASH = generate_password_hash(PASSWORD)
# Effacer la ref en clair pour éviter toute mauvaise manip
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
    global rotation_count, last_rotation_time
    if not web_containers:
        log("[WARN] No web containers configured for rotation.")
        return

    # choose an initial active container that exists
    initial = None
    for c in web_containers:
        cont = get_container_safe(c)
        if cont:
            initial = c
            break
    if not initial:
        log("[ERROR] No valid container found to start as initial active.")
        return

    # ensure initial is running and marked active
    try:
        cont = get_container_safe(initial)
        if cont and cont.status != "running":
            try:
                cont.start()
            except Exception as e:
                log(f"[ERROR] Failed to start initial {initial}: {e}")
        mark_active(initial)
    except Exception:
        pass

    rotation_count = 0
    last_rotation_time = datetime.now(LOCAL_TZ)
    log(f"Initial rotation: {initial} active")
    active_name = initial

    while True:
        try:
            choices = [c for c in web_containers if c != active_name]
            if not choices:
                time.sleep(5)
                continue

            next_name = random.choice(choices)
            next_cont = get_container_safe(next_name)
            if not next_cont:
                time.sleep(5)
                continue

            if next_cont.status != "running":
                try:
                    next_cont.start()
                except Exception as e:
                    log(f"[ERROR] Failed to start {next_name}: {e}")
                    time.sleep(5)
                    continue

            ok = wait_until_healthy(next_cont)
            if not ok:
                log(f"[WARNING] {next_name} did not become healthy, skipping")
                time.sleep(5)
                continue

            log(f"{next_name} marked ACTIVE at {datetime.now(LOCAL_TZ).strftime('%H:%M:%S')}")
            mark_active(next_name)
            old_cont = get_container_safe(active_name)
            accumulate_and_clear_active(active_name)
            elapsed = accumulate_and_clear_active(active_name)
            if elapsed > 0:
                total_s = container_total_active_seconds.get(active_name, 0)
                log(f"Accumulated {elapsed}s for {active_name} (total={total_s}s)")

            if old_cont and old_cont.status == "running":
                try:
                    old_cont.stop()
                except Exception as e:
                    log(f"[ERROR] Failed to stop {active_name}: {e}")

            active_name = next_name
            rotation_count += 1
            last_rotation_time = datetime.now(LOCAL_TZ)
            log(f"Rotation #{rotation_count}: {active_name} is now active")
            time.sleep(interval)
        except Exception:
            log(f"Exception in orchestrator loop:\n{traceback.format_exc()}")
            time.sleep(5)

# ------------------------------
# Flask app + CSRF + session cookies
# ------------------------------
app = Flask(__name__, template_folder=HTML_DIR, static_folder=HTML_DIR)
app.secret_key = os.environ.get("VAULT_SECRET_KEY")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False  # ↩️ pass to True when HTTPS
)

# CSRF
csrf = CSRFProtect(app)

logging.getLogger('werkzeug').setLevel(logging.ERROR)

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
    vault_health_timeout = int(os.getenv("VAULT_HEALTH_TIMEOUT", "30"))
    return render_template(
        "index.html",
        vault_rotation_interval=vault_rotation_interval,
        vault_health_timeout=vault_health_timeout
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

@app.route("/orchestrator/favicon.png", strict_slashes=False)
def favicon():
    return send_from_directory(os.path.join(os.path.dirname(__file__)), "favicon.png")

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
        """Send container status as SSE """
        while True:
            try:
                now = datetime.now(LOCAL_TZ)
                containers = {}
                for name in web_containers:
                    cont = get_container_safe(name)
                    state = cont.status if cont else "not found"
                    health = cont.attrs.get("State", {}).get("Health", {}).get("Status") if cont else None
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
                    "last_rotation": last_rotation_time.strftime("%Y-%m-%d %H:%M:%S") if last_rotation_time else None,
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
    response.headers["X-Accel-Buffering"] = "no"  # disable proxy buffering (nginx/haproxy)
    response.headers["Connection"] = "keep-alive"
    return response

# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    log("=== Orchestrator started ===")
    Thread(target=orchestrator_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8081, debug=False)

