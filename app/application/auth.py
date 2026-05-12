from __future__ import annotations

from app.domain.exceptions import AccessDeniedError


class AccessPolicy:
    def __init__(self, owner_ids: set[int]) -> None:
        self._owner_ids = owner_ids

    def ensure_allowed(self, telegram_user_id: int) -> None:
        if self._owner_ids and telegram_user_id not in self._owner_ids:
            raise AccessDeniedError("Access denied for this Telegram user")
