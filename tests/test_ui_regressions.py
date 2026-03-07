from lc_keys import LCKey, LC_KT_CHAR
from ui_event import UI_EVENT_KEY, ui_event_from_key
from ui_layout import ui_rect, ui_layout_stack_vertical, ui_layout_stack_horizontal
from ui_runtime import (
    UIRuntime,
    ui_runtime_dispatch,
    ui_runtime_set_focus,
)
from ui_event import ui_command_event, UI_CMD_FOCUS_NEXT, UI_CMD_FOCUS_PREV, UI_CMD_REDRAW
from ui_view import (
    UI_VIEW_VISIBLE,
    ui_view_create_root,
    ui_view_create_label,
    ui_view_create_container,
    ui_view_add_child,
    UI_VIEW_FOCUSABLE,
)


def test_ui_event_from_key_copies_input_key():
    key = LCKey(type=LC_KT_CHAR, rune=ord("a"), mods=1)

    ev = ui_event_from_key(key)

    assert ev.type == UI_EVENT_KEY
    assert ev.key is not key
    assert ev.key.rune == ord("a")

    key.rune = ord("b")
    assert ev.key.rune == ord("a")


def test_ui_layout_stack_vertical_ignores_none_views_for_distribution():
    parent = ui_rect(0, 0, 10, 20)
    a = ui_view_create_label("a", 0, 0, 0, 0, "A")
    b = ui_view_create_label("b", 0, 0, 0, 0, "B")

    assert ui_layout_stack_vertical(parent, [a, None, b], gap=1) == 0

    assert a.frame_rect.height == 4
    assert b.frame_rect.height == 5
    assert b.frame_rect.y == 5


def test_ui_layout_stack_horizontal_ignores_none_views_for_distribution():
    parent = ui_rect(0, 0, 3, 10)
    a = ui_view_create_label("a", 0, 0, 0, 0, "A")
    b = ui_view_create_label("b", 0, 0, 0, 0, "B")

    assert ui_layout_stack_horizontal(parent, [a, None, b], gap=1) == 0

    assert a.frame_rect.width == 4
    assert b.frame_rect.width == 5
    assert b.frame_rect.x == 5


def test_ui_runtime_set_focus_rejects_invisible_view():
    root = ui_view_create_root("root")
    target = ui_view_create_label("target", 0, 0, 1, 10, "x")
    target.flags &= ~UI_VIEW_VISIBLE

    rt = UIRuntime(root=root)

    assert ui_runtime_set_focus(rt, target) == -1
    assert rt.focused is None


def test_ui_runtime_dispatch_focus_command_returns_redraw(monkeypatch):
    root = ui_view_create_root("root")
    first = ui_view_create_container("first", 0, 0, 1, 10)
    second = ui_view_create_container("second", 1, 0, 1, 10)
    first.flags |= UI_VIEW_FOCUSABLE
    second.flags |= UI_VIEW_FOCUSABLE

    assert ui_view_add_child(root, first) == 0
    assert ui_view_add_child(root, second) == 0

    rt = UIRuntime(root=root, focused=first)

    assert ui_runtime_dispatch(rt, ui_command_event(UI_CMD_FOCUS_NEXT)) == UI_CMD_REDRAW
    assert rt.focused is second

    assert ui_runtime_dispatch(rt, ui_command_event(UI_CMD_FOCUS_PREV)) == UI_CMD_REDRAW
    assert rt.focused is first
