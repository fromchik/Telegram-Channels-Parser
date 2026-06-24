from __future__ import annotations

from html import escape

from telethon.tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityCustomEmoji,
    MessageEntityItalic,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
    MessageEntityUrl,
)


class TelegramHtmlFormatter:
    def format(self, text: str | None, entities: list | None) -> str:
        if not text:
            return "<i>Пост без текста</i>"

        result = escape(text, quote=False)
        entities = sorted(entities or [], key=lambda entity: entity.offset, reverse=True)
        for entity in entities:
            start = len(escape(text[: entity.offset], quote=False))
            end = start + len(escape(text[entity.offset : entity.offset + entity.length], quote=False))
            chunk = result[start:end]
            raw_chunk = text[entity.offset : entity.offset + entity.length]
            replacement = self._wrap_entity(entity, chunk, raw_chunk)
            result = f"{result[:start]}{replacement}{result[end:]}"
        return result

    def _wrap_entity(self, entity, escaped_chunk: str, raw_chunk: str) -> str:
        if isinstance(entity, MessageEntityBold):
            return f"<b>{escaped_chunk}</b>"
        if isinstance(entity, MessageEntityItalic):
            return f"<i>{escaped_chunk}</i>"
        if isinstance(entity, MessageEntityUnderline):
            return f"<u>{escaped_chunk}</u>"
        if isinstance(entity, MessageEntitySpoiler):
            return f"<tg-spoiler>{escaped_chunk}</tg-spoiler>"
        if isinstance(entity, MessageEntityCode):
            return f"<code>{escaped_chunk}</code>"
        if isinstance(entity, MessageEntityPre):
            language = escape(entity.language or "", quote=True)
            if language:
                return f'<pre><code class="language-{language}">{escaped_chunk}</code></pre>'
            return f"<pre>{escaped_chunk}</pre>"
        if isinstance(entity, MessageEntityTextUrl):
            url = escape(entity.url, quote=True)
            return f'<a href="{url}">{escaped_chunk}</a>'
        if isinstance(entity, MessageEntityUrl):
            url = escape(raw_chunk, quote=True)
            return f'<a href="{url}">{escaped_chunk}</a>'
        if isinstance(entity, MessageEntityStrike):
            return f"<s>{escaped_chunk}</s>"
        if isinstance(entity, MessageEntityBlockquote):
            return f"<blockquote>{escaped_chunk}</blockquote>"
        if isinstance(entity, MessageEntityCustomEmoji):
            return escaped_chunk
        return escaped_chunk

