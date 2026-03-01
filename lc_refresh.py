from typing import Optional

from lc_term import LC_ATTR_NONE, LC_DIRTY, LC_FORCEPAINT
from lc_window import LCCell, LCWin
from lc_screen import lc, lc_check_resize

LC_RENDER_BATCH_BYTES = 8192


def _hash_attr(h: int, attr: int) -> int:
    # Hash the full integer attribute value, not just the low byte.
    # This keeps row-hash change detection correct if the attribute
    # model grows beyond 8 bits.
    v = int(attr) & 0xFFFFFFFF
    for shift in (0, 8, 16, 24):
        h ^= (v >> shift) & 0xFF
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _can_use_row_hash_shortcut(win: LCWin, abs_y: int) -> bool:
    # The row-hash cache is keyed by physical screen row.
    # Only use the row-hash shortcut when the window row maps to the full
    # visible physical row domain represented by lc.hashes[abs_y].
    if abs_y < 0 or abs_y >= lc.lines:
        return False
    if win.parent is not None:
        return False
    if win.begx != 0:
        return False
    return win.maxx == lc.cols


def line_hash(cells: list[LCCell]) -> int:
    # FNV-1a over rendered cell content and attr.
    h = 2166136261
    for cell in cells:
        data = cell.ch.encode('utf-8', 'replace')
        for b in data:
            h ^= b
            h = (h * 16777619) & 0xFFFFFFFF

        h = _hash_attr(h, cell.attr)
    return h


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
        lc.cur_attr = attr
        lc.term.note_attr(attr)

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


def lc_wrefresh(win: Optional[LCWin]) -> int:
    if win is None or not win.alive:
        return -1

    requested_win = win
    rc = lc_check_resize()
    if rc < 0:
        return -1
    if rc == 1:
        # A root resize invalidates all derived windows. Do not silently
        # replace an explicitly requested derived window with stdscr.
        #
        # After a rebuild:
        #   - dead windows must fail refresh
        #   - derived windows from the old topology must fail refresh
        #   - only a root refresh may fall through to the rebuilt stdscr
        if not requested_win.alive:
            return -1
        if requested_win.parent is not None:
            return -1
        win = lc.stdscr

    if win is None or not win.alive:
        return -1
    out = bytearray()

    if len(lc.screen) != lc.lines or (lc.lines > 0 and len(lc.screen[0]) != lc.cols):
        lc.screen = [[LCCell(' ', LC_ATTR_NONE) for _x in range(lc.cols)] for _y in range(lc.lines)]
        lc.hashes = [0 for _ in range(lc.lines)]
        lc.term.clear_screen()
        lc.cur_y = 0
        lc.cur_x = 0
        lc.term.reset_state()
        lc.cur_attr = LC_ATTR_NONE

    for y in range(win.maxy):
        abs_y = win.begy + y
        if abs_y >= lc.lines:
            continue

        ln = win.lines[y]
        if not (ln.flags & LC_DIRTY):
            continue

        h = line_hash(ln.line)
        if _can_use_row_hash_shortcut(win, abs_y):
            if h == lc.hashes[abs_y] and not (ln.flags & LC_FORCEPAINT):
                ln.firstch = 0
                ln.lastch = 0
                ln.flags = 0
                continue

            lc.hashes[abs_y] = h
        start_x = max(0, ln.firstch)
        end_x = min(win.maxx, ln.lastch + 1)
        run_start_x = -1
        run_cells: list[LCCell] = []

        for x in range(start_x, end_x):
            abs_x = win.begx + x
            if abs_x >= lc.cols:
                _flush_cell_run(out, abs_y, run_start_x, run_cells)
                run_start_x = -1
                run_cells = []
                continue

            cell = ln.line[x]
            scr = lc.screen[abs_y][abs_x]
            if scr.ch == cell.ch and scr.attr == cell.attr:
                _flush_cell_run(out, abs_y, run_start_x, run_cells)
                run_start_x = -1
                run_cells = []
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

            lc.screen[abs_y][abs_x] = LCCell(cell.ch, cell.attr)

        _flush_cell_run(out, abs_y, run_start_x, run_cells)

        # Keep output writes bounded even when many rows changed.
        # This is a throughput/simplicity compromise, not a semantic boundary.
        if len(out) >= LC_RENDER_BATCH_BYTES:
            _flush(out)

        ln.firstch = 0
        ln.lastch = 0
        ln.flags = 0

    final_y = win.begy + win.cury
    final_x = win.begx + win.curx
    if final_y < lc.lines and final_x < lc.cols:
        _append_move(out, final_y, final_x)
        lc.cur_y = final_y
        lc.cur_x = final_x

    if lc.cur_attr != LC_ATTR_NONE:
        _append_attr(out, LC_ATTR_NONE)
        lc.term.note_attr(LC_ATTR_NONE)
    lc.cur_attr = LC_ATTR_NONE

    _flush(out)
    return 0
