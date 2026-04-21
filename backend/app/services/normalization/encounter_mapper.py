from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.canonical_patient import EncounterSummary
from app.models.raw_fhir import RawFHIRResource


RawEncounterInput = RawFHIRResource | Mapping[str, Any]


def _payload(resource: RawEncounterInput) -> dict[str, Any]:
    if isinstance(resource, RawFHIRResource):
        return dict(resource.payload)
    return dict(resource)


def _resource_id(resource: RawEncounterInput) -> str:
    if isinstance(resource, RawFHIRResource):
        return resource.resource_id
    return str(dict(resource).get("id", ""))


def _codeable_text(value: Any, default: str | None = None) -> str | None:
    if isinstance(value, str):
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


def map_encounter(resource: RawEncounterInput) -> EncounterSummary:
    """Map a raw FHIR Encounter payload into the canonical encounter summary."""

    payload = _payload(resource)
    period = payload.get("period") if isinstance(payload.get("period"), Mapping) else {}
    encounter_class = payload.get("class")
    raw_location = (payload.get("location") or [{}])[0]
    location = raw_location if isinstance(raw_location, Mapping) else {}
    raw_participant = (payload.get("participant") or [{}])[0]
    participant = raw_participant if isinstance(raw_participant, Mapping) else {}
    hospitalization = payload.get("hospitalization") if isinstance(payload.get("hospitalization"), Mapping) else {}

    if isinstance(encounter_class, Mapping):
        encounter_class_value = str(
            encounter_class.get("display")
            or encounter_class.get("code")
            or "unknown"
        )
    else:
        encounter_class_value = str(encounter_class or "unknown")

    return EncounterSummary(
        encounter_id=_resource_id(resource),
        status=str(payload.get("status", "unknown")),
        encounter_class=encounter_class_value,
        start_time=period.get("start"),
        end_time=period.get("end"),
        facility_name=((payload.get("serviceProvider") or {}).get("display")),
        location_name=((location.get("location") or {}).get("display")),
        attending_clinician=((participant.get("individual") or {}).get("display")),
        reason_for_visit=_codeable_text((payload.get("reasonCode") or [{}])[0]),
        discharge_disposition=_codeable_text(hospitalization.get("dischargeDisposition")),
    )
