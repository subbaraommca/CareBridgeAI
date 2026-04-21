from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from typing import Any

from app.models.raw_fhir import RawFHIRResource


def _copy_resource(resource: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(resource)


def _tag_as_adapted(resource: dict[str, Any], source_version: str = "R4") -> dict[str, Any]:
    adapted = _copy_resource(resource)
    meta = adapted.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        adapted["meta"] = meta

    tags = meta.get("tag")
    if not isinstance(tags, list):
        tags = []
        meta["tag"] = tags

    tags.append(
        {
            "system": "https://carebridge.ai/fhir-adapters",
            "code": f"adapted-from-{source_version.lower()}",
            "display": f"Adapted from {source_version} for canonical handling with selective R5 support",
        }
    )
    return adapted


def _build_canonical_projection(
    resource: dict[str, Any],
    canonical_resource_type: str,
) -> dict[str, Any]:
    payload = _tag_as_adapted(resource)
    return {
        "canonical_resource_type": canonical_resource_type,
        "canonical_id": str(payload.get("id", "")),
        "source_resource_type": str(resource.get("resourceType", canonical_resource_type)),
        "source_version": "R4",
        "payload": payload,
    }


def adapt_patient_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 Patient into a canonical projection with selective R5 support.

    CareBridge AI keeps its interoperability boundary aligned to FHIR R4 while
    allowing selected R5-oriented internal features where they add value. This
    adapter is intentionally conservative: it preserves the original data, adds
    minimal normalization, and avoids destructive translation until field-level
    mappings are validated.
    """

    adapted = _build_canonical_projection(resource, "Patient")
    payload = adapted["payload"]
    name = (payload.get("name") or [{}])[0]
    adapted["canonical_patient"] = {
        "patient_id": str(payload.get("id", "")),
        "given_name": ((name.get("given") or ["Unknown"])[0]),
        "family_name": name.get("family", "Patient"),
        "birth_date": payload.get("birthDate"),
        "gender": payload.get("gender"),
        "medical_record_number": ((payload.get("identifier") or [{}])[0]).get("value"),
    }
    return adapted


def adapt_encounter_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 Encounter into a canonical projection with selective R5 support.

    The canonical target can use R5-oriented features, but the current adapter
    favors data preservation over aggressive structural change. Assumptions are
    documented in the output metadata and can be tightened as requirements mature.
    """

    adapted = _build_canonical_projection(resource, "Encounter")
    payload = adapted["payload"]
    period = payload.get("period") or {}
    location = (payload.get("location") or [{}])[0]
    adapted["canonical_encounter"] = {
        "encounter_id": str(payload.get("id", "")),
        "status": payload.get("status", "unknown"),
        "encounter_class": (payload.get("class") or {}).get("code", "unknown")
        if isinstance(payload.get("class"), dict)
        else payload.get("class", "unknown"),
        "start_time": period.get("start"),
        "end_time": period.get("end"),
        "location_name": ((location.get("location") or {}).get("display")),
        "reason_for_visit": ((payload.get("reasonCode") or [{}])[0]).get("text"),
    }
    return adapted


def adapt_condition_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 Condition into a canonical projection with selective R5 support.

    External systems may remain on R4 for some time, so this adapter keeps the
    original payload intact and normalizes only a small canonical surface needed
    by downstream workflows.
    """

    adapted = _build_canonical_projection(resource, "Condition")
    payload = adapted["payload"]
    adapted["canonical_condition"] = {
        "condition_id": str(payload.get("id", "")),
        "code": ((payload.get("code") or {}).get("coding") or [{}])[0].get("code"),
        "display": (payload.get("code") or {}).get("text", "Unknown condition"),
        "clinical_status": ((payload.get("clinicalStatus") or {}).get("text")),
        "verification_status": ((payload.get("verificationStatus") or {}).get("text")),
        "recorded_at": payload.get("recordedDate"),
        "onset_datetime": payload.get("onsetDateTime"),
    }
    return adapted


def adapt_allergy_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 AllergyIntolerance into a canonical projection with selective R5 support.

    This first-pass adapter retains the original structure and lifts only a
    narrow, low-risk set of fields into a reusable normalized view.
    """

    adapted = _build_canonical_projection(resource, "AllergyIntolerance")
    payload = adapted["payload"]
    reaction = (payload.get("reaction") or [{}])[0]
    manifestation = (reaction.get("manifestation") or [{}])[0]
    adapted["canonical_allergy"] = {
        "allergy_id": str(payload.get("id", "")),
        "code": ((payload.get("code") or {}).get("coding") or [{}])[0].get("code"),
        "substance": (payload.get("code") or {}).get("text", "Unknown substance"),
        "reaction": manifestation.get("text"),
        "severity": reaction.get("severity"),
        "criticality": payload.get("criticality"),
        "clinical_status": ((payload.get("clinicalStatus") or {}).get("text")),
        "verification_status": ((payload.get("verificationStatus") or {}).get("text")),
    }
    return adapted


def adapt_medication_request_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 MedicationRequest into a canonical projection with selective R5 support.

    The adapter keeps the upstream R4 payload available verbatim and emits a
    small medication-focused view suitable for conservative internal use until
    exact translation rules are defined.
    """

    adapted = _build_canonical_projection(resource, "MedicationRequest")
    payload = adapted["payload"]
    dosage = (payload.get("dosageInstruction") or [{}])[0]
    adapted["canonical_medication"] = {
        "medication_id": str(payload.get("id", "")),
        "code": (((payload.get("medicationCodeableConcept") or {}).get("coding") or [{}])[0]).get("code"),
        "display": (payload.get("medicationCodeableConcept") or {}).get("text", "Unknown medication"),
        "status": payload.get("status", "unknown"),
        "dosage_text": dosage.get("text"),
        "route": ((dosage.get("route") or {}).get("text")),
        "frequency": ((dosage.get("timing") or {}).get("code", {}).get("text"))
        if isinstance((dosage.get("timing") or {}).get("code"), dict)
        else None,
        "authored_on": payload.get("authoredOn"),
    }
    return adapted


def adapt_medication_statement_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 MedicationStatement into a canonical projection with selective R5 support.

    The canonical model stays stable even when external systems send R4
    statements. This adapter preserves source fidelity and exposes a small
    normalized medication view with minimal assumptions.
    """

    adapted = _build_canonical_projection(resource, "MedicationStatement")
    payload = adapted["payload"]
    dosage = (payload.get("dosage") or [{}])[0]
    adapted["canonical_medication"] = {
        "medication_id": str(payload.get("id", "")),
        "code": (((payload.get("medicationCodeableConcept") or {}).get("coding") or [{}])[0]).get("code"),
        "display": (payload.get("medicationCodeableConcept") or {}).get("text", "Unknown medication"),
        "status": payload.get("status", "unknown"),
        "dosage_text": dosage.get("text"),
        "route": ((dosage.get("route") or {}).get("text")),
        "frequency": None,
        "authored_on": payload.get("dateAsserted") or payload.get("effectiveDateTime"),
    }
    return adapted


def adapt_observation_r4_to_r5(resource: dict[str, Any]) -> dict[str, Any]:
    """Adapt an R4 Observation into a canonical projection with selective R5 support.

    This conservative scaffold keeps the original observation payload intact and
    extracts only a simple canonical view aligned to the platform's internal
    expectations.
    """

    adapted = _build_canonical_projection(resource, "Observation")
    payload = adapted["payload"]
    value_quantity = payload.get("valueQuantity") or {}
    adapted["canonical_observation"] = {
        "observation_id": str(payload.get("id", "")),
        "code": ((payload.get("code") or {}).get("coding") or [{}])[0].get("code"),
        "display": (payload.get("code") or {}).get("text", "Unknown observation"),
        "status": payload.get("status", "unknown"),
        "value_text": payload.get("valueString"),
        "value_numeric": value_quantity.get("value"),
        "unit": value_quantity.get("unit"),
        "effective_at": payload.get("effectiveDateTime"),
    }
    return adapted


def adapt_r4_resource_to_r5(resource: RawFHIRResource) -> RawFHIRResource:
    """Adapt a raw R4 resource wrapper into the platform's canonical raw wrapper.

    This compatibility helper preserves the original payload and applies a
    conservative resource-specific adapter where available. External systems may
    remain on R4 while CareBridge AI selectively supports R5-oriented internal
    features where they improve workflow modeling.
    """

    adapters: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "Patient": adapt_patient_r4_to_r5,
        "Encounter": adapt_encounter_r4_to_r5,
        "Condition": adapt_condition_r4_to_r5,
        "AllergyIntolerance": adapt_allergy_r4_to_r5,
        "MedicationRequest": adapt_medication_request_r4_to_r5,
        "MedicationStatement": adapt_medication_statement_r4_to_r5,
        "Observation": adapt_observation_r4_to_r5,
    }
    adapter = adapters.get(resource.resource_type)
    adapted_payload = adapter(resource.payload) if adapter else _tag_as_adapted(resource.payload)
    return RawFHIRResource(
        source_version="R5",
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        fetched_at=resource.fetched_at,
        payload=adapted_payload,
    )
