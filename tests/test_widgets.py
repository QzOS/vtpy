"""
Tests for the widgets module.

Tests InputField and ListBox widgets.
"""

import pytest

from widgets.input_field import InputField, input_field_create
from widgets.listbox import ListBox, listbox_create
from lc_keys import LC_KT_CHAR, LC_KT_KEYSYM, LC_KEY_LEFT, LC_KEY_RIGHT, LC_KEY_DOWN, LC_KEY_UP, LC_KEY_HOME, LC_KEY_END
from ui_event import UI_CMD_NONE, UI_CMD_REDRAW


class TestInputField:
    """Tests for InputField widget."""
    
    def test_input_field_creation(self):
        """Test basic InputField creation."""
        field = InputField(id='test', placeholder='Enter name...')
        assert field.id == 'test'
        assert field.placeholder == 'Enter name...'
        assert field.value == ''
        assert field.cursor_pos == 0
    
    def test_input_field_typing(self):
        """Test character input."""
        field = InputField(id='test')
        
        # Type 'Hello'
        assert field.handle_key_event(LC_KT_CHAR, ord('H'), 0, 0) == UI_CMD_REDRAW
        assert field.handle_key_event(LC_KT_CHAR, ord('e'), 0, 0) == UI_CMD_REDRAW
        assert field.handle_key_event(LC_KT_CHAR, ord('l'), 0, 0) == UI_CMD_REDRAW
        assert field.handle_key_event(LC_KT_CHAR, ord('l'), 0, 0) == UI_CMD_REDRAW
        assert field.handle_key_event(LC_KT_CHAR, ord('o'), 0, 0) == UI_CMD_REDRAW
        
        assert field.value == 'Hello'
        assert field.cursor_pos == 5
    
    def test_input_field_cursor_movement(self):
        """Test cursor movement with arrow keys."""
        field = InputField(id='test')
        field.set_value('Hello')
        
        # Move left
        assert field.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_LEFT, 0) == UI_CMD_REDRAW
        assert field.cursor_pos == 4
        
        # Move left again
        assert field.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_LEFT, 0) == UI_CMD_REDRAW
        assert field.cursor_pos == 3
        
        # Move right
        assert field.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_RIGHT, 0) == UI_CMD_REDRAW
        assert field.cursor_pos == 4
        
        # Home
        assert field.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_HOME, 0) == UI_CMD_REDRAW
        assert field.cursor_pos == 0
        
        # End
        assert field.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_END, 0) == UI_CMD_REDRAW
        assert field.cursor_pos == 5
    
    def test_input_field_backspace(self):
        """Test backspace deletion."""
        field = InputField(id='test')
        field.set_value('Hello')
        
        # Backspace as character
        assert field.handle_key_event(LC_KT_CHAR, 127, 0, 0) == UI_CMD_REDRAW
        assert field.value == 'Hell'
        assert field.cursor_pos == 4
    
    def test_input_field_max_length(self):
        """Test max length enforcement."""
        field = InputField(id='test', max_length=5)
        
        # Type exactly 5 characters
        for ch in 'Hello':
            field.handle_key_event(LC_KT_CHAR, ord(ch), 0, 0)
        
        assert field.value == 'Hello'
        assert len(field.value) == 5
        
        # Try to add more
        result = field.handle_key_event(LC_KT_CHAR, ord('!'), 0, 0)
        assert result == UI_CMD_NONE  # No change
        assert field.value == 'Hello'  # Still 5 chars
    
    def test_input_field_password_display(self):
        """Test password masking."""
        field = InputField(id='test', password=True)
        field.set_value('secret')
        
        display = field.get_display_text()
        assert display == '******'
        assert field.value == 'secret'  # Actual value unchanged
    
    def test_input_field_placeholder_display(self):
        """Test placeholder when empty."""
        field = InputField(id='test', placeholder='Enter name')
        
        # Empty shows placeholder
        assert field.get_display_text() == 'Enter name'
        
        # With value shows value
        field.set_value('John')
        assert field.get_display_text() == 'John'
    
    def test_input_field_on_change_callback(self):
        """Test on_change callback is called."""
        changes = []
        field = InputField(id='test', on_change=lambda v: changes.append(v))
        
        field.handle_key_event(LC_KT_CHAR, ord('a'), 0, 0)
        assert changes == ['a']
        
        field.handle_key_event(LC_KT_CHAR, ord('b'), 0, 0)
        assert changes == ['a', 'ab']
    
    def test_input_field_on_submit_callback(self):
        """Test on_submit callback is called on Enter."""
        submitted = []
        field = InputField(id='test', on_submit=lambda v: submitted.append(v))
        field.set_value('test value')
        
        # Enter key
        field.handle_key_event(LC_KT_CHAR, ord('\n'), 0, 0)
        assert submitted == ['test value']


