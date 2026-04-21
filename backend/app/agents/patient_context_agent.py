from __future__ import annotations

from collections.abc import Callable

from app.models.canonical_patient import ProvenanceRecord
from app.models.raw_fhir import RawFHIRResource
from app.models.workflow_models import ContextFetchRequest, ContextFetchResponse
from app.services.adapters.r4_to_r5 import adapt_r4_resource_to_r5
from app.services.fhir_gateway.client import FHIRGatewayClient, FhirGatewayClient
from app.services.normalization.patient_mapper import build_patient_snapshot


class PatientContextAgent:
    """Fetches patient-centric clinical context from source systems."""

    RESOURCE_TYPES = (
        "Patient",
        "Encounter",
        "Condition",
        "AllergyIntolerance",
        "MedicationRequest",
        "MedicationStatement",
        "Observation",
    )

    def __init__(
        self,
        fhir_client_factory: Callable[..., FhirGatewayClient] = FHIRGatewayClient,
    ) -> None:
        self.fhir_client_factory = fhir_client_factory

    def _build_search_params(
        self,
        resource_type: str,
        patient_id: str,
        encounter_id: str | None,
    ) -> dict[str, str]:
        if resource_type == "Patient":
            return {"_id": patient_id}
        if resource_type == "Encounter":
            return {"_id": encounter_id} if encounter_id else {"subject": f"Patient/{patient_id}"}
        if resource_type == "AllergyIntolerance":
            return {"patient": f"Patient/{patient_id}"}
        return {"subject": f"Patient/{patient_id}"}

    def _adapt_for_internal_use(
        self,
        resources: list[RawFHIRResource],
        source_version: str,
    ) -> list[RawFHIRResource]:
        if source_version not in {"R4", "R4B"}:
            return resources
        adapted_resources: list[RawFHIRResource] = []
        for resource in resources:
            adapted = adapt_r4_resource_to_r5(resource)
            normalized_payload = adapted.payload.get("payload", adapted.payload)
            adapted_resources.append(
                RawFHIRResource(
                    source_version="R5",
                    resource_type=resource.resource_type,
                    resource_id=resource.resource_id,
                    fetched_at=resource.fetched_at,
                    payload=normalized_payload if isinstance(normalized_payload, dict) else resource.payload,
                )
            )
        return adapted_resources

    def _group_resources_by_type(self, resources: list[RawFHIRResource]) -> dict[str, list[RawFHIRResource]]:
        grouped: dict[str, list[RawFHIRResource]] = {}
        for resource in resources:
            grouped.setdefault(resource.resource_type, []).append(resource)
        return grouped

    def fetch_patient_context(
        self,
        patient_id: str,
        encounter_id: str | None = None,
        fhir_base_url: str | None = None,
        access_token: str | None = None,
        correlation_id: str = "patient-context",
    ) -> ContextFetchResponse:
        client = self.fhir_client_factory(base_url=fhir_base_url, auth_token=access_token)
        try:
            metadata = client.get_server_metadata()

            raw_resources: list[RawFHIRResource] = []
            for resource_type in self.RESOURCE_TYPES:
                params = self._build_search_params(resource_type, patient_id, encounter_id)
                bundle = client.search_resources(resource_type, params)
                raw_resources.extend(bundle.entries)

            internal_resources = self._adapt_for_internal_use(raw_resources, metadata.fhir_version)
            grouped_resources = self._group_resources_by_type(internal_resources)
            snapshot = build_patient_snapshot(
                grouped_resources,
                trace_id=correlation_id,
                source_version=metadata.fhir_version,
            )

            return ContextFetchResponse(
                status="completed",
                patient_id=patient_id,
                encounter_id=encounter_id,
                source_version=metadata.fhir_version,
                raw_resource_count=len(raw_resources),
                resources=raw_resources,
                patient_snapshot=snapshot,
                provenance=[
                    ProvenanceRecord(
                        trace_id=correlation_id,
                        source_version=metadata.fhir_version,
                        agent_name="patient-context-agent",
                        note=(
                            f"Fetched {len(raw_resources)} raw FHIR resources from {metadata.base_url} "
                            "and normalized them into a patient snapshot."
                        ),
                    )
                ],
                message="Patient context fetched and normalized successfully.",
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def fetch(self, request: ContextFetchRequest) -> ContextFetchResponse:
        return self.fetch_patient_context(
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
            correlation_id=request.correlation_id,
        )
