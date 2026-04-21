from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.raw_fhir import RawFHIRResource


FIXTURES_DIR = Path(__file__).resolve().parent


def fixture_path(name: str) -> Path:
    """Return the absolute path for a fixture file under backend/tests/fixtures."""

    return FIXTURES_DIR / name


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture by filename."""

    with fixture_path(name).open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def load_transition_of_care_scenario() -> dict[str, list[dict[str, Any]]]:
    """Load the synthetic transition-of-care fixture set grouped by FHIR resource type."""

    return {
        "Patient": [load_fixture("patient.json")],
        "Encounter": [load_fixture("encounter.json")],
        "Condition": [load_fixture("condition.json")],
        "AllergyIntolerance": [load_fixture("allergy_intolerance.json")],
        "MedicationRequest": [load_fixture("medication_request_lisinopril_10mg.json")],
        "MedicationStatement": [load_fixture("medication_statement_lisinopril_20mg.json")],
        "Observation": [load_fixture("observation_potassium_high.json")],
    }


def build_raw_fhir_resources(source_version: str = "R4") -> dict[str, list[RawFHIRResource]]:
    """Wrap the synthetic scenario resources in RawFHIRResource models for service tests."""

    scenario = load_transition_of_care_scenario()
    wrapped_resources: dict[str, list[RawFHIRResource]] = {}
    for resource_type, resources in scenario.items():
        wrapped_resources[resource_type] = [
            RawFHIRResource(
                source_version=source_version,
                resource_type=resource_type,
                resource_id=str(resource.get("id", "")),
                payload=resource,
            )
            for resource in resources
        ]
    return wrapped_resources
