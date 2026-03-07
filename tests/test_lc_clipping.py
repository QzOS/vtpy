from lc_term import LC_ATTR_NONE
from lc_window import (
    _box_edges,
    _clip_rect_shape,
    _fill_rect_extents_clipped,
    _box_title_span,
    _interior_rect_shape,
    _normalize_rect_shape,
    _rect_shape_to_extents,
    lc_new,
    lc_waddstr,
    lc_wdraw_box,
    lc_wdraw_box_title,
    lc_wdraw_hline,
    lc_wdraw_panel,
    lc_wdraw_vline,
    lc_wfill,
    lc_wmove,
)


def _row_text(win, y: int) -> str:
    return "".join(cell.ch for cell in win.lines[y].line)


def test_fill_rect_clips_negative_and_right_edge():
    win = lc_new(3, 5, 0, 0)
    _fill_rect_extents_clipped(win, 0, -2, 2, 10, "x")

    assert _row_text(win, 0) == "xxxxx"
    assert _row_text(win, 1) == "xxxxx"
    assert _row_text(win, 2) == "     "


def test_fill_rect_clips_top_and_bottom():
    win = lc_new(4, 4, 0, 0)
    _fill_rect_extents_clipped(win, -3, 1, 10, 3, "z")

    assert _row_text(win, 0) == " zz "
    assert _row_text(win, 1) == " zz "
    assert _row_text(win, 2) == " zz "
    assert _row_text(win, 3) == " zz "


def test_fill_rect_preserves_requested_attr():
    win = lc_new(2, 4, 0, 0)
    _fill_rect_extents_clipped(win, 0, 1, 2, 3, "q", 7)

    assert win.lines[0].line[0].ch == " "
    assert win.lines[0].line[1].ch == "q"
    assert win.lines[0].line[2].ch == "q"
    assert win.lines[1].line[1].ch == "q"
    assert win.lines[1].line[2].ch == "q"

    assert win.lines[0].line[1].attr == 7
    assert win.lines[0].line[2].attr == 7
    assert win.lines[1].line[1].attr == 7
    assert win.lines[1].line[2].attr == 7


def test_wfill_clips_and_sets_attr():
    win = lc_new(3, 5, 0, 0)
    assert lc_wfill(win, -1, 2, 3, 4, ".", 9) == 0
    assert _row_text(win, 0) == "  ..."
    assert _row_text(win, 1) == "  ..."
    assert win.lines[0].line[2].attr == 9
    assert win.lines[1].line[4].attr == 9


def test_waddstr_clips_when_reaching_window_end():
    win = lc_new(2, 3, 0, 0)
    assert lc_wmove(win, 1, 1) == 0
    assert lc_waddstr(win, "abcd") == 0

    assert _row_text(win, 0) == "   "
    assert _row_text(win, 1) == " ab"
    # Saturating cursor policy: cursor stays at last cell
    assert win.cury == 1
    assert win.curx == 2


def test_waddstr_returns_error_for_invalid_cursor():
    win = lc_new(2, 2, 0, 0)
    win.cury = 3
    win.curx = 0
    assert lc_waddstr(win, "x") == -1


def test_waddstr_fills_exactly_to_end():
    """Test writing exactly enough chars to fill to the last cell."""
    win = lc_new(2, 3, 0, 0)
    assert lc_wmove(win, 1, 0) == 0
    assert lc_waddstr(win, "abc") == 0

    assert _row_text(win, 0) == "   "
    assert _row_text(win, 1) == "abc"
    # Saturating cursor policy: cursor stays at last cell (1, 2)
    assert win.cury == 1
    assert win.curx == 2


def test_hline_clips_left_edge():
    win = lc_new(3, 5, 0, 0)
    assert lc_wdraw_hline(win, 1, -2, 5, "-", LC_ATTR_NONE) == 0
    assert _row_text(win, 1) == "---  "


def test_hline_fully_outside_is_noop_success():
    win = lc_new(3, 5, 0, 0)
    assert lc_wdraw_hline(win, 1, 10, 4, "-", LC_ATTR_NONE) == 0
    assert _row_text(win, 1) == "     "


def test_vline_clips_top_edge():
    win = lc_new(5, 4, 0, 0)
    assert lc_wdraw_vline(win, -2, 1, 5, "|", LC_ATTR_NONE) == 0
    assert _row_text(win, 0) == " |  "
    assert _row_text(win, 1) == " |  "
    assert _row_text(win, 2) == " |  "
    assert _row_text(win, 3) == "    "
    assert _row_text(win, 4) == "    "


