from __future__ import annotations

import httpx

from app.domain.exceptions import ExternalServiceError


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def generate_text(self, prompt: str) -> str:
        if not self._api_key:
            raise ExternalServiceError("OPENROUTER_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You rewrite Telegram posts and return HTML only."},
                {"role": "user", "content": prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self._base_url}/chat/completions", headers=headers, json=payload)

        if response.status_code >= 400:
            raise ExternalServiceError(f"OpenRouter error: {response.status_code} {response.text}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError("OpenRouter returned an unexpected response") from exc
