from app.models.canonical_patient import (
    EncounterSummary,
    MedicationRecord,
    PatientDemographics,
    PatientSnapshot,
    ProvenanceRecord,
)
from app.models.raw_fhir import RawFHIRResource
from app.models.workflow_models import (
    ContextFetchResponse,
    MedicationFinding,
    MedRecResponse,
    TransitionRequest,
    WorkflowMode,
    WorkflowRunRequest,
    WorkflowRunResponse,
)


def test_patient_snapshot_model_creation() -> None:
    snapshot = PatientSnapshot(
        patient=PatientDemographics(
            patient_id="patient-123",
            given_name="Alex",
            family_name="Morgan",
            gender="female",
        ),
        encounter=EncounterSummary(
            encounter_id="enc-1",
            encounter_class="emergency",
            status="in-progress",
        ),
        medications=[
            MedicationRecord(
                medication_id="med-1",
                display="Aspirin 81 mg",
                status="active",
            )
        ],
        provenance=[
            ProvenanceRecord(
                trace_id="trace-123",
                source_system="ehr-primary",
                agent_name="patient-context-agent",
            )
        ],
    )

    assert snapshot.patient.patient_id == "patient-123"
    assert snapshot.encounter is not None
    assert snapshot.encounter.encounter_class == "emergency"
    assert snapshot.medications[0].display == "Aspirin 81 mg"


def test_workflow_models_accept_example_payloads() -> None:
    resource = RawFHIRResource(
        source_version="R5",
        resource_type="Patient",
        resource_id="patient-123",
        payload={"resourceType": "Patient", "id": "patient-123"},
    )

    request = WorkflowRunRequest(
        mode=WorkflowMode.MED_REC,
        patient_id="patient-123",
        encounter_id="enc-1",
        source_resources=[resource],
    )
    response = WorkflowRunResponse.accepted(
        mode=request.mode,
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
        correlation_id=request.correlation_id,
        message="Accepted",
    )
    medrec_response = MedRecResponse.accepted(
        patient_id="patient-123",
        encounter_id="enc-1",
        correlation_id="corr-1",
        message="Medication reconciliation accepted",
        findings=[
            MedicationFinding(
                category="duplicate_medication",
                severity="medium",
                medication_display="Aspirin 81 mg",
                rationale="Possible duplicate detected.",
            )
        ],
    )
    context_response = ContextFetchResponse(
        patient_id="patient-123",
        encounter_id="enc-1",
        resources=[resource],
        message="Fetched context",
    )
    transition_request = TransitionRequest(
        patient_id="patient-123",
        encounter_id="enc-1",
    )

    assert response.mode is WorkflowMode.MED_REC
    assert medrec_response.findings[0].category == "duplicate_medication"
    assert context_response.resources[0].resource_id == "patient-123"
    assert transition_request.mode is WorkflowMode.DISCHARGE_HANDOFF
