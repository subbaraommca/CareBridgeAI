from __future__ import annotations

from collections.abc import Iterable

from app.models.canonical_patient import MedicationRecord
from app.models.workflow_models import MedicationFinding


def detect_missing_dose_frequency(
    medications: Iterable[MedicationRecord],
) -> list[MedicationFinding]:
    """Detect medications that are missing deterministic dosing information."""

    findings: list[MedicationFinding] = []
    for medication in medications:
        missing_parts: list[str] = []
        if not (medication.dosage_text or "").strip():
            missing_parts.append("dose instructions")
        if not (medication.frequency or "").strip():
            missing_parts.append("frequency")

        if not missing_parts:
            continue

        findings.append(
            MedicationFinding(
                category="missing_dose_frequency",
                severity="medium",
                medication_id=medication.medication_id,
                medication_display=medication.display,
                rationale=(
                    f"{medication.display} is missing {', '.join(missing_parts)} needed "
                    "for medication reconciliation."
                ),
                recommended_action="Collect the missing dosing details from the care team or source record.",
            )
        )

    return findings


def generate_verification_questions(
    medications: Iterable[MedicationRecord],
    issues: Iterable[MedicationFinding],
) -> list[str]:
    """Generate deterministic verification questions from identified reconciliation issues."""

    medication_by_id = {medication.medication_id: medication for medication in medications}
    questions: list[str] = []
    seen_questions: set[str] = set()

    for issue in issues:
        medication = medication_by_id.get(issue.medication_id or "")
        medication_name = issue.medication_display or (medication.display if medication else "this medication")

        if issue.category == "duplicate_medication":
            question = f"Should {medication_name} remain active, or is it a duplicate entry?"
        elif issue.category == "possible_duplicate_therapy":
            question = f"Are similar therapies involving {medication_name} intentionally concurrent?"
        elif issue.category == "allergy_conflict":
            question = f"Is {medication_name} appropriate given the documented allergy history?"
        elif issue.category == "missing_dose_frequency":
            question = f"What dose and frequency should be recorded for {medication_name}?"
        else:
            question = f"What clinical verification is needed for {medication_name}?"

        if question in seen_questions:
            continue

        seen_questions.add(question)
        questions.append(question)

    return questions


def build_verification_queue(medications: list[MedicationRecord]) -> list[str]:
    """Compatibility helper preserved for earlier callers."""

    return [finding.medication_display or "" for finding in detect_missing_dose_frequency(medications)]
