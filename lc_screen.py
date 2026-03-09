import sys
from contextlib import contextmanager, suppress
from typing import Optional, TYPE_CHECKING

from lc_geometry import (
    lc_panel_content_rect as _lc_panel_content_rect,
    lc_panel_header_rect as _lc_panel_header_rect,
    lc_rect_split_horizontal as _lc_rect_split_horizontal,
    lc_rect_split_vertical as _lc_rect_split_vertical,
)

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
    lc_panel_header_subwin,
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
    lc_mvwaddstr,
    lc_wput,
    lc_wtouchline,
    lc_wtouchwin,
    lc_winsdelln,
    lc_wscrl,
)

if TYPE_CHECKING:
    from lc_window import LCWin


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

        # Lifecycle state:
        # - backend_started: backend.init() succeeded and backend.end() is required
        # - session_active: terminal session fully entered and stdscr is usable
        self.backend_started = False
        self.session_active = False


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
    lc.stdscr = None
    lc.backend_started = False
    lc.session_active = False


def _session_stdscr() -> Optional[LCWin]:
    if lc.stdscr is None:
        return None
    if not lc.session_active and _backend_is_live():
        return None
    return lc.stdscr


def _make_blank_screen(rows: int, cols: int) -> list[list[LCCell]]:
    return [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(cols)]
        for _y in range(rows)
    ]


def _get_stdscr() -> Optional[LCWin]:
    if not lc.session_active and _backend_is_live():
        return None
    return lc.stdscr


def _backend_is_live() -> bool:
    return bool(lc.backend_started)


def _reset_render_cache(rows: int, cols: int) -> None:
    lc.screen = _make_blank_screen(rows, cols)
    lc.vscreen = _make_blank_screen(rows, cols)
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


def _free_stdscr_if_present() -> None:
    if lc.stdscr is not None:
        lc_free(lc.stdscr)
        lc.stdscr = None


def _teardown_runtime_terminal_state(entered_alt: bool) -> None:
    with suppress(OSError, ValueError):
        lc.term.set_attr(LC_ATTR_NONE)
        lc.term.set_wrap(True)
        lc_keypad(False)
        lc.term.show_cursor(True)
        if entered_alt:
            lc.term.use_alternate_screen(False)


def _shutdown_runtime(entered_alt: bool) -> None:
    if _backend_is_live():
        _teardown_runtime_terminal_state(entered_alt)
        with suppress(Exception):
            backend.end(lc)

    lc.term.reset_state()
    _free_stdscr_if_present()
    _reset_runtime_state()


def _cleanup_failed_init(entered_alt: bool) -> None:
    _shutdown_runtime(entered_alt)


def _begin_backend() -> int:
    if _backend_is_live() or lc.session_active:
        return -1
    rc = backend.init(lc)
    if rc != 0:
        _reset_runtime_state()
        return -1
    lc.backend_started = True
    return 0


def _activate_session(stdscr: LCWin, rows: int, cols: int) -> LCWin:
    lc.stdscr = stdscr
    lc.lines = rows
    lc.cols = cols
    lc.session_active = True
    return stdscr


def lc_init() -> Optional[LCWin]:
    if lc.session_active or _backend_is_live():
        return None

    if _begin_backend() != 0:
        return None

    rows, cols = _get_winsize()
    stdscr = lc_new(rows, cols, 0, 0)
    if stdscr is None:
        _cleanup_failed_init(False)
        return None

    entered_alt = False
    try:
        # Backend-owned terminal/output state is now live. All terminal control,
        # size assumptions, and root-window allocation from this point onward
        # are based on that active backend state.
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
        return _activate_session(stdscr, rows, cols)
    except (OSError, ValueError):
        _cleanup_failed_init(entered_alt)
        return None


def lc_subwindow(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]:
    if _session_stdscr() is None:
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


def _lc_panel_subwin_from_window(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 0,
) -> Optional[LCWin]:
    return lc_panel_subwin(parent, y, x, height, width, header_height)


def _lc_panel_header_subwin_from_window(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 1,
) -> Optional[LCWin]:
    return lc_panel_header_subwin(parent, y, x, height, width, header_height)


def lc_panel_content_subwindow(
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 0,
) -> Optional[LCWin]:
    if _session_stdscr() is None:
        return None
    return _lc_panel_subwin_from_window(lc.stdscr, y, x, height, width, header_height)


def lc_panel_content_subwindow_from(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 0,
) -> Optional[LCWin]:
    return _lc_panel_subwin_from_window(parent, y, x, height, width, header_height)


def lc_panel_header_subwindow(
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 1,
) -> Optional[LCWin]:
    if _session_stdscr() is None:
        return None
    return _lc_panel_header_subwin_from_window(lc.stdscr, y, x, height, width, header_height)


