from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceSystemProvenance(BaseModel):
    """Provenance describing the source clinical system and source contract version."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source_system: str = Field(default="unknown", description="Originating EHR or source platform.")
    source_version: str = Field(default="R5", description="FHIR version or equivalent source contract version.")
    fetched_at: datetime = Field(default_factory=utc_now, description="Timestamp when source data was fetched.")


class NormalizationProvenance(BaseModel):
    """Provenance describing canonical normalization logic applied to source data."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    normalization_version: str = Field(
        default="carebridge-normalization-v1",
        description="Version identifier for normalization logic.",
    )
    canonical_model_version: str = Field(
        default="carebridge-r5-native-v1",
        description="Version identifier for the internal canonical model.",
    )


class SummarizationProvenance(BaseModel):
    """Provenance describing summarization configuration and fallback behavior."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    summarization_version: str = Field(
        default="carebridge-summarization-v1",
        description="Version identifier for summarization prompt or orchestration logic.",
    )
    provider: str = Field(default="gemini", description="Provider used for summarization.")
    model_name: str | None = Field(default=None, description="Configured summarization model when used.")
    used_fallback: bool = Field(default=False, description="Whether deterministic fallback text was used.")


class ProvenanceEnvelope(BaseModel):
    """Combined provenance metadata carried across fetch, normalization, and summarization layers."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    trace_id: str = Field(description="Workflow trace identifier.")
    source: SourceSystemProvenance = Field(description="Source system provenance metadata.")
    normalization: NormalizationProvenance = Field(description="Normalization provenance metadata.")
    summarization: SummarizationProvenance | None = Field(
        default=None,
        description="Optional summarization provenance metadata.",
    )
    recorded_at: datetime = Field(default_factory=utc_now, description="Timestamp when provenance was assembled.")


def build_provenance_envelope(
    trace_id: str,
    source_system: str,
    source_version: str,
    normalization_version: str = "carebridge-normalization-v1",
    summarization_version: str | None = None,
    summarization_provider: str = "gemini",
    summarization_model: str | None = None,
    used_fallback: bool = False,
) -> ProvenanceEnvelope:
    summarization = None
    if summarization_version is not None:
        summarization = SummarizationProvenance(
            summarization_version=summarization_version,
            provider=summarization_provider,
            model_name=summarization_model,
            used_fallback=used_fallback,
        )

    return ProvenanceEnvelope(
        trace_id=trace_id,
        source=SourceSystemProvenance(source_system=source_system, source_version=source_version),
        normalization=NormalizationProvenance(normalization_version=normalization_version),
        summarization=summarization,
    )
