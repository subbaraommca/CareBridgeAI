from app.models.canonical_patient import PatientDemographics, PatientSnapshot, ProvenanceRecord
from app.models.workflow_models import TransitionRequest, TransitionResponse
from app.services.audit.audit_logger import AuditLogger
from app.services.summarization.gemini_client import GeminiClient
from app.services.summarization.prompt_manager import (
    build_patient_discharge_instructions_prompt,
    build_transition_clinician_prompt,
)


class TransitionAgent:
    """Produces discharge and handoff transition summaries."""

    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self.audit_logger = AuditLogger()
        self.gemini_client = gemini_client or GeminiClient()

    def summarize(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        transition_type: str,
        encounter_id: str | None = None,
    ) -> TransitionResponse:
        clinician_prompt = build_transition_clinician_prompt(snapshot, transition_type=transition_type)
        patient_prompt = build_patient_discharge_instructions_prompt(snapshot)

        clinician_fallback = self._build_clinician_fallback(snapshot, transition_type)
        patient_fallback = self._build_patient_fallback(snapshot)

        clinician_result = self.gemini_client.generate_summary(clinician_prompt, clinician_fallback)
        patient_result = self.gemini_client.generate_summary(patient_prompt, patient_fallback)

        response = TransitionResponse.accepted(
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id or (snapshot.encounter.encounter_id if snapshot.encounter else None),
            correlation_id=correlation_id,
            message="Transition summary generated.",
            summary_text=clinician_result.text,
            artifacts={
                "provider": clinician_result.provider if not clinician_result.used_fallback else patient_result.provider,
                "clinician_model": clinician_result.model,
                "patient_model": patient_result.model,
                "used_fallback": clinician_result.used_fallback or patient_result.used_fallback,
                "patient_instructions": patient_result.text,
                "transition_type": transition_type,
            },
        )
        response.handoff_sections = {
            "clinician_summary": clinician_result.text,
            "patient_instructions": patient_result.text,
        }
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="transition-agent",
                note="Transition summary and patient instructions generated.",
            )
        ]
        return response

    def _build_clinician_fallback(self, snapshot: PatientSnapshot, transition_type: str) -> str:
        recent_observations = ", ".join(obs.display for obs in snapshot.observations[:5]) or "None documented"
        medications = ", ".join(med.display for med in snapshot.medications[:5]) or "None documented"
        return (
            "Transition Summary\n"
            f"- Transition type: {transition_type}\n"
            f"- Encounter status: {snapshot.encounter.status if snapshot.encounter else 'not available'}\n"
            f"- Active medications: {medications}\n"
            f"- Recent observations: {recent_observations}\n\n"
            "Key Evidence From Supplied Data\n"
            "- This summary reflects only the supplied canonical patient snapshot.\n\n"
            "Assumptions or Unknowns\n"
            "- Additional discharge or handoff details are unavailable because Gemini is not configured or did not return usable output."
        )

    def _build_patient_fallback(self, snapshot: PatientSnapshot) -> str:
        medication_names = ", ".join(med.display for med in snapshot.medications[:5]) or "No medications listed"
        return (
            "What Happened Today\n"
            "- A transition-of-care summary was prepared from the supplied record.\n\n"
            "What Information Is Explicitly Supported By The Record\n"
            f"- Medications listed: {medication_names}\n\n"
            "Questions Or Unknowns To Clarify With The Care Team\n"
            "- Ask the care team about any missing follow-up, medication, or symptom instructions."
        )

    def run(self, request: TransitionRequest) -> TransitionResponse:
        snapshot = request.patient_snapshot or PatientSnapshot(
            patient=PatientDemographics(patient_id=request.patient_id),
        )
        response = self.summarize(
            snapshot=snapshot,
            correlation_id=request.correlation_id,
            transition_type=request.transition_type.value,
            encounter_id=request.encounter_id,
        )
        response.mode = request.mode
        response.artifacts.update({"requested_outputs": request.requested_outputs})
        self.audit_logger.record_event(
            event_type="workflow.transition.completed",
            subject_id=snapshot.patient.patient_id,
            details={"correlation_id": response.correlation_id},
        )
        return response
