from telethon.tl.types import MessageEntityBold, MessageEntityTextUrl, MessageEntityUnderline

from app.infrastructure.telegram.formatter import TelegramHtmlFormatter


def test_formatter_wraps_basic_entities() -> None:
    formatter = TelegramHtmlFormatter()
    text = "Hello world"
    entities = [MessageEntityBold(offset=0, length=5), MessageEntityUnderline(offset=6, length=5)]

    html = formatter.format(text, entities)

    assert "<b>Hello</b>" in html
    assert "<u>world</u>" in html


def test_formatter_formats_text_url() -> None:
    formatter = TelegramHtmlFormatter()
    text = "Click here"
    entities = [MessageEntityTextUrl(offset=6, length=4, url="https://example.com")]

    html = formatter.format(text, entities)

    assert '<a href="https://example.com">here</a>' in html
