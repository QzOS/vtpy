"""Shared geometry/layout helpers for the lc_* core and UI layer.

This module centralizes rectangle clipping, box/interior helpers, panel zoning,
and basic rect splitting so the window layer and future UI/layout code can
share one coordinate model without cross-layer imports.
"""

from __future__ import annotations


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


def _rect_shape_to_extents(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    if height <= 0 or width <= 0:
        return y, x, y, x
    return y, x, y + height, x + width


def _clip_hspan(limit_x: int, x: int, width: int) -> tuple[int, int]:
    return _clip_range(x, width, limit_x)


def _clip_vspan(limit_y: int, y: int, height: int) -> tuple[int, int]:
    return _clip_range(y, height, limit_y)


def _clip_rect_extents(limit_y: int, limit_x: int, y0: int, x0: int, y1: int, x1: int) -> tuple[int, int, int, int]:
    if y0 >= y1 or x0 >= x1:
        return 0, 0, 0, 0

    ys, ye = _clip_range(y0, y1 - y0, limit_y)
    xs, xe = _clip_range(x0, x1 - x0, limit_x)
    if ys >= ye or xs >= xe:
        return 0, 0, 0, 0
    return ys, xs, ye, xe


def _clip_rect_shape(limit_y: int, limit_x: int, y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    y0, x0, y1, x1 = _rect_shape_to_extents(y, x, height, width)
    return _clip_rect_extents(limit_y, limit_x, y0, x0, y1, x1)


def _normalize_rect_shape(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    if height <= 0 or width <= 0:
        return y, x, 0, 0
    return y, x, height, width


def _box_edges(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    top = y
    left = x
    bottom = y + height - 1
    right = x + width - 1
    return top, left, bottom, right


def _interior_rect_shape(y: int, x: int, height: int, width: int) -> tuple[int, int, int, int]:
    y, x, height, width = _normalize_rect_shape(y, x, height, width)
    if height <= 2 or width <= 2:
        return y + 1, x + 1, 0, 0
    return y + 1, x + 1, height - 2, width - 2


def _clamp_partition(size: int, total: int) -> int:
    if total <= 0 or size <= 0:
        return 0
    if size >= total:
        return total
    return size


def lc_rect_split_vertical(y: int, x: int, height: int, width: int, top_height: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y, x, height, width = _normalize_rect_shape(y, x, height, width)
    split = _clamp_partition(top_height, height)
    return (y, x, split, width), (y + split, x, height - split, width)


def lc_rect_split_horizontal(y: int, x: int, height: int, width: int, left_width: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y, x, height, width = _normalize_rect_shape(y, x, height, width)
    split = _clamp_partition(left_width, width)
    return (y, x, height, split), (y, x + split, height, width - split)


def _panel_header_height(inner_h: int, header_height: int) -> int:
    if inner_h <= 0 or header_height <= 0:
        return 0
    return min(inner_h, header_height)


def lc_panel_header_rect(y: int, x: int, height: int, width: int, header_height: int = 1) -> tuple[int, int, int, int]:
    inner_y, inner_x, inner_h, inner_w = _interior_rect_shape(y, x, height, width)
    header_h = _panel_header_height(inner_h, header_height)
    if header_h <= 0:
        return inner_y, inner_x, 0, 0
    header_rect, _ = lc_rect_split_vertical(inner_y, inner_x, inner_h, inner_w, header_h)
    return header_rect


def lc_panel_content_rect(y: int, x: int, height: int, width: int, header_height: int = 0) -> tuple[int, int, int, int]:
    inner_y, inner_x, inner_h, inner_w = _interior_rect_shape(y, x, height, width)
    header_h = _panel_header_height(inner_h, header_height)
    if header_h <= 0:
        return inner_y, inner_x, inner_h, inner_w
    _, content_rect = lc_rect_split_vertical(inner_y, inner_x, inner_h, inner_w, header_h)
    return content_rect


def lc_panel_regions(y: int, x: int, height: int, width: int, header_height: int = 0) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    return (
        lc_panel_header_rect(y, x, height, width, header_height),
        lc_panel_content_rect(y, x, height, width, header_height),
    )
