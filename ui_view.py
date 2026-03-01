from dataclasses import dataclass, field
from typing import Optional

from lc_term import LC_ATTR_NONE
from lc_window import (
    LCWin,
    lc_subwin,
    lc_wclear,
    lc_wdraw_panel,
    lc_wfill,
    lc_wmove,
    lc_waddstr,
)
from ui_layout import (
    UIRect,
    ui_rect,
    ui_rect_copy,
    ui_rect_empty,
    ui_rect_inset,
    ui_rect_is_empty,
    ui_layout_stack_vertical,
)
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
UI_VIEW_CONTAINER = 1 << 5

UI_LAYOUT_NONE = 0
UI_LAYOUT_STACK_V = 1

UI_VIEWKIND_GENERIC = 0
UI_VIEWKIND_ROOT = 1
UI_VIEWKIND_CONTAINER = 2
UI_VIEWKIND_PANEL = 3
UI_VIEWKIND_LABEL = 4

UI_BIND_CONTENT = 0
UI_BIND_FRAME = 1

UI_ALIGN_LEFT = 0
UI_ALIGN_CENTER = 1
UI_ALIGN_RIGHT = 2


@dataclass
class UIDrawContext:
    is_root: bool = False


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
    bind_policy: int = UI_BIND_CONTENT
    bound_win: Optional[LCWin] = None
    kind: int = UI_VIEWKIND_GENERIC
    min_height: int = 0
    min_width: int = 0
    pref_height: int = 0
    pref_width: int = 0
    layout_kind: int = UI_LAYOUT_NONE
    layout_gap: int = 0
    fill_ch: str = " "
    fill_attr: int = LC_ATTR_NONE
    text: str = ""
    text_attr: int = LC_ATTR_NONE
    text_align: int = UI_ALIGN_LEFT
    user_data: object = None

    def is_visible(self) -> bool:
        return bool(self.flags & UI_VIEW_VISIBLE)

    def is_panel(self) -> bool:
        return bool(self.flags & UI_VIEW_PANEL)

    def is_enabled(self) -> bool:
        return bool(self.flags & UI_VIEW_ENABLED)

    def is_container(self) -> bool:
        return bool(self.flags & UI_VIEW_CONTAINER)

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
    container: bool = False,
    kind: int = UI_VIEWKIND_GENERIC,
) -> UIView:
    flags = UI_VIEW_VISIBLE | UI_VIEW_ENABLED | UI_VIEW_DIRTY
    if focusable:
        flags |= UI_VIEW_FOCUSABLE
    if panel:
        flags |= UI_VIEW_PANEL
    if container:
        flags |= UI_VIEW_CONTAINER

    return UIView(
        id=view_id,
        frame_rect=ui_rect(y, x, height, width),
        content_rect=ui_rect(y, x, height, width),
        bind_policy=UI_BIND_CONTENT,
        kind=kind,
        flags=flags,
    )


def ui_view_create_panel(
    view_id: str,
    y: int,
    x: int,
    height: int,
    width: int,
    title: str = "",
) -> UIView:
    view = ui_view_create(
        view_id, y, x, height, width, panel=True, container=True, kind=UI_VIEWKIND_PANEL
    )
    view.bind_policy = UI_BIND_FRAME
    view.title = title
    return view


def ui_view_create_root(view_id: str = "root") -> UIView:
    view = ui_view_create(
        view_id,
        0,
        0,
        0,
        0,
        container=True,
        kind=UI_VIEWKIND_ROOT,
    )
    view.bind_policy = UI_BIND_FRAME
    return view


def ui_view_create_container(
    view_id: str,
    y: int,
    x: int,
    height: int,
    width: int,
    panel: bool = False,
    title: str = "",
) -> UIView:
    kind = UI_VIEWKIND_PANEL if panel else UI_VIEWKIND_CONTAINER
    view = ui_view_create(
        view_id, y, x, height, width, panel=panel, container=True, kind=kind
    )
    if panel:
        view.bind_policy = UI_BIND_FRAME
    else:
        view.bind_policy = UI_BIND_CONTENT
    view.title = title
    return view


def ui_view_create_label(
    view_id: str,
    y: int,
    x: int,
    height: int,
    width: int,
    text: str = "",
) -> UIView:
    view = ui_view_create(
        view_id,
        y,
        x,
        height,
        width,
        focusable=False,
        panel=False,
        container=False,
        kind=UI_VIEWKIND_LABEL,
    )
    view.bind_policy = UI_BIND_CONTENT
    view.text = text
    return view


def ui_view_set_text(view: Optional[UIView], text: str) -> int:
    if view is None:
        return -1
    if text is None:
        return -1
    view.text = text
    ui_view_mark_dirty(view)
    return 0


def ui_view_set_layout_stack_vertical(view: Optional[UIView], gap: int = 0) -> int:
    if view is None:
        return -1
    view.flags |= UI_VIEW_CONTAINER
    view.layout_kind = UI_LAYOUT_STACK_V
    view.layout_gap = gap if gap >= 0 else 0
    return 0


def ui_view_set_fill(view: Optional[UIView], ch: str, attr: int = LC_ATTR_NONE) -> int:
    if view is None:
        return -1
    if not ch:
        return -1
    view.fill_ch = ch[0]
    view.fill_attr = attr
    ui_view_mark_dirty(view)
    return 0


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


