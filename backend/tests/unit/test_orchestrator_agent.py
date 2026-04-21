from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.canonical_patient import (
    EncounterSummary,
    MedicationRecord,
    PatientDemographics,
    PatientSnapshot,
    ProvenanceRecord,
)
from app.models.workflow_models import (
    ContextFetchResponse,
    MedRecResponse,
    MedicationFinding,
    TransitionResponse,
    WorkflowMode,
    WorkflowRunRequest,
    WorkflowRunResponse,
)


def build_snapshot() -> PatientSnapshot:
    return PatientSnapshot(
        patient=PatientDemographics(
            patient_id="patient-123",
            given_name="Alex",
            family_name="Morgan",
        ),
        encounter=EncounterSummary(
            encounter_id="enc-1",
            encounter_class="emergency",
            status="finished",
            reason_for_visit="Shortness of breath",
        ),
        medications=[
            MedicationRecord(
                medication_id="med-1",
                display="Aspirin 81 mg",
                dosage_text="81 mg daily",
                frequency="1 per day",
            )
        ],
    )


class FakePatientContextAgent:
    def __init__(self, snapshot: PatientSnapshot | None = None) -> None:
        self.snapshot = snapshot or build_snapshot()
        self.calls: list[dict[str, str | None]] = []

    def fetch_patient_context(
        self,
        patient_id: str,
        encounter_id: str | None = None,
        fhir_base_url: str | None = None,
        access_token: str | None = None,
        correlation_id: str = "patient-context",
    ) -> ContextFetchResponse:
        self.calls.append(
            {
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "fhir_base_url": fhir_base_url,
                "access_token": access_token,
                "correlation_id": correlation_id,
            }
        )
        return ContextFetchResponse(
            patient_id=patient_id,
            encounter_id=encounter_id,
            source_version="R5",
            raw_resource_count=7,
            patient_snapshot=self.snapshot,
            provenance=[
                ProvenanceRecord(
                    trace_id=correlation_id,
                    source_version="R5",
                    agent_name="patient-context-agent",
                    note="Fetched and normalized patient context.",
                )
            ],
            message="Context fetched.",
        )


class FakeEDSummaryAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def summarize(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        encounter_id: str | None = None,
    ) -> WorkflowRunResponse:
        self.calls.append({"patient_id": snapshot.patient.patient_id, "correlation_id": correlation_id})
        response = WorkflowRunResponse.accepted(
            mode=WorkflowMode.ED_SUMMARY,
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message="ED summary generated.",
            patient_snapshot=snapshot,
            artifacts={"provider": "fake"},
        )
        response.summary_text = "ED summary text."
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="ed-summary-agent",
                note="Generated ED summary.",
            )
        ]
        return response


class FakeMedRecAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def reconcile(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        encounter_id: str | None = None,
    ) -> MedRecResponse:
        self.calls.append({"patient_id": snapshot.patient.patient_id, "correlation_id": correlation_id})
        issue = MedicationFinding(
            category="missing_dose_frequency",
            severity="medium",
            medication_id="med-1",
            medication_display="Aspirin 81 mg",
            rationale="Dose or frequency is incomplete.",
            recommended_action="Verify the active medication instructions.",
        )
        response = MedRecResponse.accepted(
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message="Medication reconciliation completed.",
            summary_text="Medication reconciliation summary.",
            normalized_medications=snapshot.medications,
            issues=[issue],
            verification_questions=["What is the correct aspirin dose and frequency?"],
        )
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="medrec-agent",
                note="Ran deterministic medication reconciliation.",
            )
        ]
        return response


class FakeTransitionAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def summarize(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        transition_type: str,
        encounter_id: str | None = None,
    ) -> TransitionResponse:
        self.calls.append(
            {
                "patient_id": snapshot.patient.patient_id,
                "correlation_id": correlation_id,
                "transition_type": transition_type,
            }
        )
        response = TransitionResponse.accepted(
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message="Transition summary generated.",
            summary_text="Transition summary text.",
            mode=WorkflowMode.DISCHARGE_HANDOFF,
            artifacts={"patient_instructions": "Patient instructions text."},
        )
        response.handoff_sections = {
            "clinician_summary": "Transition summary text.",
            "patient_instructions": "Patient instructions text.",
        }
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="transition-agent",
                note="Generated transition summary.",
            )
        ]
        return response


def build_agent() -> tuple[OrchestratorAgent, FakePatientContextAgent, FakeEDSummaryAgent, FakeMedRecAgent, FakeTransitionAgent]:
    context_agent = FakePatientContextAgent()
    ed_agent = FakeEDSummaryAgent()
    medrec_agent = FakeMedRecAgent()
    transition_agent = FakeTransitionAgent()
    orchestrator = OrchestratorAgent(
        patient_context_agent=context_agent,
        ed_summary_agent=ed_agent,
        medrec_agent=medrec_agent,
        transition_agent=transition_agent,
    )
    return orchestrator, context_agent, ed_agent, medrec_agent, transition_agent


