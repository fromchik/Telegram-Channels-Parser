from __future__ import annotations

from dataclasses import dataclass

from app.application.dto import MediaAttachmentDTO


@dataclass(slots=True)
class AiPostInput:
    source_title: str
    source: str
    html_text: str
    media: list[MediaAttachmentDTO]


class AiPostProcessor:
    def __init__(self, client) -> None:
        self._client = client

    async def process(self, post: AiPostInput) -> str:
        prompt = (
            "Ты редактор Telegram-постов. Выполни обработку текста поста по правилам:\n"
            "1. Если текст не на русском языке, переведи его на русский.\n"
            "2. Удали водяные знаки, упоминания и рекламные вставки канала, если они не несут смысловой нагрузки.\n"
            "3. Перефразируй текст, сохранив факты и общий смысл.\n"
            "4. Сохрани удобочитаемую Telegram HTML-разметку там, где это уместно.\n"
            "5. Не добавляй от себя новых фактов.\n"
            "6. Верни только готовый текст поста в HTML без пояснений.\n\n"
            f"Источник: {post.source_title} (@{post.source})\n\n"
            f"Пост:\n{post.html_text}"
        )
        return await self._client.generate_text(prompt)
