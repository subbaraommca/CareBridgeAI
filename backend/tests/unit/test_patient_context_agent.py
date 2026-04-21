from app.agents.patient_context_agent import PatientContextAgent
from app.models.raw_fhir import RawFHIRBundle, RawFHIRResource
from app.services.fhir_gateway.metadata import FHIRGatewayMetadata


class FakeFhirGatewayClient:
    def __init__(self, *, base_url: str | None = None, auth_token: str | None = None) -> None:
        self.base_url = base_url
        self.auth_token = auth_token

    def get_server_metadata(self) -> FHIRGatewayMetadata:
        return FHIRGatewayMetadata(
            base_url=self.base_url or "https://example.org/fhir",
            fhir_version="R4",
            software_name="mock-fhir",
            raw_capability_statement={"fhirVersion": "4.0.1"},
            native_mode="R4",
        )

    def search_resources(self, resource_type: str, params: dict[str, str]) -> RawFHIRBundle:
        patient_id = "patient-123"
        encounter_id = "enc-1"

        resources: dict[str, list[RawFHIRResource]] = {
            "Patient": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="Patient",
                    resource_id=patient_id,
                    payload={
                        "resourceType": "Patient",
                        "id": patient_id,
                        "name": [{"given": ["Alex"], "family": "Morgan"}],
                        "identifier": [{"value": "MRN-42"}],
                    },
                )
            ],
            "Encounter": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="Encounter",
                    resource_id=encounter_id,
                    payload={
                        "resourceType": "Encounter",
                        "id": encounter_id,
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "status": "finished",
                        "class": {"code": "EMER"},
                    },
                )
            ],
            "Condition": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="Condition",
                    resource_id="cond-1",
                    payload={
                        "resourceType": "Condition",
                        "id": "cond-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "code": {"text": "Hypertension", "coding": [{"code": "38341003"}]},
                    },
                )
            ],
            "AllergyIntolerance": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="AllergyIntolerance",
                    resource_id="alg-1",
                    payload={
                        "resourceType": "AllergyIntolerance",
                        "id": "alg-1",
                        "patient": {"reference": f"Patient/{patient_id}"},
                        "code": {"text": "Penicillin", "coding": [{"code": "70618"}]},
                    },
                )
            ],
            "MedicationRequest": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="MedicationRequest",
                    resource_id="medreq-1",
                    payload={
                        "resourceType": "MedicationRequest",
                        "id": "medreq-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "status": "active",
                        "medicationCodeableConcept": {"text": "Aspirin 81 mg", "coding": [{"code": "1191"}]},
                    },
                )
            ],
            "MedicationStatement": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="MedicationStatement",
                    resource_id="medstmt-1",
                    payload={
                        "resourceType": "MedicationStatement",
                        "id": "medstmt-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "status": "active",
                        "medicationReference": {"reference": "Medication/metformin", "display": "Metformin"},
                    },
                )
            ],
            "Observation": [
                RawFHIRResource(
                    source_version="R4",
                    resource_type="Observation",
                    resource_id="obs-1",
                    payload={
                        "resourceType": "Observation",
                        "id": "obs-1",
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "status": "final",
                        "code": {"text": "Heart rate", "coding": [{"code": "8867-4"}]},
                        "valueQuantity": {"value": 84, "unit": "beats/minute"},
                    },
                )
            ],
        }
        return RawFHIRBundle(source_version="R4", entries=resources.get(resource_type, []))


def test_patient_context_agent_fetches_resources_and_builds_snapshot() -> None:
    agent = PatientContextAgent(fhir_client_factory=FakeFhirGatewayClient)

    response = agent.fetch_patient_context(
        patient_id="patient-123",
        encounter_id="enc-1",
        fhir_base_url="https://example.org/fhir",
        access_token="secret-token",
        correlation_id="trace-ctx-1",
    )

    assert response.source_version == "R4"
    assert response.raw_resource_count == 7
    assert response.patient_snapshot is not None
    assert response.patient_snapshot.patient.patient_id == "patient-123"
    assert response.patient_snapshot.patient.family_name == "Morgan"
    assert response.patient_snapshot.encounter is not None
    assert response.patient_snapshot.encounter.encounter_id == "enc-1"
    assert len(response.patient_snapshot.medications) == 2
    assert len(response.patient_snapshot.observations) == 1
    assert response.provenance[0].trace_id == "trace-ctx-1"
    assert "normalized them into a patient snapshot" in (response.provenance[0].note or "")


def test_patient_context_agent_uses_r4_adapter_for_internal_snapshot_building() -> None:
    agent = PatientContextAgent(fhir_client_factory=FakeFhirGatewayClient)

    response = agent.fetch_patient_context(patient_id="patient-123", correlation_id="trace-ctx-2")

    assert response.patient_snapshot is not None
    assert response.patient_snapshot.provenance[0].source_version == "R4"
    assert response.resources[0].source_version == "R4"
