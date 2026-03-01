from dataclasses import dataclass, field
from typing import Optional

from lc_term import LC_ATTR_NONE
from lc_window import LCWin, lc_subwin, lc_wclear
from ui_layout import UIRect, ui_rect, ui_rect_empty
from ui_event import (
    UI_CMD_NONE,
    UI_CMD_REDRAW,
    UI_EVENT_COMMAND,
    UI_EVENT_FOCUS_IN,
    UI_EVENT_FOCUS_OUT,
    UIEvent,
)


UI_VIEW_VISIBLE = 1 << 0
UI_VIEW_ENABLED = 1 << 1
UI_VIEW_FOCUSABLE = 1 << 2
UI_VIEW_DIRTY = 1 << 3
UI_VIEW_PANEL = 1 << 4


@dataclass
class UIView:
    id: str = ""
    frame_rect: UIRect = field(default_factory=ui_rect_empty)
    content_rect: UIRect = field(default_factory=ui_rect_empty)
    parent: Optional["UIView"] = None
    children: list["UIView"] = field(default_factory=list)
    flags: int = UI_VIEW_VISIBLE | UI_VIEW_ENABLED | UI_VIEW_DIRTY
    title: str = ""
    attr: int = LC_ATTR_NONE
    has_focus: bool = False
    bound_win: Optional[LCWin] = None
    user_data: object = None

    def is_visible(self) -> bool:
        return bool(self.flags & UI_VIEW_VISIBLE)

    def is_panel(self) -> bool:
        return bool(self.flags & UI_VIEW_PANEL)

    def is_enabled(self) -> bool:
        return bool(self.flags & UI_VIEW_ENABLED)

    def is_focusable(self) -> bool:
        return bool(self.flags & UI_VIEW_FOCUSABLE)

    def is_dirty(self) -> bool:
        return bool(self.flags & UI_VIEW_DIRTY)

    def set_dirty(self) -> None:
        self.flags |= UI_VIEW_DIRTY

    def clear_dirty(self) -> None:
        self.flags &= ~UI_VIEW_DIRTY


def ui_view_create(
    view_id: str,
    y: int,
    x: int,
    height: int,
    width: int,
    focusable: bool = False,
    panel: bool = False,
) -> UIView:
    flags = UI_VIEW_VISIBLE | UI_VIEW_ENABLED | UI_VIEW_DIRTY
    if focusable:
        flags |= UI_VIEW_FOCUSABLE
    if panel:
        flags |= UI_VIEW_PANEL

    return UIView(
        id=view_id,
        frame_rect=ui_rect(y, x, height, width),
        content_rect=ui_rect(y, x, height, width),
        flags=flags,
    )


def ui_view_add_child(parent: Optional[UIView], child: Optional[UIView]) -> int:
    if parent is None or child is None:
        return -1
    if child.parent is not None:
        return -1

    child.parent = parent
    parent.children.append(child)
    parent.set_dirty()
    return 0


def ui_view_remove_child(parent: Optional[UIView], child: Optional[UIView]) -> int:
    if parent is None or child is None:
        return -1
    if child.parent is not parent:
        return -1
    if child not in parent.children:
        return -1

    parent.children.remove(child)
    child.parent = None
    child.set_dirty()
    parent.set_dirty()
    return 0


def ui_view_mark_dirty(view: Optional[UIView]) -> None:
    cur = view
    while cur is not None:
        cur.set_dirty()
        cur = cur.parent


def ui_view_bind_window(
    parent_win: Optional[LCWin],
    view: Optional[UIView],
) -> Optional[LCWin]:
    r = None

    if parent_win is None or view is None:
        return None

    r = view.content_rect
    if r.height <= 0 or r.width <= 0:
        return None
    return lc_subwin(parent_win, r.height, r.width, r.y, r.x)


def ui_view_bind_root_window(
    root_win: Optional[LCWin],
    view: Optional[UIView],
) -> Optional[LCWin]:
    if root_win is None or view is None:
        return None

    view.bound_win = root_win
    return root_win


def ui_view_bind_child_window(
    parent_win: Optional[LCWin],
    view: Optional[UIView],
) -> Optional[LCWin]:
    return ui_view_bind_window(parent_win, view)


def ui_view_layout_default(view: Optional[UIView]) -> int:
    child = None

    if view is None:
        return -1
    for child in view.children:
        child.content_rect = ui_rect(
            child.frame_rect.y, child.frame_rect.x, child.frame_rect.height, child.frame_rect.width
        )
    return 0


def ui_view_unbind(view: Optional[UIView]) -> None:
    if view is None:
        return
    view.bound_win = None
    for child in view.children:
        ui_view_unbind(child)


def ui_view_rebind_tree(
    view: Optional[UIView],
    parent_win: Optional[LCWin],
) -> int:
    child = None

    if view is None:
        return -1

    if view.parent is None:
        view.bound_win = ui_view_bind_root_window(parent_win, view)
    else:
        view.bound_win = ui_view_bind_child_window(parent_win, view)

    if view.bound_win is None:
        return -1

    for child in view.children:
        if ui_view_rebind_tree(child, view.bound_win) != 0:
            return -1

    return 0


def ui_view_find_by_id(view: Optional[UIView], view_id: str) -> Optional[UIView]:
    child = None
    found = None

    if view is None:
        return None
    if view.id == view_id:
        return view

    for child in view.children:
        found = ui_view_find_by_id(child, view_id)
        if found is not None:
            return found
    return None


def ui_view_collect_focusable(view: Optional[UIView], out: list[UIView]) -> None:
    child = None

    if view is None:
        return
    if not view.is_visible() or not view.is_enabled():
        return
    if view.is_focusable():
        out.append(view)
    for child in view.children:
        ui_view_collect_focusable(child, out)


def ui_view_handle_event(view: Optional[UIView], ev: UIEvent) -> int:
    if view is None or ev is None:
        return UI_CMD_NONE
    if not view.is_visible() or not view.is_enabled():
        return UI_CMD_NONE

    if ev.type == UI_EVENT_FOCUS_IN:
        view.has_focus = True
        ui_view_mark_dirty(view)
        return UI_CMD_REDRAW

    if ev.type == UI_EVENT_FOCUS_OUT:
        view.has_focus = False
        ui_view_mark_dirty(view)
        return UI_CMD_REDRAW

    if ev.type == UI_EVENT_COMMAND:
        return ev.command

    return UI_CMD_NONE


def ui_view_draw(view: Optional[UIView]) -> int:
    child = None

    if view is None:
        return -1
    if not view.is_visible():
        return 0
    if view.bound_win is None:
        return -1

    # Minimal skeleton rule:
    # a view owns the full content region of its bound window.
    # Frame drawing, title drawing and richer layout zoning live above this
    # primitive baseline.
    lc_wclear(view.bound_win)
    view.clear_dirty()

    for child in view.children:
        if ui_view_draw(child) != 0:
            return -1
    return 0
