import fcntl
import struct
import sys
import termios
from typing import Optional

from lc_term import LC_ATTR_NONE, Terminal
from lc_window import LCCell, LCWin, lc_free, lc_new, mark_dirty


class LCState:
    def __init__(self) -> None:
        self.stdscr: Optional[LCWin] = None
        self.lines = 0
        self.cols = 0
        self.term = Terminal()

        self.orig_term = None
        self.cur_term = None

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
        buf = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
        rows, cols, _xp, _yp = struct.unpack('HHHH', buf)
        if rows > 0 and cols > 0:
            return rows, cols
    except OSError:
        pass
    return 24, 80


def lc_init() -> Optional[LCWin]:
    rows, cols = _get_winsize()
    lc.lines = rows
    lc.cols = cols

    lc.stdscr = lc_new(rows, cols, 0, 0)
    if lc.stdscr is None:
        return None

    fd = sys.stdin.fileno()
    lc.orig_term = termios.tcgetattr(fd)
    lc.cur_term = termios.tcgetattr(fd)

    lc.cur_term[3] &= ~(termios.ICANON | termios.ECHO)
    lc.cur_term[6][termios.VMIN] = 1
    lc.cur_term[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSAFLUSH, lc.cur_term)

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
    fd = sys.stdin.fileno()

    if lc.orig_term is not None:
        termios.tcsetattr(fd, termios.TCSAFLUSH, lc.orig_term)

    lc_keypad(False)
    lc.term.show_cursor(True)
    lc.term.use_alternate_screen(False)

    if lc.stdscr is not None:
        lc_free(lc.stdscr)
        lc.stdscr = None

    return 0


def _apply_term() -> int:
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, lc.cur_term)
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


def lc_move(y: int, x: int) -> int:
    if lc.stdscr is None:
        return -1
    if y < 0 or y >= lc.stdscr.maxy or x < 0 or x >= lc.stdscr.maxx:
        return -1
    lc.stdscr.cury = y
    lc.stdscr.curx = x
    return 0


def lc_put(ch: int) -> int:
    if lc.stdscr is None:
        return -1

    win = lc.stdscr
    if win.curx >= win.maxx or win.cury >= win.maxy:
        return -1

    ln = win.lines[win.cury]
    ln.line[win.curx].ch = chr(ch)
    ln.line[win.curx].attr = LC_ATTR_NONE
    mark_dirty(ln, win.curx, win.curx + 1, win.maxx)

    win.curx += 1
    if win.curx >= win.maxx:
        win.curx = 0
        if win.cury < win.maxy - 1:
            win.cury += 1

    return 0


def lc_set_escdelay(ms: int) -> int:
    lc.escdelay_ms = ms
    return 0


def lc_nodelay(on: bool) -> int:
    lc.nodelay_on = bool(on)
    return 0


def lc_meta_esc(on: bool) -> int:
    lc.meta_on = bool(on)
    return 0
