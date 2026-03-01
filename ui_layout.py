from dataclasses import dataclass
from typing import Optional


@dataclass
class UIRect:
    y: int = 0
    x: int = 0
    height: int = 0
    width: int = 0


def ui_rect(y: int, x: int, height: int, width: int) -> UIRect:
    return UIRect(y=y, x=x, height=height, width=width)


def ui_rect_empty() -> UIRect:
    return UIRect()


def ui_rect_normalize(y: int, x: int, height: int, width: int) -> UIRect:
    if height <= 0 or width <= 0:
        return UIRect(y=y, x=x, height=0, width=0)
    return UIRect(y=y, x=x, height=height, width=width)


def ui_rect_inset(rect: UIRect, top: int, left: int, bottom: int, right: int) -> UIRect:
    if rect is None:
        return ui_rect_empty()

    y = rect.y + top
    x = rect.x + left
    height = rect.height - top - bottom
    width = rect.width - left - right
    return ui_rect_normalize(y, x, height, width)


def ui_rect_panel_content(rect: UIRect) -> UIRect:
    if rect is None:
        return ui_rect_empty()
    return ui_rect_inset(rect, 1, 1, 1, 1)


def ui_rect_split_vertical(rect: UIRect, top_height: int) -> tuple[UIRect, UIRect]:
    if rect is None:
        return ui_rect_empty(), ui_rect_empty()

    if top_height <= 0:
        return ui_rect_empty(), ui_rect(rect.y, rect.x, rect.height, rect.width)
    if top_height >= rect.height:
        return ui_rect(rect.y, rect.x, rect.height, rect.width), ui_rect_empty()

    top = ui_rect(rect.y, rect.x, top_height, rect.width)
    bottom = ui_rect(rect.y + top_height, rect.x, rect.height - top_height, rect.width)
    return top, bottom


def ui_rect_split_horizontal(rect: UIRect, left_width: int) -> tuple[UIRect, UIRect]:
    if rect is None:
        return ui_rect_empty(), ui_rect_empty()

    if left_width <= 0:
        return ui_rect_empty(), ui_rect(rect.y, rect.x, rect.height, rect.width)
    if left_width >= rect.width:
        return ui_rect(rect.y, rect.x, rect.height, rect.width), ui_rect_empty()

    left = ui_rect(rect.y, rect.x, rect.height, left_width)
    right = ui_rect(rect.y, rect.x + left_width, rect.height, rect.width - left_width)
    return left, right


def ui_layout_assign_root(view, height: int, width: int) -> int:
    if view is None:
        return -1

    frame = ui_rect(0, 0, height, width)
    view.frame_rect = frame
    view.content_rect = frame
    return 0


def ui_layout_assign_panel(view, rect: UIRect) -> int:
    if view is None or rect is None:
        return -1

    view.frame_rect = ui_rect(rect.y, rect.x, rect.height, rect.width)
    view.content_rect = ui_rect_panel_content(view.frame_rect)
    return 0


def ui_layout_stack_vertical(parent_rect: UIRect, views: list, gap: int = 0) -> int:
    cur_y = 0
    view = None
    remaining = 0
    count = 0
    i = 0
    h = 0

    if parent_rect is None:
        return -1
    if views is None:
        return -1

    count = len(views)
    if count == 0:
        return 0

    remaining = parent_rect.height - (gap * (count - 1))
    if remaining < 0:
        remaining = 0

    cur_y = parent_rect.y

    for i, view in enumerate(views):
        if view is None:
            continue

        if i == count - 1:
            h = (parent_rect.y + parent_rect.height) - cur_y
        else:
            h = remaining // (count - i)

        if h < 0:
            h = 0

        view.frame_rect = ui_rect(cur_y, parent_rect.x, h, parent_rect.width)
        view.content_rect = ui_rect(cur_y, parent_rect.x, h, parent_rect.width)

        cur_y += h + gap
        remaining -= h

    return 0
