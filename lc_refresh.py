from typing import Optional

from lc_term import LC_ATTR_NONE, LC_DIRTY, LC_FORCEPAINT
from lc_window import LCCell, LCRow, LCWin

LC_RENDER_BATCH_BYTES = 8192

_runtime = None


def lc_bind_runtime(runtime_module) -> None:
    global _runtime
    _runtime = runtime_module


def _get_runtime():
    if _runtime is None:
        raise RuntimeError("lc_refresh runtime is not bound")
    return _runtime


def _lc():
    return _get_runtime().lc


def _refresh_cache_has_shape(cache: list[list[LCCell]], rows: int, cols: int) -> bool:
    return _get_runtime().lc_refresh_cache_has_shape(cache, rows, cols)


def _refresh_ensure_virtual_cache_shape() -> None:
    _get_runtime().lc_refresh_ensure_virtual_cache_shape()


def _refresh_mark_full_virtual_dirty() -> None:
    _get_runtime().lc_refresh_mark_full_virtual_dirty()


def _refresh_physical_cache_valid() -> bool:
    return _get_runtime().lc_refresh_physical_cache_valid()


def _refresh_reinit_physical_cache() -> None:
    _get_runtime().lc_refresh_reinit_physical_cache()


def _refresh_resize_gate() -> int:
    return _get_runtime().lc_refresh_resize_gate()


def _refresh_session_ready() -> bool:
    return _get_runtime().lc_refresh_session_ready()


def _refresh_target_after_resize(requested: Optional[LCWin], resize_rc: int) -> Optional[LCWin]:
    return _get_runtime().lc_refresh_target_after_resize(requested, resize_rc)


def lc_check_resize() -> int:
    return _refresh_resize_gate()


def _dirty_span_for_row(win: LCWin, ln: LCRow, abs_y: int) -> tuple[int, int]:
    if abs_y < 0 or abs_y >= _lc().lines:
        return 0, 0
    if not (ln.flags & LC_DIRTY):
        return 0, 0

    start_x = max(0, int(ln.firstch))
    end_x = min(win.maxx, int(ln.lastch) + 1)

    if start_x >= end_x:
        return 0, 0

    return start_x, end_x


def _clear_row_dirty(ln: LCRow) -> None:
    ln.firstch = 0
    ln.lastch = 0
    ln.flags = 0


def _mark_virtual_dirty(abs_y: int, start_x: int, end_x: int) -> None:
    if abs_y < 0 or abs_y >= _lc().lines:
        return
    if start_x >= end_x:
        return

    if _lc().vdirty_first[abs_y] < 0:
        _lc().vdirty_first[abs_y] = start_x
        _lc().vdirty_last[abs_y] = end_x - 1
        return

    if start_x < _lc().vdirty_first[abs_y]:
        _lc().vdirty_first[abs_y] = start_x
    if (end_x - 1) > _lc().vdirty_last[abs_y]:
        _lc().vdirty_last[abs_y] = end_x - 1


def _clear_virtual_dirty(abs_y: int) -> None:
    if abs_y < 0 or abs_y >= _lc().lines:
        return
    _lc().vdirty_first[abs_y] = -1
    _lc().vdirty_last[abs_y] = -1


def _sync_physical_cell(abs_y: int, abs_x: int, cell: LCCell) -> None:
    scr = _lc().screen[abs_y][abs_x]
    scr.ch = cell.ch
    scr.attr = cell.attr


def _note_emitted_attr(attr: int) -> None:
    _lc().cur_attr = attr
    _lc().term.note_attr(attr)


def _append_move(buf: bytearray, y: int, x: int) -> None:
    buf.extend(_lc().term.move_bytes(y, x))


def _append_attr(buf: bytearray, attr: int) -> None:
    buf.extend(_lc().term.attr_bytes(attr))


def _append_text(buf: bytearray, text: str) -> None:
    buf.extend(_lc().term.encode_text(text))


def _flush(buf: bytearray) -> None:
    if not buf:
        return
    _lc().term.write_bytes(buf)
    buf.clear()


def _emit_run(
    buf: bytearray,
    abs_y: int,
    abs_x: int,
    text: str,
    attr: int,
) -> None:
    if not text:
        return

    if _lc().cur_y != abs_y or _lc().cur_x != abs_x:
        _append_move(buf, abs_y, abs_x)
        _lc().cur_y = abs_y
        _lc().cur_x = abs_x

    if _lc().cur_attr != attr:
        _append_attr(buf, attr)
        _note_emitted_attr(attr)

    _append_text(buf, text)
    _lc().cur_y = abs_y
    _lc().cur_x = abs_x + len(text)


def _flush_cell_run(
    buf: bytearray,
    abs_y: int,
    run_start_x: int,
    run_cells: list[LCCell],
) -> None:
    if not run_cells:
        return

    attr = run_cells[0].attr
    text = "".join(cell.ch for cell in run_cells)
    _emit_run(buf, abs_y, run_start_x, text, attr)


def _resolve_refresh_window(win: Optional[LCWin]) -> tuple[int, Optional[LCWin]]:
    if not _refresh_session_ready():
        return -1, None

    rc = lc_check_resize()
    if rc < 0:
        return -1, None

    resolved = _refresh_target_after_resize(win, rc)
    if resolved is None or not resolved.alive:
        return -1, None

    # Refresh uses global physical/desired screen caches owned by the runtime.
    # Root refresh remains the fully coherent path for the current shared-
    # backing model; derived-window refresh is still limited to dirty state
    # tracked on that derived view.
    return 0, resolved


