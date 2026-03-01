from dataclasses import dataclass
from typing import Optional

from lc_keys import LCKey, lc_readkey
from lc_refresh import lc_refresh
from lc_screen import lc_get_size, lc
from ui_event import (
    UI_CMD_NONE,
    UI_CMD_QUIT,
    UI_CMD_REDRAW,
    UI_CMD_FOCUS_NEXT,
    UI_CMD_FOCUS_PREV,
    UI_EVENT_NONE,
    UI_EVENT_COMMAND,
    UI_EVENT_RESIZE,
    UIEvent,
    ui_command_event,
    ui_event_from_key,
    ui_focus_in_event,
    ui_focus_out_event,
    ui_translate_command,
)
from ui_view import (
    UIView,
    ui_view_collect_focusable,
    ui_view_draw,
    ui_view_handle_event,
    ui_view_measure,
    ui_view_mark_dirty,
    ui_view_layout_default,
    ui_view_rebind_tree,
)
from ui_layout import ui_layout_assign_root


@dataclass
class UIRuntime:
    root: Optional[UIView] = None
    focused: Optional[UIView] = None
    running: bool = False
    last_width: int = 0
    last_height: int = 0


def ui_runtime_create(root: Optional[UIView]) -> Optional[UIRuntime]:
    rt = None
    rows = 0
    cols = 0

    if root is None:
        return None

    rows, cols = lc_get_size()
    rt = UIRuntime(root=root, focused=None, running=False,
                   last_width=cols, last_height=rows)
    return rt


def ui_runtime_layout(rt: Optional[UIRuntime]) -> int:
    rows = 0
    cols = 0

    if rt is None or rt.root is None:
        return -1

    rows, cols = lc_get_size()
    rt.last_width = cols
    rt.last_height = rows
    if ui_layout_assign_root(rt.root, rows, cols) != 0:
        return -1
    if ui_view_measure(rt.root) != 0:
        return -1
    return ui_view_layout_default(rt.root)


def ui_runtime_bind_root(rt: Optional[UIRuntime]) -> int:
    root = None

    if rt is None or rt.root is None:
        return -1

    root = rt.root
    if ui_runtime_layout(rt) != 0:
        return -1

    if lc.stdscr is None:
        return -1

    return ui_view_rebind_tree(root, lc.stdscr)


def ui_runtime_set_focus(rt: Optional[UIRuntime], view: Optional[UIView]) -> int:
    old = None

    if rt is None:
        return -1
    if view is not None and not view.is_focusable():
        return -1

    old = rt.focused
    if old is view:
        return 0

    if old is not None:
        ui_view_handle_event(old, ui_focus_out_event())

    rt.focused = view

    if rt.focused is not None:
        ui_view_handle_event(rt.focused, ui_focus_in_event())

    return 0


def ui_runtime_focus_first(rt: Optional[UIRuntime]) -> int:
    focusable: list[UIView] = []

    if rt is None or rt.root is None:
        return -1

    ui_view_collect_focusable(rt.root, focusable)
    if not focusable:
        rt.focused = None
        return 0

    return ui_runtime_set_focus(rt, focusable[0])


def ui_runtime_focus_cycle(rt: Optional[UIRuntime], step: int) -> int:
    focusable: list[UIView] = []
    i = 0
    n = 0

    if rt is None or rt.root is None:
        return -1

    ui_view_collect_focusable(rt.root, focusable)
    n = len(focusable)
    if n == 0:
        rt.focused = None
        return 0

    if rt.focused not in focusable:
        return ui_runtime_set_focus(rt, focusable[0])

    i = focusable.index(rt.focused)
    i = (i + step) % n
    return ui_runtime_set_focus(rt, focusable[i])


def ui_runtime_dispatch(rt: Optional[UIRuntime], ev: UIEvent) -> int:
    cmd = UI_CMD_NONE
    target = None

    if rt is None or rt.root is None or ev is None:
        return -1

    if ev.type == UI_EVENT_NONE:
        return 0

    if ev.type == UI_EVENT_RESIZE:
        if ui_runtime_bind_root(rt) != 0:
            return -1
        ui_view_mark_dirty(rt.root)
        return UI_CMD_REDRAW

    cmd = ui_translate_command(ev)
    if cmd != UI_CMD_NONE:
        ev = ui_command_event(cmd)

    if ev.type == UI_EVENT_COMMAND:
        if ev.command == UI_CMD_FOCUS_NEXT:
            return ui_runtime_focus_cycle(rt, 1)
        if ev.command == UI_CMD_FOCUS_PREV:
            return ui_runtime_focus_cycle(rt, -1)
        if ev.command == UI_CMD_QUIT:
            rt.running = False
            return UI_CMD_QUIT

    target = rt.focused if rt.focused is not None else rt.root
    cmd = ui_view_handle_event(target, ev)
    if cmd == UI_CMD_REDRAW:
        ui_view_mark_dirty(target)
    return cmd


def ui_runtime_redraw(rt: Optional[UIRuntime]) -> int:
    if rt is None or rt.root is None:
        return -1
    if ui_view_draw(rt.root) != 0:
        return -1
    return lc_refresh()


def ui_runtime_step(rt: Optional[UIRuntime]) -> int:
    key = LCKey()
    ev = None
    rows = 0
    cols = 0
    rc = 0

    if rt is None:
        return -1

    rc = lc_readkey(key)
    if rc != 0:
        return -1

    rows, cols = lc_get_size()
    ev = ui_event_from_key(key, width=cols, height=rows)

    rc = ui_runtime_dispatch(rt, ev)
    if rc < 0:
        return -1
    if rc == UI_CMD_QUIT:
        return 0

    return ui_runtime_redraw(rt)


def ui_runtime_run(rt: Optional[UIRuntime]) -> int:
    if rt is None or rt.root is None:
        return -1

    if ui_runtime_bind_root(rt) != 0:
        return -1
    if ui_runtime_focus_first(rt) != 0:
        return -1

    rt.running = True

    if ui_runtime_redraw(rt) != 0:
        return -1

    while rt.running:
        if ui_runtime_step(rt) < 0:
            return -1

    return 0
