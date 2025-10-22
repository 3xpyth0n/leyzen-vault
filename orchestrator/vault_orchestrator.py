#!/usr/bin/python3

import docker
import time
import random
from datetime import datetime
import traceback
from threading import Thread
import logging
from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, url_for, session
from functools import wraps
from dotenv import load_dotenv
import os
import signal
import sys

# Charge le fichier .env depuis le dossier du script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "../.env"))

# Environment
WEB_CONTAINERS = os.environ.get("VAULT_WEB_CONTAINERS").split(",")
USERNAME = os.environ.get("VAULT_USER")
PASSWORD = os.environ.get("VAULT_PASS")

# Check for all variables
required_vars = ["VAULT_USER", "VAULT_PASS", "VAULT_SECRET_KEY"]
for var in required_vars:
    if not os.environ.get(var):
        raise EnvironmentError(f"Variable {var} manquante dans .env")

# ------------------------------
# Dashboard Authentification
# ------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "vault_orchestrator.log")
HTML_DIR = os.path.join(os.path.dirname(__file__))

client = docker.from_env()
web_containers = WEB_CONTAINERS
interval = os.environ.get("VAULT_ROTATION_INTERVAL")  # seconds between rotations
health_timeout = os.environ.get("VAULT_HEALTH_TIMEOUT")  # seconds to wait for healthy

rotation_count = 0
last_rotation_time = None
container_total_active_seconds = {name: 0 for name in web_containers}
container_active_since = {name: None for name in web_containers}

# ------------------------------
# Logging helper
# ------------------------------
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ------------------------------
# Signal handler
# ------------------------------
def handle_shutdown(sig, frame):
    if sig == signal.SIGINT:
        log("=== Orchestrator stopped via Ctrl+C ===")
    elif sig == signal.SIGTERM:
        log("=== Orchestrator stopped by systemd (SIGTERM) ===")
    else:
        log(f"=== Orchestrator stopped (signal {sig}) ===")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# ------------------------------
# Safe container retrieval
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

# ------------------------------
# Wait until container is healthy
# ------------------------------
def wait_until_healthy(container, check_interval=2, timeout=health_timeout):
    start = time.time()
    while True:
        try:
            container.reload()
            status = container.attrs.get("State", {}).get("Health", {}).get("Status")
            if status == "healthy":
                return True
        except Exception:
            log(f"[WARNING] Couldn't read health for {getattr(container, 'name', 'unknown')}")
            return False
        if time.time() - start > timeout:
            log(f"[WARNING] Timeout waiting for {container.name} to become healthy.")
            return False
        time.sleep(check_interval)

# ------------------------------
# Helpers for uptime accumulation
# ------------------------------
def mark_active(container_name):
    if container_active_since.get(container_name) is None:
        container_active_since[container_name] = datetime.now()
        log(f"{container_name} marked ACTIVE at {container_active_since[container_name].strftime('%H:%M:%S')}")

def accumulate_and_clear_active(container_name):
    start_ts = container_active_since.get(container_name)
    if start_ts:
        delta = (datetime.now() - start_ts).total_seconds()
        container_total_active_seconds[container_name] += int(delta)
        container_active_since[container_name] = None
        log(f"Accumulated {int(delta)}s for {container_name} (total={container_total_active_seconds[container_name]}s)")

# ------------------------------
# Orchestrator rotation loop
# ------------------------------
def orchestrator_loop():
    global rotation_count, last_rotation_time
    initial = random.choice(web_containers)
    log(f"Initial selection: {initial}")

    for name in web_containers:
        cont = get_container_safe(name)
        if not cont:
            continue
        if name == initial:
            if cont.status != "running":
                try:
                    cont.start()
                except Exception as e:
                    log(f"[ERROR] Failed to start {name}: {e}")
                wait_until_healthy(cont)
            mark_active(name)
        else:
            if cont.status == "running":
                try:
                    cont.stop()
                except Exception as e:
                    log(f"[ERROR] Failed to stop {name}: {e}")

    rotation_count = 0
    last_rotation_time = datetime.now()
    log(f"Initial rotation: {initial} active")
    active_name = initial

    while True:
        try:
            choices = [c for c in web_containers if c != active_name]
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

            mark_active(next_name)
            old_cont = get_container_safe(active_name)
            accumulate_and_clear_active(active_name)

            if old_cont and old_cont.status == "running":
                try:
                    old_cont.stop()
                except Exception as e:
                    log(f"[ERROR] Failed to stop {active_name}: {e}")

            active_name = next_name
            rotation_count += 1
            last_rotation_time = datetime.now()
            log(f"Rotation #{rotation_count}: {active_name} is now active")
            time.sleep(interval)

        except Exception:
            log(f"Exception in orchestrator loop:\n{traceback.format_exc()}")
            time.sleep(5)

# ------------------------------
# Flask dashboard & API
# ------------------------------
app = Flask(__name__, template_folder=HTML_DIR, static_folder=HTML_DIR)
app.secret_key = os.environ.get("VAULT_SECRET_KEY")
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)

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
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            next_page = request.args.get("next") or url_for("dashboard")
            return redirect(next_page)
        else:
            error = "Utilisateur ou mot de passe incorrect"
    return render_template("login.html", error=error)

@app.route("/orchestrator/logout")
def logout():
    session["logged_in"] = False
    return redirect(url_for("login"))

@app.route("/orchestrator", strict_slashes=False)
@login_required
def dashboard():
    return render_template("index.html")

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

@app.route("/orchestrator/api/status", strict_slashes=False)
@login_required
def api_status():
    now = datetime.now()
    containers = {}
    for name in web_containers:
        cont = get_container_safe(name)
        state = cont.status if cont else "not found"
        health = cont.attrs.get("State", {}).get("Health", {}).get("Status") if cont else None
        total = container_total_active_seconds.get(name, 0)
        start_ts = container_active_since.get(name)
        if start_ts:
            total += int((now - start_ts).total_seconds())
        containers[name] = {"state": state, "health": health, "uptime": total}
    return jsonify({
        "containers": containers,
        "rotation_count": rotation_count,
        "last_rotation": last_rotation_time.strftime("%Y-%m-%d %H:%M:%S") if last_rotation_time else None
    })

# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    log("=== Orchestrator started ===")
    Thread(target=orchestrator_loop, daemon=True).start()
    print("Dashboard available at http://localhost:8080/orchestrator\n")
    app.run(host="172.17.0.1", port=8081, debug=False)

