from app.infrastructure.telegram.gateway import TelethonGateway


def test_safe_source_dir_replaces_windows_unsafe_symbols() -> None:
    value = TelethonGateway._safe_source_dir("invite:Q46QCA8BwsxhNDIy")

    assert value == "invite_Q46QCA8BwsxhNDIy"


def test_safe_source_dir_falls_back_when_empty() -> None:
    value = TelethonGateway._safe_source_dir("::://")

    assert value == "unknown_source"


def test_session_error_message_is_clear() -> None:
    error = TelethonGateway._session_error()

    assert "Telethon session is not authorized" in str(error)