def test_vline_fully_outside_is_noop_success():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_vline(win, 0, -1, 4, "|", LC_ATTR_NONE) == 0
    for y in range(4):
        assert _row_text(win, y) == "    "


def test_box_clips_right_edge():
    win = lc_new(4, 5, 0, 0)
    assert lc_wdraw_box(win, 1, 2, 3, 4) == 0

    assert _row_text(win, 0) == "     "
    assert _row_text(win, 1) == "  +--"
    assert _row_text(win, 2) == "  |  "
    assert _row_text(win, 3) == "  +--"


def test_box_clips_negative_left_edge():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_box(win, 0, -1, 3, 4) == 0

    assert _row_text(win, 0) == "--+ "
    assert _row_text(win, 1) == "  | "
    assert _row_text(win, 2) == "--+ "
    assert _row_text(win, 3) == "    "


def test_box_fully_outside_is_noop_success():
    win = lc_new(3, 3, 0, 0)
    assert lc_wdraw_box(win, 10, 10, 2, 2) == 0
    for y in range(3):
        assert _row_text(win, y) == "   "


def test_box_degenerate_height_one_clips():
    win = lc_new(3, 4, 0, 0)
    assert lc_wdraw_box(win, 1, -1, 1, 4) == 0
    assert _row_text(win, 1) == "--- "


def test_box_degenerate_width_one_clips():
    win = lc_new(4, 4, 0, 0)
    assert lc_wdraw_box(win, -1, 2, 4, 1) == 0
    assert _row_text(win, 0) == "  | "
    assert _row_text(win, 1) == "  | "
    assert _row_text(win, 2) == "  | "
    assert _row_text(win, 3) == "    "


def test_rect_shape_to_extents_keeps_positive_rect():
    assert _rect_shape_to_extents(2, 3, 4, 5) == (2, 3, 6, 8)


def test_rect_shape_to_extents_zeroes_nonpositive_size():
    assert _rect_shape_to_extents(2, 3, 0, 5) == (2, 3, 2, 3)
    assert _rect_shape_to_extents(2, 3, 4, 0) == (2, 3, 2, 3)
    assert _rect_shape_to_extents(2, 3, -1, 5) == (2, 3, 2, 3)


def test_clip_rect_shape_clips_shape_against_window():
    win = lc_new(4, 5, 0, 0)
    assert _clip_rect_shape(win, -1, 1, 4, 10) == (0, 1, 3, 5)


def test_normalize_rect_shape_keeps_positive_rect():
    assert _normalize_rect_shape(2, 3, 4, 5) == (2, 3, 4, 5)


def test_normalize_rect_shape_zeroes_nonpositive_size():
    assert _normalize_rect_shape(2, 3, 0, 5) == (2, 3, 0, 0)
    assert _normalize_rect_shape(2, 3, 4, 0) == (2, 3, 0, 0)
    assert _normalize_rect_shape(2, 3, -1, 5) == (2, 3, 0, 0)


def test_box_edges_returns_outer_bounds():
    assert _box_edges(1, 2, 4, 5) == (1, 2, 4, 6)


def test_interior_rect_for_regular_box():
    assert _interior_rect_shape(1, 2, 4, 5) == (2, 3, 2, 3)


def test_interior_rect_for_degenerate_box():
    assert _interior_rect_shape(1, 2, 2, 5) == (2, 3, 0, 0)
    assert _interior_rect_shape(1, 2, 5, 2) == (2, 3, 0, 0)


def test_wfill_empty_char_is_error():
    win = lc_new(2, 2, 0, 0)
    assert lc_wfill(win, 0, 0, 1, 1, "", LC_ATTR_NONE) == -1


def test_wfill_nonpositive_size_is_successful_noop():
    win = lc_new(2, 2, 0, 0)
    assert lc_wfill(win, 0, 0, 0, 2, "x", 1) == 0
    assert lc_wfill(win, 0, 0, 2, 0, "x", 1) == 0


def test_wfill_uses_first_character_when_given_longer_string():
    win = lc_new(2, 4, 0, 0)
    assert lc_wfill(win, 0, 0, 1, 4, "XY", 1) == 0
    assert _row_text(win, 0) == "XXXX"


