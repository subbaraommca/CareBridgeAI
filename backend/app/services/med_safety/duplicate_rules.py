from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from app.models.canonical_patient import MedicationRecord
from app.models.workflow_models import MedicationFinding


NOISE_TOKENS = {
    "mg",
    "mcg",
    "g",
    "ml",
    "tablet",
    "tablets",
    "tab",
    "tabs",
    "capsule",
    "capsules",
    "cap",
    "caps",
    "oral",
    "po",
    "solution",
    "suspension",
}


def normalize_medication_name(name: str) -> str:
    """Normalize medication display text for deterministic comparison."""

    lowered = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    cleaned = re.sub(r"\b\d+(\.\d+)?\b", " ", cleaned)
    tokens = [token for token in cleaned.split() if token and token not in NOISE_TOKENS]
    return " ".join(tokens)


def detect_duplicate_medications_by_name(
    medications: Iterable[MedicationRecord],
) -> list[MedicationFinding]:
    findings: list[MedicationFinding] = []
    seen: dict[str, MedicationRecord] = {}

    for medication in medications:
        normalized_name = normalize_medication_name(medication.display)
        if not normalized_name:
            continue

        existing = seen.get(normalized_name)
        if existing is None:
            seen[normalized_name] = medication
            continue

        findings.append(
            MedicationFinding(
                category="duplicate_medication",
                severity="high",
                medication_id=medication.medication_id,
                medication_display=medication.display,
                rationale=(
                    f"{medication.display} appears to duplicate {existing.display} "
                    "after deterministic name normalization."
                ),
                recommended_action="Confirm whether both entries should remain active.",
            )
        )

    return findings


def detect_possible_duplicate_therapy(
    medications: Iterable[MedicationRecord],
    similarity_threshold: float = 0.82,
) -> list[MedicationFinding]:
    findings: list[MedicationFinding] = []
    medications_list = list(medications)
    emitted_pairs: set[tuple[str, str]] = set()

    for index, left in enumerate(medications_list):
        left_name = normalize_medication_name(left.display)
        if not left_name:
            continue

        for right in medications_list[index + 1 :]:
            right_name = normalize_medication_name(right.display)
            if not right_name or left_name == right_name:
                continue

            similarity = SequenceMatcher(a=left_name, b=right_name).ratio()
            if similarity < similarity_threshold:
                continue

            pair = tuple(sorted((left.medication_id, right.medication_id)))
            if pair in emitted_pairs:
                continue
            emitted_pairs.add(pair)

            findings.append(
                MedicationFinding(
                    category="possible_duplicate_therapy",
                    severity="low",
                    medication_id=left.medication_id,
                    medication_display=left.display,
                    rationale=(
                        f"{left.display} and {right.display} have similar normalized names "
                        f"(similarity={similarity:.2f})."
                    ),
                    recommended_action="Review whether these therapies are intentionally concurrent.",
                )
            )

    return findings


def find_duplicate_medications(medications: list[MedicationRecord]) -> list[str]:
    """Compatibility helper preserved for earlier callers."""

    return [finding.medication_display or "" for finding in detect_duplicate_medications_by_name(medications)]
