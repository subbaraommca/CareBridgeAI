import httpx

from app.config.settings import Settings
from app.services.fhir_gateway.bundle_parser import extract_bundle_entries, parse_bundle
from app.services.fhir_gateway.client import FhirGatewayClient
from app.services.fhir_gateway.metadata import detect_fhir_version
from app.services.fhir_gateway.reference_resolver import parse_reference, resolve_reference


def test_detect_fhir_version_from_capability_statement() -> None:
    assert detect_fhir_version({"fhirVersion": "5.0.0"}) == "R5"
    assert detect_fhir_version({"fhirVersion": "4.0.1"}) == "R4"
    assert detect_fhir_version({"fhirVersion": "4.3.0"}) == "R4B"
    assert detect_fhir_version({}) == "unknown"


def test_get_server_metadata_returns_normalized_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fhir/metadata"
        return httpx.Response(
            200,
            json={
                "resourceType": "CapabilityStatement",
                "fhirVersion": "5.0.0",
                "software": {"name": "Test FHIR", "version": "1.2.3"},
                "implementation": {"description": "Mock FHIR server"},
                "format": ["json"],
            },
        )

    client = FhirGatewayClient(
        base_url="https://example.org/fhir",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    metadata = client.get_server_metadata()

    assert metadata.base_url == "https://example.org/fhir"
    assert metadata.fhir_version == "R5"
    assert metadata.software_name == "Test FHIR"
    assert metadata.implementation_description == "Mock FHIR server"


def test_read_resource_uses_bearer_token_and_returns_raw_resource() -> None:
    seen_auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers.get("Authorization"))
        if request.url.path == "/fhir/metadata":
            return httpx.Response(200, json={"resourceType": "CapabilityStatement", "fhirVersion": "5.0.0"})
        if request.url.path == "/fhir/Patient/123":
            return httpx.Response(200, json={"resourceType": "Patient", "id": "123"})
        return httpx.Response(404, json={"detail": "Not found"})

    client = FhirGatewayClient(
        base_url="https://example.org/fhir",
        auth_token="secret-token",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    resource = client.read_resource("Patient", "123")

    assert resource.resource_type == "Patient"
    assert resource.resource_id == "123"
    assert resource.source_version == "R5"
    assert seen_auth_headers == ["Bearer secret-token", "Bearer secret-token"]


def test_search_resources_returns_bundle_and_forwards_query_params() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == "/fhir/Observation":
            return httpx.Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "entry": [
                        {"resource": {"resourceType": "Observation", "id": "obs-1", "status": "final"}},
                        {"resource": {"resourceType": "Observation"}},
                        {"resource": {"id": "missing-type"}},
                        {"fullUrl": "https://example.org/fhir/Observation/obs-2", "resource": {"resourceType": "Observation"}},
                    ],
                },
            )
        if request.url.path == "/fhir/metadata":
            return httpx.Response(200, json={"resourceType": "CapabilityStatement", "fhirVersion": "4.0.1"})
        return httpx.Response(404, json={"detail": "Not found"})

    client = FhirGatewayClient(
        base_url="https://example.org/fhir",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    bundle = client.search_resources("Observation", {"patient": "123", "_count": 10, "category": None})

    assert bundle.source_version == "R4"
    assert [entry.resource_id for entry in bundle.entries] == ["obs-1", "obs-2"]
    assert "patient=123" in requested_urls[0]
    assert "_count=10" in requested_urls[0]
    assert "category=" not in requested_urls[0]


def test_fetch_bundle_supports_relative_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/fhir/Encounter":
            return httpx.Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "entry": [{"resource": {"resourceType": "Encounter", "id": "enc-1"}}],
                },
            )
        if request.url.path == "/fhir/metadata":
            return httpx.Response(200, json={"resourceType": "CapabilityStatement", "fhirVersion": "5.0.0"})
        return httpx.Response(404, json={"detail": "Not found"})

    client = FhirGatewayClient(
        base_url="https://example.org/fhir",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    bundle = client.fetch_bundle("Encounter?patient=123")

    assert len(bundle.entries) == 1
    assert bundle.entries[0].resource_type == "Encounter"
    assert bundle.entries[0].resource_id == "enc-1"


def test_bundle_parser_extracts_entries_safely() -> None:
    bundle = parse_bundle(
        {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "123"}},
                {"resource": {"resourceType": "Encounter"}},
                {"resource": "invalid"},
                "invalid-entry",
            ],
        },
        source_version="R5",
    )

    assert len(bundle.entries) == 2
    assert bundle.entries[0].resource_type == "Patient"
    assert bundle.entries[1].resource_id == "resource-1"
    assert extract_bundle_entries(None) == []


def test_reference_parser_and_resolver_handle_simple_references() -> None:
    parsed = parse_reference("Patient/123")
    assert parsed is not None
    assert parsed.resource_type == "Patient"
    assert parsed.resource_id == "123"

    bundle = parse_bundle(
        {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "123"}},
                {"resource": {"resourceType": "Encounter", "id": "abc"}},
            ],
        }
    )

    patient = resolve_reference(bundle, "Patient/123")
    encounter = resolve_reference(bundle, "Encounter/abc")
    missing = resolve_reference(bundle, "Observation/999")

    assert patient is not None
    assert patient.resource_type == "Patient"
    assert encounter is not None
    assert encounter.resource_id == "abc"
    assert missing is None


def test_settings_include_fhir_gateway_defaults() -> None:
    settings = Settings()

    assert settings.fhir_base_url
    assert settings.fhir_timeout_seconds > 0
