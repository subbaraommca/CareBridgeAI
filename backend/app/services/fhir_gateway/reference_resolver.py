from typing import NamedTuple

from app.models.raw_fhir import RawFHIRBundle, RawFHIRResource


class ParsedReference(NamedTuple):
    resource_type: str
    resource_id: str


def parse_reference(reference: str) -> ParsedReference | None:
    """Parse a simple FHIR reference such as Patient/123 or Encounter/abc."""

    normalized = reference.strip()
    if not normalized:
        return None

    if "://" in normalized:
        normalized = normalized.rstrip("/").rsplit("/", 2)[-2:]
        if len(normalized) != 2:
            return None
        resource_type, resource_id = normalized
    else:
        parts = normalized.split("/")
        if len(parts) != 2:
            return None
        resource_type, resource_id = parts

    if not resource_type or not resource_id:
        return None

    return ParsedReference(resource_type=resource_type, resource_id=resource_id)


def resolve_reference(bundle: RawFHIRBundle, reference: str) -> RawFHIRResource | None:
    parsed_reference = parse_reference(reference)
    if parsed_reference is None:
        return None

    for resource in bundle.entries:
        if (
            resource.resource_type == parsed_reference.resource_type
            and resource.resource_id == parsed_reference.resource_id
        ):
            return resource
    return None
