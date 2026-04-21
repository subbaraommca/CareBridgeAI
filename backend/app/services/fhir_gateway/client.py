from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.models.raw_fhir import RawFHIRBundle, RawFHIRResource
from app.services.fhir_gateway.bundle_parser import parse_bundle
from app.services.fhir_gateway.metadata import FHIRGatewayMetadata, build_gateway_metadata


class FhirGatewayClient:
    """Reusable HTTP client for interacting with upstream FHIR servers."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        auth_token: str | None = None,
        http_client: httpx.Client | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = (base_url or self.settings.fhir_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or self.settings.fhir_timeout_seconds
        self.auth_token = auth_token if auth_token is not None else self.settings.fhir_auth_token
        self._metadata_cache: FHIRGatewayMetadata | None = None
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=self.timeout_seconds,
            headers=self._build_headers(),
        )

        if http_client is not None:
            self._http_client.headers.update(self._build_headers())

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/fhir+json, application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _build_url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def _request_json(self, method: str, path_or_url: str, **kwargs: Any) -> dict[str, Any]:
        response = self._http_client.request(method, self._build_url(path_or_url), **kwargs)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("FHIR server returned a non-object JSON payload.")
        return payload

    def get_server_metadata(self) -> FHIRGatewayMetadata:
        if self._metadata_cache is None:
            capability_statement = self._request_json("GET", "metadata")
            self._metadata_cache = build_gateway_metadata(self.base_url, capability_statement)
        return self._metadata_cache

    def read_resource(self, resource_type: str, resource_id: str) -> RawFHIRResource:
        payload = self._request_json("GET", f"{resource_type}/{resource_id}")
        metadata = self.get_server_metadata()
        return RawFHIRResource(
            source_version=metadata.fhir_version,
            resource_type=str(payload.get("resourceType", resource_type)),
            resource_id=str(payload.get("id", resource_id)),
            payload=payload,
        )

    def search_resources(self, resource_type: str, params: dict[str, Any]) -> RawFHIRBundle:
        filtered_params = {key: value for key, value in params.items() if value is not None}
        payload = self._request_json("GET", resource_type, params=filtered_params)
        metadata = self.get_server_metadata()
        return parse_bundle(payload, source_version=metadata.fhir_version)

    def fetch_bundle(self, url: str) -> RawFHIRBundle:
        payload = self._request_json("GET", url)
        metadata = self.get_server_metadata()
        return parse_bundle(payload, source_version=metadata.fhir_version)

    def fetch_patient_context(self, patient_id: str, encounter_id: str | None = None) -> RawFHIRBundle:
        """Compatibility helper for earlier scaffolding."""

        bundle = self.search_resources("Patient", {"_id": patient_id})
        if encounter_id:
            encounter_bundle = self.search_resources("Encounter", {"_id": encounter_id})
            bundle.entries.extend(encounter_bundle.entries)
        return bundle

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> "FhirGatewayClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


FHIRGatewayClient = FhirGatewayClient
