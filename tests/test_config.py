from app.infrastructure.config import Settings


def test_normalized_database_url_keeps_sqlite_prefix() -> None:
    settings = Settings(
        BOT_TOKEN="x",
        BOT_OWNER_IDS="1",
        TELEGRAM_API_ID=1,
        TELEGRAM_API_HASH="hash",
    )

    assert settings.normalized_database_url.startswith("sqlite+aiosqlite:///")


def test_normalized_media_storage_dir_is_prepared() -> None:
    settings = Settings(
        BOT_TOKEN="x",
        BOT_OWNER_IDS="1",
        TELEGRAM_API_ID=1,
        TELEGRAM_API_HASH="hash",
        MEDIA_STORAGE_DIR="./data/test_media",
    )

    assert settings.normalized_media_storage_dir.endswith("data/test_media")
