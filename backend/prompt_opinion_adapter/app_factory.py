from __future__ import annotations

from typing import Any

from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentSkill
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from pydantic import Field

from prompt_opinion_adapter.middleware import ApiKeyMiddleware


class AgentExtensionV1(AgentExtension):
    """Compatibility shim for A2A v1 extension params."""

    params: dict[str, Any] | None = Field(default=None)


class AgentCardV1(AgentCard):
    """Compatibility shim for A2A v1 agent cards used by Prompt Opinion."""

    supportedInterfaces: list[dict[str, Any]] = Field(default_factory=list)
    securitySchemes: dict[str, Any] | None = None


def create_a2a_app(
    agent: Any,
    name: str,
    description: str,
    url: str,
    port: int,
    version: str = "0.1.0",
    fhir_extension_uri: str | None = None,
    fhir_scopes: list[dict[str, Any]] | None = None,
    require_api_key: bool = True,
    skills: list[AgentSkill] | None = None,
):
    extensions = []
    if fhir_extension_uri:
        extension_params = {"scopes": fhir_scopes or []} if fhir_scopes else None
        extensions = [
            AgentExtensionV1(
                uri=fhir_extension_uri,
                description="FHIR context allowing the agent to query CareBridge workflows securely",
                required=False,
                params=extension_params,
            )
        ]

    if require_api_key:
        security_schemes = {
            "apiKey": {
                "apiKeySecurityScheme": {
                    "name": "X-API-Key",
                    "location": "header",
                    "description": "API key required to access this agent.",
                }
            }
        }
        security = [{"apiKey": []}]
    else:
        security_schemes = None
        security = None

    agent_card = AgentCardV1(
        name=name,
        description=description,
        url=url,
        version=version,
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=False,
            extensions=extensions,
        ),
        supportedInterfaces=[
            {
                "url": url,
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        skills=skills or [],
        securitySchemes=security_schemes,
        security=security,
    )

    app = to_a2a(agent, port=port, agent_card=agent_card)
    if require_api_key:
        app.add_middleware(ApiKeyMiddleware)
    return app

