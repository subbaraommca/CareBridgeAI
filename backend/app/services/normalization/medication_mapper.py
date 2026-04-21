from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.canonical_patient import MedicationRecord
from app.models.raw_fhir import RawFHIRResource


RawMedicationInput = RawFHIRResource | Mapping[str, Any]


def _payload(resource: RawMedicationInput) -> dict[str, Any]:
    if isinstance(resource, RawFHIRResource):
        return dict(resource.payload)
    return dict(resource)


def _resource_id(resource: RawMedicationInput) -> str:
    if isinstance(resource, RawFHIRResource):
        return resource.resource_id
    return str(dict(resource).get("id", ""))


def _codeable_text(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, Mapping):
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


def _frequency_text(dosage: Mapping[str, Any]) -> str | None:
    timing = dosage.get("timing")
    if not isinstance(timing, Mapping):
        return None

    code = timing.get("code")
    if isinstance(code, Mapping):
        return _codeable_text(code, "")

    repeat = timing.get("repeat")
    if not isinstance(repeat, Mapping):
        return None

    frequency = repeat.get("frequency")
    period = repeat.get("period")
    period_unit = repeat.get("periodUnit")
    if frequency and period and period_unit:
        return f"{frequency} per {period} {period_unit}"
    if frequency:
        return str(frequency)
    return None


def _medication_details(payload: dict[str, Any]) -> tuple[str | None, str]:
    medication_codeable_concept = payload.get("medicationCodeableConcept")
    if isinstance(medication_codeable_concept, Mapping):
        return (
            _coding_code(medication_codeable_concept),
            _codeable_text(medication_codeable_concept, "Unknown medication"),
        )

    medication_reference = payload.get("medicationReference")
    if isinstance(medication_reference, Mapping):
        reference = medication_reference.get("reference")
        display = medication_reference.get("display")
        return (
            str(reference).split("/")[-1] if reference else None,
            str(display or reference or "Unknown medication"),
        )

    return None, "Unknown medication"


def map_medication(resource: RawMedicationInput) -> MedicationRecord:
    """Map MedicationRequest or MedicationStatement payloads into canonical medication records."""

    payload = _payload(resource)
    dosage = (payload.get("dosageInstruction") or payload.get("dosage") or [{}])[0]
    code, display = _medication_details(payload)

    requester = payload.get("requester") if isinstance(payload.get("requester"), Mapping) else {}
    information_source = (
        payload.get("informationSource") if isinstance(payload.get("informationSource"), Mapping) else {}
    )

    return MedicationRecord(
        medication_id=_resource_id(resource),
        code=code,
        display=display,
        status=str(payload.get("status", "unknown")),
        dosage_text=dosage.get("text") if isinstance(dosage, Mapping) else None,
        route=_codeable_text((dosage.get("route") if isinstance(dosage, Mapping) else None), "")
        or None,
        frequency=_frequency_text(dosage) if isinstance(dosage, Mapping) else None,
        authored_on=payload.get("authoredOn") or payload.get("effectiveDateTime") or payload.get("dateAsserted"),
        prescriber=str(
            requester.get("display")
            or information_source.get("display")
            or ""
        )
        or None,
    )
