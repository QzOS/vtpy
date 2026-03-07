from dataclasses import dataclass, field
from typing import Optional
from lc_term import LC_DIRTY, LC_FORCEPAINT, LC_ATTR_NONE


@dataclass
class LCCell:
    ch: str = ' '
    attr: int = LC_ATTR_NONE


@dataclass
class LCRow:
    line: list[LCCell]
    firstch: int = 0
    lastch: int = 0
    flags: int = LC_DIRTY | LC_FORCEPAINT


@dataclass
class LCWin:
    maxy: int
    maxx: int
    begy: int = 0
    begx: int = 0
    cury: int = 0
    curx: int = 0
    parent: Optional["LCWin"] = None
    root: Optional["LCWin"] = None
    pary: int = 0
    parx: int = 0
    alive: bool = True
    owns_storage: bool = True
    children: list["LCWin"] = field(default_factory=list)
    lines: list[LCRow] = field(default_factory=list)


def _is_live_window(win: Optional[LCWin]) -> bool:
    return win is not None and win.alive


def _require_live_window(win: Optional[LCWin]) -> int:
    if not _is_live_window(win):
        return -1
    return 0


def _coerce_draw_char(ch: Optional[str]) -> Optional[str]:
    if ch is None or not ch:
        return None
    return ch[0]


def _valid_window_coord(win: LCWin, y: int, x: int) -> bool:
    return 0 <= y < win.maxy and 0 <= x < win.maxx


def _has_storage_shape(win: LCWin) -> bool:
    return len(win.lines) == win.maxy and all(len(ln.line) == win.maxx for ln in win.lines)


def _root_consistent(win: LCWin) -> bool:
    if not win.alive:
        return False

    if win.root is None:
        return False

    if win.parent is None:
        return win.root is win

    return win.root is not None and win.root.alive


def _window_invariants_hold(win: Optional[LCWin]) -> bool:
    if win is None:
        return False
    if not win.alive:
        return False
    if win.maxy <= 0 or win.maxx <= 0:
        return False
    return _has_storage_shape(win) and _root_consistent(win)


def _cursor_write_prefix_len(win: LCWin, text_len: int) -> int:
    if text_len <= 0:
        return 0
    if not _cursor_writable(win):
        return 0

    remaining_cells = ((win.maxy - 1 - win.cury) * win.maxx) + (win.maxx - win.curx)
    if remaining_cells <= 0:
        return 0
    return min(text_len, remaining_cells)


def _waddstr_common(win: Optional[LCWin], s: str, attr: int) -> int:
    if s is None:
        return -1
    if _require_live_window(win) != 0:
        return -1
    if win.maxx <= 0 or win.maxy <= 0:
        return -1
    if not _cursor_writable(win):
        return -1
    if not s:
        return 0

    writable = _cursor_write_prefix_len(win, len(s))
    if writable <= 0:
        return 0

    off = 0
    while off < writable:
        row_space = win.maxx - win.curx
        chunk_len = min(writable - off, row_space)
        _store_hspan_text_unchecked(win, win.cury, win.curx, s[off:off + chunk_len], attr)
        _advance_cursor_after_span(win, chunk_len)
        off += chunk_len
    return 0


def _mark_row_dirty_span(win: LCWin, y: int, start: int, end: int) -> None:
    if not win.alive:
        return
    if y < 0 or y >= win.maxy:
        return
    mark_dirty(win.lines[y], start, end, win.maxx)


def _mark_window_dirty_rows(
    win: Optional[LCWin],
    y_start: int,
    y_end: int,
    start: int,
    end: int,
) -> None:
    if win is None or not win.alive:
        return
    if y_start >= y_end:
        return

    ys, ye = _clip_range(y_start, y_end - y_start, win.maxy)
    if ys >= ye:
        return

    for y in range(ys, ye):
        _mark_window_dirty(win, y, start, end)


def _clip_range(start: int, length: int, limit: int) -> tuple[int, int]:
    if length <= 0 or limit <= 0:
        return 0, 0

    end = start + length
    if end <= 0 or start >= limit:
        return 0, 0

    if start < 0:
        start = 0
    if end > limit:
        end = limit
    if start >= end:
        return 0, 0
    return start, end


