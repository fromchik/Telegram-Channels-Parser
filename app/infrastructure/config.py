from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    bot_owner_ids_raw: str = Field(default="", alias="BOT_OWNER_IDS")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/parserbot.db", alias="DATABASE_URL")
    telegram_api_id: int = Field(alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(alias="TELEGRAM_API_HASH")
    telethon_session_string: str = Field(default="", alias="TELETHON_SESSION_STRING")
    telethon_session_file: str = Field(default="./data/telethon_user", alias="TELETHON_SESSION_FILE")
    media_storage_dir: str = Field(default="./data/media", alias="MEDIA_STORAGE_DIR")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-oss-120b:free", alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    publish_channel_id: str = Field(default="", alias="PUBLISH_CHANNEL_ID")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_parse_limit: int = Field(default=10, alias="DEFAULT_PARSE_LIMIT")
    default_parse_period_hours: int = Field(default=24, alias="DEFAULT_PARSE_PERIOD_HOURS")
    flood_sleep_threshold: int = Field(default=60, alias="FLOOD_SLEEP_THRESHOLD")

    @property
    def bot_owner_ids(self) -> set[int]:
        return {int(value.strip()) for value in self.bot_owner_ids_raw.split(",") if value.strip()}

    @property
    def normalized_database_url(self) -> str:
        if not self.database_url.startswith("sqlite"):
            return self.database_url

        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url

        raw_path = self.database_url[len(prefix) :]
        if not raw_path or raw_path == ":memory:":
            return self.database_url

        base_dir = Path(__file__).resolve().parents[2]
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = (base_dir / db_path).resolve()

        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{db_path.as_posix()}"

    @property
    def normalized_telethon_session_file(self) -> str:
        base_dir = Path(__file__).resolve().parents[2]
        session_path = Path(self.telethon_session_file)
        if not session_path.is_absolute():
            session_path = (base_dir / session_path).resolve()
        session_path.parent.mkdir(parents=True, exist_ok=True)
        return session_path.as_posix()

    @property
    def normalized_media_storage_dir(self) -> str:
        base_dir = Path(__file__).resolve().parents[2]
        media_path = Path(self.media_storage_dir)
        if not media_path.is_absolute():
            media_path = (base_dir / media_path).resolve()
        media_path.mkdir(parents=True, exist_ok=True)
        return media_path.as_posix()


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()
