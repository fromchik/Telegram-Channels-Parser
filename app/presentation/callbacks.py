from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    action: str
    item_id: int | None = None
    extra: str | None = None
