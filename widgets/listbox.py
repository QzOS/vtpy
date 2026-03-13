"""
Scrollable list/selection widget.

Provides a focusable list with keyboard navigation, scrolling,
and selection callbacks.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, List, Any

from ui_view import (
    UIView,
    ui_view_create,
    ui_view_mark_dirty,
    UI_VIEW_VISIBLE,
    UI_VIEW_ENABLED,
    UI_VIEW_FOCUSABLE,
    UI_VIEW_DIRTY,
)
from ui_event import (
    UIEvent,
    UI_EVENT_KEY,
    UI_CMD_NONE,
    UI_CMD_REDRAW,
)
from lc_keys import (
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_UP,
    LC_KEY_DOWN,
    LC_KEY_HOME,
    LC_KEY_END,
    LC_KEY_PGUP,
    LC_KEY_PGDOWN,
)
from lc_window import lc_wmove, lc_wput, lc_wfill, lc_waddstr
from lc_term import LC_ATTR_NONE, LC_ATTR_REVERSE, LC_ATTR_BOLD


UI_VIEWKIND_LISTBOX = 101


@dataclass
class ListBox:
    """
    Scrollable list selection widget.
    
    Attributes:
        id: Unique identifier for this listbox
        items: List of items to display (strings or objects with __str__)
        selected_index: Currently selected item index (-1 if none)
        scroll_offset: Index of first visible item
        on_select: Callback when selection changes, receives (index, item)
        on_activate: Callback when Enter is pressed, receives (index, item)
    
    Usage:
        listbox = ListBox(id="files", items=["file1.txt", "file2.txt"])
        listbox.on_activate = lambda idx, item: open_file(item)
    """
    id: str = ""
    items: List[Any] = field(default_factory=list)
    selected_index: int = 0
    scroll_offset: int = 0
    on_select: Optional[Callable[[int, Any], None]] = None
    on_activate: Optional[Callable[[int, Any], None]] = None
    
    # Internal view state
    _view: Optional[UIView] = field(default=None, repr=False)
    _visible_height: int = field(default=10, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize selection to first item if items exist."""
        if self.items and self.selected_index >= len(self.items):
            self.selected_index = len(self.items) - 1
        if not self.items:
            self.selected_index = -1
    
    def set_items(self, items: List[Any]) -> None:
        """Replace the items list and reset selection."""
        self.items = items if items else []
        if not self.items:
            self.selected_index = -1
            self.scroll_offset = 0
        else:
            self.selected_index = 0
            self.scroll_offset = 0
        self._mark_dirty()
    
    def add_item(self, item: Any) -> None:
        """Add an item to the end of the list."""
        self.items.append(item)
        if self.selected_index < 0:
            self.selected_index = 0
        self._mark_dirty()
    
    def remove_item(self, index: int) -> bool:
        """Remove an item by index. Returns True if removed."""
        if index < 0 or index >= len(self.items):
            return False
        self.items.pop(index)
        # Adjust selection
        if not self.items:
            self.selected_index = -1
        elif self.selected_index >= len(self.items):
            self.selected_index = len(self.items) - 1
        self._ensure_visible()
        self._mark_dirty()
        return True
    
    def clear(self) -> None:
        """Remove all items."""
        self.items = []
        self.selected_index = -1
        self.scroll_offset = 0
        self._mark_dirty()
    
    @property
    def selected_item(self) -> Optional[Any]:
        """Get the currently selected item, or None if nothing selected."""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None
    
    def select_index(self, index: int) -> bool:
        """Select an item by index. Returns True if selection changed."""
        if not self.items:
            return False
        if index < 0:
            index = 0
        if index >= len(self.items):
            index = len(self.items) - 1
        if index == self.selected_index:
            return False
        self.selected_index = index
        self._ensure_visible()
        self._notify_select()
        self._mark_dirty()
        return True
    
    def select_next(self) -> bool:
        """Select the next item. Returns True if selection changed."""
        if not self.items:
            return False
        if self.selected_index < len(self.items) - 1:
            self.selected_index += 1
            self._ensure_visible()
            self._notify_select()
            self._mark_dirty()
            return True
        return False
    
    def select_prev(self) -> bool:
        """Select the previous item. Returns True if selection changed."""
        if not self.items:
            return False
        if self.selected_index > 0:
            self.selected_index -= 1
            self._ensure_visible()
            self._notify_select()
            self._mark_dirty()
            return True
        return False
    
    def select_first(self) -> bool:
        """Select the first item. Returns True if selection changed."""
        return self.select_index(0)
    
    def select_last(self) -> bool:
        """Select the last item. Returns True if selection changed."""
        return self.select_index(len(self.items) - 1)
    
    def page_down(self) -> bool:
        """Move selection down by one page."""
        if not self.items:
            return False
        new_index = min(
            self.selected_index + self._visible_height,
            len(self.items) - 1
        )
        return self.select_index(new_index)
    
    def page_up(self) -> bool:
        """Move selection up by one page."""
        if not self.items:
            return False
        new_index = max(self.selected_index - self._visible_height, 0)
        return self.select_index(new_index)
    
    def _ensure_visible(self) -> None:
        """Adjust scroll offset to keep selection visible."""
        if self.selected_index < 0:
            return
        
        # Scroll up if selection is above visible area
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        
        # Scroll down if selection is below visible area
        if self.selected_index >= self.scroll_offset + self._visible_height:
            self.scroll_offset = self.selected_index - self._visible_height + 1
    
    def _notify_select(self) -> None:
        """Call the on_select callback if set."""
        if self.on_select is not None and self.selected_index >= 0:
            self.on_select(self.selected_index, self.selected_item)
    
    def _notify_activate(self) -> None:
        """Call the on_activate callback if set."""
        if self.on_activate is not None and self.selected_index >= 0:
            self.on_activate(self.selected_index, self.selected_item)
    
    def _mark_dirty(self) -> None:
        """Mark the associated view as dirty."""
        if self._view is not None:
            ui_view_mark_dirty(self._view)
    
    def handle_key_event(self, key_type: int, rune: int, keysym: int, mods: int) -> int:
        """
        Handle a key event.
        
        Returns UI_CMD_REDRAW if the list was modified, UI_CMD_NONE otherwise.
        """
        # Handle keysyms (arrow keys, etc.)
        if key_type == LC_KT_KEYSYM:
            if keysym == LC_KEY_UP:
                return UI_CMD_REDRAW if self.select_prev() else UI_CMD_NONE
            if keysym == LC_KEY_DOWN:
                return UI_CMD_REDRAW if self.select_next() else UI_CMD_NONE
            if keysym == LC_KEY_HOME:
                return UI_CMD_REDRAW if self.select_first() else UI_CMD_NONE
            if keysym == LC_KEY_END:
                return UI_CMD_REDRAW if self.select_last() else UI_CMD_NONE
            if keysym == LC_KEY_PGUP:
                return UI_CMD_REDRAW if self.page_up() else UI_CMD_NONE
            if keysym == LC_KEY_PGDOWN:
                return UI_CMD_REDRAW if self.page_down() else UI_CMD_NONE
        
        # Handle character input
        if key_type == LC_KT_CHAR:
            # Enter activates
            if rune == ord('\n') or rune == ord('\r'):
                self._notify_activate()
                return UI_CMD_NONE
            
            # j/k vim-style navigation
            if rune == ord('j'):
                return UI_CMD_REDRAW if self.select_next() else UI_CMD_NONE
            if rune == ord('k'):
                return UI_CMD_REDRAW if self.select_prev() else UI_CMD_NONE
            
            # g/G for first/last
            if rune == ord('g'):
                return UI_CMD_REDRAW if self.select_first() else UI_CMD_NONE
            if rune == ord('G'):
                return UI_CMD_REDRAW if self.select_last() else UI_CMD_NONE
        
        return UI_CMD_NONE


