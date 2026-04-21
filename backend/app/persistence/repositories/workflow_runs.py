from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.workflow_models import WorkflowMode
from app.persistence.repositories.base import BasePostgresRepository, RepositoryRecord, utc_now


class WorkflowRunRecord(RepositoryRecord):
    trace_id: str = Field(description="Trace identifier for the workflow run.")
    workflow_mode: WorkflowMode = Field(description="Workflow mode executed for the trace.")
    patient_id: str = Field(description="Patient identifier associated with the workflow run.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier when available.")
    source_version: str = Field(default="R5", description="FHIR version used for the workflow context.")
    status: str = Field(default="accepted", description="Workflow status persisted for the run.")
    started_at: datetime = Field(default_factory=utc_now, description="Workflow start timestamp.")
    completed_at: datetime | None = Field(default=None, description="Workflow completion timestamp.")
    request_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized workflow request payload for audit and replay scaffolding.",
    )
    response_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized workflow response payload for audit and replay scaffolding.",
    )
    created_at: datetime = Field(default_factory=utc_now, description="Persistence creation timestamp.")


class WorkflowRunRepository(BasePostgresRepository):
    """Repository scaffold for persisting workflow execution records."""

    table_name = "workflow_runs"

    def save(self, record: WorkflowRunRecord) -> WorkflowRunRecord:
        self._insert(record.model_dump(mode="json"))
        return record

    def list_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return self._select_by_trace_id(trace_id)
