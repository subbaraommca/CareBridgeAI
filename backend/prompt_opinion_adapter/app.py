from __future__ import annotations

import os

from a2a.types import AgentSkill
from dotenv import load_dotenv

load_dotenv()

from prompt_opinion_adapter.agent import root_agent
from prompt_opinion_adapter.app_factory import create_a2a_app

PORT = int(os.getenv("PROMPT_OPINION_ADAPTER_PORT", "8010"))
BASE_URL = os.getenv("PROMPT_OPINION_AGENT_URL", f"http://localhost:{PORT}")
PO_PLATFORM_BASE_URL = os.getenv("PO_PLATFORM_BASE_URL", "http://localhost:5139").rstrip("/")


a2a_app = create_a2a_app(
    agent=root_agent,
    name="carebridge_transition_agent",
    description=(
        "CareBridge AI workflow agent for transition-of-care use cases. "
        "Supports patient context retrieval, ED summary generation, medication reconciliation, "
        "discharge or handoff summary generation, and full transition-of-care execution."
    ),
    url=BASE_URL,
    port=PORT,
    fhir_extension_uri=f"{PO_PLATFORM_BASE_URL}/schemas/a2a/v1/fhir-context",
    fhir_scopes=[
        {"name": "patient/Patient.rs", "required": True},
        {"name": "patient/Encounter.rs", "required": False},
        {"name": "patient/Condition.rs", "required": True},
        {"name": "patient/AllergyIntolerance.rs", "required": True},
        {"name": "patient/MedicationRequest.rs", "required": True},
        {"name": "patient/MedicationStatement.rs", "required": True},
        {"name": "patient/Observation.rs", "required": True},
    ],
    skills=[
        AgentSkill(
            id="carebridge-fetch-context",
            name="carebridge-fetch-context",
            description="Fetch and normalize patient context from the active FHIR session.",
            tags=["fhir", "context", "normalization"],
        ),
        AgentSkill(
            id="carebridge-ed-summary",
            name="carebridge-ed-summary",
            description="Generate an ED summary for the active patient and encounter.",
            tags=["ed-summary", "transition-of-care"],
        ),
        AgentSkill(
            id="carebridge-med-rec",
            name="carebridge-med-rec",
            description="Run deterministic medication reconciliation and verification question generation.",
            tags=["medication-reconciliation", "med-safety"],
        ),
        AgentSkill(
            id="carebridge-discharge-handoff",
            name="carebridge-discharge-handoff",
            description="Generate a discharge or clinician handoff package with medication review.",
            tags=["discharge", "handoff", "transition-of-care"],
        ),
        AgentSkill(
            id="carebridge-full-transition-of-care",
            name="carebridge-full-transition-of-care",
            description="Run the full transition-of-care workflow bundle for the active patient.",
            tags=["workflow", "transition-of-care", "orchestration"],
        ),
    ],
    require_api_key=True,
)
