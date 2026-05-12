from __future__ import annotations

import pytest

from app.application.ai import AiPostInput, AiPostProcessor
from app.application.dto import MediaAttachmentDTO
from app.domain.exceptions import ExternalServiceError


class FakeAiClient:
    def __init__(self, response: str = "<b>Готово</b>", fail: bool = False) -> None:
        self.response = response
        self.fail = fail
        self.prompt: str | None = None

    async def generate_text(self, prompt: str) -> str:
        self.prompt = prompt
        if self.fail:
            raise ExternalServiceError("AI unavailable")
        return self.response


@pytest.mark.asyncio
async def test_ai_post_processor_builds_prompt_and_returns_response() -> None:
    client = FakeAiClient()
    processor = AiPostProcessor(client)

    result = await processor.process(
        AiPostInput(source_title="Channel", source="example", html_text="<b>Hello</b>", media=[])
    )

    assert result == "<b>Готово</b>"
    assert client.prompt is not None
    assert "переведи его на русский" in client.prompt
    assert "<b>Hello</b>" in client.prompt


@pytest.mark.asyncio
async def test_ai_post_processor_propagates_client_error() -> None:
    client = FakeAiClient(fail=True)
    processor = AiPostProcessor(client)

    with pytest.raises(ExternalServiceError):
        await processor.process(AiPostInput(source_title="Channel", source="example", html_text="text", media=[]))
