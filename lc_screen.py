import sys
from contextlib import contextmanager, suppress
from typing import Optional

from lc_term import (
    LC_ATTR_NONE,
    LC_DIRTY,
    LC_FORCEPAINT,
    Terminal,
)
from lc_platform import backend
from lc_window import (
    LCCell,
    LCWin,
    lc_free,
    lc_wfill,
    lc_mvwaddstr,
    lc_panel_content_rect,
    lc_panel_subwin,
    lc_new,
    lc_invalidate_children,
    lc_subwin,
    lc_waddstr,
    lc_waddstr_attr,
    lc_wdraw_panel,
    lc_wdraw_box,
    lc_wdraw_box_title,
    lc_wdraw_hline,
    lc_wdraw_vline,
    lc_wmove,
    lc_wput,
    lc_wtouchline,
    lc_wtouchwin,
    lc_winsdelln,
    lc_wscrl,
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

        # Physical screen cache: what the terminal is believed to show now.
        self.screen: list[list[LCCell]] = []

        # Desired virtual screen: what the next doupdate should realize.
        self.vscreen: list[list[LCCell]] = []

        # Dirty spans in the desired virtual screen, indexed by physical row.
        # A value of -1 means "clean/no pending desired update".
        self.vdirty_first: list[int] = []
        self.vdirty_last: list[int] = []

        self.cur_y = 0
        self.cur_x = 0
        self.cur_attr = LC_ATTR_NONE

        # Cursor requested by the most recently staged window.
        self.virtual_cur_y = 0
        self.virtual_cur_x = 0
        self.virtual_cursor_valid = False

        self.resize_pending = False
        self._prev_winch_handler = None


lc = LCState()


def _reset_runtime_state() -> None:
    lc.screen = []
    lc.vscreen = []
    lc.vdirty_first = []
    lc.vdirty_last = []
    lc.pushback_byte = None
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    lc.virtual_cur_y = 0
    lc.virtual_cur_x = 0
    lc.virtual_cursor_valid = False
    lc.lines = 0
    lc.cols = 0
    lc.resize_pending = False
    lc.orig_term = None
    lc.cur_term = None


def _get_stdscr() -> Optional[LCWin]:
    return lc.stdscr


def _reset_render_cache(rows: int, cols: int) -> None:
    lc.screen = [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(cols)]
        for _y in range(rows)
    ]
    lc.vscreen = [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(cols)]
        for _y in range(rows)
    ]
    lc.vdirty_first = [-1 for _ in range(rows)]
    lc.vdirty_last = [-1 for _ in range(rows)]
    lc.cur_y = 0
    lc.cur_x = 0
    lc.cur_attr = LC_ATTR_NONE
    lc.virtual_cur_y = 0
    lc.virtual_cur_x = 0
    lc.virtual_cursor_valid = False
    lc.term.reset_state()


def _clamp_cursor_to_window(win: LCWin) -> None:
    if win.maxy <= 0 or win.maxx <= 0:
        win.cury = 0
        win.curx = 0
        return
    win.cury = min(max(win.cury, 0), win.maxy - 1)
    win.curx = min(max(win.curx, 0), win.maxx - 1)


def _get_winsize() -> tuple[int, int]:
    return backend.get_size(lc)


def lc_init() -> Optional[LCWin]:
    rows, cols = _get_winsize()
    lc.lines = rows
    lc.cols = cols

    lc.stdscr = lc_new(rows, cols, 0, 0)
    if lc.stdscr is None:
        return None

    if backend.init(lc) != 0:
        lc_free(lc.stdscr)
        lc.stdscr = None
        return None

    entered_alt = False
    try:
        lc.term.reset_state()
        lc.term.use_alternate_screen(True)
        entered_alt = True
        lc.term.set_wrap(False)
        rc = lc_keypad(True)
        if rc != 0:
            raise OSError(f"lc_keypad(True) failed with return code {rc}")
        lc.term.clear_screen()
        lc.term.show_cursor(False)
        _reset_render_cache(rows, cols)
        return lc.stdscr
    except (OSError, ValueError):
        with suppress(OSError, ValueError):
            lc.term.set_attr(LC_ATTR_NONE)
            lc.term.set_wrap(True)
            lc_keypad(False)
            lc.term.show_cursor(True)
            if entered_alt:
                lc.term.use_alternate_screen(False)
        backend.end(lc)
        lc.term.reset_state()
        lc_free(lc.stdscr)
        lc.stdscr = None
        _reset_runtime_state()
        return None


