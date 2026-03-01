import os
import select
import sys
from typing import Optional

from lc_screen import lc


def unread_byte(ch: int) -> None:
    lc.pushback_byte = ch & 0xFF


def read_byte() -> Optional[int]:
    if lc.pushback_byte is not None:
        ch = lc.pushback_byte
        lc.pushback_byte = None
        return ch

    while True:
        try:
            data = os.read(sys.stdin.fileno(), 1)
            if len(data) == 1:
                return data[0]
            if len(data) == 0:
                return None
        except InterruptedError:
            continue
        except OSError:
            return None


def input_pending(timeout_ms: int) -> bool:
    timeout = None if timeout_ms < 0 else timeout_ms / 1000.0

    while True:
        try:
            r, _w, _e = select.select([sys.stdin.fileno()], [], [], timeout)
            return bool(r)
        except InterruptedError:
            continue
        except OSError:
            return False
