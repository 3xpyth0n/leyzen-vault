"""Cron utility API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from croniter import croniter
from flask import Blueprint, jsonify, request

try:
    from cron_descriptor import get_description
except ImportError:
    get_description = None

from vault.database.schema import GlobalRole
from vault.extensions import csrf
from vault.middleware import get_current_user, jwt_required, require_role

logger = logging.getLogger(__name__)

cron_api_bp = Blueprint("cron_api", __name__, url_prefix="/api/v2/cron")


@cron_api_bp.route("/describe", methods=["POST"])
@csrf.exempt
@jwt_required
@require_role(GlobalRole.ADMIN)
def describe_cron():
    """Describe a cron expression.

    Request body:
        {
            "cron": str
        }

    Returns:
        JSON with human-readable description
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data or "cron" not in data:
        return jsonify({"error": "Cron expression required"}), 400

    cron_expression = data["cron"].strip()

    try:
        if not croniter.is_valid(cron_expression):
            return jsonify({"error": "Invalid cron expression"}), 400

        human_description = ""
        if get_description:
            try:
                human_description = f"“{get_description(cron_expression)}”"
            except Exception as e:
                logger.error(f"Failed to describe cron with cron-descriptor: {e}")
                human_description = ""

        now = datetime.now(timezone.utc)
        iter = croniter(cron_expression, now)
        next_run = iter.get_next(datetime)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if human_description:
        full_description = f"{human_description} • Next at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    else:
        full_description = f"Next at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    return (
        jsonify(
            {
                "description": full_description,
                "next_run": next_run.isoformat(),
            }
        ),
        200,
    )
