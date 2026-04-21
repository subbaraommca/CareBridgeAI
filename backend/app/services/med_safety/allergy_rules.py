from __future__ import annotations

from collections.abc import Iterable

from app.models.canonical_patient import AllergyRecord, MedicationRecord
from app.models.workflow_models import MedicationFinding
from app.services.med_safety.duplicate_rules import normalize_medication_name


def detect_allergy_conflicts(
    medications: Iterable[MedicationRecord],
    allergies: Iterable[AllergyRecord],
) -> list[MedicationFinding]:
    """Detect simple medication-allergy conflicts using substance text matching."""

    allergy_terms = [
        (
            allergy,
            normalize_medication_name(allergy.substance),
        )
        for allergy in allergies
        if allergy.substance
    ]

    findings: list[MedicationFinding] = []
    for medication in medications:
        normalized_medication_name = normalize_medication_name(medication.display)
        if not normalized_medication_name:
            continue

        for allergy, allergy_term in allergy_terms:
            if not allergy_term:
                continue

            if allergy_term in normalized_medication_name or normalized_medication_name in allergy_term:
                findings.append(
                    MedicationFinding(
                        category="allergy_conflict",
                        severity="high",
                        medication_id=medication.medication_id,
                        medication_display=medication.display,
                        rationale=(
                            f"{medication.display} matches the documented allergy substance "
                            f"{allergy.substance}."
                        ),
                        recommended_action="Verify whether this medication should be held or replaced.",
                    )
                )

    return findings


def check_allergy_conflicts(medications: list[MedicationRecord]) -> list[str]:
    """Compatibility helper preserved for earlier callers."""

    return []
