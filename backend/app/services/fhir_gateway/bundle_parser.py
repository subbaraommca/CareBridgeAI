from datetime import UTC, datetime
from typing import Any, Mapping

from app.models.raw_fhir import RawFHIRBundle, RawFHIRResource


def _infer_resource_id(resource: Mapping[str, Any], entry: Mapping[str, Any], index: int) -> str:
    resource_id = resource.get("id")
    if resource_id:
        return str(resource_id)

    full_url = str(entry.get("fullUrl", "")).rstrip("/")
    if full_url and "/" in full_url:
        return full_url.rsplit("/", 1)[-1]

    return f"resource-{index}"


def extract_bundle_entries(
    bundle_payload: Mapping[str, Any] | None,
    source_version: str = "R5",
) -> list[RawFHIRResource]:
    """Safely extract raw resources from a FHIR bundle payload."""

    if not isinstance(bundle_payload, Mapping):
        return []

    entries = bundle_payload.get("entry", [])
    if not isinstance(entries, list):
        return []

    fetched_at = datetime.now(UTC)
    resources: list[RawFHIRResource] = []

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue

        resource = entry.get("resource")
        if not isinstance(resource, Mapping):
            continue

        resource_type = resource.get("resourceType")
        if not resource_type:
            continue

        resources.append(
            RawFHIRResource(
                source_version=source_version,
                resource_type=str(resource_type),
                resource_id=_infer_resource_id(resource, entry, index),
                fetched_at=fetched_at,
                payload=dict(resource),
            )
        )

    return resources


def parse_bundle(
    bundle_payload: Mapping[str, Any] | None,
    source_version: str = "R5",
) -> RawFHIRBundle:
    """Convert an arbitrary FHIR bundle payload into the internal raw bundle wrapper."""

    return RawFHIRBundle(
        source_version=source_version,
        entries=extract_bundle_entries(bundle_payload, source_version=source_version),
    )


def extract_resources(bundle: RawFHIRBundle, resource_type: str | None = None) -> list[RawFHIRResource]:
    if resource_type is None:
        return list(bundle.entries)
    return [entry for entry in bundle.entries if entry.resource_type == resource_type]
