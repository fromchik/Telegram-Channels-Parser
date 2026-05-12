from app.application.html_sanitizer import sanitize_telegram_html


def test_sanitizer_replaces_br_with_newline() -> None:
    value = sanitize_telegram_html("Hello<br>world")

    assert value == "Hello\nworld"


def test_sanitizer_removes_unsupported_tags() -> None:
    value = sanitize_telegram_html("<div>Hello</div><b>world</b>")

    assert value == "Hello<b>world</b>"
