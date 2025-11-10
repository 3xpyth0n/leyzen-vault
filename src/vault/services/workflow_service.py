"""Workflow automation service for advanced workspace features."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from vault.database.schema import Workflow, WorkflowExecution, db


class WorkflowService:
    """Service for workflow automation."""

    def create_workflow(
        self,
        user_id: str,
        name: str,
        trigger_event: str,
        trigger_conditions: dict[str, Any],
        actions: list[dict[str, Any]],
        description: str | None = None,
    ) -> Workflow:
        """Create a workflow.

        Args:
            user_id: User ID creating workflow
            name: Workflow name
            trigger_event: Event that triggers workflow
            trigger_conditions: Conditions for trigger
            actions: List of actions to execute
            description: Optional description

        Returns:
            Workflow object
        """
        workflow = Workflow(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            trigger_event=trigger_event,
            trigger_conditions=json.dumps(trigger_conditions),
            actions=json.dumps(actions),
            is_active=True,
        )
        db.session.add(workflow)
        db.session.commit()

        return workflow

    def trigger_workflow(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> list[WorkflowExecution]:
        """Trigger workflows for an event.

        Args:
            event_type: Event type
            event_data: Event data

        Returns:
            List of workflow executions
        """
        workflows = (
            db.session.query(Workflow)
            .filter_by(trigger_event=event_type, is_active=True)
            .all()
        )

        executions = []

        for workflow in workflows:
            # Check conditions
            conditions = json.loads(workflow.trigger_conditions)
            if not self._check_conditions(conditions, event_data):
                continue

            # Use transaction context manager for consistent transaction handling
            from vault.database.transaction import db_transaction

            # Create execution
            execution = WorkflowExecution(
                id=str(uuid.uuid4()),
                workflow_id=workflow.id,
                trigger_event=event_type,
                trigger_data=json.dumps(event_data),
                status="running",
            )
            db.session.add(execution)

            try:
                with db_transaction():
                    # Execute actions
                    actions = json.loads(workflow.actions)
                    for action in actions:
                        self._execute_action(action, event_data)

                    execution.status = "success"
                    execution.completed_at = datetime.now(timezone.utc)
                    workflow.execution_count += 1
                    workflow.last_triggered_at = datetime.now(timezone.utc)
            except Exception as e:
                # Transaction already rolled back by context manager
                execution.status = "failed"
                execution.error_message = str(e)
                execution.completed_at = datetime.now(timezone.utc)
                # Commit the execution record with failed status
                db.session.commit()

            executions.append(execution)

        return executions

    def _check_conditions(
        self,
        conditions: dict[str, Any],
        event_data: dict[str, Any],
    ) -> bool:
        """Check if conditions match event data.

        Args:
            conditions: Condition dictionary
            event_data: Event data

        Returns:
            True if conditions match, False otherwise
        """
        # Simple condition checking (can be extended)
        for key, value in conditions.items():
            if key not in event_data:
                return False
            if event_data[key] != value:
                return False
        return True

    def _execute_action(
        self,
        action: dict[str, Any],
        event_data: dict[str, Any],
    ) -> None:
        """Execute a workflow action.

        Args:
            action: Action definition
            event_data: Event data

        Raises:
            ValueError: If action type is unknown
        """
        action_type = action.get("type")

        if action_type == "notify":
            # Send notification
            # Implementation would integrate with notification service
            pass
        elif action_type == "copy_file":
            # Copy file to another location
            # Implementation would use file service
            pass
        elif action_type == "transform":
            # Transform file (e.g., convert format)
            # Implementation would use transformation service
            pass
        elif action_type == "webhook":
            # Call webhook
            from vault.services.webhook_service import WebhookService

            webhook_service = WebhookService()
            webhook_service.trigger_webhook(
                event_type=action.get("event_type", ""),
                payload=event_data,
            )
        else:
            raise ValueError(f"Unknown action type: {action_type}")