def lc_panel_header_subwindow_from(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 1,
) -> Optional[LCWin]:
    return _lc_panel_header_subwin_from_window(parent, y, x, height, width, header_height)


def lc_get_panel_header_rect(
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 1,
) -> tuple[int, int, int, int]:
    return _lc_panel_header_rect(y, x, height, width, header_height)


def lc_get_panel_content_rect(
    y: int,
    x: int,
    height: int,
    width: int,
    header_height: int = 0,
) -> tuple[int, int, int, int]:
    return _lc_panel_content_rect(y, x, height, width, header_height)


def lc_rect_split_vertical(
    y: int, x: int, height: int, width: int, top_height: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    return _lc_rect_split_vertical(y, x, height, width, top_height)


def lc_rect_split_horizontal(y: int, x: int, height: int, width: int, left_width: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    return _lc_rect_split_horizontal(y, x, height, width, left_width)


def lc_end() -> int:
    entered_alt = bool(lc.session_active)
    _shutdown_runtime(entered_alt)

    with suppress(OSError, ValueError):
        sys.stdout.flush()

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
    if not lc.session_active and _backend_is_live():
        return False

    if backend.poll_resize(lc):
        lc.resize_pending = True
    return bool(lc.resize_pending)


def lc_get_size() -> tuple[int, int]:
    return lc.lines, lc.cols


def lc_check_resize() -> int:
    if not lc.session_active and _backend_is_live():
        return 0

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


def lc_refresh_session_ready() -> bool:
    if not _backend_is_live():
        return True
    return bool(lc.session_active and lc.stdscr is not None)


def lc_refresh_resize_gate() -> int:
    # Runtime-owned pre-refresh gate.
    #
    # Return values:
    #   -1 : refresh cannot proceed
    #    0 : no resize rebuild occurred
    #    1 : resize rebuild occurred and stdscr may have been replaced
    if not lc_refresh_session_ready():
        return -1
    return lc_check_resize()


def lc_refresh_target_after_resize(requested: Optional["LCWin"], resize_rc: int) -> Optional["LCWin"]:
    if requested is None or not requested.alive:
        return None

    if resize_rc < 0:
        return None

    if resize_rc == 0:
        return requested

    if requested.parent is not None:
        return None

    return lc.stdscr if lc_refresh_session_ready() else None


def lc_refresh_cache_has_shape(cache: list[list[LCCell]], rows: int, cols: int) -> bool:
    if len(cache) != rows:
        return False
    if rows == 0:
        return True
    return all(len(row) == cols for row in cache)


def lc_refresh_reinit_physical_cache() -> None:
    lc.screen = [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(lc.cols)]
        for _y in range(lc.lines)
    ]
    lc.term.clear_screen()
    lc.cur_y = 0
    lc.cur_x = 0
    lc.term.reset_state()
    lc.cur_attr = LC_ATTR_NONE


def lc_refresh_ensure_virtual_cache_shape() -> None:
    if lc_refresh_cache_has_shape(lc.vscreen, lc.lines, lc.cols):
        return

    lc.vscreen = _make_blank_screen(lc.lines, lc.cols)
    lc.vdirty_first = [-1 for _ in range(lc.lines)]
    lc.vdirty_last = [-1 for _ in range(lc.lines)]
    lc.virtual_cur_y = 0
    lc.virtual_cur_x = 0
    lc.virtual_cursor_valid = False


def lc_refresh_mark_full_virtual_dirty() -> None:
    if lc.lines <= 0 or lc.cols <= 0:
        return

    for abs_y in range(lc.lines):
        lc.vdirty_first[abs_y] = 0
        lc.vdirty_last[abs_y] = lc.cols - 1


def lc_refresh_physical_cache_valid() -> bool:
    return lc_refresh_cache_has_shape(lc.screen, lc.lines, lc.cols)


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
    header_height: int = 0,
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
        header_height,
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
    # Negative delay values are not meaningful; reject them to avoid
    # accidentally storing a value that would disable the escape timer.
    if ms < 0:
        return -1
    lc.escdelay_ms = ms
    return 0


def lc_nodelay(on: bool) -> int:
    if not lc.session_active and _backend_is_live():
        return -1
    lc.nodelay_on = bool(on)
    return 0


def lc_meta_esc(on: bool) -> int:
    if not lc.session_active and _backend_is_live():
        return -1
    lc.meta_on = bool(on)
    return 0

# Bind the runtime-owned screen/session state into the refresh layer only
# after this module has finished defining that contract surface. This avoids
# an import-time lc_screen <-> lc_refresh cycle while keeping refresh coupled
# to an explicit runtime-facing helper boundary.
from lc_refresh import lc_bind_runtime as _lc_refresh_bind_runtime

_lc_refresh_bind_runtime(sys.modules[__name__])