def test_draw_lines_use_first_character_when_given_longer_string():
    win = lc_new(3, 4, 0, 0)
    assert lc_wdraw_hline(win, 0, 0, 4, "=-", LC_ATTR_NONE) == 0
    assert lc_wdraw_vline(win, 0, 3, 3, "|!", LC_ATTR_NONE) == 0
    assert _row_text(win, 0) == "===|"
    assert _row_text(win, 1) == "   |"
    assert _row_text(win, 2) == "   |"


def test_box_characters_use_first_character_when_given_longer_strings():
    win = lc_new(3, 5, 0, 0)
    assert lc_wdraw_box(win, 0, 0, 3, 5, LC_ATTR_NONE, "=-", "|!", "TL", "TR", "BL", "BR") == 0
    assert _row_text(win, 0) == "T===T"
    assert _row_text(win, 1) == "|   |"
    assert _row_text(win, 2) == "B===B"


def test_box_title_span_regular_case():
    y, x, label = _box_title_span(1, 2, 4, 8, "abc")
    assert y == 1
    assert x == 3
    assert label == " abc "


def test_box_title_span_clips_to_inner_width():
    y, x, label = _box_title_span(0, 0, 3, 5, "abcdef")
    assert y == 0
    assert x == 1
    assert label == " ab"


def test_wdraw_box_title_writes_on_top_edge():
    win = lc_new(4, 10, 0, 0)
    assert lc_wdraw_box(win, 0, 0, 4, 10) == 0
    assert lc_wdraw_box_title(win, 0, 0, 4, 10, "hdr", 7) == 0

    assert _row_text(win, 0) == "+ hdr ---+"
    assert win.lines[0].line[1].attr == 7
    assert win.lines[0].line[5].attr == 7


def test_wdraw_box_title_clips_small_box():
    win = lc_new(3, 6, 0, 0)
    assert lc_wdraw_box(win, 0, 0, 3, 6) == 0
    assert lc_wdraw_box_title(win, 0, 0, 3, 6, "abcdef", 3) == 0

    assert _row_text(win, 0) == "+ abc+"


def test_wdraw_box_title_outside_window_is_noop_success():
    win = lc_new(3, 4, 0, 0)
    assert lc_wdraw_box_title(win, 10, 10, 3, 5, "x", 1) == 0
    for y in range(3):
        assert _row_text(win, y) == "    "


def test_wdraw_box_title_none_is_error():
    win = lc_new(3, 4, 0, 0)
    assert lc_wdraw_box_title(win, 0, 0, 3, 4, None, 1) == -1


def test_wdraw_panel_draws_frame_title_and_fill():
    win = lc_new(5, 12, 0, 0)
    assert lc_wdraw_panel(win, 0, 0, 5, 12, "hdr", 7, ".", 3) == 0

    assert _row_text(win, 0) == "+ hdr -----+"
    assert _row_text(win, 1) == "|..........|"
    assert _row_text(win, 2) == "|..........|"
    assert _row_text(win, 3) == "|..........|"
    assert _row_text(win, 4) == "+----------+"

    assert win.lines[0].line[1].attr == 7
    assert win.lines[1].line[1].attr == 3
    assert win.lines[3].line[10].attr == 3


def test_wdraw_panel_without_title_or_fill_is_just_box():
    win = lc_new(3, 6, 0, 0)
    assert lc_wdraw_panel(win, 0, 0, 3, 6) == 0

    assert _row_text(win, 0) == "+----+"
    assert _row_text(win, 1) == "|    |"
    assert _row_text(win, 2) == "+----+"


def test_wdraw_panel_fill_only_uses_interior():
    win = lc_new(4, 7, 0, 0)
    assert lc_wdraw_panel(win, 0, 0, 4, 7, None, 1, "x", 9) == 0

    assert _row_text(win, 0) == "+-----+"
    assert _row_text(win, 1) == "|xxxxx|"
    assert _row_text(win, 2) == "|xxxxx|"
    assert _row_text(win, 3) == "+-----+"
    assert win.lines[1].line[1].attr == 9


def test_wdraw_panel_clips_like_box():
    win = lc_new(4, 6, 0, 0)
    assert lc_wdraw_panel(win, 0, 3, 4, 6, "t", 2, ".", 4) == 0
    assert _row_text(win, 0) == "   + t"
    assert _row_text(win, 1) == "   |.."
    assert _row_text(win, 2) == "   |.."
    assert _row_text(win, 3) == "   +--"
