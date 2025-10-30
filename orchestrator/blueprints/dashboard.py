"""Dashboard and API routes."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

from ..extensions import csrf
from ..services.rotation import RotationService
from .utils import get_client_ip, login_required


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/orchestrator")

csp_report_attempts: Dict[str | None, Deque[datetime]] = defaultdict(deque)


def _logger():
    return current_app.config["LOGGER"]


def _settings():
    return current_app.config["SETTINGS"]


def _rotation_service() -> RotationService:
    return current_app.config["ROTATION_SERVICE"]


@dashboard_bp.route("/", strict_slashes=False)
@login_required
def dashboard():
    settings = _settings()
    return render_template(
        "dashboard/index.html",
        vault_rotation_interval=int(settings.rotation_interval),
    )


@dashboard_bp.route("/api/control", methods=["POST"])
@login_required
def api_control():
    rotation = _rotation_service()

    try:
        data = request.get_json(force=True)
    except Exception:
        _logger().log("[CONTROL ERROR] Invalid JSON body received")
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

    action = (data.get("action") or "").strip().lower()

    if action == "start" and rotation.rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Already running",
                    "rotation_active": rotation.rotation_active,
                }
            ),
            400,
        )

    if action == "stop" and not rotation.rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Already stopped",
                    "rotation_active": rotation.rotation_active,
                }
            ),
            400,
        )

    if action == "kill" and rotation.rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Stop orchestrator before kill",
                    "rotation_active": rotation.rotation_active,
                }
            ),
            400,
        )

    if action == "rotate" and not rotation.rotation_active:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Resume rotation before forcing a switch.",
                    "rotation_active": rotation.rotation_active,
                }
            ),
            400,
        )

    client_ip = get_client_ip()
    _logger().log(
        "[CONTROL] Received action",
        context={"action": action, "client_ip": client_ip},
    )

    if action == "stop":
        rotation.pause_rotation()
        _logger().log("[ORCH] Rotation paused by user")
        return jsonify(
            {
                "status": "ok",
                "message": "Rotation stopped.",
                "rotation_active": rotation.rotation_active,
            }
        )

    if action == "start":
        rotation.resume_rotation()
        return jsonify(
            {
                "status": "ok",
                "message": "Rotation resumed with clean state.",
                "rotation_active": rotation.rotation_active,
            }
        )

    if action == "kill":
        stopped = rotation.kill_all_containers()
        return jsonify(
            {
                "status": "ok",
                "message": f"Killed containers: {', '.join(stopped) or 'none'}",
                "rotation_active": rotation.rotation_active,
            }
        )

    if action == "rotate":
        success, message, snapshot = rotation.force_rotate()
        status_code = 200 if success else 409
        response = {
            "status": "ok" if success else "error",
            "message": message,
            "rotation_active": rotation.rotation_active,
        }
        if snapshot:
            response["snapshot"] = snapshot
        return jsonify(response), status_code

    return jsonify({"status": "error", "message": f"Unknown action '{action}'"}), 400


@dashboard_bp.route("/logs", strict_slashes=False)
@login_required
def logs():
    logger = _logger()
    try:
        with open(logger.log_file, "r", encoding="utf-8") as handle:
            content = handle.read()
        return render_template("logs.html", log_content=content)
    except Exception as exc:
        return f"Error reading logs: {exc}", 500


@dashboard_bp.route("/logs/raw", strict_slashes=False)
@login_required
def logs_raw():
    logger = _logger()
    try:
        with open(logger.log_file, "r", encoding="utf-8") as handle:
            content = handle.read()
        return content, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as exc:
        return f"Error reading logs: {exc}", 500


@dashboard_bp.route("/static/js/<path:filename>", strict_slashes=False)
@login_required
def serve_js(filename: str):
    js_dir = Path(__file__).resolve().parent.parent / "static" / "js"
    response = send_from_directory(str(js_dir), filename)
    response.headers["Cache-Control"] = "public, max-age=3600, immutable"
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    return response


@dashboard_bp.route("/static/<path:filename>")
def orchestrator_static(filename: str):
    return send_from_directory("static", filename)


@dashboard_bp.route("/favicon.png", strict_slashes=False)
def favicon():
    orchestrator_dir = Path(__file__).resolve().parent.parent
    return send_from_directory(str(orchestrator_dir), "favicon.png")


@dashboard_bp.route("/csp-violation-report-endpoint", methods=["POST"])
@csrf.exempt
def csp_violation_report():
    settings = _settings()
    client_ip = get_client_ip() or "unknown"
    now = datetime.now()
    attempts = csp_report_attempts[client_ip]

    while attempts and now - attempts[0] > settings.csp_report_rate_window:
        attempts.popleft()

    if len(attempts) >= settings.csp_report_rate_limit:
        _logger().log(
            "[CSP VIOLATION] rate limit exceeded",
            context={
                "client_ip": client_ip,
                "limit": settings.csp_report_rate_limit,
                "window_seconds": int(settings.csp_report_rate_window.total_seconds()),
            },
        )
        return "", 429

    content_length = request.content_length
    if (
        settings.csp_report_max_size
        and content_length is not None
        and content_length > settings.csp_report_max_size
    ):
        _logger().log(
            "[CSP VIOLATION] payload rejected",
            context={
                "client_ip": client_ip,
                "content_length": content_length,
                "max_length": settings.csp_report_max_size,
            },
        )
        return "", 413

    attempts.append(now)

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

    _logger().log("[CSP VIOLATION] Report received", context=filtered_report)
    return "", 204


@dashboard_bp.route("/api/stream", strict_slashes=False)
@login_required
def api_stream():
    rotation = _rotation_service()

    def event_stream():
        while True:
            try:
                data = rotation.build_stream_snapshot()
                chunk = f"data: {json.dumps(data)}\n\n"
                yield chunk
                time.sleep(0.5)
            except GeneratorExit:
                break
            except Exception as exc:
                _logger().log(f"[SSE ERROR] {exc}")
                time.sleep(0.5)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


__all__ = ["dashboard_bp"]
