from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.workflow_models import WorkflowMode
from app.persistence.repositories.base import BasePostgresRepository, RepositoryRecord, utc_now


class AgentOutputRecord(RepositoryRecord):
    trace_id: str = Field(description="Trace identifier tying this output to a workflow.")
    workflow_mode: WorkflowMode = Field(description="Workflow mode associated with the output.")
    agent_name: str = Field(description="Agent that produced the output artifact.")
    output_type: str = Field(default="summary", description="High-level type for the stored output.")
    status: str = Field(default="completed", description="Processing status for the agent output.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized output payload produced by the agent.",
    )
    created_at: datetime = Field(default_factory=utc_now, description="Persistence creation timestamp.")


class AgentOutputRepository(BasePostgresRepository):
    """Repository scaffold for persisting normalized agent outputs."""

    table_name = "agent_outputs"

    def save(self, record: AgentOutputRecord) -> AgentOutputRecord:
        self._insert(record.model_dump(mode="json"))
        return record

    def list_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return self._select_by_trace_id(trace_id)