def _clip_hspan(win: Optional[LCWin], y: int, x: int, width: int) -> tuple[Optional[LCRow], int, int]:
    if win is None:
        return None, 0, 0
    if y < 0 or y >= win.maxy:
        return None, 0, 0
    start, end = _clip_range(x, width, win.maxx)
    if start >= end:
        return None, 0, 0
    return win.lines[y], start, end


def _clip_vspan(win: Optional[LCWin], y: int, x: int, height: int) -> tuple[int, int]:
    if win is None:
        return 0, 0
    if x < 0 or x >= win.maxx:
        return 0, 0
    return _clip_range(y, height, win.maxy)


def _clip_rect(win: Optional[LCWin], y0: int, x0: int, y1: int, x1: int) -> tuple[int, int, int, int]:
    if win is None:
        return 0, 0, 0, 0
    if y0 >= y1 or x0 >= x1:
        return 0, 0, 0, 0

    ys, ye = _clip_range(y0, y1 - y0, win.maxy)
    xs, xe = _clip_range(x0, x1 - x0, win.maxx)
    if ys >= ye or xs >= xe:
        return 0, 0, 0, 0
    return ys, xs, ye, xe


def _normalize_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    if height <= 0 or width <= 0:
        return y, x, 0, 0
    return y, x, height, width


