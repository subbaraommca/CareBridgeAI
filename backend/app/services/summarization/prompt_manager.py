from __future__ import annotations

import json

from app.models.canonical_patient import PatientSnapshot


def _render_snapshot_context(snapshot: PatientSnapshot) -> str:
    return json.dumps(snapshot.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True)


def _shared_guardrails(audience: str) -> str:
    return (
        f"You are writing a {audience} clinical summary for CareBridge AI.\n"
        "Use only the supplied structured patient data.\n"
        "Do not invent diagnoses, symptoms, medications, lab values, or follow-up plans.\n"
        "Do not make diagnosis claims.\n"
        "Do not provide unsupported treatment recommendations.\n"
        "Clearly separate evidence from assumptions or unknowns.\n"
        "If data is missing, say it is not available in the supplied record.\n"
    )


def build_ed_summary_prompt(snapshot: PatientSnapshot) -> str:
    return (
        _shared_guardrails("clinician-facing ED")
        + "Produce these sections exactly:\n"
        "1. ED Summary\n"
        "2. Evidence From Supplied Data\n"
        "3. Assumptions or Unknowns\n\n"
        "Focus on encounter context, active issues, medications, allergies, and key observations.\n"
        "Supplied patient snapshot:\n"
        f"{_render_snapshot_context(snapshot)}"
    )


def build_transition_clinician_prompt(snapshot: PatientSnapshot, transition_type: str) -> str:
    return (
        _shared_guardrails("clinician-facing transition-of-care")
        + f"Generate a {transition_type} summary for clinicians.\n"
        "Produce these sections exactly:\n"
        "1. Transition Summary\n"
        "2. Key Evidence From Supplied Data\n"
        "3. Assumptions or Unknowns\n\n"
        "Focus on current encounter context, active conditions, medications, allergies, and recent observations.\n"
        "Supplied patient snapshot:\n"
        f"{_render_snapshot_context(snapshot)}"
    )


def build_patient_discharge_instructions_prompt(snapshot: PatientSnapshot) -> str:
    return (
        _shared_guardrails("patient-friendly discharge")
        + "Write patient-friendly discharge instructions in plain language.\n"
        "Produce these sections exactly:\n"
        "1. What Happened Today\n"
        "2. What Information Is Explicitly Supported By The Record\n"
        "3. Questions Or Unknowns To Clarify With The Care Team\n\n"
        "Do not add treatment advice unless it is explicitly present in the supplied data.\n"
        "Supplied patient snapshot:\n"
        f"{_render_snapshot_context(snapshot)}"
    )
