from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config.settings import Settings, get_settings


@dataclass(slots=True)
class GeminiGenerationResult:
    text: str
    used_fallback: bool
    provider: str
    model: str


class GeminiClient:
    """Minimal Gemini REST wrapper with deterministic fallback behavior."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = self.settings.gemini_api_key
        self.model = self.settings.gemini_model
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=20.0)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def generate_summary(self, prompt: str, fallback_text: str) -> GeminiGenerationResult:
        if not self.is_configured():
            return GeminiGenerationResult(
                text=fallback_text,
                used_fallback=True,
                provider="fallback",
                model=self.model,
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
            },
        }

        try:
            response = self._http_client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            text = self._extract_text(response.json())
            if not text:
                raise ValueError("Gemini response did not include text output.")

            return GeminiGenerationResult(
                text=text,
                used_fallback=False,
                provider="gemini",
                model=self.model,
            )
        except Exception:
            return GeminiGenerationResult(
                text=fallback_text,
                used_fallback=True,
                provider="fallback",
                model=self.model,
            )

    def _extract_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return ""

        text_parts: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    text_parts.append(str(part["text"]))

        return "\n".join(part for part in text_parts if part.strip()).strip()

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()
