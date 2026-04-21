from app.models.canonical_patient import PatientDemographics, PatientSnapshot, ProvenanceRecord
from app.models.workflow_models import WorkflowMode, WorkflowRunRequest, WorkflowRunResponse
from app.services.audit.audit_logger import AuditLogger
from app.services.summarization.gemini_client import GeminiClient
from app.services.summarization.prompt_manager import build_ed_summary_prompt


class EDSummaryAgent:
    """Produces an emergency department summary artifact."""

    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self.audit_logger = AuditLogger()
        self.gemini_client = gemini_client or GeminiClient()

    def summarize(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        encounter_id: str | None = None,
    ) -> WorkflowRunResponse:
        prompt = build_ed_summary_prompt(snapshot)
        fallback_summary = self._build_fallback_summary(snapshot)
        generation = self.gemini_client.generate_summary(prompt, fallback_summary)

        response = WorkflowRunResponse.accepted(
            mode=WorkflowMode.ED_SUMMARY,
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id or (snapshot.encounter.encounter_id if snapshot.encounter else None),
            correlation_id=correlation_id,
            message="ED summary generated.",
            patient_snapshot=snapshot,
            artifacts={
                "provider": generation.provider,
                "model": generation.model,
                "used_fallback": generation.used_fallback,
            },
        )
        response.summary_text = generation.text
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="ed-summary-agent",
                note=f"ED summary generated using {generation.provider}.",
            )
        ]
        return response

    def _build_fallback_summary(self, snapshot: PatientSnapshot) -> str:
        encounter_status = snapshot.encounter.status if snapshot.encounter else "not available"
        reasons = snapshot.encounter.reason_for_visit if snapshot.encounter else "not available"
        medication_names = ", ".join(med.display for med in snapshot.medications[:5]) or "None documented"
        allergy_names = ", ".join(allergy.substance for allergy in snapshot.allergies[:5]) or "None documented"
        return (
            "ED Summary\n"
            f"- Encounter status: {encounter_status}\n"
            f"- Reason for visit: {reasons}\n"
            f"- Medications in record: {medication_names}\n"
            f"- Allergies in record: {allergy_names}\n\n"
            "Evidence From Supplied Data\n"
            "- This summary was generated only from the supplied canonical patient snapshot.\n\n"
            "Assumptions or Unknowns\n"
            "- Missing details remain unavailable because Gemini is not configured or did not return usable output."
        )

    def run(self, request: WorkflowRunRequest) -> WorkflowRunResponse:
        snapshot = request.patient_snapshot or PatientSnapshot(
            patient=PatientDemographics(patient_id=request.patient_id),
        )
        response = self.summarize(
            snapshot=snapshot,
            correlation_id=request.correlation_id,
            encounter_id=request.encounter_id,
        )
        self.audit_logger.record_event(
            event_type="workflow.ed_summary.completed",
            subject_id=snapshot.patient.patient_id,
            details={"correlation_id": response.correlation_id},
        )
        return response