def lc_subwindow(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]:
    if lc.stdscr is None:
        return None
    return lc_subwin(lc.stdscr, nlines, ncols, begin_y, begin_x)


def lc_subwindow_from(
    parent: Optional[LCWin],
    nlines: int,
    ncols: int,
    begin_y: int,
    begin_x: int,
) -> Optional[LCWin]:
    return lc_subwin(parent, nlines, ncols, begin_y, begin_x)


def lc_panel_content_subwindow(
    y: int,
    x: int,
    height: int,
    width: int,
) -> Optional[LCWin]:
    if lc.stdscr is None:
        return None
    return lc_panel_subwin(lc.stdscr, y, x, height, width)


def lc_panel_content_subwindow_from(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
) -> Optional[LCWin]:
    return lc_panel_subwin(parent, y, x, height, width)


def lc_get_panel_content_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    return lc_panel_content_rect(y, x, height, width)


def lc_end() -> int:
    try:
        with suppress(OSError, ValueError):
            lc.term.set_attr(LC_ATTR_NONE)
            lc.term.set_wrap(True)
            lc_keypad(False)
            lc.term.show_cursor(True)
            lc.term.use_alternate_screen(False)
            sys.stdout.flush()
    except OSError:
        pass
    finally:
        lc.term.reset_state()
        backend.end(lc)

        if lc.stdscr is not None:
            lc_free(lc.stdscr)
            lc.stdscr = None

        _reset_runtime_state()
    return 0


def _mark_all_dirty(win: LCWin) -> None:
    for ln in win.lines:
        ln.firstch = 0
        if win.maxx > 0:
            ln.lastch = win.maxx - 1
        else:
            ln.lastch = 0
        ln.flags = LC_DIRTY | LC_FORCEPAINT


def _copy_overlap(dst: LCWin, src: LCWin) -> None:
    copy_rows = min(src.maxy, dst.maxy)
    copy_cols = min(src.maxx, dst.maxx)

    for y in range(copy_rows):
        src_ln = src.lines[y]
        dst_ln = dst.lines[y]
        for x in range(copy_cols):
            dst_ln.line[x].ch = src_ln.line[x].ch
            dst_ln.line[x].attr = src_ln.line[x].attr


def lc_is_resize_pending() -> bool:
    # Ask the backend first so this reflects newly observed platform resize
    # state rather than only whatever the core has already consumed.
    if backend.poll_resize(lc):
        lc.resize_pending = True
    return bool(lc.resize_pending)


def lc_get_size() -> tuple[int, int]:
    return lc.lines, lc.cols


def lc_check_resize() -> int:
    resize_seen = backend.poll_resize(lc)
    old = lc.stdscr
    rows, cols = _get_winsize()

    if resize_seen:
        backend.clear_resize(lc)

    if rows <= 0 or cols <= 0:
        lc.resize_pending = False
        return 0

    if old is None:
        lc.resize_pending = False
        return 0

    if not resize_seen and rows == lc.lines and cols == lc.cols:
        return 0

    lc_invalidate_children(old)
    new_win = lc_new(rows, cols, old.begy, old.begx)
    if new_win is None:
        return -1

    _copy_overlap(new_win, old)
    new_win.cury = old.cury
    new_win.curx = old.curx
    _clamp_cursor_to_window(new_win)

    lc_free(old)
    lc.stdscr = new_win
    lc.lines = rows
    lc.cols = cols
    _reset_render_cache(rows, cols)
    _mark_all_dirty(new_win)
    lc.resize_pending = False
    return 1


