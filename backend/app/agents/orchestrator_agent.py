from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.agents.ed_summary_agent import EDSummaryAgent
from app.agents.medrec_agent import MedRecAgent
from app.agents.patient_context_agent import PatientContextAgent
from app.agents.transition_agent import TransitionAgent
from app.models.canonical_patient import PatientSnapshot, ProvenanceRecord
from app.models.workflow_models import (
    MedRecResponse,
    TransitionResponse,
    WorkflowMode,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.audit.audit_logger import AuditLogger


class OrchestratorAgent:
    """Coordinates transition-of-care workflows across context, safety, and summary agents."""

    def __init__(
        self,
        patient_context_agent: PatientContextAgent | None = None,
        ed_summary_agent: EDSummaryAgent | None = None,
        medrec_agent: MedRecAgent | None = None,
        transition_agent: TransitionAgent | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger()
        self.patient_context_agent = patient_context_agent or PatientContextAgent()
        self.ed_summary_agent = ed_summary_agent or EDSummaryAgent()
        self.medrec_agent = medrec_agent or MedRecAgent()
        self.transition_agent = transition_agent or TransitionAgent()

    def _generate_trace_id(self) -> str:
        return str(uuid4())

    def _extract_connection_settings(self, request: WorkflowRunRequest) -> tuple[str | None, str | None]:
        metadata = request.metadata or {}
        fhir_base_url = metadata.get("fhir_base_url")
        access_token = metadata.get("access_token")

        return (
            fhir_base_url if isinstance(fhir_base_url, str) and fhir_base_url.strip() else None,
            access_token if isinstance(access_token, str) and access_token.strip() else None,
        )

    def _fetch_patient_snapshot(
        self,
        request: WorkflowRunRequest,
        trace_id: str,
    ) -> tuple[PatientSnapshot, str, int, list[ProvenanceRecord]]:
        fhir_base_url, access_token = self._extract_connection_settings(request)
        context_response = self.patient_context_agent.fetch_patient_context(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            fhir_base_url=fhir_base_url,
            access_token=access_token,
            correlation_id=trace_id,
        )

        if context_response.patient_snapshot is None:
            raise RuntimeError("Patient context fetch completed without a normalized patient snapshot.")

        return (
            context_response.patient_snapshot,
            context_response.source_version,
            context_response.raw_resource_count,
            list(context_response.provenance),
        )

    def _run_ed_summary(
        self,
        snapshot: PatientSnapshot,
        request: WorkflowRunRequest,
        trace_id: str,
    ) -> WorkflowRunResponse:
        return self.ed_summary_agent.summarize(
            snapshot=snapshot,
            correlation_id=trace_id,
            encounter_id=request.encounter_id,
        )

    def _run_medrec(
        self,
        snapshot: PatientSnapshot,
        request: WorkflowRunRequest,
        trace_id: str,
    ) -> MedRecResponse:
        return self.medrec_agent.reconcile(
            snapshot=snapshot,
            correlation_id=trace_id,
            encounter_id=request.encounter_id,
        )

    def _run_transition(
        self,
        snapshot: PatientSnapshot,
        request: WorkflowRunRequest,
        trace_id: str,
    ) -> TransitionResponse:
        transition_request = request.to_transition_request()
        return self.transition_agent.summarize(
            snapshot=snapshot,
            correlation_id=trace_id,
            transition_type=transition_request.transition_type.value,
            encounter_id=request.encounter_id,
        )

    def _compose_summary_text(
        self,
        mode: WorkflowMode,
        ed_response: WorkflowRunResponse | None,
        medrec_response: MedRecResponse | None,
        transition_response: TransitionResponse | None,
    ) -> str | None:
        if mode is WorkflowMode.ED_SUMMARY:
            return ed_response.summary_text if ed_response else None
        if mode is WorkflowMode.MED_REC:
            return medrec_response.summary_text if medrec_response else None
        if mode is WorkflowMode.DISCHARGE_HANDOFF:
            return transition_response.summary_text if transition_response else None

        sections = [
            ("ED Summary", ed_response.summary_text if ed_response else None),
            ("Medication Reconciliation", medrec_response.summary_text if medrec_response else None),
            ("Transition Summary", transition_response.summary_text if transition_response else None),
        ]
        rendered_sections = [
            f"{title}\n{text}"
            for title, text in sections
            if text
        ]
        return "\n\n".join(rendered_sections) if rendered_sections else None

    def _build_artifacts(
        self,
        request: WorkflowRunRequest,
        trace_id: str,
        source_version: str,
        raw_resource_count: int,
        ed_response: WorkflowRunResponse | None,
        medrec_response: MedRecResponse | None,
        transition_response: TransitionResponse | None,
    ) -> dict[str, Any]:
        artifacts: dict[str, Any] = {
            "trace_id": trace_id,
            "requested_mode": request.mode.value,
            "request_correlation_id": request.correlation_id,
            "source_version": source_version,
            "raw_resource_count": raw_resource_count,
        }

        if ed_response is not None:
            artifacts["ed_summary"] = {
                "summary_text": ed_response.summary_text,
                **ed_response.artifacts,
            }

        if medrec_response is not None:
            artifacts["medrec"] = {
                "summary_text": medrec_response.summary_text,
                "issues": [issue.model_dump() for issue in medrec_response.issues],
                "verification_questions": list(medrec_response.verification_questions),
                "normalized_medications": [
                    medication.model_dump() for medication in medrec_response.normalized_medications
                ],
            }

        if transition_response is not None:
            artifacts["transition"] = {
                "summary_text": transition_response.summary_text,
                "handoff_sections": dict(transition_response.handoff_sections),
                **transition_response.artifacts,
            }

        return artifacts

    def _build_provenance(
        self,
        trace_id: str,
        source_version: str,
        mode: WorkflowMode,
        context_provenance: list[ProvenanceRecord],
        ed_response: WorkflowRunResponse | None,
        medrec_response: MedRecResponse | None,
        transition_response: TransitionResponse | None,
    ) -> list[ProvenanceRecord]:
        provenance = list(context_provenance)
        if ed_response is not None:
            provenance.extend(ed_response.provenance)
        if medrec_response is not None:
            provenance.extend(medrec_response.provenance)
        if transition_response is not None:
            provenance.extend(transition_response.provenance)

        provenance.append(
            ProvenanceRecord(
                trace_id=trace_id,
                source_version=source_version,
                agent_name="orchestrator-agent",
                note=f"Completed {mode.value} workflow orchestration.",
            )
        )
        return provenance

    def run(self, request: WorkflowRunRequest) -> WorkflowRunResponse:
        patient_id = request.patient_id.strip()
        if not patient_id:
            raise ValueError("patient_id must not be empty.")

        trace_id = self._generate_trace_id()
        self.audit_logger.record_event(
            event_type="workflow.received",
            subject_id=patient_id,
            details={
                "workflow": request.mode.value,
                "trace_id": trace_id,
                "request_correlation_id": request.correlation_id,
            },
        )

        try:
            snapshot, source_version, raw_resource_count, context_provenance = self._fetch_patient_snapshot(
                request=request.model_copy(update={"patient_id": patient_id}),
                trace_id=trace_id,
            )

            ed_response: WorkflowRunResponse | None = None
            medrec_response: MedRecResponse | None = None
            transition_response: TransitionResponse | None = None

            if request.mode is WorkflowMode.ED_SUMMARY:
                ed_response = self._run_ed_summary(snapshot, request, trace_id)
            elif request.mode is WorkflowMode.MED_REC:
                medrec_response = self._run_medrec(snapshot, request, trace_id)
            elif request.mode is WorkflowMode.DISCHARGE_HANDOFF:
                medrec_response = self._run_medrec(snapshot, request, trace_id)
                transition_response = self._run_transition(snapshot, request, trace_id)
            elif request.mode is WorkflowMode.FULL_TRANSITION_OF_CARE:
                ed_response = self._run_ed_summary(snapshot, request, trace_id)
                medrec_response = self._run_medrec(snapshot, request, trace_id)
                transition_response = self._run_transition(snapshot, request, trace_id)
            else:
                raise ValueError(f"Unsupported workflow mode: {request.mode}")

            findings = medrec_response.issues if medrec_response is not None else []
            response = WorkflowRunResponse(
                status="completed",
                mode=request.mode,
                patient_id=patient_id,
                encounter_id=request.encounter_id,
                correlation_id=trace_id,
                message=f"{request.mode.value} workflow completed successfully.",
                summary_text=self._compose_summary_text(
                    mode=request.mode,
                    ed_response=ed_response,
                    medrec_response=medrec_response,
                    transition_response=transition_response,
                ),
                findings=findings,
                patient_snapshot=snapshot,
                provenance=self._build_provenance(
                    trace_id=trace_id,
                    source_version=source_version,
                    mode=request.mode,
                    context_provenance=context_provenance,
                    ed_response=ed_response,
                    medrec_response=medrec_response,
                    transition_response=transition_response,
                ),
                artifacts=self._build_artifacts(
                    request=request,
                    trace_id=trace_id,
                    source_version=source_version,
                    raw_resource_count=raw_resource_count,
                    ed_response=ed_response,
                    medrec_response=medrec_response,
                    transition_response=transition_response,
                ),
            )

            self.audit_logger.record_event(
                event_type="workflow.completed",
                subject_id=patient_id,
                details={"workflow": request.mode.value, "trace_id": trace_id},
            )
            return response
        except Exception as exc:
            self.audit_logger.record_event(
                event_type="workflow.failed",
                subject_id=patient_id,
                details={
                    "workflow": request.mode.value,
                    "trace_id": trace_id,
                    "error": str(exc),
                },
            )
            raise