def test_orchestrator_runs_ed_summary_mode() -> None:
    orchestrator, context_agent, ed_agent, medrec_agent, transition_agent = build_agent()
    request = WorkflowRunRequest(
        mode=WorkflowMode.ED_SUMMARY,
        patient_id="patient-123",
        encounter_id="enc-1",
        correlation_id="request-corr-1",
        metadata={"fhir_base_url": "https://example.org/fhir", "access_token": "secret-token"},
    )

    response = orchestrator.run(request)

    assert response.mode is WorkflowMode.ED_SUMMARY
    assert response.status == "completed"
    assert response.summary_text == "ED summary text."
    assert response.findings == []
    assert response.artifacts["source_version"] == "R5"
    assert response.artifacts["raw_resource_count"] == 7
    assert response.artifacts["request_correlation_id"] == "request-corr-1"
    assert response.artifacts["ed_summary"]["summary_text"] == "ED summary text."
    assert "medrec" not in response.artifacts
    assert "transition" not in response.artifacts
    assert response.correlation_id != "request-corr-1"
    assert len(context_agent.calls) == 1
    assert context_agent.calls[0]["fhir_base_url"] == "https://example.org/fhir"
    assert context_agent.calls[0]["access_token"] == "secret-token"
    assert len(ed_agent.calls) == 1
    assert medrec_agent.calls == []
    assert transition_agent.calls == []


def test_orchestrator_runs_medrec_mode() -> None:
    orchestrator, _, ed_agent, medrec_agent, transition_agent = build_agent()
    request = WorkflowRunRequest(
        mode=WorkflowMode.MED_REC,
        patient_id="patient-123",
        encounter_id="enc-1",
        correlation_id="request-corr-2",
    )

    response = orchestrator.run(request)

    assert response.mode is WorkflowMode.MED_REC
    assert response.summary_text == "Medication reconciliation summary."
    assert len(response.findings) == 1
    assert response.findings[0].category == "missing_dose_frequency"
    assert response.artifacts["medrec"]["verification_questions"] == [
        "What is the correct aspirin dose and frequency?"
    ]
    assert ed_agent.calls == []
    assert len(medrec_agent.calls) == 1
    assert transition_agent.calls == []


def test_orchestrator_runs_discharge_handoff_mode() -> None:
    orchestrator, _, ed_agent, medrec_agent, transition_agent = build_agent()
    request = WorkflowRunRequest(
        mode=WorkflowMode.DISCHARGE_HANDOFF,
        patient_id="patient-123",
        encounter_id="enc-1",
        correlation_id="request-corr-3",
    )

    response = orchestrator.run(request)

    assert response.mode is WorkflowMode.DISCHARGE_HANDOFF
    assert response.summary_text == "Transition summary text."
    assert len(response.findings) == 1
    assert response.artifacts["transition"]["patient_instructions"] == "Patient instructions text."
    assert response.artifacts["medrec"]["summary_text"] == "Medication reconciliation summary."
    assert ed_agent.calls == []
    assert len(medrec_agent.calls) == 1
    assert len(transition_agent.calls) == 1


def test_orchestrator_runs_full_transition_of_care_mode() -> None:
    orchestrator, _, ed_agent, medrec_agent, transition_agent = build_agent()
    request = WorkflowRunRequest(
        mode=WorkflowMode.FULL_TRANSITION_OF_CARE,
        patient_id="patient-123",
        encounter_id="enc-1",
        correlation_id="request-corr-4",
    )

    response = orchestrator.run(request)

    assert response.mode is WorkflowMode.FULL_TRANSITION_OF_CARE
    assert response.summary_text is not None
    assert "ED Summary" in response.summary_text
    assert "Medication Reconciliation" in response.summary_text
    assert "Transition Summary" in response.summary_text
    assert len(response.findings) == 1
    assert response.patient_snapshot is not None
    assert response.patient_snapshot.patient.patient_id == "patient-123"
    assert response.provenance[-1].agent_name == "orchestrator-agent"
    assert len(ed_agent.calls) == 1
    assert len(medrec_agent.calls) == 1
    assert len(transition_agent.calls) == 1


def test_orchestrator_rejects_empty_patient_id() -> None:
    orchestrator, _, _, _, _ = build_agent()
    request = WorkflowRunRequest(
        mode=WorkflowMode.MED_REC,
        patient_id="   ",
        correlation_id="request-corr-5",
    )

    try:
        orchestrator.run(request)
    except ValueError as exc:
        assert str(exc) == "patient_id must not be empty."
    else:
        raise AssertionError("Expected ValueError for empty patient_id.")
