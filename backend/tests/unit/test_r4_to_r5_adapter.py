from app.models.raw_fhir import RawFHIRResource
from app.services.adapters.r4_to_r5 import (
    adapt_allergy_r4_to_r5,
    adapt_condition_r4_to_r5,
    adapt_encounter_r4_to_r5,
    adapt_medication_request_r4_to_r5,
    adapt_medication_statement_r4_to_r5,
    adapt_observation_r4_to_r5,
    adapt_patient_r4_to_r5,
    adapt_r4_resource_to_r5,
)


PATIENT_R4 = {
    "resourceType": "Patient",
    "id": "patient-123",
    "name": [{"given": ["Alex"], "family": "Morgan"}],
    "gender": "female",
    "birthDate": "1980-01-01",
    "identifier": [{"value": "MRN-100"}],
}

ENCOUNTER_R4 = {
    "resourceType": "Encounter",
    "id": "enc-1",
    "status": "finished",
    "class": {"code": "EMER"},
    "period": {"start": "2026-04-16T10:00:00Z", "end": "2026-04-16T12:00:00Z"},
    "reasonCode": [{"text": "Chest pain"}],
}

CONDITION_R4 = {
    "resourceType": "Condition",
    "id": "cond-1",
    "code": {"text": "Hypertension", "coding": [{"code": "38341003"}]},
    "clinicalStatus": {"text": "active"},
    "verificationStatus": {"text": "confirmed"},
    "recordedDate": "2026-04-16T12:00:00Z",
}

ALLERGY_R4 = {
    "resourceType": "AllergyIntolerance",
    "id": "alg-1",
    "code": {"text": "Penicillin", "coding": [{"code": "70618"}]},
    "criticality": "high",
    "reaction": [{"severity": "severe", "manifestation": [{"text": "Rash"}]}],
}

MEDICATION_REQUEST_R4 = {
    "resourceType": "MedicationRequest",
    "id": "mr-1",
    "status": "active",
    "authoredOn": "2026-04-16T11:00:00Z",
    "medicationCodeableConcept": {"text": "Aspirin 81 mg", "coding": [{"code": "1191"}]},
    "dosageInstruction": [{"text": "Take daily", "route": {"text": "oral"}}],
}

MEDICATION_STATEMENT_R4 = {
    "resourceType": "MedicationStatement",
    "id": "ms-1",
    "status": "active",
    "effectiveDateTime": "2026-04-16T11:00:00Z",
    "medicationCodeableConcept": {"text": "Metformin", "coding": [{"code": "860975"}]},
    "dosage": [{"text": "500 mg twice daily", "route": {"text": "oral"}}],
}

OBSERVATION_R4 = {
    "resourceType": "Observation",
    "id": "obs-1",
    "status": "final",
    "code": {"text": "Heart rate", "coding": [{"code": "8867-4"}]},
    "valueQuantity": {"value": 80, "unit": "beats/minute"},
    "effectiveDateTime": "2026-04-16T11:30:00Z",
}


def test_adapt_patient_r4_to_r5_preserves_payload_and_extracts_canonical_fields() -> None:
    adapted = adapt_patient_r4_to_r5(PATIENT_R4)

    assert adapted["source_version"] == "R4"
    assert adapted["payload"]["resourceType"] == "Patient"
    assert adapted["canonical_patient"]["patient_id"] == "patient-123"
    assert adapted["canonical_patient"]["medical_record_number"] == "MRN-100"


def test_adapt_encounter_and_condition_r4_to_r5_extract_basic_canonical_views() -> None:
    encounter = adapt_encounter_r4_to_r5(ENCOUNTER_R4)
    condition = adapt_condition_r4_to_r5(CONDITION_R4)

    assert encounter["canonical_encounter"]["encounter_class"] == "EMER"
    assert encounter["canonical_encounter"]["reason_for_visit"] == "Chest pain"
    assert condition["canonical_condition"]["display"] == "Hypertension"
    assert condition["canonical_condition"]["clinical_status"] == "active"


def test_adapt_allergy_and_medication_resources_r4_to_r5_extract_expected_fields() -> None:
    allergy = adapt_allergy_r4_to_r5(ALLERGY_R4)
    medication_request = adapt_medication_request_r4_to_r5(MEDICATION_REQUEST_R4)
    medication_statement = adapt_medication_statement_r4_to_r5(MEDICATION_STATEMENT_R4)

    assert allergy["canonical_allergy"]["substance"] == "Penicillin"
    assert allergy["canonical_allergy"]["reaction"] == "Rash"
    assert medication_request["canonical_medication"]["display"] == "Aspirin 81 mg"
    assert medication_statement["canonical_medication"]["display"] == "Metformin"


def test_adapt_observation_r4_to_r5_extracts_value_fields() -> None:
    adapted = adapt_observation_r4_to_r5(OBSERVATION_R4)

    assert adapted["canonical_observation"]["display"] == "Heart rate"
    assert adapted["canonical_observation"]["value_numeric"] == 80
    assert adapted["canonical_observation"]["unit"] == "beats/minute"


def test_generic_raw_resource_adapter_wraps_structured_adapter_output() -> None:
    raw_resource = RawFHIRResource(
        source_version="R4",
        resource_type="Patient",
        resource_id="patient-123",
        payload=PATIENT_R4,
    )

    adapted = adapt_r4_resource_to_r5(raw_resource)

    assert adapted.source_version == "R5"
    assert adapted.payload["canonical_resource_type"] == "Patient"
    assert adapted.payload["canonical_patient"]["family_name"] == "Morgan"