def _apply_term() -> int:
    return backend.apply_term(lc)


def lc_raw() -> int:
    return backend.raw(lc)


def lc_noraw() -> int:
    return backend.noraw(lc)


def lc_cbreak() -> int:
    return backend.cbreak(lc)


def lc_nocbreak() -> int:
    return backend.nocbreak(lc)


def lc_echo() -> int:
    return backend.echo(lc)


def lc_noecho() -> int:
    return backend.noecho(lc)


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
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    if y < 0 or y >= stdscr.maxy or x < 0 or x >= stdscr.maxx:
        return -1
    return lc_wmove(stdscr, y, x)


def lc_put(ch: int) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wput(stdscr, ch, LC_ATTR_NONE)


def lc_addstr(s: str) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    if s is None:
        return -1
    return lc_waddstr(stdscr, s)


def lc_addstr_attr(s: str, attr: int) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    if s is None:
        return -1
    return lc_waddstr_attr(stdscr, s, attr)


def lc_mvaddstr(y: int, x: int, s: str) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_mvwaddstr(stdscr, y, x, s)


def lc_put_attr(ch: int, attr: int) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wput(stdscr, ch, attr)


def lc_fill(
    y: int,
    x: int,
    height: int,
    width: int,
    ch: str = " ",
    attr: int = LC_ATTR_NONE,
) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wfill(stdscr, y, x, height, width, ch, attr)


def lc_touchline(y: int, n: int = 1) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wtouchline(stdscr, y, n)


def lc_touchwin() -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wtouchwin(stdscr)


def lc_insdelln(n: int) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_winsdelln(stdscr, n)


def lc_scrl(n: int) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wscrl(stdscr, n)


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
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wdraw_hline(stdscr, y, x, width, ch, attr)


def lc_draw_vline(y: int, x: int, height: int, ch: str = "|", attr: int = LC_ATTR_NONE) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wdraw_vline(stdscr, y, x, height, ch, attr)


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
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wdraw_box(stdscr, y, x, height, width, attr, hch, vch, tl, tr, bl, br)


def lc_draw_box_title(
    y: int,
    x: int,
    height: int,
    width: int,
    title: str,
    attr: int = LC_ATTR_NONE,
) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wdraw_box_title(
        stdscr, y, x, height, width, title, attr
    )


def lc_draw_panel(
    y: int,
    x: int,
    height: int,
    width: int,
    title: Optional[str] = None,
    frame_attr: int = LC_ATTR_NONE,
    fill: Optional[str] = None,
    fill_attr: int = LC_ATTR_NONE,
    hch: str = "-",
    vch: str = "|",
    tl: str = "+",
    tr: str = "+",
    bl: str = "+",
    br: str = "+",
) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_wdraw_panel(
        stdscr,
        y,
        x,
        height,
        width,
        title,
        frame_attr,
        fill,
        fill_attr,
        hch, vch, tl, tr, bl, br,
    )


def lc_addstr_at(y: int, x: int, s: str) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    return lc_mvwaddstr(stdscr, y, x, s)


def lc_addstr_centered(y: int, s: str) -> int:
    stdscr = _get_stdscr()
    if stdscr is None:
        return -1
    x = lc_center_x(lc.cols, s)
    return lc_mvwaddstr(stdscr, y, x, s)


def lc_set_escdelay(ms: int) -> int:
    lc.escdelay_ms = ms
    return 0


def lc_nodelay(on: bool) -> int:
    lc.nodelay_on = bool(on)
    return 0


def lc_meta_esc(on: bool) -> int:
    lc.meta_on = bool(on)
    return 0
