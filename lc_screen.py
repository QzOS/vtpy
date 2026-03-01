import fcntl
import signal
import struct
import sys
import termios
from contextlib import contextmanager
from typing import Optional

from lc_term import (
    LC_ATTR_NONE,
    LC_DIRTY,
    LC_FORCEPAINT,
    Terminal,
)
from lc_window import (
    LCCell,
    LCWin,
    lc_free,
    lc_mvwaddstr,
    lc_new,
    lc_waddstr,
    lc_wdraw_box,
    lc_wdraw_hline,
    lc_wdraw_vline,
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

        self.resize_pending = False
        self._prev_winch_handler = None


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


def _on_sigwinch(signum, frame) -> None:
    del signum
    del frame
    lc.resize_pending = True


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
    lc.term.set_wrap(False)
    lc_keypad(True)
    lc.term.clear_screen()
    lc.term.show_cursor(False)

    lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _x in range(cols)] for _y in range(rows)]
    lc.hashes = [0 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE

    lc.resize_pending = False
    lc._prev_winch_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)

    return lc.stdscr


def lc_end() -> int:
    # Emit terminal restore sequences before restoring termios.
    try:
        lc.term.set_attr(LC_ATTR_NONE)
        lc.term.set_wrap(True)
        lc_keypad(False)
        lc.term.show_cursor(True)
        lc.term.use_alternate_screen(False)
        sys.stdout.flush()
    except OSError:
        pass

    if lc._prev_winch_handler is not None:
        try:
            signal.signal(signal.SIGWINCH, lc._prev_winch_handler)
        except (OSError, ValueError):
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
    lc.orig_term = None
    lc.cur_term = None
    lc.pushback_byte = None
    lc.resize_pending = False
    lc._prev_winch_handler = None
    lc.in_fd = 0
    lc.out_fd = 1
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    return 0


def _mark_all_dirty(win: LCWin) -> None:
    for ln in win.lines:
        ln.firstch = 0
        if win.maxx > 0:
            ln.lastch = win.maxx - 1
        else:
            ln.lastch = 0
        ln.flags = LC_DIRTY | LC_FORCEPAINT


def lc_is_resize_pending() -> bool:
    return bool(lc.resize_pending)


def lc_get_size() -> tuple[int, int]:
    return lc.lines, lc.cols


def lc_check_resize() -> int:
    old = lc.stdscr
    rows, cols = _get_winsize()

    if rows <= 0 or cols <= 0:
        lc.resize_pending = False
        return 0

    if old is None:
        lc.resize_pending = False
        return 0

    if not lc.resize_pending and rows == lc.lines and cols == lc.cols:
        return 0

    new_win = lc_new(rows, cols, old.begy, old.begx)
    if new_win is None:
        return -1

    copy_rows = min(old.maxy, new_win.maxy)
    copy_cols = min(old.maxx, new_win.maxx)

    for y in range(copy_rows):
        old_ln = old.lines[y]
        new_ln = new_win.lines[y]
        for x in range(copy_cols):
            new_ln.line[x].ch = old_ln.line[x].ch
            new_ln.line[x].attr = old_ln.line[x].attr

    if old.cury < new_win.maxy:
        new_win.cury = old.cury
    else:
        new_win.cury = new_win.maxy - 1

    if old.curx < new_win.maxx:
        new_win.curx = old.curx
    else:
        new_win.curx = new_win.maxx - 1

    lc_free(old)
    lc.stdscr = new_win
    lc.lines = rows
    lc.cols = cols
    lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _x in range(cols)] for _y in range(rows)]
    lc.hashes = [0 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    lc.term.reset_state()
    _mark_all_dirty(new_win)
    lc.resize_pending = False
    return 1


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


def lc_center_x(width: int, text: str) -> int:
    if width <= 0:
        return 0
    if text is None:
        return 0
    text_len = len(text)
    if text_len >= width:
        return 0
    return (width - text_len) // 2


def lc_draw_hline(y: int, x: int, width: int, ch: str = "-", attr: int = LC_ATTR_NONE) -> int:
    if lc.stdscr is None:
        return -1
    return lc_wdraw_hline(lc.stdscr, y, x, width, ch, attr)


def lc_draw_vline(y: int, x: int, height: int, ch: str = "|", attr: int = LC_ATTR_NONE) -> int:
    if lc.stdscr is None:
        return -1
    return lc_wdraw_vline(lc.stdscr, y, x, height, ch, attr)


def lc_draw_box(
    y: int,
    x: int,
    height: int,
    width: int,
    attr: int = LC_ATTR_NONE,
    hch: str = "-",
    vch: str = "|",
    tl: str = "+",
    tr: str = "+",
    bl: str = "+",
    br: str = "+",
) -> int:
    if lc.stdscr is None:
        return -1
    return lc_wdraw_box(lc.stdscr, y, x, height, width, attr, hch, vch, tl, tr, bl, br)


def lc_addstr_at(y: int, x: int, s: str) -> int:
    if lc.stdscr is None:
        return -1
    return lc_mvwaddstr(lc.stdscr, y, x, s)


def lc_addstr_centered(y: int, s: str) -> int:
    if lc.stdscr is None:
        return -1
    x = lc_center_x(lc.cols, s)
    return lc_mvwaddstr(lc.stdscr, y, x, s)


def lc_set_escdelay(ms: int) -> int:
    lc.escdelay_ms = ms
    return 0


def lc_nodelay(on: bool) -> int:
    lc.nodelay_on = bool(on)
    return 0


def lc_meta_esc(on: bool) -> int:
    lc.meta_on = bool(on)
    return 0
