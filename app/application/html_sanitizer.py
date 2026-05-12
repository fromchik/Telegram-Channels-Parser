from __future__ import annotations

import re


ALLOWED_TAGS = {
    "b",
    "/b",
    "strong",
    "/strong",
    "i",
    "/i",
    "em",
    "/em",
    "u",
    "/u",
    "s",
    "/s",
    "strike",
    "/strike",
    "tg-spoiler",
    "/tg-spoiler",
    "code",
    "/code",
    "pre",
    "/pre",
    "blockquote",
    "/blockquote",
    "a",
    "/a",
}


def sanitize_telegram_html(value: str) -> str:
    text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")

    def replace_tag(match: re.Match[str]) -> str:
        full = match.group(0)
        inner = match.group(1).strip()
        tag_name = inner.split()[0].lower() if inner else ""

        if inner.lower().startswith("a "):
            tag_name = "a"

        if tag_name in ALLOWED_TAGS:
            return full
        return ""

    text = re.sub(r"<([^>]+)>", replace_tag, text)
    return text
