"""Webhook service for external integrations."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from vault.database.schema import Webhook, db


class WebhookService:
    """Service for managing webhooks."""

    def create_webhook(
        self,
        user_id: str,
        url: str,
        events: list[str],
        secret: str | None = None,
    ) -> Webhook:
        """Create a webhook.

        Args:
            user_id: User ID creating webhook
            url: Webhook URL
            events: List of event types to subscribe to
            secret: Optional secret (generated if not provided)

        Returns:
            Webhook object
        """
        import secrets

        if not secret:
            secret = secrets.token_urlsafe(32)

        webhook = Webhook(
            id=str(uuid.uuid4()),
            user_id=user_id,
            url=url,
            secret=secret,
            events=json.dumps(events),
            is_active=True,
        )
        db.session.add(webhook)
        db.session.commit()

        return webhook

    def trigger_webhook(
        self,
        event_type: str,
        payload: dict[str, Any],
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Trigger webhooks for an event.

        Args:
            event_type: Event type (e.g., "file.uploaded", "file.shared")
            payload: Event payload
            user_id: Optional user ID filter

        Returns:
            List of webhook delivery results
        """
        query = db.session.query(Webhook).filter_by(is_active=True)

        if user_id:
            query = query.filter_by(user_id=user_id)

        webhooks = query.all()
        results = []

        for webhook in webhooks:
            try:
                events = json.loads(webhook.events)
                if event_type not in events:
                    continue

                # Sign payload with HMAC
                signature = hmac.new(
                    webhook.secret.encode(),
                    json.dumps(payload).encode(),
                    hashlib.sha256,
                ).hexdigest()

                headers = {
                    "Content-Type": "application/json",
                    "X-Leyzen-Signature": f"sha256={signature}",
                    "X-Leyzen-Event": event_type,
                }

                # Send webhook
                response = requests.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=5,
                )

                webhook.last_triggered_at = datetime.now(timezone.utc)
                if response.status_code >= 400:
                    webhook.failure_count += 1
                else:
                    webhook.failure_count = 0

                db.session.commit()

                results.append(
                    {
                        "webhook_id": webhook.id,
                        "status_code": response.status_code,
                        "success": response.status_code < 400,
                    }
                )
            except Exception as e:
                webhook.failure_count += 1
                webhook.last_triggered_at = datetime.now(timezone.utc)
                db.session.commit()

                results.append(
                    {
                        "webhook_id": webhook.id,
                        "error": str(e),
                        "success": False,
                    }
                )

        return results

    def list_webhooks(
        self,
        user_id: str,
    ) -> list[Webhook]:
        """List webhooks for a user.

        Args:
            user_id: User ID

        Returns:
            List of Webhook objects
        """
        return db.session.query(Webhook).filter_by(user_id=user_id).all()

    def delete_webhook(self, webhook_id: str, user_id: str) -> bool:
        """Delete a webhook.

        Args:
            webhook_id: Webhook ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False otherwise
        """
        webhook = (
            db.session.query(Webhook).filter_by(id=webhook_id, user_id=user_id).first()
        )

        if not webhook:
            return False

        db.session.delete(webhook)
        db.session.commit()
        return True
