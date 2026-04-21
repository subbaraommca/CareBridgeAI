from tests.fixtures import build_raw_fhir_resources, load_fixture, load_transition_of_care_scenario


def test_load_fixture_returns_synthetic_patient_payload() -> None:
    patient = load_fixture("patient.json")

    assert patient["resourceType"] == "Patient"
    assert patient["id"] == "cbai-patient-1001"
    assert patient["meta"]["tag"][0]["display"] == "Synthetic Test/Demo Data"


def test_transition_of_care_scenario_is_coherent() -> None:
    scenario = load_transition_of_care_scenario()

    assert set(scenario) == {
        "Patient",
        "Encounter",
        "Condition",
        "AllergyIntolerance",
        "MedicationRequest",
        "MedicationStatement",
        "Observation",
    }
    assert scenario["Encounter"][0]["subject"]["reference"] == "Patient/cbai-patient-1001"
    assert scenario["MedicationRequest"][0]["medicationCodeableConcept"]["text"] == "Lisinopril 10 mg tablet"
    assert scenario["MedicationStatement"][0]["medicationCodeableConcept"]["text"] == "Lisinopril 20 mg tablet"
    assert scenario["Observation"][0]["interpretation"][0]["text"] == "High"


def test_build_raw_fhir_resources_wraps_fixture_payloads() -> None:
    resources = build_raw_fhir_resources(source_version="R4")

    assert resources["Patient"][0].source_version == "R4"
    assert resources["Patient"][0].resource_type == "Patient"
    assert resources["Patient"][0].payload["id"] == "cbai-patient-1001"
    assert resources["Observation"][0].payload["valueQuantity"]["value"] == 5.8
