# Minimal UI event layer.
from dataclasses import dataclass
from typing import Optional

from lc_keys import (
    LCKey,
    LC_KT_CHAR,
    LC_KT_KEYSYM,
    LC_KEY_RESIZE,
)


UI_EVENT_NONE = 0
UI_EVENT_KEY = 1
UI_EVENT_COMMAND = 2
UI_EVENT_RESIZE = 3
UI_EVENT_FOCUS_IN = 4
UI_EVENT_FOCUS_OUT = 5


UI_CMD_NONE = 0
UI_CMD_QUIT = 1
UI_CMD_REDRAW = 2
UI_CMD_FOCUS_NEXT = 3
UI_CMD_FOCUS_PREV = 4
UI_CMD_ACTIVATE = 5


@dataclass
class UIEvent:
    type: int = UI_EVENT_NONE
    key: Optional[LCKey] = None
    command: int = UI_CMD_NONE
    width: int = 0
    height: int = 0


def _copy_key(key: Optional[LCKey]) -> Optional[LCKey]:
    if key is None:
        return None
    return LCKey(
        type=key.type,
        mods=key.mods,
        rune=key.rune,
        keysym=key.keysym,
    )


def ui_event_from_key(key: LCKey, width: int = 0, height: int = 0) -> UIEvent:
    ev = UIEvent()

    if key is None:
        return ev

    if key.type == LC_KT_KEYSYM and key.keysym == LC_KEY_RESIZE:
        ev.type = UI_EVENT_RESIZE
        ev.width = width
        ev.height = height
        return ev

    ev.type = UI_EVENT_KEY
    ev.key = _copy_key(key)
    return ev


def ui_focus_in_event() -> UIEvent:
    return UIEvent(type=UI_EVENT_FOCUS_IN)


def ui_focus_out_event() -> UIEvent:
    return UIEvent(type=UI_EVENT_FOCUS_OUT)


def ui_command_event(command: int) -> UIEvent:
    return UIEvent(type=UI_EVENT_COMMAND, command=command)


def ui_translate_command(ev: UIEvent) -> int:
    key = None

    if ev is None:
        return UI_CMD_NONE
    if ev.type != UI_EVENT_KEY:
        return UI_CMD_NONE

    key = ev.key
    if key is None:
        return UI_CMD_NONE

    if key.type == LC_KT_CHAR:
        if key.rune == ord('\t'):
            return UI_CMD_FOCUS_NEXT
        if key.rune in (ord('\n'), ord('\r')):
            return UI_CMD_ACTIVATE
        if key.rune in (ord('q'), ord('Q')):
            return UI_CMD_QUIT
        return UI_CMD_NONE

    if key.type == LC_KT_KEYSYM:
        return UI_CMD_NONE

    return UI_CMD_NONE
