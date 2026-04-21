from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field


def detect_fhir_version(capability_statement: Mapping[str, Any] | None) -> str:
    """Detect the FHIR release from a server capability statement."""

    if not capability_statement:
        return "unknown"

    raw_version = str(capability_statement.get("fhirVersion", "")).strip()
    if not raw_version:
        return "unknown"

    normalized = raw_version.upper()
    if normalized.startswith("5"):
        return "R5"
    if normalized.startswith("4.3"):
        return "R4B"
    if normalized.startswith("4"):
        return "R4"
    if normalized.startswith("3"):
        return "STU3"

    return normalized


class FHIRGatewayMetadata(BaseModel):
    """Normalized representation of a FHIR server capability statement."""

    base_url: str = Field(description="FHIR server base URL.")
    fhir_version: str = Field(default="unknown", description="Detected FHIR release for the server.")
    software_name: str | None = Field(default=None, description="FHIR server software name.")
    software_version: str | None = Field(default=None, description="FHIR server software version.")
    implementation_description: str | None = Field(
        default=None,
        description="Human readable implementation description from the capability statement.",
    )
    formats: list[str] = Field(default_factory=list, description="Declared supported response formats.")
    raw_capability_statement: dict[str, Any] = Field(
        default_factory=dict,
        description="Original capability statement payload returned by the server.",
    )
    supports_r4_adapter: bool = Field(
        default=True,
        description="Whether the gateway can route non-R5 sources through an adapter layer.",
    )
    native_mode: str = Field(
        default="R5",
        description="Preferred native mode for downstream internal processing.",
    )

    model_config = ConfigDict(extra="forbid")


def build_gateway_metadata(
    base_url: str,
    capability_statement: Mapping[str, Any] | None,
) -> FHIRGatewayMetadata:
    capability = dict(capability_statement or {})
    detected_version = detect_fhir_version(capability)

    return FHIRGatewayMetadata(
        base_url=base_url,
        fhir_version=detected_version,
        software_name=capability.get("software", {}).get("name"),
        software_version=capability.get("software", {}).get("version"),
        implementation_description=capability.get("implementation", {}).get("description"),
        formats=list(capability.get("format", []) or []),
        raw_capability_statement=capability,
        native_mode="R5" if detected_version == "unknown" else detected_version,
    )