def _box_edges(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    top = y
    left = x
    bottom = y + height - 1
    right = x + width - 1
    return top, left, bottom, right


def _interior_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    y, x, height, width = _normalize_rect(y, x, height, width)
    if height <= 2 or width <= 2:
        return y + 1, x + 1, 0, 0
    return y + 1, x + 1, height - 2, width - 2


def _store_cell_unchecked(win: LCWin, y: int, x: int, ch: str, attr: int) -> None:
    # Preconditions:
    # - win is alive and win.lines is populated
    # - 0 <= y < win.maxy, 0 <= x < win.maxx
    # - ch is non-empty
    outch = _coerce_draw_char(ch)
    assert outch is not None
    win.lines[y].line[x].ch = outch
    win.lines[y].line[x].attr = attr
    _mark_window_dirty(win, y, x, x + 1)


def _store_hspan_char_unchecked(
    win: LCWin,
    y: int,
    start: int,
    end: int,
    ch: str,
    attr: int,
) -> None:
    # Preconditions:
    # - win is alive and win.lines is populated
    # - 0 <= y < win.maxy, 0 <= start < end <= win.maxx
    # - ch is non-empty
    outch = _coerce_draw_char(ch)
    assert outch is not None
    ln = win.lines[y]
    for x in range(start, end):
        ln.line[x].ch = outch
        ln.line[x].attr = attr
    _mark_window_dirty(win, y, start, end)


def _store_hspan_text_unchecked(win: LCWin, y: int, start: int, text: str, attr: int) -> None:
    # Preconditions:
    # - win is alive and win.lines is populated
    # - 0 <= y < win.maxy, 0 <= start, start + len(text) <= win.maxx
    # - text is non-empty
    # Dirty marking is intentionally amortized to one span for the whole write.
    end = start + len(text)
    ln = win.lines[y]
    for i, x in enumerate(range(start, end)):
        ln.line[x].ch = text[i]
        ln.line[x].attr = attr
    _mark_window_dirty(win, y, start, end)


def _write_hspan(
    win: Optional[LCWin],
    y: int,
    start: int,
    end: int,
    ch: str,
    attr: int,
) -> None:
    if not _is_live_window(win):
        return
    if y < 0 or y >= win.maxy:
        return
    if start < 0 or end > win.maxx or start >= end:
        return
    if not ch:
        return

    _store_hspan_char_unchecked(win, y, start, end, ch, attr)


def _write_hspan_text(win: Optional[LCWin], y: int, start: int, text: str, attr: int) -> None:
    if not _is_live_window(win) or text is None or not text:
        return
    end = start + len(text)
    if y < 0 or y >= win.maxy or start < 0 or end > win.maxx or start >= end:
        return
    _store_hspan_text_unchecked(win, y, start, text, attr)


def _write_text_clipped(
    win: Optional[LCWin],
    y: int,
    x: int,
    text: str,
    attr: int,
) -> int:
    if not _is_live_window(win):
        return -1
    if text is None:
        return -1
    if y < 0 or y >= win.maxy:
        return 0
    if not text:
        return 0

    ln, start, end = _clip_hspan(win, y, x, len(text))
    if ln is None or start >= end:
        return 0

    src_off = start - x
    _write_hspan_text(win, y, start, text[src_off:src_off + (end - start)], attr)
    return 0


def _mark_window_dirty(win: Optional[LCWin], y: int, start: int, end: int) -> None:
    # Propagate a dirty span upward through the parent chain.
    # Shared-backing windows keep independent dirty metadata, so every write
    # must mark the local row and then the parent-relative span in ancestors.
    cur = win
    cy = y
    cs = start
    ce = end

    while cur is not None:
        if not _window_invariants_hold(cur):
            return
        if cy < 0 or cy >= cur.maxy:
            return

        _mark_row_dirty_span(cur, cy, cs, ce)

        parent = cur.parent
        if parent is None:
            return

        cy += cur.pary
        cs += cur.parx
        ce += cur.parx
        cur = parent


def _set_cell(win: Optional[LCWin], y: int, x: int, ch: str, attr: int) -> None:
    # Internal single-cell write used by cursor-driven and drawing helpers.
    # Validates bounds and aliveness, then delegates to the unchecked writer.
    if not _is_live_window(win):
        return
    if not _valid_window_coord(win, y, x):
        return
    if _coerce_draw_char(ch) is None:
        return
    _store_cell_unchecked(win, y, x, ch, attr)


# _write_cell is an alias for _set_cell kept for call-site readability in box
# drawing, where using _set_cell directly would read ambiguously.
_write_cell = _set_cell


def _cursor_at_last_cell(win: LCWin) -> bool:
    if win.maxy <= 0 or win.maxx <= 0:
        return False
    return win.cury == (win.maxy - 1) and win.curx == (win.maxx - 1)


def _cursor_writable(win: LCWin) -> bool:
    if win.maxy <= 0 or win.maxx <= 0:
        return False
    if win.cury < 0 or win.cury >= win.maxy:
        return False
    if win.curx < 0 or win.curx >= win.maxx:
        return False
    return True


def _cursor_strictly_valid(win: Optional[LCWin]) -> bool:
    if win is None:
        return False
    if not win.alive:
        return False
    return _cursor_writable(win)


def _advance_cursor(win: LCWin) -> None:
    # Saturating cursor policy:
    # once the cursor reaches the final writable cell, it stays there.
    # The window layer does not expose an out-of-range end-of-window state
    # through cury/curx.
    if win.maxy <= 0 or win.maxx <= 0:
        return
    if _cursor_at_last_cell(win):
        return
    win.curx += 1
    if win.curx >= win.maxx:
        win.curx = 0
        win.cury += 1


def _advance_cursor_after_span(win: LCWin, span_len: int) -> None:
    # Preconditions:
    # - cursor is currently writable
    # - span_len >= 0
    # - span_len does not advance beyond the final writable cell
    if span_len <= 0:
        return

    remaining = span_len
    while remaining > 0 and not _cursor_at_last_cell(win):
        row_space = win.maxx - win.curx
        step = min(remaining, row_space)
        remaining -= step
        win.curx += step
        if win.curx >= win.maxx:
            if win.cury >= (win.maxy - 1):
                win.curx = win.maxx - 1
            else:
                win.curx = 0
                win.cury += 1


def _box_title_span(
    y: int,
    x: int,
    height: int,
    width: int,
    title: str,
) -> tuple[int, int, str]:
    top, left, _bottom, right = _box_edges(y, x, height, width)
    if title is None:
        title = ""

    label = f" {title} "
    inner_left = left + 1
    inner_right = right - 1
    if inner_left > inner_right:
        return top, inner_left, ""

    usable = inner_right - inner_left + 1
    if usable <= 0:
        return top, inner_left, ""
    return top, inner_left, label[:usable]


def mark_dirty(ln: Optional[LCRow], start: int, end: int, maxx: int) -> None:
    if ln is None or start >= maxx:
        return
    if end > maxx:
        end = maxx
    if start < 0:
        start = 0
    if end == 0 or start >= end:
        return

    first = start
    last = end - 1

    if ln.flags & LC_DIRTY:
        if first < ln.firstch:
            ln.firstch = first
        if last > ln.lastch:
            ln.lastch = last
    else:
        ln.firstch = first
        ln.lastch = last
        ln.flags |= LC_DIRTY

    ln.flags |= LC_FORCEPAINT


def lc_new(nlines: int, ncols: int, begin_y: int, begin_x: int) -> Optional[LCWin]:
    if nlines <= 0 or ncols <= 0:
        return None
    if begin_y < 0 or begin_x < 0:
        return None

    lines: list[LCRow] = []
    for _y in range(nlines):
        row_cells = [LCCell(' ', LC_ATTR_NONE) for _x in range(ncols)]
        row = LCRow(line=row_cells, firstch=0, lastch=ncols - 1,
                    flags=LC_DIRTY | LC_FORCEPAINT)
        lines.append(row)

    win = LCWin(
        maxy=nlines,
        maxx=ncols,
        begy=begin_y,
        begx=begin_x,
        cury=0,
        curx=0,
        parent=None,
        root=None,
        pary=0,
        parx=0,
        alive=True,
        owns_storage=True,
        children=[],
        lines=lines
    )
    win.root = win
    if not _window_invariants_hold(win):
        return None
    return win


def lc_subwin(
    parent: Optional[LCWin],
    nlines: int,
    ncols: int,
    begin_y: int,
    begin_x: int,
) -> Optional[LCWin]:
    if not _window_invariants_hold(parent):
        return None
    if nlines <= 0 or ncols <= 0:
        return None
    if begin_y < 0 or begin_x < 0:
        return None
    if begin_y >= parent.maxy or begin_x >= parent.maxx:
        return None
    if begin_y + nlines > parent.maxy:
        return None
    if begin_x + ncols > parent.maxx:
        return None

    lines: list[LCRow] = []
    for y in range(nlines):
        parent_ln = parent.lines[begin_y + y]
        shared_cells = parent_ln.line[begin_x:begin_x + ncols]
        row = LCRow(
            line=shared_cells,
            firstch=0,
            lastch=ncols - 1,
            flags=LC_DIRTY | LC_FORCEPAINT,
        )
        lines.append(row)

    root = parent.root
    sub = LCWin(
        maxy=nlines,
        maxx=ncols,
        begy=parent.begy + begin_y,
        begx=parent.begx + begin_x,
        cury=0,
        curx=0,
        parent=parent,
        root=root,
        pary=begin_y,
        parx=begin_x,
        alive=True,
        owns_storage=False,
        children=[],
        lines=lines,
    )
    if not _window_invariants_hold(sub):
        return None
    parent.children.append(sub)
    return sub


def lc_panel_subwin(
    parent: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
) -> Optional[LCWin]:
    if not _window_invariants_hold(parent):
        return None

    y, x, height, width = _normalize_rect(y, x, height, width)
    if height <= 0 or width <= 0:
        return None

    inner_y, inner_x, inner_h, inner_w = _interior_rect(y, x, height, width)
    if inner_h <= 0 or inner_w <= 0:
        return None

    return lc_subwin(parent, inner_h, inner_w, inner_y, inner_x)


def lc_panel_content_rect(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    return _interior_rect(y, x, height, width)


def _detach_from_parent(win: LCWin) -> None:
    parent = win.parent
    if parent is not None and not parent.alive:
        parent = None
    if parent is None:
        return
    if win in parent.children:
        parent.children.remove(win)
    win.parent = None


def _free_recursive(win: LCWin) -> None:
    if not win.alive:
        return

    while win.children:
        child = win.children[-1]
        _free_recursive(child)

    _detach_from_parent(win)
    win.lines.clear()
    win.children.clear()
    win.alive = False
    win.root = None
    win.owns_storage = False
    win.pary = 0
    win.parx = 0
    win.cury = 0
    win.curx = 0


def lc_invalidate_children(win: Optional[LCWin]) -> None:
    if not _is_live_window(win):
        return

    while win.children:
        child = win.children[-1]
        _free_recursive(child)


def lc_free(win: Optional[LCWin]) -> int:
    if not _is_live_window(win):
        return -1
    _free_recursive(win)
    return 0


def lc_wtouchline(win: Optional[LCWin], y: int, n: int = 1) -> int:
    # Mark one or more rows dirty/forcepaint without mutating cell content.
    # Dirty spans propagate up the parent chain so root refresh remains
    # coherent for shared-backing subwindows.
    if not _is_live_window(win):
        return -1
    if n <= 0:
        return 0

    _mark_window_dirty_rows(win, y, y + n, 0, win.maxx)
    return 0


def lc_wtouchwin(win: Optional[LCWin]) -> int:
    # Mark the full window dirty/forcepaint without changing any cells.
    if not _is_live_window(win):
        return -1

    _mark_window_dirty_rows(win, 0, win.maxy, 0, win.maxx)
    return 0


def _copy_row_span_values(
    win: LCWin,
    dst_y: int,
    src_y: int,
    start: int,
    end: int,
) -> None:
    # Copy cell values only.
    # Do not replace row objects or row line lists; shared-backing subwindows
    # rely on stable aliasing of the underlying cell objects.
    if dst_y == src_y or start >= end:
        return

    dst_ln = win.lines[dst_y]
    src_ln = win.lines[src_y]

    for x in range(start, end):
        dst_ln.line[x].ch = src_ln.line[x].ch
        dst_ln.line[x].attr = src_ln.line[x].attr


def _blank_row_span(
    win: LCWin,
    y: int,
    start: int,
    end: int,
    attr: int = LC_ATTR_NONE,
) -> None:
    if start >= end:
        return

    ln = win.lines[y]
    for x in range(start, end):
        ln.line[x].ch = ' '
        ln.line[x].attr = attr


def _shift_rows_in_window(
    win: Optional[LCWin],
    top: int,
    bottom: int,
    n: int,
    fill_attr: int = LC_ATTR_NONE,
) -> int:
    # Shift row content within [top, bottom) across the full local width.
    #
    # Sign convention:
    #   n > 0: move content down by n rows, blank newly exposed rows at top
    #   n < 0: move content up by -n rows, blank newly exposed rows at bottom
    #
    # This is content movement, not row-structure movement. LCRow objects and
    # row line lists remain stable so shared-backing subwindows preserve their
    # aliasing model.
    if _require_live_window(win) != 0:
        return -1
    if top < 0 or bottom < 0 or top > bottom:
        return -1
    if top >= win.maxy:
        return 0
    if bottom > win.maxy:
        bottom = win.maxy
    if top >= bottom:
        return 0
    if n == 0:
        return 0

    span_h = bottom - top
    width = win.maxx
    if width <= 0:
        return 0

    if n >= span_h or n <= -span_h:
        for y in range(top, bottom):
            _blank_row_span(win, y, 0, width, fill_attr)
        _mark_window_dirty_rows(win, top, bottom, 0, width)
        return 0

    if n > 0:
        # Move downward. Copy bottom-up for overlap safety.
        for dst_y in range(bottom - 1, top + n - 1, -1):
            src_y = dst_y - n
            _copy_row_span_values(win, dst_y, src_y, 0, width)
        for y in range(top, top + n):
            _blank_row_span(win, y, 0, width, fill_attr)
    else:
        count = -n
        # Move upward. Copy top-down for overlap safety.
        for dst_y in range(top, bottom - count):
            src_y = dst_y + count
            _copy_row_span_values(win, dst_y, src_y, 0, width)
        for y in range(bottom - count, bottom):
            _blank_row_span(win, y, 0, width, fill_attr)

    _mark_window_dirty_rows(win, top, bottom, 0, width)
    return 0


# ---------------------------------------------------------------------------
# Clipped drawing/fill family
#
# These helpers operate on clipped geometry. They do NOT use or advance the
# cursor. They are the correct family for drawing borders, lines, and fills
# at explicit coordinates.
# ---------------------------------------------------------------------------

def fill_rect(
    win: Optional[LCWin],
    y0: int,
    x0: int,
    y1: int,
    x1: int,
    ch: str,
    attr: int = LC_ATTR_NONE,
) -> None:
    if not _is_live_window(win):
        return
    if not ch:
        return

    ys, xs, ye, xe = _clip_rect(win, y0, x0, y1, x1)
    if ys >= ye or xs >= xe:
        return

    for y in range(ys, ye):
        _write_hspan(win, y, xs, xe, ch, attr)


def lc_wclear(win: Optional[LCWin]) -> int:
    if not _is_live_window(win):
        return -1
    fill_rect(win, 0, 0, win.maxy, win.maxx, ' ', LC_ATTR_NONE)
    win.cury = 0
    win.curx = 0
    return 0


def lc_wclrtobot(win: Optional[LCWin]) -> int:
    if not _cursor_strictly_valid(win):
        return -1

    y = win.cury
    x = win.curx
    fill_rect(win, y, x, y + 1, win.maxx, ' ', LC_ATTR_NONE)
    if y + 1 < win.maxy:
        fill_rect(win, y + 1, 0, win.maxy, win.maxx, ' ', LC_ATTR_NONE)
    return 0


def lc_wclrtoeol(win: Optional[LCWin]) -> int:
    if not _cursor_strictly_valid(win):
        return -1
    fill_rect(win, win.cury, win.curx, win.cury + 1, win.maxx, ' ', LC_ATTR_NONE)
    return 0


def lc_wfill(
    win: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    ch: str = ' ',
    attr: int = LC_ATTR_NONE,
) -> int:
    outch = _coerce_draw_char(ch)
    if _require_live_window(win) != 0:
        return -1
    if outch is None:
        return -1
    if height <= 0 or width <= 0:
        return 0
    fill_rect(win, y, x, y + height, x + width, outch, attr)
    return 0


def lc_winsdelln(win: Optional[LCWin], n: int) -> int:
    # Insert/delete lines relative to the current cursor row.
    # n > 0 inserts blank lines at cury, shifting existing content down.
    # n < 0 deletes lines at cury, shifting lower content up.
    if _require_live_window(win) != 0:
        return -1
    if not _cursor_writable(win):
        return -1
    if n == 0:
        return 0

    return _shift_rows_in_window(win, win.cury, win.maxy, n, LC_ATTR_NONE)


def lc_wscrl(win: Optional[LCWin], n: int) -> int:
    # Scroll the full window.
    # Positive n scrolls content up; negative n scrolls content down.
    if _require_live_window(win) != 0:
        return -1
    if n == 0:
        return 0

    return _shift_rows_in_window(win, 0, win.maxy, -n, LC_ATTR_NONE)


# ---------------------------------------------------------------------------
# Cursor-driven write family
#
# These helpers write at the current cursor position and advance the cursor
# after each character. The cursor saturates at the last valid cell rather
# than wrapping or raising an error. Use lc_wmove to reposition before writing.
#
# Completion semantics:
# - These operations are not atomic all-or-nothing writes.
# - A single-cell write at the final writable cell succeeds and leaves the
#   cursor at that same cell.
# - A bulk write stores the longest visible prefix permitted by the current
#   cursor position and window bounds under the saturating cursor policy.
# - If the bulk write reaches the final writable cell, that cell is written,
#   the cursor remains there, and the function returns success.
# - The API does not expose a public end-of-window sentinel cursor state, so
#   any remaining suffix beyond that point is intentionally not written.
# - Invalid window or invalid current cursor state still returns -1.
# ---------------------------------------------------------------------------

def lc_waddstr_attr(win: Optional[LCWin], s: str, attr: int) -> int:
    # Attributed variant of lc_waddstr() with the same saturating cursor
    # semantics. The full string is not guaranteed to be written; the visible
    # prefix is stored and the final writable cell, if reached, is written and
    # the cursor saturates there.
    return _waddstr_common(win, s, attr)


def lc_waddstr(win: Optional[LCWin], s: str) -> int:
    return _waddstr_common(win, s, LC_ATTR_NONE)


def lc_wmove(win: Optional[LCWin], y: int, x: int) -> int:
    if _require_live_window(win) != 0:
        return -1
    if not _valid_window_coord(win, y, x):
        return -1
    win.cury = y
    win.curx = x
    return 0


def lc_wput(win: Optional[LCWin], ch: int, attr: int = LC_ATTR_NONE) -> int:
    if _require_live_window(win) != 0:
        return -1
    if not _cursor_writable(win):
        return -1

    try:
        outch = chr(ch)
    except (TypeError, ValueError):
        return -1

    # Single-cell success at the final writable cell is intentional.
    # The cursor model saturates there rather than advancing to a sentinel
    # end-of-window position.
    _set_cell(win, win.cury, win.curx, outch, attr)
    if not _cursor_at_last_cell(win):
        _advance_cursor(win)
    return 0


def lc_mvwaddstr(win: Optional[LCWin], y: int, x: int, s: str) -> int:
    if lc_wmove(win, y, x) != 0:
        return -1
    return lc_waddstr(win, s)


def lc_wdraw_hline(
    win: Optional[LCWin],
    y: int,
    x: int,
    width: int,
    ch: str = "-",
    attr: int = LC_ATTR_NONE,
) -> int:
    outch = _coerce_draw_char(ch)
    if _require_live_window(win) != 0:
        return -1
    if outch is None:
        return -1
    if width <= 0:
        return 0

    ln, start, end = _clip_hspan(win, y, x, width)
    if ln is None or start >= end:
        return 0

    _write_hspan(win, y, start, end, outch, attr)
    return 0


def lc_wdraw_vline(
    win: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    ch: str = "|",
    attr: int = LC_ATTR_NONE,
) -> int:
    outch = _coerce_draw_char(ch)
    if _require_live_window(win) != 0:
        return -1
    if outch is None:
        return -1
    if height <= 0:
        return 0

    start, end = _clip_vspan(win, y, x, height)
    if start >= end:
        return 0

    for cy in range(start, end):
        _store_cell_unchecked(win, cy, x, outch, attr)
    return 0


def lc_wdraw_box(
    win: Optional[LCWin],
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
    hch = _coerce_draw_char(hch)
    vch = _coerce_draw_char(vch)
    tl = _coerce_draw_char(tl)
    tr = _coerce_draw_char(tr)
    bl = _coerce_draw_char(bl)
    br = _coerce_draw_char(br)

    if _require_live_window(win) != 0:
        return -1

    y, x, height, width = _normalize_rect(y, x, height, width)
    if hch is None or vch is None or tl is None or tr is None or bl is None or br is None:
        return -1
    if height <= 0 or width <= 0:
        return 0

    if height == 1:
        return lc_wdraw_hline(win, y, x, width, hch, attr)

    if width == 1:
        return lc_wdraw_vline(win, y, x, height, vch, attr)

    top, left, bottom, right = _box_edges(y, x, height, width)
    inner_y, inner_x, inner_h, inner_w = _interior_rect(y, x, height, width)

    rc = lc_wdraw_hline(win, top, left + 1, width - 2, hch, attr)
    if rc != 0:
        return rc
    rc = lc_wdraw_hline(win, bottom, left + 1, width - 2, hch, attr)
    if rc != 0:
        return rc

    if inner_h > 0:
        rc = lc_wdraw_vline(win, inner_y, left, inner_h, vch, attr)
        if rc != 0:
            return rc
        rc = lc_wdraw_vline(win, inner_y, right, inner_h, vch, attr)
        if rc != 0:
            return rc

    _write_cell(win, top, left, tl, attr)
    _write_cell(win, top, right, tr, attr)
    _write_cell(win, bottom, left, bl, attr)
    _write_cell(win, bottom, right, br, attr)

    return 0


def lc_wdraw_box_title(
    win: Optional[LCWin],
    y: int,
    x: int,
    height: int,
    width: int,
    title: str,
    attr: int = LC_ATTR_NONE,
) -> int:
    if _require_live_window(win) != 0:
        return -1

    y, x, height, width = _normalize_rect(y, x, height, width)
    if height <= 0 or width <= 0:
        return 0
    if title is None:
        return -1
    if height < 1 or width < 1:
        return 0

    title_y, title_x, label = _box_title_span(y, x, height, width, title)
    if not label:
        return 0

    return _write_text_clipped(win, title_y, title_x, label, attr)


def lc_wdraw_panel(
    win: Optional[LCWin],
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
    if _require_live_window(win) != 0:
        return -1

    rc = lc_wdraw_box(win, y, x, height, width, frame_attr, hch, vch, tl, tr, bl, br)
    if rc != 0:
        return rc

    if title is not None and title != "":
        rc = lc_wdraw_box_title(win, y, x, height, width, title, frame_attr)
        if rc != 0:
            return rc

    if fill is not None:
        inner_y, inner_x, inner_h, inner_w = _interior_rect(y, x, height, width)
        if inner_h > 0 and inner_w > 0:
            rc = lc_wfill(win, inner_y, inner_x, inner_h, inner_w, fill, fill_attr)
            if rc != 0:
                return rc

    return 0
