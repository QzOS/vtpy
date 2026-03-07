from typing import Optional

from lc_term import LC_ATTR_NONE, LC_DIRTY, LC_FORCEPAINT
from lc_window import LCCell, LCRow, LCWin
from lc_screen import lc, lc_check_resize

LC_RENDER_BATCH_BYTES = 8192


def _reinit_physical_cache() -> None:
    lc.screen = [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(lc.cols)]
        for _y in range(lc.lines)
    ]
    lc.term.clear_screen()
    lc.cur_y = 0
    lc.cur_x = 0
    lc.term.reset_state()
    lc.cur_attr = LC_ATTR_NONE


def _reinit_virtual_cache() -> None:
    lc.vscreen = [
        [LCCell(' ', LC_ATTR_NONE) for _x in range(lc.cols)]
        for _y in range(lc.lines)
    ]
    lc.vdirty_first = [-1 for _ in range(lc.lines)]
    lc.vdirty_last = [-1 for _ in range(lc.lines)]
    lc.virtual_cur_y = 0
    lc.virtual_cur_x = 0
    lc.virtual_cursor_valid = False


def _mark_full_virtual_dirty() -> None:
    if lc.lines <= 0 or lc.cols <= 0:
        return

    for abs_y in range(lc.lines):
        lc.vdirty_first[abs_y] = 0
        lc.vdirty_last[abs_y] = lc.cols - 1


def _ensure_virtual_cache_shape() -> None:
    if len(lc.vscreen) != lc.lines or (lc.lines > 0 and len(lc.vscreen[0]) != lc.cols):
        _reinit_virtual_cache()


def _dirty_span_for_row(win: LCWin, ln: LCRow, abs_y: int) -> tuple[int, int]:
    if abs_y < 0 or abs_y >= lc.lines:
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
    if abs_y < 0 or abs_y >= lc.lines:
        return
    if start_x >= end_x:
        return

    if lc.vdirty_first[abs_y] < 0:
        lc.vdirty_first[abs_y] = start_x
        lc.vdirty_last[abs_y] = end_x - 1
        return

    if start_x < lc.vdirty_first[abs_y]:
        lc.vdirty_first[abs_y] = start_x
    if (end_x - 1) > lc.vdirty_last[abs_y]:
        lc.vdirty_last[abs_y] = end_x - 1


def _clear_virtual_dirty(abs_y: int) -> None:
    if abs_y < 0 or abs_y >= lc.lines:
        return
    lc.vdirty_first[abs_y] = -1
    lc.vdirty_last[abs_y] = -1


def _sync_physical_cell(abs_y: int, abs_x: int, cell: LCCell) -> None:
    scr = lc.screen[abs_y][abs_x]
    scr.ch = cell.ch
    scr.attr = cell.attr


def _note_emitted_attr(attr: int) -> None:
    lc.cur_attr = attr
    lc.term.note_attr(attr)


def lc_refresh() -> int:
    return lc_wrefresh(lc.stdscr)


def _append_move(buf: bytearray, y: int, x: int) -> None:
    buf.extend(lc.term.move_bytes(y, x))


def _append_attr(buf: bytearray, attr: int) -> None:
    buf.extend(lc.term.attr_bytes(attr))


def _append_text(buf: bytearray, text: str) -> None:
    buf.extend(lc.term.encode_text(text))


