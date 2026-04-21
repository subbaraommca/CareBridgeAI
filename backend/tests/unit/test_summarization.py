import httpx

from app.agents.ed_summary_agent import EDSummaryAgent
from app.agents.transition_agent import TransitionAgent
from app.config.settings import Settings
from app.models.canonical_patient import (
    AllergyRecord,
    EncounterSummary,
    MedicationRecord,
    ObservationRecord,
    PatientDemographics,
    PatientSnapshot,
)
from app.services.summarization.gemini_client import GeminiClient
from app.services.summarization.prompt_manager import (
    build_ed_summary_prompt,
    build_patient_discharge_instructions_prompt,
    build_transition_clinician_prompt,
)


def build_snapshot() -> PatientSnapshot:
    return PatientSnapshot(
        patient=PatientDemographics(
            patient_id="patient-123",
            given_name="Alex",
            family_name="Morgan",
        ),
        encounter=EncounterSummary(
            encounter_id="enc-1",
            encounter_class="emergency",
            status="finished",
            reason_for_visit="Chest pain",
        ),
        allergies=[AllergyRecord(allergy_id="alg-1", substance="Penicillin")],
        medications=[MedicationRecord(medication_id="med-1", display="Aspirin 81 mg")],
        observations=[ObservationRecord(observation_id="obs-1", display="Heart rate", value_numeric=84)],
    )


def test_prompt_templates_include_guardrails_and_snapshot_context() -> None:
    snapshot = build_snapshot()

    ed_prompt = build_ed_summary_prompt(snapshot)
    transition_prompt = build_transition_clinician_prompt(snapshot, transition_type="discharge")
    patient_prompt = build_patient_discharge_instructions_prompt(snapshot)

    for prompt in (ed_prompt, transition_prompt, patient_prompt):
        assert "Use only the supplied structured patient data." in prompt
        assert "Do not make diagnosis claims." in prompt
        assert "Do not provide unsupported treatment recommendations." in prompt
        assert "Clearly separate evidence from assumptions or unknowns." in prompt
        assert '"patient_id": "patient-123"' in prompt

    assert "1. ED Summary" in ed_prompt
    assert "1. Transition Summary" in transition_prompt
    assert "1. What Happened Today" in patient_prompt


def test_gemini_client_returns_fallback_when_not_configured() -> None:
    client = GeminiClient(settings=Settings(gemini_api_key=None, gemini_model="gemini-test"))

    result = client.generate_summary("prompt", "fallback text")

    assert result.text == "fallback text"
    assert result.used_fallback is True
    assert result.provider == "fallback"


def test_gemini_client_parses_mocked_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "generateContent" in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Clinician summary line 1."},
                                {"text": "Clinician summary line 2."},
                            ]
                        }
                    }
                ]
            },
        )

    client = GeminiClient(
        settings=Settings(gemini_api_key="secret", gemini_model="gemini-test"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.generate_summary("prompt", "fallback text")

    assert result.used_fallback is False
    assert result.provider == "gemini"
    assert result.text == "Clinician summary line 1.\nClinician summary line 2."


def test_ed_summary_agent_returns_structured_output_with_fallback() -> None:
    snapshot = build_snapshot()
    agent = EDSummaryAgent(gemini_client=GeminiClient(settings=Settings(gemini_api_key=None)))

    response = agent.summarize(snapshot, correlation_id="corr-ed-1")

    assert response.summary_text is not None
    assert "ED Summary" in response.summary_text
    assert response.artifacts["provider"] == "fallback"
    assert response.patient_snapshot == snapshot


def test_transition_agent_returns_clinician_and_patient_outputs() -> None:
    snapshot = build_snapshot()
    agent = TransitionAgent(gemini_client=GeminiClient(settings=Settings(gemini_api_key=None)))

    response = agent.summarize(snapshot, correlation_id="corr-tr-1", transition_type="handoff")

    assert response.summary_text is not None
    assert "Transition Summary" in response.summary_text
    assert response.handoff_sections["clinician_summary"] == response.summary_text
    assert "What Happened Today" in response.handoff_sections["patient_instructions"]
    assert response.artifacts["patient_instructions"] == response.handoff_sections["patient_instructions"]
