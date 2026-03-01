from typing import Optional

from lc_screen import lc
from lc_platform import backend


class LCInputSource:
    def __init__(self) -> None:
        self.state = lc

    def unread_byte(self, ch: int) -> None:
        backend.unread_byte(self.state, ch)

    def read_byte(self) -> Optional[int]:
        return backend.read_byte(self.state)

    def input_pending(self, timeout_ms: int) -> bool:
        return backend.input_pending(self.state, timeout_ms)


default_input = LCInputSource()


def unread_byte(ch: int) -> None:
    default_input.unread_byte(ch)


def read_byte() -> Optional[int]:
    return default_input.read_byte()


def input_pending(timeout_ms: int) -> bool:
    return default_input.input_pending(timeout_ms)