def _flush(buf: bytearray) -> None:
    if not buf:
        return
    lc.term.write_bytes(buf)
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

    if lc.cur_y != abs_y or lc.cur_x != abs_x:
        _append_move(buf, abs_y, abs_x)
        lc.cur_y = abs_y
        lc.cur_x = abs_x

    if lc.cur_attr != attr:
        _append_attr(buf, attr)
        _note_emitted_attr(attr)

    _append_text(buf, text)
    lc.cur_y = abs_y
    lc.cur_x = abs_x + len(text)


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
    if win is None or not win.alive:
        return -1, None

    # Refresh uses a global physical-screen cache.
    # Root refresh is the fully coherent presentation path for the current
    # shared-backing model. Derived-window refresh is limited to dirty state
    # tracked on that derived view.
    requested_win = win
    requested_is_root = requested_win.parent is None

    rc = lc_check_resize()
    if rc < 0:
        return -1, None
    if rc == 1:
        # A root resize invalidates all derived windows. Do not silently
        # replace an explicitly requested derived window with stdscr.
        #
        # After a rebuild:
        #   - derived windows from the old topology must fail refresh
        #   - an explicit refresh of the old root may fall through to rebuilt stdscr
        if not requested_is_root:
            return -1, None
        win = lc.stdscr

    if win is None or not win.alive:
        return -1, None

    return 0, win


def lc_wnoutrefresh(win: Optional[LCWin]) -> int:
    # Stage the dirty visible portion of a window into the global desired
    # screen. This does not write terminal output. Later staged windows may
    # overwrite earlier desired content in overlapping regions.
    rc, win = _resolve_refresh_window(win)
    if rc != 0 or win is None:
        return -1

    if len(lc.vscreen) != lc.lines or (lc.lines > 0 and len(lc.vscreen[0]) != lc.cols):
        _reinit_virtual_cache()

    for y in range(win.maxy):
        abs_y = win.begy + y
        if abs_y < 0 or abs_y >= lc.lines:
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
            if abs_x < 0 or abs_x >= lc.cols:
                continue

            src = ln.line[x]
            dst = lc.vscreen[abs_y][abs_x]
            if dst.ch != src.ch or dst.attr != src.attr:
                dst.ch = src.ch
                dst.attr = src.attr
                row_changed = True

        if row_changed:
            clipped_start = max(0, win.begx + start_x)
            clipped_end = min(lc.cols, win.begx + end_x)
            if clipped_start < clipped_end:
                _mark_virtual_dirty(abs_y, clipped_start, clipped_end)

        _clear_row_dirty(ln)

    final_y = win.begy + win.cury
    final_x = win.begx + win.curx
    if 0 <= final_y < lc.lines and 0 <= final_x < lc.cols:
        lc.virtual_cur_y = final_y
        lc.virtual_cur_x = final_x
        lc.virtual_cursor_valid = True
    else:
        lc.virtual_cursor_valid = False

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
    if len(lc.screen) != lc.lines or (lc.lines > 0 and len(lc.screen[0]) != lc.cols):
        _reinit_physical_cache()
        physical_reinit = True

    _ensure_virtual_cache_shape()

    # If the physical cache was reinitialized, the terminal was logically
    # cleared. The full desired screen must therefore be considered dirty.
    if physical_reinit:
        _mark_full_virtual_dirty()

    out = bytearray()

    for abs_y in range(lc.lines):
        first = lc.vdirty_first[abs_y]
        last = lc.vdirty_last[abs_y]
        if first < 0 or last < first:
            continue

        start_x = first
        end_x = last + 1
        run_start_x = -1
        run_cells: list[LCCell] = []

        for abs_x in range(start_x, end_x):
            cell = lc.vscreen[abs_y][abs_x]
            scr = lc.screen[abs_y][abs_x]
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

    if lc.virtual_cursor_valid:
        final_y = lc.virtual_cur_y
        final_x = lc.virtual_cur_x
        if final_y < lc.lines and final_x < lc.cols:
            _append_move(out, final_y, final_x)
            lc.cur_y = final_y
            lc.cur_x = final_x

    if lc.cur_attr != LC_ATTR_NONE:
        _append_attr(out, LC_ATTR_NONE)
        _note_emitted_attr(LC_ATTR_NONE)

    _flush(out)
    return 0


def lc_wrefresh(win: Optional[LCWin]) -> int:
    rc = lc_wnoutrefresh(win)
    if rc != 0:
        return rc
    return lc_doupdate()
