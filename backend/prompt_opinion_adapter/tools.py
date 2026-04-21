from __future__ import annotations

import logging
from typing import Any

from google.adk.tools import ToolContext

from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.patient_context_agent import PatientContextAgent
from app.models.workflow_models import WorkflowMode, WorkflowRunRequest

logger = logging.getLogger(__name__)

orchestrator_agent = OrchestratorAgent()
patient_context_agent = PatientContextAgent()


def _resolve_identifier(explicit_value: str | None, state_value: str | None) -> str:
    value = explicit_value or state_value or ""
    return str(value).strip()


def _base_metadata(tool_context: ToolContext) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "prompt-opinion-a2a-adapter",
        "fhir_base_url": str(tool_context.state.get("fhir_url", "")).rstrip("/"),
        "access_token": str(tool_context.state.get("fhir_token", "")),
        "fhir_context_uri": str(tool_context.state.get("fhir_context_uri", "")),
    }
    return {key: value for key, value in metadata.items() if value}


def _require_patient_context(patient_id: str) -> dict[str, Any] | None:
    if patient_id:
        return None
    return {
        "status": "error",
        "error_message": (
            "Patient context is not available. Prompt Opinion must send FHIR metadata "
            "with at least fhirUrl, fhirToken, and patientId."
        ),
    }


def _snapshot_summary(snapshot: Any) -> dict[str, Any]:
    return {
        "patient_id": snapshot.patient.patient_id,
        "encounter_id": snapshot.encounter.encounter_id if snapshot.encounter else None,
        "condition_count": len(snapshot.conditions),
        "allergy_count": len(snapshot.allergies),
        "medication_count": len(snapshot.medications),
        "observation_count": len(snapshot.observations),
    }


def _workflow_result_to_dict(response: Any) -> dict[str, Any]:
    medrec_artifact = response.artifacts.get("medrec", {}) if isinstance(response.artifacts, dict) else {}
    transition_artifact = response.artifacts.get("transition", {}) if isinstance(response.artifacts, dict) else {}

    return {
        "status": response.status,
        "workflow_mode": response.mode.value,
        "trace_id": response.correlation_id,
        "patient_id": response.patient_id,
        "encounter_id": response.encounter_id,
        "message": response.message,
        "summary_text": response.summary_text,
        "findings": [finding.model_dump(mode="json") for finding in response.findings],
        "verification_questions": list(medrec_artifact.get("verification_questions", [])),
        "patient_instructions": transition_artifact.get("patient_instructions"),
        "artifacts": response.artifacts,
        "provenance": [record.model_dump(mode="json") for record in response.provenance],
        "patient_snapshot_summary": _snapshot_summary(response.patient_snapshot) if response.patient_snapshot else None,
    }


def _run_workflow(
    mode: WorkflowMode,
    patient_id: str,
    encounter_id: str | None,
    tool_context: ToolContext,
) -> dict[str, Any]:
    request = WorkflowRunRequest(
        mode=mode,
        patient_id=patient_id,
        encounter_id=encounter_id or None,
        requested_by="prompt-opinion",
        metadata=_base_metadata(tool_context),
    )
    response = orchestrator_agent.run(request)
    tool_context.state["last_trace_id"] = response.correlation_id
    tool_context.state["last_workflow_mode"] = response.mode.value
    return _workflow_result_to_dict(response)


def fetch_patient_context(
    patient_id: str = "",
    encounter_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Fetch and normalize patient context from the current Prompt Opinion FHIR session."""

    if tool_context is None:
        raise ValueError("tool_context is required.")

    resolved_patient_id = _resolve_identifier(patient_id, tool_context.state.get("patient_id"))
    missing_context = _require_patient_context(resolved_patient_id)
    if missing_context:
        return missing_context

    resolved_encounter_id = _resolve_identifier(encounter_id, tool_context.state.get("encounter_id")) or None
    response = patient_context_agent.fetch_patient_context(
        patient_id=resolved_patient_id,
        encounter_id=resolved_encounter_id,
        fhir_base_url=_base_metadata(tool_context).get("fhir_base_url"),
        access_token=_base_metadata(tool_context).get("access_token"),
        correlation_id=str(tool_context.state.get("last_trace_id", "prompt-opinion-context")),
    )
    tool_context.state["last_patient_id"] = resolved_patient_id

    return {
        "status": response.status,
        "patient_id": response.patient_id,
        "encounter_id": response.encounter_id,
        "source_version": response.source_version,
        "raw_resource_count": response.raw_resource_count,
        "message": response.message,
        "patient_snapshot": response.patient_snapshot.model_dump(mode="json") if response.patient_snapshot else None,
        "patient_snapshot_summary": _snapshot_summary(response.patient_snapshot) if response.patient_snapshot else None,
        "provenance": [record.model_dump(mode="json") for record in response.provenance],
    }


def run_ed_summary(
    patient_id: str = "",
    encounter_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run the CareBridge ED summary workflow for the active patient."""

    if tool_context is None:
        raise ValueError("tool_context is required.")

    resolved_patient_id = _resolve_identifier(patient_id, tool_context.state.get("patient_id"))
    missing_context = _require_patient_context(resolved_patient_id)
    if missing_context:
        return missing_context

    resolved_encounter_id = _resolve_identifier(encounter_id, tool_context.state.get("encounter_id")) or None
    return _run_workflow(WorkflowMode.ED_SUMMARY, resolved_patient_id, resolved_encounter_id, tool_context)


def run_medication_reconciliation(
    patient_id: str = "",
    encounter_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run deterministic medication reconciliation for the active patient."""

    if tool_context is None:
        raise ValueError("tool_context is required.")

    resolved_patient_id = _resolve_identifier(patient_id, tool_context.state.get("patient_id"))
    missing_context = _require_patient_context(resolved_patient_id)
    if missing_context:
        return missing_context

    resolved_encounter_id = _resolve_identifier(encounter_id, tool_context.state.get("encounter_id")) or None
    return _run_workflow(WorkflowMode.MED_REC, resolved_patient_id, resolved_encounter_id, tool_context)


def run_discharge_handoff(
    patient_id: str = "",
    encounter_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run the discharge or handoff workflow, including medication reconciliation."""

    if tool_context is None:
        raise ValueError("tool_context is required.")

    resolved_patient_id = _resolve_identifier(patient_id, tool_context.state.get("patient_id"))
    missing_context = _require_patient_context(resolved_patient_id)
    if missing_context:
        return missing_context

    resolved_encounter_id = _resolve_identifier(encounter_id, tool_context.state.get("encounter_id")) or None
    return _run_workflow(WorkflowMode.DISCHARGE_HANDOFF, resolved_patient_id, resolved_encounter_id, tool_context)


def run_full_transition_of_care(
    patient_id: str = "",
    encounter_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run the full transition-of-care workflow bundle for the active patient."""

    if tool_context is None:
        raise ValueError("tool_context is required.")

    resolved_patient_id = _resolve_identifier(patient_id, tool_context.state.get("patient_id"))
    missing_context = _require_patient_context(resolved_patient_id)
    if missing_context:
        return missing_context

    resolved_encounter_id = _resolve_identifier(encounter_id, tool_context.state.get("encounter_id")) or None
    return _run_workflow(WorkflowMode.FULL_TRANSITION_OF_CARE, resolved_patient_id, resolved_encounter_id, tool_context)

