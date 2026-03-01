from ui_view import (
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
