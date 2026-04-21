from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

FHIR_CONTEXT_KEY = "fhir-context"


def _coerce_fhir_data(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _extract_metadata_sources(callback_context: Any, llm_request: Any) -> list[tuple[str, Any]]:
    callback_metadata = getattr(callback_context, "metadata", None)

    run_config = getattr(callback_context, "run_config", None)
    custom_metadata = getattr(run_config, "custom_metadata", None) if run_config else None
    a2a_metadata = custom_metadata.get("a2a_metadata") if isinstance(custom_metadata, dict) else None

    llm_contents = getattr(llm_request, "contents", None)
    content_metadata = None
    if isinstance(llm_contents, list) and llm_contents:
        last_item = llm_contents[-1]
        if isinstance(last_item, dict):
            content_metadata = last_item.get("metadata")

    return [
        ("callback_context.metadata", callback_metadata),
        ("callback_context.run_config.custom_metadata.a2a_metadata", a2a_metadata),
        ("llm_request.contents[-1].metadata", content_metadata),
    ]


def extract_fhir_from_payload(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Extract Prompt Opinion FHIR metadata from a raw A2A JSON-RPC payload."""

    if not isinstance(payload, dict):
        return None, None

    params = payload.get("params")
    if not isinstance(params, dict):
        return None, None

    for metadata in (params.get("metadata"), (params.get("message") or {}).get("metadata")):
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if FHIR_CONTEXT_KEY in str(key):
                    return str(key), _coerce_fhir_data(value)

    return None, None


def extract_prompt_opinion_context(callback_context: Any, llm_request: Any) -> None:
    """ADK callback that moves Prompt Opinion FHIR metadata into session state."""

    metadata: dict[str, Any] = {}
    selected_source = "none"

    for source_name, candidate in _extract_metadata_sources(callback_context, llm_request):
        if isinstance(candidate, dict) and candidate:
            metadata = candidate
            selected_source = source_name
            break

    if not metadata:
        logger.info("prompt_opinion_context_missing metadata_source=%s", selected_source)
        return None

    fhir_context: dict[str, Any] | None = None
    context_uri: str | None = None
    for key, value in metadata.items():
        if FHIR_CONTEXT_KEY in str(key):
            context_uri = str(key)
            fhir_context = _coerce_fhir_data(value)
            break

    if not fhir_context:
        logger.info("prompt_opinion_context_not_found metadata_source=%s", selected_source)
        return None

    callback_context.state["fhir_url"] = str(fhir_context.get("fhirUrl", "")).rstrip("/")
    callback_context.state["fhir_token"] = str(fhir_context.get("fhirToken", ""))
    callback_context.state["patient_id"] = str(fhir_context.get("patientId", ""))
    callback_context.state["encounter_id"] = str(fhir_context.get("encounterId", ""))
    callback_context.state["fhir_context_uri"] = context_uri or ""

    logger.info(
        "prompt_opinion_context_loaded metadata_source=%s patient_id=%s encounter_id=%s fhir_url_set=%s",
        selected_source,
        callback_context.state["patient_id"] or "[EMPTY]",
        callback_context.state["encounter_id"] or "[EMPTY]",
        bool(callback_context.state["fhir_url"]),
    )
    return None

