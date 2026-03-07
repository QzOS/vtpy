import lc_screen
from lc_window import lc_new


class _RecordingTerm:
    def __init__(self) -> None:
        self._last_attr = None
        self.writes = []

    def move_bytes(self, y: int, x: int) -> bytes:
        return b""

    def attr_bytes(self, attr: int) -> bytes:
        return b""

    def encode_text(self, s: str) -> bytes:
        return s.encode("utf-8", "replace")

    def write_bytes(self, data: bytes | bytearray) -> None:
        self.writes.append(bytes(data))

    def clear_screen(self) -> None:
        pass

    def reset_state(self) -> None:
        self._last_attr = None

    def note_attr(self, attr: int) -> None:
        self._last_attr = attr


def _install_test_screen(win):
    term = _RecordingTerm()
    lc_screen.lc.stdscr = win
    lc_screen.lc.lines = win.maxy
    lc_screen.lc.cols = win.maxx
    lc_screen.lc.screen = [
        [lc_screen.LCCell(" ", 0) for _x in range(win.maxx)]
        for _y in range(win.maxy)
    ]
    lc_screen.lc.vscreen = [
        [lc_screen.LCCell(" ", 0) for _x in range(win.maxx)]
        for _y in range(win.maxy)
    ]
    lc_screen.lc.vdirty_first = [-1 for _ in range(win.maxy)]
    lc_screen.lc.vdirty_last = [-1 for _ in range(win.maxy)]
    lc_screen.lc.cur_y = 0
    lc_screen.lc.cur_x = 0
    lc_screen.lc.cur_attr = 0
    lc_screen.lc.virtual_cur_y = 0
    lc_screen.lc.virtual_cur_x = 0
    lc_screen.lc.virtual_cursor_valid = False
    lc_screen.lc.resize_pending = False
    lc_screen.lc.term = term
    return term
