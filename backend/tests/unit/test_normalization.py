from app.services.normalization.encounter_mapper import map_encounter
from app.services.normalization.medication_mapper import map_medication
from app.services.normalization.observation_mapper import map_observation
from app.services.normalization.patient_mapper import build_patient_snapshot, map_allergy, map_condition, map_patient


PATIENT = {
    "resourceType": "Patient",
    "id": "patient-123",
    "identifier": [{"value": "MRN-42"}],
    "name": [{"given": ["Alex", "Jordan"], "family": "Morgan"}],
    "gender": "female",
    "birthDate": "1980-01-01",
    "telecom": [
        {"system": "phone", "value": "555-111-2222"},
        {"system": "email", "value": "alex@example.org"},
    ],
    "communication": [{"language": {"text": "English"}}],
}

ENCOUNTER = {
    "resourceType": "Encounter",
    "id": "enc-1",
    "status": "finished",
    "class": {"code": "EMER"},
    "subject": {"reference": "Patient/patient-123"},
    "period": {"start": "2026-04-16T10:00:00Z", "end": "2026-04-16T12:00:00Z"},
    "serviceProvider": {"display": "CareBridge General Hospital"},
    "participant": [{"individual": {"display": "Dr. Avery"}}],
    "reasonCode": [{"text": "Shortness of breath"}],
    "hospitalization": {"dischargeDisposition": {"text": "Home"}},
}

CONDITION = {
    "resourceType": "Condition",
    "id": "cond-1",
    "subject": {"reference": "Patient/patient-123"},
    "code": {"text": "Hypertension", "coding": [{"code": "38341003"}]},
    "clinicalStatus": {"text": "active"},
    "verificationStatus": {"text": "confirmed"},
    "category": [{"text": "problem-list-item"}],
    "onsetDateTime": "2026-04-01T09:00:00Z",
}

ALLERGY = {
    "resourceType": "AllergyIntolerance",
    "id": "alg-1",
    "patient": {"reference": "Patient/patient-123"},
    "code": {"text": "Penicillin", "coding": [{"code": "70618"}]},
    "criticality": "high",
    "reaction": [{"severity": "severe", "manifestation": [{"text": "Rash"}]}],
}

MEDICATION_REQUEST = {
    "resourceType": "MedicationRequest",
    "id": "medreq-1",
    "status": "active",
    "subject": {"reference": "Patient/patient-123"},
    "medicationCodeableConcept": {"text": "Aspirin 81 mg", "coding": [{"code": "1191"}]},
    "dosageInstruction": [
        {
            "text": "Take one tablet daily",
            "route": {"text": "oral"},
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
        }
    ],
    "authoredOn": "2026-04-16T11:00:00Z",
    "requester": {"display": "Dr. Avery"},
}

MEDICATION_STATEMENT = {
    "resourceType": "MedicationStatement",
    "id": "medstmt-1",
    "status": "active",
    "subject": {"reference": "Patient/patient-123"},
    "medicationReference": {"reference": "Medication/metformin", "display": "Metformin 500 mg"},
    "dosage": [{"text": "500 mg twice daily", "route": {"text": "oral"}}],
    "effectiveDateTime": "2026-04-16T11:30:00Z",
}

OBSERVATION = {
    "resourceType": "Observation",
    "id": "obs-1",
    "status": "final",
    "subject": {"reference": "Patient/patient-123"},
    "code": {"text": "Heart rate", "coding": [{"code": "8867-4"}]},
    "valueQuantity": {"value": 88, "unit": "beats/minute"},
    "interpretation": [{"text": "Normal"}],
    "effectiveDateTime": "2026-04-16T11:35:00Z",
}

UNRELATED_OBSERVATION = {
    "resourceType": "Observation",
    "id": "obs-2",
    "status": "final",
    "subject": {"reference": "Patient/other-patient"},
    "code": {"text": "Respiratory rate"},
    "valueString": "18",
}


def test_individual_mappers_extract_common_fhir_fields() -> None:
    patient = map_patient(PATIENT)
    encounter = map_encounter(ENCOUNTER)
    condition = map_condition(CONDITION)
    allergy = map_allergy(ALLERGY)
    medication = map_medication(MEDICATION_REQUEST)
    observation = map_observation(OBSERVATION)

    assert patient.medical_record_number == "MRN-42"
    assert patient.preferred_language == "English"
    assert encounter.reason_for_visit == "Shortness of breath"
    assert condition.code == "38341003"
    assert allergy.reaction == "Rash"
    assert medication.frequency == "1 per 1 d"
    assert observation.value_numeric == 88
    assert observation.unit == "beats/minute"


def test_medication_mapper_supports_medication_reference_and_dosage_basics() -> None:
    medication = map_medication(MEDICATION_STATEMENT)

    assert medication.display == "Metformin 500 mg"
    assert medication.code == "metformin"
    assert medication.dosage_text == "500 mg twice daily"
    assert medication.route == "oral"


def test_build_patient_snapshot_builds_canonical_snapshot_and_filters_by_subject() -> None:
    snapshot = build_patient_snapshot(
        {
            "Patient": [PATIENT],
            "Encounter": [ENCOUNTER],
            "Condition": [CONDITION],
            "AllergyIntolerance": [ALLERGY],
            "MedicationRequest": [MEDICATION_REQUEST],
            "MedicationStatement": [MEDICATION_STATEMENT],
            "Observation": [OBSERVATION, UNRELATED_OBSERVATION],
        },
        trace_id="trace-123",
        source_version="R4",
    )

    assert snapshot.patient.patient_id == "patient-123"
    assert snapshot.patient.family_name == "Morgan"
    assert snapshot.encounter is not None
    assert snapshot.encounter.discharge_disposition == "Home"
    assert len(snapshot.conditions) == 1
    assert snapshot.conditions[0].display == "Hypertension"
    assert len(snapshot.allergies) == 1
    assert snapshot.allergies[0].substance == "Penicillin"
    assert len(snapshot.medications) == 2
    assert {med.display for med in snapshot.medications} == {"Aspirin 81 mg", "Metformin 500 mg"}
    assert len(snapshot.observations) == 1
    assert snapshot.observations[0].display == "Heart rate"
    assert snapshot.provenance[0].trace_id == "trace-123"
    assert snapshot.provenance[0].source_version == "R4"
