from lc_geometry import (
    lc_panel_content_rect,
    lc_panel_header_rect,
    lc_rect_split_horizontal,
    lc_rect_split_vertical,
)
from lc_window import lc_new, lc_panel_header_subwin, lc_panel_subwin, lc_wdraw_panel


def _line_text(win, y):
    return "".join(cell.ch for cell in win.lines[y].line)


def test_rect_split_vertical():
    top, bottom = lc_rect_split_vertical(2, 4, 10, 20, 3)
    assert top == (2, 4, 3, 20)
    assert bottom == (5, 4, 7, 20)


def test_rect_split_horizontal():
    left, right = lc_rect_split_horizontal(1, 2, 6, 12, 5)
    assert left == (1, 2, 6, 5)
    assert right == (1, 7, 6, 7)


def test_panel_header_and_content_rects_shift_content_down():
    assert lc_panel_header_rect(0, 0, 6, 10, 1) == (1, 1, 1, 8)
    assert lc_panel_content_rect(0, 0, 6, 10, 1) == (2, 1, 3, 8)


def test_panel_subwindows_follow_header_zoning():
    root = lc_new(10, 20, 0, 0)
    assert root is not None

    header = lc_panel_header_subwin(root, 1, 2, 6, 10, 1)
    content = lc_panel_subwin(root, 1, 2, 6, 10, 1)

    assert header is not None
    assert content is not None
    assert (header.begy, header.begx, header.maxy, header.maxx) == (2, 3, 1, 8)
    assert (content.begy, content.begx, content.maxy, content.maxx) == (3, 3, 3, 8)


def test_draw_panel_with_title_uses_header_band_for_fill_zoning():
    root = lc_new(8, 20, 0, 0)
    assert root is not None

    rc = lc_wdraw_panel(root, 1, 1, 6, 12, title="Title", header_height=1, fill=".")
    assert rc == 0
    assert _line_text(root, 2)[2:9] == " Title "
    assert _line_text(root, 2).count('.') == 0
    assert _line_text(root, 3)[2:10] == "........"
