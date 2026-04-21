from __future__ import annotations

import os

from google.adk.agents import Agent

from prompt_opinion_adapter.context import extract_prompt_opinion_context
from prompt_opinion_adapter.tools import (
    fetch_patient_context,
    run_discharge_handoff,
    run_ed_summary,
    run_full_transition_of_care,
    run_medication_reconciliation,
)


root_agent = Agent(
    name="carebridge_transition_agent",
    model=os.getenv("PROMPT_OPINION_MODEL", "gemini-2.5-flash"),
    description=(
        "A transition-of-care workflow agent for CareBridge AI. "
        "It can fetch patient context, generate ED summaries, run medication reconciliation, "
        "prepare discharge or handoff summaries, and run the full transition-of-care workflow."
    ),
    instruction=(
        "You are the CareBridge AI transition-of-care agent. "
        "Use the available tools to execute workflows against the active patient context. "
        "Do not invent clinical data. If patient context is missing, explain that Prompt Opinion "
        "must provide FHIR metadata including a FHIR server URL, bearer token, and patient ID. "
        "Prefer the full transition-of-care workflow when the user asks for a complete discharge-ready result. "
        "Use medication reconciliation for medication safety review only, ED summary for ED summarization only, "
        "and discharge handoff when the user specifically wants a discharge or clinician handoff summary. "
        "When you use a workflow tool, return the workflow result clearly, including the trace ID and any findings."
    ),
    tools=[
        fetch_patient_context,
        run_ed_summary,
        run_medication_reconciliation,
        run_discharge_handoff,
        run_full_transition_of_care,
    ],
    before_model_callback=extract_prompt_opinion_context,
)

