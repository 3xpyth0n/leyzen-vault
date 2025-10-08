#!/usr/bin/env python3
import docker
import time
import random
from datetime import datetime
import traceback
from threading import Thread
import logging
from flask import Flask, render_template, send_from_directory, jsonify
import os

LOG_FILE = "./orchestrator/vault_orchestrator.log"
HTML_DIR = os.path.join(os.path.dirname(__file__))

client = docker.from_env()
web_containers = ["paperless_web1", "paperless_web2", "paperless_web3"]
interval = 120  # seconds between rotations
health_timeout = 60  # seconds to wait for healthy

# rotation bookkeeping
rotation_count = 0
last_rotation_time = None

# uptime tracking: total seconds accumulated while container was the active one
container_total_active_seconds = {name: 0 for name in web_containers}
# when a container became active (datetime) or None
container_active_since = {name: None for name in web_containers}

# ------------------------------
# Logging helper
# ------------------------------
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

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
            # container might disappear; bail out
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
    """Mark container as active starting now (if not already)."""
    if container_active_since.get(container_name) is None:
        container_active_since[container_name] = datetime.now()
        log(f"{container_name} marked ACTIVE at {container_active_since[container_name].strftime('%H:%M:%S')}")

def accumulate_and_clear_active(container_name):
    """If container had an active start time, add duration to total and clear the start."""
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

    # Initial setup: pick one active and ensure it's running; stop others
    initial = random.choice(web_containers)
    log(f"Initial selection: {initial}")
    for name in web_containers:
        cont = get_container_safe(name)
        if not cont:
            continue
        if name == initial:
            if cont.status != "running":
                log(f"Starting initial container {name}")
                try:
                    cont.start()
                except Exception as e:
                    log(f"[ERROR] Failed to start {name}: {e}")
                # wait healthy (best-effort)
                wait_until_healthy(cont)
            mark_active(name)
        else:
            if cont.status == "running":
                log(f"Stopping initial container {name}")
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

            # Start next container if needed
            if next_cont.status != "running":
                log(f"Starting next container {next_name}")
                try:
                    next_cont.start()
                except Exception as e:
                    log(f"[ERROR] Failed to start {next_name}: {e}")
                    time.sleep(5)
                    continue

            # Wait until next is healthy before switching
            ok = wait_until_healthy(next_cont)
            if not ok:
                log(f"[WARNING] {next_name} did not become healthy, skipping this candidate")
                # optionally stop the container we just started if you don't want orphan running instances
                # next_cont.stop()
                time.sleep(5)
                continue

            # Next is ready -> perform relay:
            # 1) mark next as active (start time)
            mark_active(next_name)

            # 2) stop old after marking next active, and accumulate its active time
            old_cont = get_container_safe(active_name)
            # accumulate active time for old (it was active since container_active_since[active_name])
            accumulate_and_clear_active(active_name)

            if old_cont and old_cont.status == "running":
                log(f"Stopping old container {active_name}")
                try:
                    old_cont.stop()
                except Exception as e:
                    log(f"[ERROR] Failed to stop {active_name}: {e}")

            # update rotation metadata
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

# quiet werkzeug logs
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)

@app.route("/")
def dashboard():
    return render_template("index.html")

@app.route("/logs")
def logs():
    try:
        with open(LOG_FILE, "r") as f:
            content = f.read()
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <link rel="icon" type="image/png" href="/favicon.png" />
            <title>Vault Orchestrator Logs</title>
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    background-color: #071024;
                    color: #f1f5f9;
                    font-family: monospace;
                    height: 100%;
                    overflow: hidden; /* bloque le scroll global */
                }}
                h1 {{
                    color: #fde047;
                    font-size: 1.5rem;
                    margin: 1rem;
                }}
                pre {{
                    background: #1e293b;
                    padding: 1rem;
                    border-radius: 8px;
                    height: calc(100vh - 80px); /* occupe la place sous le titre */
                    margin: 0 1rem 1rem 1rem;
                    overflow-y: auto; /* scroll uniquement dans le bloc */
                    white-space: pre-wrap;
                    word-break: break-word;
                }}
            </style>
        </head>
        <body>
            <h1>Vault Orchestrator Logs</h1>
            <pre>{content}</pre>
        </body>
        </html>
        """
    except Exception as e:
        return f"Error reading logs: {e}", 500

@app.route("/favicon.png")
def favicon():
    return send_from_directory(HTML_DIR, "favicon.png")

@app.route("/api/status")
def api_status():
    now = datetime.now()
    containers = {}
    for name in web_containers:
        cont = get_container_safe(name)
        # state = docker container lifecycle state (running/exited/etc)
        state = cont.status if cont else "not found"
        # health can be None if no healthcheck is defined or if attrs missing
        health = None
        if cont:
            health = cont.attrs.get("State", {}).get("Health", {}).get("Status")

        # compute uptime as accumulated total + current active interval (if marked active)
        total = container_total_active_seconds.get(name, 0)
        start_ts = container_active_since.get(name)
        if start_ts:
            total += int((now - start_ts).total_seconds())

        containers[name] = {
            "state": state,
            "health": health,
            "uptime": total
        }

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
    # run flask without debug and suppress startup banner if desired
    # app.run prints some lines; keeping default but werkzeug access logs are silenced
    app.run(host="0.0.0.0", port=8081, debug=False)

