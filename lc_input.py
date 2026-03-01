import os
import select
import sys
from typing import Optional

from lc_screen import lc


class LCInputSource:
    def __init__(self) -> None:
        self.state = lc

    def unread_byte(self, ch: int) -> None:
        self.state.pushback_byte = ch & 0xFF

    def read_byte(self) -> Optional[int]:
        if self.state.pushback_byte is not None:
            ch = self.state.pushback_byte
            self.state.pushback_byte = None
            return ch

        while True:
            try:
                data = os.read(self.state.in_fd, 1)
                if len(data) == 1:
                    return data[0]
                if len(data) == 0:
                    return None
            except InterruptedError:
                continue
            except (OSError, ValueError):
                return None

    def input_pending(self, timeout_ms: int) -> bool:
        timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
        while True:
            try:
                r, _w, _e = select.select([self.state.in_fd], [], [], timeout)
                return bool(r)
            except InterruptedError:
                continue
            except (OSError, ValueError):
                return False


default_input = LCInputSource()


def unread_byte(ch: int) -> None:
    default_input.unread_byte(ch)


def read_byte() -> Optional[int]:
    return default_input.read_byte()


def input_pending(timeout_ms: int) -> bool:
    return default_input.input_pending(timeout_ms)
