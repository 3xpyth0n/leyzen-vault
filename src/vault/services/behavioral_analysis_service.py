"""Advanced analytics and behavioral analysis service."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.database.schema import BehaviorAnalytics, db


class BehavioralAnalysisService:
    """Service for behavioral analysis and anomaly detection."""

    def record_event(
        self,
        user_id: str,
        event_type: str,
        event_data: dict[str, Any],
        ip_address: str | None = None,
        device_fingerprint: str | None = None,
        location: str | None = None,
    ) -> BehaviorAnalytics:
        """Record a behavioral event.

        Args:
            user_id: User ID
            event_type: Event type
            event_data: Event data
            ip_address: IP address
            device_fingerprint: Device fingerprint
            location: Location

        Returns:
            BehaviorAnalytics object
        """
        analytics = BehaviorAnalytics(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            event_data=json.dumps(event_data),
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            location=location,
        )
        db.session.add(analytics)
        db.session.commit()

        return analytics

    def analyze_user_patterns(
        self,
        user_id: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Analyze user behavior patterns.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with behavioral patterns
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        events = (
            db.session.query(BehaviorAnalytics)
            .filter(
                BehaviorAnalytics.user_id == user_id,
                BehaviorAnalytics.timestamp >= threshold,
            )
            .all()
        )

        # Analyze patterns
        event_counts = defaultdict(int)
        hourly_patterns = defaultdict(int)
        location_patterns = defaultdict(int)

        for event in events:
            event_counts[event.event_type] += 1
            hour = event.timestamp.hour
            hourly_patterns[hour] += 1
            if event.location:
                location_patterns[event.location] += 1

        return {
            "total_events": len(events),
            "event_counts": dict(event_counts),
            "hourly_patterns": dict(hourly_patterns),
            "location_patterns": dict(location_patterns),
            "most_active_hour": (
                max(hourly_patterns.items(), key=lambda x: x[1])[0]
                if hourly_patterns
                else None
            ),
            "most_common_location": (
                max(location_patterns.items(), key=lambda x: x[1])[0]
                if location_patterns
                else None
            ),
        }

    def detect_anomalies(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Detect behavioral anomalies.

        Args:
            user_id: User ID

        Returns:
            List of detected anomalies
        """
        patterns = self.analyze_user_patterns(user_id)
        anomalies = []

        # Get recent events
        recent_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_events = (
            db.session.query(BehaviorAnalytics)
            .filter(
                BehaviorAnalytics.user_id == user_id,
                BehaviorAnalytics.timestamp >= recent_threshold,
            )
            .all()
        )

        # Check for unusual activity times
        if patterns.get("most_active_hour") is not None:
            current_hour = datetime.now(timezone.utc).hour
            usual_hour = patterns["most_active_hour"]
            if abs(current_hour - usual_hour) > 6:
                anomalies.append(
                    {
                        "type": "unusual_time",
                        "severity": "medium",
                        "message": f"Activity at unusual hour (usual: {usual_hour}, current: {current_hour})",
                    }
                )

        # Check for unusual locations
        if patterns.get("most_common_location"):
            recent_locations = {e.location for e in recent_events if e.location}
            usual_location = patterns["most_common_location"]
            if recent_locations and usual_location not in recent_locations:
                anomalies.append(
                    {
                        "type": "unusual_location",
                        "severity": "high",
                        "message": f"Activity from unusual location (usual: {usual_location})",
                    }
                )

        # Check for rapid successive actions (potential automated attack)
        if len(recent_events) > 100:
            anomalies.append(
                {
                    "type": "high_frequency",
                    "severity": "medium",
                    "message": f"Unusually high number of events in last 24h: {len(recent_events)}",
                }
            )

        return anomalies

    def generate_risk_score(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Generate risk score for user based on behavior.

        Args:
            user_id: User ID

        Returns:
            Dictionary with risk score and factors
        """
        anomalies = self.detect_anomalies(user_id)

        risk_score = 0
        factors = []

        for anomaly in anomalies:
            severity = anomaly.get("severity", "low")
            if severity == "high":
                risk_score += 30
            elif severity == "medium":
                risk_score += 15
            else:
                risk_score += 5

            factors.append(anomaly)

        # Normalize to 0-100
        risk_score = min(100, risk_score)

        return {
            "risk_score": risk_score,
            "level": (
                "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low"
            ),
            "factors": factors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
