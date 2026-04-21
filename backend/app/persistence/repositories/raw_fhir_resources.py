from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.raw_fhir import RawFHIRResource
from app.persistence.repositories.base import BasePostgresRepository, RepositoryRecord, utc_now


class RawFHIRResourceRecord(RepositoryRecord):
    trace_id: str = Field(description="Trace identifier tying the resource to a workflow.")
    patient_id: str = Field(description="Patient identifier associated with the fetched resource.")
    source_version: str = Field(default="R5", description="FHIR version associated with the resource payload.")
    resource_type: str = Field(description="FHIR resource type, such as Patient or Observation.")
    resource_id: str = Field(description="FHIR logical id in the source system.")
    fetched_at: datetime = Field(default_factory=utc_now, description="Timestamp when the resource was fetched.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Unmodified FHIR payload.")
    created_at: datetime = Field(default_factory=utc_now, description="Persistence creation timestamp.")

    @classmethod
    def from_raw_resource(
        cls,
        trace_id: str,
        patient_id: str,
        resource: RawFHIRResource,
    ) -> "RawFHIRResourceRecord":
        return cls(
            trace_id=trace_id,
            patient_id=patient_id,
            source_version=resource.source_version,
            resource_type=resource.resource_type,
            resource_id=resource.resource_id,
            fetched_at=resource.fetched_at,
            payload=resource.payload,
        )


class RawFHIRResourceRepository(BasePostgresRepository):
    """Repository scaffold for persisting raw FHIR resources fetched during workflows."""

    table_name = "raw_fhir_resources"

    def save(self, record: RawFHIRResourceRecord) -> RawFHIRResourceRecord:
        self._insert(record.model_dump(mode="json"))
        return record

    def save_many(self, records: list[RawFHIRResourceRecord]) -> list[RawFHIRResourceRecord]:
        for record in records:
            self.save(record)
        return records

    def list_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return self._select_by_trace_id(trace_id)