def lc_wstage(win: Optional[LCWin]) -> int:
    # Stage the dirty visible portion of a window into the global desired
    # screen. This does not write terminal output. Later staged windows may
    # overwrite earlier desired content in overlapping regions.
    rc, win = _resolve_refresh_window(win)
    if rc != 0 or win is None:
        return -1

    if not _refresh_cache_has_shape(_lc().vscreen, _lc().lines, _lc().cols):
        _refresh_ensure_virtual_cache_shape()

    for y in range(win.maxy):
        abs_y = win.begy + y
        if abs_y < 0 or abs_y >= _lc().lines:
            continue

        ln = win.lines[y]
        if not (ln.flags & LC_DIRTY):
            continue

        start_x, end_x = _dirty_span_for_row(win, ln, abs_y)
        if start_x >= end_x:
            _clear_row_dirty(ln)
            continue

        row_changed = False

        for x in range(start_x, end_x):
            abs_x = win.begx + x
            if abs_x < 0 or abs_x >= _lc().cols:
                continue

            src = ln.line[x]
            dst = _lc().vscreen[abs_y][abs_x]
            if dst.ch != src.ch or dst.attr != src.attr:
                dst.ch = src.ch
                dst.attr = src.attr
                row_changed = True

        if row_changed:
            clipped_start = max(0, win.begx + start_x)
            clipped_end = min(_lc().cols, win.begx + end_x)
            if clipped_start < clipped_end:
                _mark_virtual_dirty(abs_y, clipped_start, clipped_end)

        _clear_row_dirty(ln)

    final_y = win.begy + win.cury
    final_x = win.begx + win.curx
    if 0 <= final_y < _lc().lines and 0 <= final_x < _lc().cols:
        _lc().virtual_cur_y = final_y
        _lc().virtual_cur_x = final_x
        _lc().virtual_cursor_valid = True
    else:
        _lc().virtual_cursor_valid = False

    return 0


def lc_doupdate() -> int:
    # Two-phase flush must not emit stale staged geometry across a resize
    # rebuild. If a rebuild occurred, stdscr has already been replaced and any
    # derived topology must be rebuilt and restaged by the application.
    rc = lc_check_resize()
    if rc < 0:
        return -1
    if rc == 1:
        return 0

    physical_reinit = False
    if not _refresh_physical_cache_valid():
        _refresh_reinit_physical_cache()
        physical_reinit = True

    _refresh_ensure_virtual_cache_shape()

    # If the physical cache was reinitialized, the terminal was logically
    # cleared. The full desired screen must therefore be considered dirty.
    if physical_reinit:
        _refresh_mark_full_virtual_dirty()

    out = bytearray()

    for abs_y in range(_lc().lines):
        first = _lc().vdirty_first[abs_y]
        last = _lc().vdirty_last[abs_y]
        if first < 0 or last < first:
            continue

        start_x = first
        end_x = last + 1
        run_start_x = -1
        run_cells: list[LCCell] = []

        for abs_x in range(start_x, end_x):
            cell = _lc().vscreen[abs_y][abs_x]
            scr = _lc().screen[abs_y][abs_x]
            if scr.ch == cell.ch and scr.attr == cell.attr:
                _flush_cell_run(out, abs_y, run_start_x, run_cells)
                run_start_x = -1
                run_cells.clear()
                continue

            if not run_cells:
                run_start_x = abs_x
                run_cells.append(cell)
            else:
                prev_abs_x = run_start_x + len(run_cells) - 1
                prev_attr = run_cells[-1].attr
                if abs_x == prev_abs_x + 1 and cell.attr == prev_attr:
                    run_cells.append(cell)
                else:
                    _flush_cell_run(out, abs_y, run_start_x, run_cells)
                    run_start_x = abs_x
                    run_cells = [cell]

            _sync_physical_cell(abs_y, abs_x, cell)

        _flush_cell_run(out, abs_y, run_start_x, run_cells)

        # Keep output writes bounded even when many rows changed.
        # This is a throughput/simplicity compromise, not a semantic boundary.
        if len(out) >= LC_RENDER_BATCH_BYTES:
            _flush(out)

        _clear_virtual_dirty(abs_y)

    if _lc().virtual_cursor_valid:
        final_y = _lc().virtual_cur_y
        final_x = _lc().virtual_cur_x
        if final_y < _lc().lines and final_x < _lc().cols:
            _append_move(out, final_y, final_x)
            _lc().cur_y = final_y
            _lc().cur_x = final_x

    if _lc().cur_attr != LC_ATTR_NONE:
        _append_attr(out, LC_ATTR_NONE)
        _note_emitted_attr(LC_ATTR_NONE)

    _flush(out)
    return 0


def lc_flush() -> int:
    return lc_doupdate()


def lc_wstageflush(win: Optional[LCWin]) -> int:
    rc = lc_wstage(win)
    if rc != 0:
        return rc
    return lc_flush()


def lc_refresh() -> int:
    return lc_wstageflush(_lc().stdscr)


def lc_wnoutrefresh(win: Optional[LCWin]) -> int:
    return lc_wstage(win)


def lc_wrefresh(win: Optional[LCWin]) -> int:
    return lc_wstageflush(win)
