from datetime import UTC, datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class RawFHIRBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class RawFHIRResource(RawFHIRBaseModel):
    source_version: str = Field(
        default="R5",
        description="FHIR version associated with the resource payload.",
    )
    resource_type: str = Field(
        description="FHIR resource type, such as Patient or Encounter.",
        validation_alias=AliasChoices("resource_type", "resourceType"),
    )
    resource_id: str = Field(
        description="Logical identifier of the FHIR resource in the source system.",
        validation_alias=AliasChoices("resource_id", "id"),
    )
    fetched_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when this raw resource was fetched.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Unmodified raw FHIR resource payload.",
        validation_alias=AliasChoices("payload", "data"),
    )

    @model_validator(mode="after")
    def ensure_payload_identity(self) -> "RawFHIRResource":
        self.payload.setdefault("resourceType", self.resource_type)
        self.payload.setdefault("id", self.resource_id)
        return self

    @property
    def id(self) -> str:
        return self.resource_id

    @property
    def data(self) -> dict[str, Any]:
        return self.payload


class RawFHIRBundle(RawFHIRBaseModel):
    source_version: str = Field(
        default="R5",
        description="FHIR version associated with this resource collection.",
    )
    fetched_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when the resource collection was assembled.",
    )
    entries: list[RawFHIRResource] = Field(
        default_factory=list,
        description="Raw FHIR resources gathered for a workflow or fetch operation.",
    )
