from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.canonical_patient import (
    AllergyRecord,
    ConditionRecord,
    PatientDemographics,
    PatientSnapshot,
    ProvenanceRecord,
)
from app.models.raw_fhir import RawFHIRResource
from app.services.normalization.encounter_mapper import map_encounter
from app.services.normalization.medication_mapper import map_medication
from app.services.normalization.observation_mapper import map_observation


RawFHIRInput = RawFHIRResource | Mapping[str, Any]


def _payload(resource: RawFHIRInput) -> dict[str, Any]:
    if isinstance(resource, RawFHIRResource):
        return dict(resource.payload)
    return dict(resource)


def _resource_id(resource: RawFHIRInput) -> str:
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


def _subject_reference(payload: dict[str, Any]) -> str | None:
    subject = payload.get("subject")
    if isinstance(subject, Mapping) and subject.get("reference"):
        return str(subject["reference"])

    patient = payload.get("patient")
    if isinstance(patient, Mapping) and patient.get("reference"):
        return str(patient["reference"])

    return None


def _reference_id(reference: str | None) -> str | None:
    if not reference:
        return None
    parts = reference.split("/")
    if len(parts) < 2:
        return None
    return parts[-1]


def _resources_for_type(
    resources: dict[str, Any],
    resource_type: str,
) -> list[RawFHIRInput]:
    value = resources.get(resource_type, [])
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _matches_patient(resource: RawFHIRInput, patient_id: str | None) -> bool:
    if not patient_id:
        return True
    reference_id = _reference_id(_subject_reference(_payload(resource)))
    return reference_id in {None, patient_id}


def map_patient(resource: RawFHIRInput) -> PatientDemographics:
    """Map a raw FHIR Patient payload into canonical demographics."""

    payload = _payload(resource)
    raw_name = (payload.get("name") or [{}])[0]
    name = raw_name if isinstance(raw_name, Mapping) else {}
    telecom = payload.get("telecom") if isinstance(payload.get("telecom"), list) else []
    communication = (payload.get("communication") or [{}])[0]

    phone = next(
        (
            str(item.get("value"))
            for item in telecom
            if isinstance(item, Mapping) and item.get("system") == "phone" and item.get("value")
        ),
        None,
    )
    email = next(
        (
            str(item.get("value"))
            for item in telecom
            if isinstance(item, Mapping) and item.get("system") == "email" and item.get("value")
        ),
        None,
    )
    language = _codeable_text(
        communication.get("language") if isinstance(communication, Mapping) else None,
        None,
    )

    return PatientDemographics(
        patient_id=_resource_id(resource) or "unknown-patient",
        medical_record_number=((payload.get("identifier") or [{}])[0]).get("value"),
        given_name=((name.get("given") or ["Unknown"])[0]),
        family_name=name.get("family", "Patient"),
        middle_name=((name.get("given") or [None, None])[1] if len(name.get("given") or []) > 1 else None),
        birth_date=payload.get("birthDate"),
        gender=payload.get("gender"),
        phone=phone,
        email=email,
        preferred_language=language,
    )


def map_condition(resource: RawFHIRInput) -> ConditionRecord:
    payload = _payload(resource)
    return ConditionRecord(
        condition_id=_resource_id(resource),
        code=_coding_code(payload.get("code")),
        display=_codeable_text(payload.get("code"), "Unknown condition") or "Unknown condition",
        clinical_status=_codeable_text(payload.get("clinicalStatus")),
        verification_status=_codeable_text(payload.get("verificationStatus")),
        category=_codeable_text((payload.get("category") or [{}])[0]),
        onset_datetime=payload.get("onsetDateTime"),
        abatement_datetime=payload.get("abatementDateTime"),
        recorded_at=payload.get("recordedDate"),
    )


def map_allergy(resource: RawFHIRInput) -> AllergyRecord:
    payload = _payload(resource)
    reaction = (payload.get("reaction") or [{}])[0]
    manifestation = (reaction.get("manifestation") or [{}])[0] if isinstance(reaction, Mapping) else {}

    return AllergyRecord(
        allergy_id=_resource_id(resource),
        code=_coding_code(payload.get("code")),
        substance=_codeable_text(payload.get("code"), "Unknown substance") or "Unknown substance",
        reaction=_codeable_text(manifestation),
        severity=reaction.get("severity") if isinstance(reaction, Mapping) else None,
        criticality=payload.get("criticality"),
        clinical_status=_codeable_text(payload.get("clinicalStatus")),
        verification_status=_codeable_text(payload.get("verificationStatus")),
    )


def build_patient_snapshot(
    resources: dict[str, Any],
    trace_id: str,
    source_version: str,
) -> PatientSnapshot:
    """Build a canonical patient snapshot from grouped raw FHIR resources.

    The expected input shape is a dictionary keyed by FHIR resource type with
    list values, for example `{"Patient": [...], "Encounter": [...], ...}`.
    """

    patient_resources = _resources_for_type(resources, "Patient")
    patient_id = None
    if patient_resources:
        patient_id = _resource_id(patient_resources[0]) or None
    else:
        for resource_type in (
            "Encounter",
            "Condition",
            "AllergyIntolerance",
            "MedicationRequest",
            "MedicationStatement",
            "Observation",
        ):
            for candidate in _resources_for_type(resources, resource_type):
                patient_id = _reference_id(_subject_reference(_payload(candidate)))
                if patient_id:
                    break
            if patient_id:
                break

    patient = (
        map_patient(patient_resources[0])
        if patient_resources
        else PatientDemographics(patient_id=patient_id or "unknown-patient")
    )

    encounter = next(
        (
            map_encounter(resource)
            for resource in _resources_for_type(resources, "Encounter")
            if _matches_patient(resource, patient.patient_id)
        ),
        None,
    )

    conditions = [
        map_condition(resource)
        for resource in _resources_for_type(resources, "Condition")
        if _matches_patient(resource, patient.patient_id)
    ]
    allergies = [
        map_allergy(resource)
        for resource in _resources_for_type(resources, "AllergyIntolerance")
        if _matches_patient(resource, patient.patient_id)
    ]
    medications = [
        map_medication(resource)
        for resource_type in ("MedicationRequest", "MedicationStatement")
        for resource in _resources_for_type(resources, resource_type)
        if _matches_patient(resource, patient.patient_id)
    ]
    observations = [
        map_observation(resource)
        for resource in _resources_for_type(resources, "Observation")
        if _matches_patient(resource, patient.patient_id)
    ]

    return PatientSnapshot(
        patient=patient,
        encounter=encounter,
        conditions=conditions,
        allergies=allergies,
        medications=medications,
        observations=observations,
        provenance=[
            ProvenanceRecord(
                trace_id=trace_id,
                source_version=source_version,
                agent_name="normalization.build_patient_snapshot",
                note="Canonical patient snapshot built from raw FHIR resources.",
            )
        ],
    )
