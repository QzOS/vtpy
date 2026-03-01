from ui_view import (
    UI_VIEW_VISIBLE,
    UIView,
    ui_view_create_root,
    ui_view_create_container,
    ui_view_create_label,
    ui_view_add_child,
    ui_view_mark_dirty,
    ui_view_draw,
)


class _DummyWin:
    pass


def _bind_tree_fake(view: UIView) -> None:
    view.bound_win = _DummyWin()
    for child in view.children:
        _bind_tree_fake(child)


def _clear_tree_dirty(view: UIView) -> None:
    view.clear_dirty()
    for child in view.children:
        _clear_tree_dirty(child)


def test_ui_draw_skips_fully_clean_subtree(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_container("child", 0, 0, 1, 10)
    leaf = ui_view_create_label("leaf", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0
    assert ui_view_add_child(child, leaf) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == []


def test_ui_draw_traverses_dirty_child_under_clean_parent(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_container("child", 0, 0, 3, 10)
    leaf = ui_view_create_label("leaf", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0
    assert ui_view_add_child(child, leaf) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)
    leaf.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == ["leaf"]
    assert not leaf.is_dirty()
    assert not child.is_dirty()
    assert not root.is_dirty()


def test_ui_draw_draws_dirty_parent_and_dirty_child(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_container("child", 0, 0, 3, 10)
    leaf = ui_view_create_label("leaf", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0
    assert ui_view_add_child(child, leaf) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)

    root.set_dirty()
    leaf.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == ["root", "leaf"]
    assert not root.is_dirty()
    assert not leaf.is_dirty()


def test_ui_draw_skips_clean_sibling_and_draws_dirty_sibling(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    a = ui_view_create_label("a", 0, 0, 1, 10, "A")
    b = ui_view_create_label("b", 1, 0, 1, 10, "B")

    assert ui_view_add_child(root, a) == 0
    assert ui_view_add_child(root, b) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)
    b.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == ["b"]
    assert not a.is_dirty()
    assert not b.is_dirty()


def test_ui_view_mark_dirty_propagates_to_ancestors():
    root = ui_view_create_root("root")
    child = ui_view_create_container("child", 0, 0, 3, 10)
    leaf = ui_view_create_label("leaf", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0
    assert ui_view_add_child(child, leaf) == 0

    _clear_tree_dirty(root)
    ui_view_mark_dirty(leaf)

    assert leaf.is_dirty()
    assert child.is_dirty()
    assert root.is_dirty()


def test_ui_draw_returns_error_for_unbound_visible_view(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0

    # Only bind root. Child remains unbound and visible.
    root.bound_win = _DummyWin()
    root.set_dirty()
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == -1
    assert calls == ["root"]


def test_ui_draw_stops_on_draw_self_error(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)
    root.set_dirty()
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        if view.id == "root":
            return -1
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == -1
    assert calls == ["root"]


def test_ui_draw_skips_invisible_subtree_even_if_dirty(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    parent = ui_view_create_container("parent", 0, 0, 3, 10)
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, parent) == 0
    assert ui_view_add_child(parent, child) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)

    parent.flags &= ~UI_VIEW_VISIBLE
    parent.set_dirty()
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == []
    assert parent.is_dirty()
    assert child.is_dirty()


def test_ui_draw_skips_invisible_child_without_bound_window(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0

    _clear_tree_dirty(root)
    root.bound_win = _DummyWin()

    child.flags &= ~UI_VIEW_VISIBLE
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == []


def test_ui_draw_requires_bound_window_for_dirty_visible_descendant(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    parent = ui_view_create_container("parent", 0, 0, 3, 10)
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, parent) == 0
    assert ui_view_add_child(parent, child) == 0

    _clear_tree_dirty(root)
    root.bound_win = _DummyWin()
    parent.bound_win = _DummyWin()
    child.bound_win = None
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == -1
    assert calls == []


def test_ui_draw_stops_on_dirty_descendant_draw_error(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    left = ui_view_create_label("left", 0, 0, 1, 10, "L")
    right = ui_view_create_label("right", 1, 0, 1, 10, "R")

    assert ui_view_add_child(root, left) == 0
    assert ui_view_add_child(root, right) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)
    left.set_dirty()
    right.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        if view.id == "left":
            return -1
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == -1
    assert calls == ["left"]
    assert left.is_dirty()
    assert right.is_dirty()


def test_ui_draw_clean_root_skips_invisible_dirty_descendant(monkeypatch):
    calls = []

    root = ui_view_create_root("root")
    child = ui_view_create_label("child", 0, 0, 1, 10, "hello")

    assert ui_view_add_child(root, child) == 0

    _bind_tree_fake(root)
    _clear_tree_dirty(root)

    child.flags &= ~UI_VIEW_VISIBLE
    child.set_dirty()

    def fake_draw_self(view, ctx=None):
        calls.append(view.id)
        return 0

    monkeypatch.setattr("ui_view.ui_view_draw_self", fake_draw_self)

    assert ui_view_draw(root) == 0
    assert calls == []
    assert child.is_dirty()