def listbox_create(
    view_id: str,
    y: int,
    x: int,
    height: int,
    width: int,
    items: Optional[List[Any]] = None,
) -> tuple[UIView, ListBox]:
    """
    Create a ListBox with its associated UIView.
    
    Args:
        view_id: Unique identifier for the view
        y: Vertical position (row)
        x: Horizontal position (column)
        height: Height of the listbox
        width: Width of the listbox
        items: Initial list of items
    
    Returns:
        Tuple of (UIView, ListBox) for integration with UI runtime
    
    Usage:
        view, listbox = listbox_create("files", 5, 10, 15, 40)
        listbox.set_items(["file1.txt", "file2.txt"])
        listbox.on_activate = lambda idx, item: open_file(item)
        ui_view_add_child(root, view)
    """
    view = ui_view_create(
        view_id=view_id,
        y=y,
        x=x,
        height=height,
        width=width,
        focusable=True,
        panel=False,
        container=False,
        kind=UI_VIEWKIND_LISTBOX,
    )
    
    listbox = ListBox(
        id=view_id,
        items=items if items else [],
    )
    listbox._view = view
    listbox._visible_height = height
    
    view.user_data = listbox
    
    return view, listbox


def listbox_draw(view: UIView, has_focus: bool) -> int:
    """
    Draw a ListBox into its bound window.
    
    Args:
        view: The UIView containing the ListBox
        has_focus: Whether the listbox currently has focus
    
    Returns:
        0 on success, -1 on error
    """
    if view is None or view.bound_win is None:
        return -1
    
    if view.user_data is None:
        return -1
    
    listbox = view.user_data
    if not isinstance(listbox, ListBox):
        return -1
    
    win = view.bound_win
    height = view.content_rect.height
    width = view.content_rect.width
    
    if height <= 0 or width <= 0:
        return 0
    
    # Update visible height
    listbox._visible_height = height
    
    # Clear the area
    if lc_wfill(win, 0, 0, height, width, ' ', LC_ATTR_NONE) != 0:
        return -1
    
    # Draw items
    for row in range(height):
        item_index = listbox.scroll_offset + row
        
        if item_index >= len(listbox.items):
            break
        
        item = listbox.items[item_index]
        text = str(item) if item is not None else ""
        
        # Truncate to width
        if len(text) > width:
            text = text[:width - 3] + "..." if width > 3 else text[:width]
        
        # Determine attributes
        is_selected = (item_index == listbox.selected_index)
        if is_selected:
            attr = LC_ATTR_REVERSE
            if has_focus:
                attr |= LC_ATTR_BOLD
        else:
            attr = LC_ATTR_NONE
        
        # Draw the row
        lc_wmove(win, row, 0)
        
        # Fill entire row with attribute for selection highlight
        if is_selected:
            for col in range(width):
                if col < len(text):
                    lc_wput(win, ord(text[col]), attr)
                else:
                    lc_wput(win, ord(' '), attr)
        else:
            for ch in text:
                lc_wput(win, ord(ch), attr)
    
    return 0


def listbox_handle_event(view: UIView, ev: UIEvent) -> int:
    """
    Handle an event for a ListBox.
    
    Args:
        view: The UIView containing the ListBox
        ev: The event to handle
    
    Returns:
        Command code (UI_CMD_REDRAW if changed, UI_CMD_NONE otherwise)
    """
    if view is None or ev is None:
        return UI_CMD_NONE
    
    if view.user_data is None:
        return UI_CMD_NONE
    
    listbox = view.user_data
    if not isinstance(listbox, ListBox):
        return UI_CMD_NONE
    
    if ev.type != UI_EVENT_KEY:
        return UI_CMD_NONE
    
    if ev.key is None:
        return UI_CMD_NONE
    
    return listbox.handle_key_event(ev.key.type, ev.key.rune, ev.key.keysym, ev.key.mods)
