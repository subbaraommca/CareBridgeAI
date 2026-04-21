from __future__ import annotations

import json
import logging
import os
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from prompt_opinion_adapter.context import extract_fhir_from_payload

logger = logging.getLogger(__name__)


def _load_valid_api_keys() -> set[str]:
    keys: set[str] = set()

    for env_name in (
        "PROMPT_OPINION_API_KEYS",
        "API_KEYS",
    ):
        raw = os.getenv(env_name, "")
        if raw:
            keys.update(item.strip() for item in raw.split(",") if item.strip())

    for env_name in (
        "PROMPT_OPINION_API_KEY_PRIMARY",
        "PROMPT_OPINION_API_KEY_SECONDARY",
        "API_KEY_PRIMARY",
        "API_KEY_SECONDARY",
    ):
        value = os.getenv(env_name, "").strip()
        if value:
            keys.add(value)

    return keys


VALID_API_KEYS = _load_valid_api_keys()


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Prompt Opinion compatibility middleware with API-key enforcement."""

    async def dispatch(self, request: Request, call_next):
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="replace")
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            parsed = {}

        method_aliases = {
            "SendMessage": "message/send",
            "SendStreamingMessage": "message/send",
            "GetTask": "tasks/get",
            "CancelTask": "tasks/cancel",
            "TaskResubscribe": "tasks/resubscribe",
        }
        role_aliases = {
            "ROLE_USER": "user",
            "ROLE_AGENT": "agent",
        }
        body_dirty = False

        if isinstance(parsed, dict) and parsed.get("method") in method_aliases:
            parsed["method"] = method_aliases[parsed["method"]]
            body_dirty = True

        def _fix_roles(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("role") in role_aliases:
                    node["role"] = role_aliases[node["role"]]
                for value in node.values():
                    _fix_roles(value)
            elif isinstance(node, list):
                for item in node:
                    _fix_roles(item)

        if isinstance(parsed, dict):
            before = json.dumps(parsed, sort_keys=True)
            _fix_roles(parsed)
            if json.dumps(parsed, sort_keys=True) != before:
                body_dirty = True

        fhir_key, fhir_data = extract_fhir_from_payload(parsed)
        if isinstance(parsed, dict):
            params = parsed.get("params")
            if isinstance(params, dict) and fhir_key and fhir_data and not params.get("metadata"):
                params["metadata"] = {fhir_key: fhir_data}
                body_dirty = True

        if body_dirty:
            body_bytes = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            request._body = body_bytes  # type: ignore[attr-defined]

        if request.url.path == "/.well-known/agent-card.json":
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "detail": "X-API-Key header is required."},
            )
        if api_key not in VALID_API_KEYS:
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden", "detail": "Invalid API key."},
            )

        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        try:
            response_payload = json.loads(response_body)
        except Exception:
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/a2a+json",
            )

        result = response_payload.get("result") if isinstance(response_payload, dict) else None
        if isinstance(result, dict) and result.get("kind") == "task":
            state_map = {
                "completed": "TASK_STATE_COMPLETED",
                "working": "TASK_STATE_WORKING",
                "submitted": "TASK_STATE_SUBMITTED",
                "input-required": "TASK_STATE_INPUT_REQUIRED",
                "failed": "TASK_STATE_FAILED",
                "canceled": "TASK_STATE_CANCELED",
            }

            task = {
                "id": result.get("id"),
                "contextId": result.get("contextId"),
                "status": {
                    "state": state_map.get((result.get("status") or {}).get("state", ""), "TASK_STATE_COMPLETED")
                },
                "artifacts": [],
            }

            for artifact in result.get("artifacts", []):
                clean_parts = []
                for part in artifact.get("parts", []):
                    clean_parts.append({key: value for key, value in part.items() if key != "kind"})
                clean_artifact = {key: value for key, value in artifact.items() if key != "parts"}
                clean_artifact["parts"] = clean_parts
                task["artifacts"].append(clean_artifact)

            response_payload["result"] = {"task": task}
            response_body = json.dumps(response_payload, ensure_ascii=False).encode("utf-8")

        headers = dict(response.headers)
        headers["content-length"] = str(len(response_body))
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/a2a+json",
        )

