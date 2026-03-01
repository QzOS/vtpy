import fcntl
import os
import struct
import sys
import termios
from contextlib import contextmanager
from typing import Optional

from lc_term import (
    LC_ATTR_NONE,
    Terminal,
)
from lc_window import (
    LCCell,
    LCWin,
    lc_free,
    lc_new,
    lc_wmove,
    lc_wput,
)


class LCState:
    def __init__(self) -> None:
        self.stdscr: Optional[LCWin] = None
        self.lines = 0
        self.cols = 0
        self.term = Terminal()

        self.orig_term = None
        self.cur_term = None

        self.in_fd = 0
        self.out_fd = 1

        self.escdelay_ms = 50
        self.nodelay_on = False
        self.meta_on = True
        self.pushback_byte: Optional[int] = None

        self.screen: list[list[LCCell]] = []
        self.hashes: list[int] = []
        self.cur_y = 0
        self.cur_x = 0
        self.cur_attr = LC_ATTR_NONE


lc = LCState()


def _get_winsize() -> tuple[int, int]:
    try:
        buf = fcntl.ioctl(lc.out_fd, termios.TIOCGWINSZ, b'\x00' * 8)
        rows, cols, _xp, _yp = struct.unpack('HHHH', buf)
        if rows > 0 and cols > 0:
            return rows, cols
    except OSError:
        pass
    return 24, 80


def lc_init() -> Optional[LCWin]:
    lc.in_fd = sys.stdin.fileno()
    lc.out_fd = sys.stdout.fileno()
    lc.term.out_fd = lc.out_fd
    rows, cols = _get_winsize()
    lc.lines = rows
    lc.cols = cols

    lc.stdscr = lc_new(rows, cols, 0, 0)
    if lc.stdscr is None:
        return None

    lc.orig_term = termios.tcgetattr(lc.in_fd)
    lc.cur_term = termios.tcgetattr(lc.in_fd)

    lc.cur_term[3] &= ~(termios.ICANON | termios.ECHO)
    lc.cur_term[6][termios.VMIN] = 1
    lc.cur_term[6][termios.VTIME] = 0
    termios.tcsetattr(lc.in_fd, termios.TCSAFLUSH, lc.cur_term)

    lc.term.reset_state()
    lc.term.use_alternate_screen(True)
    lc_keypad(True)
    lc.term.clear_screen()
    lc.term.show_cursor(False)

    lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _x in range(cols)] for _y in range(rows)]
    lc.hashes = [0 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE

    return lc.stdscr


def lc_end() -> int:
    # Emit terminal restore sequences before restoring termios.
    try:
        lc.term.set_attr(LC_ATTR_NONE)
        lc_keypad(False)
        lc.term.show_cursor(True)
        lc.term.use_alternate_screen(False)
        sys.stdout.flush()
    except OSError:
        pass

    lc.term.reset_state()
    if lc.orig_term is not None:
        try:
            termios.tcsetattr(lc.in_fd, termios.TCSAFLUSH, lc.orig_term)
        except OSError:
            pass

    if lc.stdscr is not None:
        lc_free(lc.stdscr)
        lc.stdscr = None

    lc.screen = []
    lc.hashes = []
    lc.pushback_byte = None
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    return 0


def _apply_term() -> int:
    try:
        termios.tcsetattr(lc.in_fd, termios.TCSAFLUSH, lc.cur_term)
        return 0
    except OSError:
        return -1


def lc_raw() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] &= ~(termios.ICANON | termios.ISIG | termios.ECHO)
    lc.cur_term[6][termios.VMIN] = 1
    lc.cur_term[6][termios.VTIME] = 0
    return _apply_term()


def lc_noraw() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] |= (termios.ICANON | termios.ISIG)
    return _apply_term()


def lc_cbreak() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] &= ~termios.ICANON
    lc.cur_term[6][termios.VMIN] = 1
    lc.cur_term[6][termios.VTIME] = 0
    return _apply_term()


def lc_nocbreak() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] |= termios.ICANON
    return _apply_term()


def lc_echo() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] |= termios.ECHO
    return _apply_term()


def lc_noecho() -> int:
    if lc.cur_term is None:
        return -1
    lc.cur_term[3] &= ~termios.ECHO
    return _apply_term()


def lc_keypad(on: bool) -> int:
    return lc.term.set_keypad_transmit(bool(on))


@contextmanager
def lc_session():
    win = lc_init()
    if win is None:
        raise RuntimeError("lc_init failed")
    try:
        yield win
    finally:
        lc_end()


def lc_move(y: int, x: int) -> int:
    if lc.stdscr is None:
        return -1
    if y < 0 or y >= lc.stdscr.maxy or x < 0 or x >= lc.stdscr.maxx:
        return -1
    return lc_wmove(lc.stdscr, y, x)


def lc_put(ch: int) -> int:
    if lc.stdscr is None:
        return -1
    return lc_wput(lc.stdscr, ch, LC_ATTR_NONE)


def lc_addstr(s: str) -> int:
    if lc.stdscr is None:
        return -1
    if s is None:
        return -1

    for ch in s:
        if lc_put(ord(ch)) != 0:
            return -1
    return 0


def lc_mvaddstr(y: int, x: int, s: str) -> int:
    if lc_move(y, x) != 0:
        return -1
    return lc_addstr(s)


def lc_put_attr(ch: int, attr: int) -> int:
    if lc.stdscr is None:
        return -1
    return lc_wput(lc.stdscr, ch, attr)


def lc_set_escdelay(ms: int) -> int:
    lc.escdelay_ms = ms
    return 0


def lc_nodelay(on: bool) -> int:
    lc.nodelay_on = bool(on)
    return 0


def lc_meta_esc(on: bool) -> int:
    lc.meta_on = bool(on)
    return 0
