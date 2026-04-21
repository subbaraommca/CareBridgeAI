from prompt_opinion_adapter.context import extract_fhir_from_payload, extract_prompt_opinion_context


class FakeCallbackContext:
    def __init__(self, metadata=None) -> None:
        self.metadata = metadata
        self.state = {}
        self.run_config = None


class FakeLlmRequest:
    def __init__(self) -> None:
        self.contents = []


def test_extract_fhir_from_payload_reads_prompt_opinion_metadata() -> None:
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "metadata": {
                    "https://workspace.promptopinion.ai/schemas/a2a/v1/fhir-context": {
                        "fhirUrl": "https://example.org/fhir",
                        "fhirToken": "secret-token",
                        "patientId": "patient-123",
                        "encounterId": "enc-1",
                    }
                }
            }
        },
    }

    key, value = extract_fhir_from_payload(payload)

    assert key is not None
    assert value is not None
    assert value["patientId"] == "patient-123"
    assert value["encounterId"] == "enc-1"


def test_extract_prompt_opinion_context_populates_callback_state() -> None:
    callback_context = FakeCallbackContext(
        metadata={
            "https://workspace.promptopinion.ai/schemas/a2a/v1/fhir-context": {
                "fhirUrl": "https://example.org/fhir/",
                "fhirToken": "secret-token",
                "patientId": "patient-123",
                "encounterId": "enc-1",
            }
        }
    )

    extract_prompt_opinion_context(callback_context, FakeLlmRequest())

    assert callback_context.state["fhir_url"] == "https://example.org/fhir"
    assert callback_context.state["fhir_token"] == "secret-token"
    assert callback_context.state["patient_id"] == "patient-123"
    assert callback_context.state["encounter_id"] == "enc-1"
