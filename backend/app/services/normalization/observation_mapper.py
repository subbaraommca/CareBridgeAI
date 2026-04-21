from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.canonical_patient import ObservationRecord
from app.models.raw_fhir import RawFHIRResource


RawObservationInput = RawFHIRResource | Mapping[str, Any]


def _payload(resource: RawObservationInput) -> dict[str, Any]:
    if isinstance(resource, RawFHIRResource):
        return dict(resource.payload)
    return dict(resource)


def _resource_id(resource: RawObservationInput) -> str:
    if isinstance(resource, RawFHIRResource):
        return resource.resource_id
    return str(dict(resource).get("id", ""))


def _codeable_text(value: Any, default: str | None = None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    if not isinstance(value, Mapping):
        return default

    text = value.get("text")
    if text:
        return str(text)

    coding = value.get("coding")
    if isinstance(coding, list):
        for item in coding:
            if not isinstance(item, Mapping):
                continue
            display = item.get("display")
            if display:
                return str(display)
            code = item.get("code")
            if code:
                return str(code)

    return default


def _coding_code(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    coding = value.get("coding")
    if not isinstance(coding, list):
        return None
    for item in coding:
        if isinstance(item, Mapping) and item.get("code"):
            return str(item["code"])
    return None


def map_observation(resource: RawObservationInput) -> ObservationRecord:
    """Map a raw FHIR Observation payload into the canonical observation record."""

    payload = _payload(resource)
    value_quantity = payload.get("valueQuantity") if isinstance(payload.get("valueQuantity"), Mapping) else {}
    value_text = (
        payload.get("valueString")
        or _codeable_text(payload.get("valueCodeableConcept"))
    )

    return ObservationRecord(
        observation_id=_resource_id(resource),
        code=_coding_code(payload.get("code")),
        display=_codeable_text(payload.get("code"), "Unknown observation") or "Unknown observation",
        status=str(payload.get("status", "unknown")),
        value_text=str(value_text) if value_text is not None else None,
        value_numeric=value_quantity.get("value"),
        unit=value_quantity.get("unit"),
        interpretation=_codeable_text((payload.get("interpretation") or [{}])[0]),
        effective_at=payload.get("effectiveDateTime") or payload.get("issued") or payload.get("effectiveInstant"),
    )
