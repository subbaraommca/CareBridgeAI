from app.agents.medrec_agent import MedRecAgent
from app.models.canonical_patient import AllergyRecord, MedicationRecord, PatientDemographics, PatientSnapshot
from app.models.workflow_models import MedRecRequest
from app.services.med_safety.allergy_rules import detect_allergy_conflicts
from app.services.med_safety.duplicate_rules import (
    detect_duplicate_medications_by_name,
    detect_possible_duplicate_therapy,
    normalize_medication_name,
)
from app.services.med_safety.verification_rules import (
    detect_missing_dose_frequency,
    generate_verification_questions,
)


def build_snapshot(
    medications: list[MedicationRecord],
    allergies: list[AllergyRecord] | None = None,
) -> PatientSnapshot:
    return PatientSnapshot(
        patient=PatientDemographics(patient_id="patient-123", given_name="Alex", family_name="Morgan"),
        medications=medications,
        allergies=allergies or [],
    )


def test_normalize_medication_name_removes_noise_tokens() -> None:
    assert normalize_medication_name("Aspirin 81 mg tablet") == "aspirin"
    assert normalize_medication_name(" Metformin 500 MG oral tablet ") == "metformin"


def test_duplicate_medication_detection_finds_exact_name_duplicates() -> None:
    medications = [
        MedicationRecord(medication_id="med-1", display="Aspirin 81 mg tablet"),
        MedicationRecord(medication_id="med-2", display="Aspirin 325 mg tablet"),
        MedicationRecord(medication_id="med-3", display="Metformin 500 mg"),
    ]

    issues = detect_duplicate_medications_by_name(medications)

    assert len(issues) == 1
    assert issues[0].category == "duplicate_medication"
    assert issues[0].severity == "high"
    assert issues[0].medication_display == "Aspirin 325 mg tablet"


def test_possible_duplicate_therapy_detection_finds_similar_names() -> None:
    medications = [
        MedicationRecord(medication_id="med-1", display="Metoprolol tartrate"),
        MedicationRecord(medication_id="med-2", display="Metoprolol succinate"),
        MedicationRecord(medication_id="med-3", display="Lisinopril"),
    ]

    issues = detect_possible_duplicate_therapy(medications, similarity_threshold=0.7)

    assert len(issues) == 1
    assert issues[0].category == "possible_duplicate_therapy"
    assert issues[0].severity == "low"


def test_allergy_conflict_detection_matches_substance_text() -> None:
    medications = [
        MedicationRecord(medication_id="med-1", display="Penicillin V potassium"),
        MedicationRecord(medication_id="med-2", display="Metformin"),
    ]
    allergies = [
        AllergyRecord(allergy_id="alg-1", substance="Penicillin", reaction="Rash"),
    ]

    issues = detect_allergy_conflicts(medications, allergies)

    assert len(issues) == 1
    assert issues[0].category == "allergy_conflict"
    assert issues[0].severity == "high"


def test_missing_dose_frequency_detection_flags_incomplete_medications() -> None:
    medications = [
        MedicationRecord(medication_id="med-1", display="Lisinopril", dosage_text=None, frequency=None),
        MedicationRecord(
            medication_id="med-2",
            display="Metformin",
            dosage_text="500 mg twice daily",
            frequency="2 per day",
        ),
    ]

    issues = detect_missing_dose_frequency(medications)

    assert len(issues) == 1
    assert issues[0].category == "missing_dose_frequency"
    assert issues[0].severity == "medium"


def test_verification_question_generation_is_deterministic_and_deduplicated() -> None:
    medications = [
        MedicationRecord(medication_id="med-1", display="Aspirin"),
    ]
    issues = detect_missing_dose_frequency(medications) + detect_missing_dose_frequency(medications)

    questions = generate_verification_questions(medications, issues)

    assert questions == ["What dose and frequency should be recorded for Aspirin?"]


def test_medrec_agent_happy_path_returns_no_issues() -> None:
    snapshot = build_snapshot(
        [
            MedicationRecord(
                medication_id="med-1",
                display="Metformin",
                dosage_text="500 mg twice daily",
                frequency="2 per day",
            )
        ]
    )

    response = MedRecAgent().reconcile(snapshot, correlation_id="corr-1")

    assert response.issues == []
    assert response.verification_questions == []
    assert response.summary_text == "Reviewed 1 medications and found 0 issues. 0 verification questions were generated."


def test_medrec_agent_returns_structured_response_for_multiple_issue_types() -> None:
    snapshot = build_snapshot(
        medications=[
            MedicationRecord(medication_id="med-1", display="Aspirin 81 mg tablet", dosage_text=None, frequency=None),
            MedicationRecord(medication_id="med-2", display="Aspirin 325 mg tablet", dosage_text=None, frequency=None),
            MedicationRecord(medication_id="med-3", display="Penicillin V potassium", dosage_text="1 tab", frequency="1 per day"),
            MedicationRecord(medication_id="med-4", display="Metoprolol tartrate", dosage_text="25 mg", frequency="2 per day"),
            MedicationRecord(medication_id="med-5", display="Metoprolol succinate", dosage_text="50 mg", frequency="1 per day"),
        ],
        allergies=[AllergyRecord(allergy_id="alg-1", substance="Penicillin", reaction="Rash")],
    )

    response = MedRecAgent().reconcile(snapshot, correlation_id="corr-2")

    categories = [issue.category for issue in response.issues]

    assert "duplicate_medication" in categories
    assert "allergy_conflict" in categories
    assert "missing_dose_frequency" in categories
    assert "possible_duplicate_therapy" in categories
    assert response.findings == response.issues
    assert len(response.verification_questions) >= 4
    assert "Reviewed 5 medications and found" in (response.summary_text or "")


def test_medrec_agent_run_supports_request_wrapper_without_snapshot() -> None:
    request = MedRecRequest(
        patient_id="patient-123",
        medications=[
            MedicationRecord(medication_id="med-1", display="Lisinopril", dosage_text=None, frequency=None),
        ],
        allergies=[],
        correlation_id="corr-3",
    )

    response = MedRecAgent().run(request)

    assert response.patient_id == "patient-123"
    assert len(response.issues) == 1
    assert response.verification_questions == ["What dose and frequency should be recorded for Lisinopril?"]
