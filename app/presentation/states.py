from aiogram.fsm.state import State, StatesGroup


class ChannelState(StatesGroup):
    waiting_for_source = State()


class CollectionState(StatesGroup):
    waiting_for_name = State()
    waiting_for_channel_source = State()