def ui_view_bind_rect(parent_win: Optional[LCWin], rect: UIRect) -> Optional[LCWin]:
    if parent_win is None or rect is None:
        return None
    if rect.height <= 0 or rect.width <= 0:
        return None
    return lc_subwin(parent_win, rect.height, rect.width, rect.y, rect.x)


def ui_view_bind_window(parent_win: Optional[LCWin], view: Optional[UIView]) -> Optional[LCWin]:
    r = None

    if parent_win is None or view is None:
        return None

    if view.bind_policy == UI_BIND_FRAME:
        r = view.frame_rect
    else:
        r = view.content_rect

    return ui_view_bind_rect(parent_win, r)


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


def ui_view_measure(view: Optional[UIView]) -> int:
    child = None

    if view is None:
        return -1

    for child in view.children:
        if ui_view_measure(child) != 0:
            return -1

    if view.pref_height < view.min_height:
        view.pref_height = view.min_height
    if view.pref_width < view.min_width:
        view.pref_width = view.min_width

    return 0


def ui_view_apply_content_rect(view: Optional[UIView]) -> int:
    if view is None:
        return -1

    if view.is_panel():
        view.content_rect = ui_rect_inset(view.frame_rect, 1, 1, 1, 1)
    else:
        view.content_rect = ui_rect_copy(view.frame_rect)

    return 0


def ui_view_layout_children(view: Optional[UIView]) -> int:
    if view is None:
        return -1

    if not view.children:
        return 0

    if ui_rect_is_empty(view.content_rect):
        for child in view.children:
            child.frame_rect = ui_rect_empty()
            child.content_rect = ui_rect_empty()
        return 0

    if view.layout_kind == UI_LAYOUT_STACK_V:
        return ui_layout_stack_vertical(view.content_rect, view.children, view.layout_gap)

    for child in view.children:
        child.frame_rect = ui_rect(
            child.frame_rect.y, child.frame_rect.x, child.frame_rect.height, child.frame_rect.width
        )
        child.content_rect = ui_rect_copy(child.frame_rect)

    return 0


def ui_view_layout_default(view: Optional[UIView]) -> int:
    child = None

    if view is None:
        return -1

    if ui_view_apply_content_rect(view) != 0:
        return -1
    if ui_view_layout_children(view) != 0:
        return -1

    for child in view.children:
        if ui_view_layout_default(child) != 0:
            return -1

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


def ui_view_draw_rect(view: UIView) -> UIRect:
    if view.bind_policy == UI_BIND_FRAME:
        return view.frame_rect
    return view.content_rect


def ui_view_draw_size(view: UIView) -> tuple[int, int]:
    r = ui_view_draw_rect(view)
    return r.height, r.width


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


def _ui_view_draw_label(view: UIView) -> int:
    r = ui_view_draw_rect(view)
    text = view.text
    x = 0

    if view.bound_win is None:
        return -1
    if ui_rect_is_empty(r):
        return 0

    if text is None:
        text = ""
    if len(text) > r.width:
        text = text[:r.width]

    if view.fill_ch:
        if lc_wfill(view.bound_win, 0, 0, r.height, r.width, view.fill_ch, view.fill_attr) != 0:
            return -1
    else:
        if lc_wclear(view.bound_win) != 0:
            return -1

    if not text or r.height <= 0 or r.width <= 0:
        return 0

    if view.text_align == UI_ALIGN_CENTER:
        x = max(0, (r.width - len(text)) // 2)
    elif view.text_align == UI_ALIGN_RIGHT:
        x = max(0, r.width - len(text))
    else:
        x = 0

    if lc_wmove(view.bound_win, 0, x) != 0:
        return -1
    return lc_waddstr(view.bound_win, text)


def _ui_view_draw_panel(view: UIView) -> int:
    r = ui_view_draw_rect(view)
    if view.bound_win is None:
        return -1
    return lc_wdraw_panel(
        view.bound_win,
        0,
        0,
        r.height,
        r.width,
        title=view.title if view.title else None,
        frame_attr=view.attr,
        fill=view.fill_ch,
        fill_attr=view.fill_attr,
    )


def _ui_view_draw_container(view: UIView) -> int:
    r = ui_view_draw_rect(view)
    if view.bound_win is None:
        return -1
    if ui_rect_is_empty(r):
        return 0
    if view.fill_ch:
        return lc_wfill(view.bound_win, 0, 0, r.height, r.width, view.fill_ch, view.fill_attr)
    return lc_wclear(view.bound_win)


def ui_view_draw_self(view: Optional[UIView], ctx: Optional[UIDrawContext] = None) -> int:
    if view is None:
        return -1
    if view.bound_win is None:
        return -1

    if view.kind == UI_VIEWKIND_LABEL:
        return _ui_view_draw_label(view)
    if view.kind == UI_VIEWKIND_PANEL:
        return _ui_view_draw_panel(view)
    if view.kind == UI_VIEWKIND_CONTAINER:
        return _ui_view_draw_container(view)
    if view.kind == UI_VIEWKIND_ROOT:
        return _ui_view_draw_container(view)

    return lc_wclear(view.bound_win)


def ui_view_draw(view: Optional[UIView]) -> int:
    child = None
    ctx = UIDrawContext()

    if view is None:
        return -1
    if not view.is_visible():
        return 0
    if view.bound_win is None:
        return -1

    ctx.is_root = (view.parent is None)
    if ui_view_draw_self(view, ctx) != 0:
        return -1
    view.clear_dirty()

    for child in view.children:
        if ui_view_draw(child) != 0:
            return -1
    return 0
