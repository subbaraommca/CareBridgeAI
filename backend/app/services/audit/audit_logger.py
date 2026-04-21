from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.workflow_models import WorkflowMode


logger = logging.getLogger("carebridge.audit")


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuditStepStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AuditEvent(BaseModel):
    """Structured audit event contract for workflow execution scaffolding."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    trace_id: str = Field(description="Workflow trace identifier.")
    workflow_mode: WorkflowMode | str = Field(description="Workflow mode associated with the event.")
    source_version: str = Field(default="R5", description="FHIR version for the workflow context.")
    step_name: str = Field(description="Workflow step or agent stage being recorded.")
    step_status: AuditStepStatus = Field(description="Lifecycle status for the workflow step.")
    recorded_at: datetime = Field(default_factory=utc_now, description="Timestamp for the audit event.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured details for the audit event.",
    )


class AuditLogger:
    """Structured audit logger with backward-compatible event recording."""

    def __init__(self, event_sink: list[AuditEvent] | None = None) -> None:
        self.event_sink = event_sink

    def record_step(
        self,
        trace_id: str,
        workflow_mode: WorkflowMode | str,
        step_name: str,
        step_status: AuditStepStatus,
        source_version: str = "R5",
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            trace_id=trace_id,
            workflow_mode=workflow_mode,
            source_version=source_version,
            step_name=step_name,
            step_status=step_status,
            details=details or {},
        )
        logger.info(
            "trace_id=%s workflow_mode=%s source_version=%s step_name=%s step_status=%s details=%s",
            event.trace_id,
            event.workflow_mode,
            event.source_version,
            event.step_name,
            event.step_status,
            event.details,
        )
        if self.event_sink is not None:
            self.event_sink.append(event)
        return event

    def record_event(self, event_type: str, subject_id: str, details: dict[str, Any] | None = None) -> AuditEvent:
        payload = details or {}
        trace_id = str(payload.get("trace_id") or payload.get("correlation_id") or subject_id)
        workflow_mode = str(payload.get("workflow") or "unknown")
        source_version = str(payload.get("source_version") or "R5")
        step_status = self._status_from_event_type(event_type)

        return self.record_step(
            trace_id=trace_id,
            workflow_mode=workflow_mode,
            step_name=event_type,
            step_status=step_status,
            source_version=source_version,
            details={"subject_id": subject_id, **payload},
        )

    def _status_from_event_type(self, event_type: str) -> AuditStepStatus:
        normalized = event_type.lower()
        if normalized.endswith(".failed"):
            return AuditStepStatus.FAILED
        if normalized.endswith(".completed"):
            return AuditStepStatus.COMPLETED
        if normalized.endswith(".skipped"):
            return AuditStepStatus.SKIPPED
        return AuditStepStatus.STARTED