class TestListBox:
    """Tests for ListBox widget."""
    
    def test_listbox_creation(self):
        """Test basic ListBox creation."""
        listbox = ListBox(id='test', items=['a', 'b', 'c'])
        assert listbox.id == 'test'
        assert listbox.items == ['a', 'b', 'c']
        assert listbox.selected_index == 0
        assert listbox.selected_item == 'a'
    
    def test_listbox_empty(self):
        """Test empty ListBox."""
        listbox = ListBox(id='test')
        assert listbox.items == []
        assert listbox.selected_index == -1
        assert listbox.selected_item is None
    
    def test_listbox_navigation_down(self):
        """Test down navigation."""
        listbox = ListBox(id='test', items=['a', 'b', 'c'])
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_DOWN, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 1
        assert listbox.selected_item == 'b'
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_DOWN, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 2
        assert listbox.selected_item == 'c'
        
        # At end, no change
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_DOWN, 0) == UI_CMD_NONE
        assert listbox.selected_index == 2
    
    def test_listbox_navigation_up(self):
        """Test up navigation."""
        listbox = ListBox(id='test', items=['a', 'b', 'c'])
        listbox.selected_index = 2
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_UP, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 1
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_UP, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 0
        
        # At start, no change
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_UP, 0) == UI_CMD_NONE
        assert listbox.selected_index == 0
    
    def test_listbox_home_end(self):
        """Test Home/End navigation."""
        listbox = ListBox(id='test', items=['a', 'b', 'c', 'd', 'e'])
        listbox.selected_index = 2
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_HOME, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 0
        
        assert listbox.handle_key_event(LC_KT_KEYSYM, 0, LC_KEY_END, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 4
    
    def test_listbox_vim_keys(self):
        """Test j/k vim-style navigation."""
        listbox = ListBox(id='test', items=['a', 'b', 'c'])
        
        # j = down
        assert listbox.handle_key_event(LC_KT_CHAR, ord('j'), 0, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 1
        
        # k = up
        assert listbox.handle_key_event(LC_KT_CHAR, ord('k'), 0, 0) == UI_CMD_REDRAW
        assert listbox.selected_index == 0
    
    def test_listbox_on_select_callback(self):
        """Test on_select callback."""
        selections = []
        listbox = ListBox(
            id='test',
            items=['a', 'b', 'c'],
            on_select=lambda idx, item: selections.append((idx, item))
        )
        
        listbox.select_next()
        assert selections == [(1, 'b')]
        
        listbox.select_next()
        assert selections == [(1, 'b'), (2, 'c')]
    
    def test_listbox_on_activate_callback(self):
        """Test on_activate callback on Enter."""
        activated = []
        listbox = ListBox(
            id='test',
            items=['a', 'b', 'c'],
            on_activate=lambda idx, item: activated.append((idx, item))
        )
        
        listbox.handle_key_event(LC_KT_CHAR, ord('\n'), 0, 0)
        assert activated == [(0, 'a')]
    
    def test_listbox_set_items(self):
        """Test replacing items."""
        listbox = ListBox(id='test', items=['a', 'b'])
        listbox.selected_index = 1
        
        listbox.set_items(['x', 'y', 'z'])
        assert listbox.items == ['x', 'y', 'z']
        assert listbox.selected_index == 0  # Reset to first
    
    def test_listbox_add_remove_item(self):
        """Test adding and removing items."""
        listbox = ListBox(id='test', items=['a', 'b'])
        
        listbox.add_item('c')
        assert listbox.items == ['a', 'b', 'c']
        
        listbox.remove_item(1)
        assert listbox.items == ['a', 'c']
    
    def test_listbox_clear(self):
        """Test clearing all items."""
        listbox = ListBox(id='test', items=['a', 'b', 'c'])
        listbox.selected_index = 2
        
        listbox.clear()
        assert listbox.items == []
        assert listbox.selected_index == -1


class TestInputFieldCreate:
    """Tests for input_field_create factory function."""
    
    def test_creates_view_and_field(self):
        """Test that factory creates both view and field."""
        view, field = input_field_create('test', 5, 10, 30)
        
        assert view is not None
        assert field is not None
        assert view.id == 'test'
        assert field.id == 'test'
        assert view.user_data is field
        assert field._view is view
    
    def test_view_has_correct_geometry(self):
        """Test view geometry matches parameters."""
        view, field = input_field_create('test', 5, 10, 30)
        
        assert view.frame_rect.y == 5
        assert view.frame_rect.x == 10
        assert view.frame_rect.width == 30
        assert view.frame_rect.height == 1  # Single line


class TestListBoxCreate:
    """Tests for listbox_create factory function."""
    
    def test_creates_view_and_listbox(self):
        """Test that factory creates both view and listbox."""
        view, listbox = listbox_create('test', 5, 10, 15, 40)
        
        assert view is not None
        assert listbox is not None
        assert view.id == 'test'
        assert listbox.id == 'test'
        assert view.user_data is listbox
        assert listbox._view is view
    
    def test_view_has_correct_geometry(self):
        """Test view geometry matches parameters."""
        view, listbox = listbox_create('test', 5, 10, 15, 40)
        
        assert view.frame_rect.y == 5
        assert view.frame_rect.x == 10
        assert view.frame_rect.width == 40
        assert view.frame_rect.height == 15
    
    def test_with_initial_items(self):
        """Test factory with initial items."""
        view, listbox = listbox_create('test', 0, 0, 10, 20, items=['a', 'b', 'c'])
        
        assert listbox.items == ['a', 'b', 'c']
        assert listbox.selected_index == 0
