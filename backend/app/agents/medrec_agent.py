from app.models.canonical_patient import PatientDemographics, PatientSnapshot, ProvenanceRecord
from app.models.workflow_models import MedRecRequest, MedRecResponse
from app.services.audit.audit_logger import AuditLogger
from app.services.med_safety.allergy_rules import detect_allergy_conflicts
from app.services.med_safety.duplicate_rules import (
    detect_duplicate_medications_by_name,
    detect_possible_duplicate_therapy,
)
from app.services.med_safety.verification_rules import (
    detect_missing_dose_frequency,
    generate_verification_questions,
)


class MedRecAgent:
    """Runs medication reconciliation foundations."""

    def __init__(self) -> None:
        self.audit_logger = AuditLogger()

    def reconcile(
        self,
        snapshot: PatientSnapshot,
        correlation_id: str,
        encounter_id: str | None = None,
    ) -> MedRecResponse:
        exact_duplicates = detect_duplicate_medications_by_name(snapshot.medications)
        similar_therapy = detect_possible_duplicate_therapy(snapshot.medications)
        allergy_conflicts = detect_allergy_conflicts(snapshot.medications, snapshot.allergies)
        missing_dose_frequency = detect_missing_dose_frequency(snapshot.medications)

        issues = exact_duplicates + similar_therapy + allergy_conflicts + missing_dose_frequency
        verification_questions = generate_verification_questions(snapshot.medications, issues)

        summary_text = (
            f"Reviewed {len(snapshot.medications)} medications and found {len(issues)} issues. "
            f"{len(verification_questions)} verification questions were generated."
        )

        response = MedRecResponse.accepted(
            patient_id=snapshot.patient.patient_id,
            encounter_id=encounter_id or (snapshot.encounter.encounter_id if snapshot.encounter else None),
            correlation_id=correlation_id,
            message="Medication reconciliation completed deterministically.",
            summary_text=summary_text,
            normalized_medications=snapshot.medications,
            issues=issues,
            verification_questions=verification_questions,
        )
        response.provenance = [
            ProvenanceRecord(
                trace_id=correlation_id,
                source_version="R5",
                agent_name="medrec-agent",
                note="Deterministic medication reconciliation rules engine completed.",
            )
        ]
        return response

    def run(self, request: MedRecRequest) -> MedRecResponse:
        snapshot = request.patient_snapshot or PatientSnapshot(
            patient=PatientDemographics(patient_id=request.patient_id),
            encounter=None,
            allergies=request.allergies,
            medications=request.medications,
        )
        response = self.reconcile(
            snapshot=snapshot,
            correlation_id=request.correlation_id,
            encounter_id=request.encounter_id,
        )
        self.audit_logger.record_event(
            event_type="workflow.medrec.completed",
            subject_id=snapshot.patient.patient_id,
            details={"correlation_id": response.correlation_id},
        )
        return response
