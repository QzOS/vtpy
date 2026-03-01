from dataclasses import dataclass

from lc_term import LC_ERR, LC_OK
from lc_input import LCInputSource, default_input
from lc_screen import lc, lc_check_resize


LC_KT_CHAR = 1
LC_KT_KEYSYM = 2

LC_MOD_SHIFT = 1
LC_MOD_ALT = 2
LC_MOD_CTRL = 4

# Keysyms. Keep these in a private range.
LC_KEY_RESIZE = 0x1000
LC_KEY_UP = 0x1001
LC_KEY_DOWN = 0x1002
LC_KEY_RIGHT = 0x1003
LC_KEY_LEFT = 0x1004
LC_KEY_HOME = 0x1005
LC_KEY_END = 0x1006
LC_KEY_PGUP = 0x1007
LC_KEY_PGDOWN = 0x1008
LC_KEY_INSERT = 0x1009
LC_KEY_DELETE = 0x100A
LC_KEY_BTAB = 0x100B

LC_KEY_F1 = 0x1011
LC_KEY_F2 = 0x1012
LC_KEY_F3 = 0x1013
LC_KEY_F4 = 0x1014
LC_KEY_F5 = 0x1015
LC_KEY_F6 = 0x1016
LC_KEY_F7 = 0x1017
LC_KEY_F8 = 0x1018
LC_KEY_F9 = 0x1019
LC_KEY_F10 = 0x101A
LC_KEY_F11 = 0x101B
LC_KEY_F12 = 0x101C
LC_KEY_F13 = 0x101D
LC_KEY_F14 = 0x101E
LC_KEY_F15 = 0x101F
LC_KEY_F16 = 0x1020
LC_KEY_F17 = 0x1021
LC_KEY_F18 = 0x1022
LC_KEY_F19 = 0x1023
LC_KEY_F20 = 0x1024

LC_KEY_SHIFT_UP = 0x1101
LC_KEY_SHIFT_DOWN = 0x1102
LC_KEY_SHIFT_RIGHT = 0x1103
LC_KEY_SHIFT_LEFT = 0x1104
LC_KEY_SHIFT_HOME = 0x1105
LC_KEY_SHIFT_END = 0x1106
LC_KEY_SHIFT_PGUP = 0x1107
LC_KEY_SHIFT_PGDOWN = 0x1108

LC_KEY_CTRL_UP = 0x1201
LC_KEY_CTRL_DOWN = 0x1202
LC_KEY_CTRL_RIGHT = 0x1203
LC_KEY_CTRL_LEFT = 0x1204


@dataclass
class LCKey:
    type: int = 0
    mods: int = 0
    rune: int = 0
    keysym: int = 0


class LCKeyParser:
    def __init__(self, source: LCInputSource) -> None:
        self.source = source

    def _decode_ss3(self) -> int:
        ch = self.source.read_byte()
        if ch is None:
            return -1

        table = {
            ord('F'): LC_KEY_END,
            ord('H'): LC_KEY_HOME,
            ord('A'): LC_KEY_UP,
            ord('B'): LC_KEY_DOWN,
            ord('C'): LC_KEY_RIGHT,
            ord('D'): LC_KEY_LEFT,
            ord('P'): LC_KEY_F1,
            ord('Q'): LC_KEY_F2,
            ord('R'): LC_KEY_F3,
            ord('S'): LC_KEY_F4,
            ord('p'): ord('0'),
            ord('q'): ord('1'),
            ord('r'): ord('2'),
            ord('s'): ord('3'),
            ord('t'): ord('4'),
            ord('u'): ord('5'),
            ord('v'): ord('6'),
            ord('w'): ord('7'),
            ord('x'): ord('8'),
            ord('y'): ord('9'),
            ord('n'): ord('.'),
            ord('m'): ord('-'),
            ord('M'): ord('\n'),
        }
        return table.get(ch, -1)

    def _decode_utf8(self, first: int) -> int:
        if first < 0x80:
            return first

        if 0xC2 <= first <= 0xDF:
            need = 1
            code = first & 0x1F
            minimum = 0x80
        elif 0xE0 <= first <= 0xEF:
            need = 2
            code = first & 0x0F
            minimum = 0x800
        elif 0xF0 <= first <= 0xF4:
            need = 3
            code = first & 0x07
            minimum = 0x10000
        else:
            return first

        cont = []
        for _ in range(need):
            nxt = self.source.read_byte()
            if nxt is None:
                return first
            if (nxt & 0xC0) != 0x80:
                self.source.unread_byte(nxt)
                return first
            cont.append(nxt)

        for nxt in cont:
            code = (code << 6) | (nxt & 0x3F)

        if code < minimum or 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
            return first

        return code

    def _apply_modifiers(self, base: int, shift_code: int, ctrl_code: int, mod_value: int) -> int:
        if mod_value < 0 or mod_value == 1:
            return base

        if mod_value in (5, 7):
            if ctrl_code:
                return ctrl_code
        elif mod_value in (6, 8):
            if ctrl_code:
                return ctrl_code
            if shift_code:
                return shift_code
        elif mod_value in (2, 4):
            if shift_code:
                return shift_code

        return base

    def _mods_from_xterm(self, mod_value: int) -> int:
        if mod_value < 0:
            return 0

        mods = 0
        bits = mod_value - 1
        if bits & 1:
            mods |= LC_MOD_SHIFT
        if bits & 2:
            mods |= LC_MOD_ALT
        if bits & 4:
            mods |= LC_MOD_CTRL
        return mods

    def _decode_csi(self) -> int:
        buf = bytearray()

        while len(buf) < 31:
            ch = self.source.read_byte()
            if ch is None:
                return -1
            buf.append(ch)
            if (ord('A') <= ch <= ord('Z')) or ch == ord('~'):
                break

        if not buf:
            return -1

        final = buf[-1]
        body = bytes(buf[:-1]).decode('ascii', 'ignore')

        params: list[int] = []
        current = 0
        have_number = False

        for c in body:
            if '0' <= c <= '9':
                current = current * 10 + (ord(c) - ord('0'))
                have_number = True
            elif c == ';':
                params.append(current if have_number else 0)
                current = 0
                have_number = False

        if have_number:
            params.append(current)

        mod_value = -1
        for candidate in reversed(params):
            if candidate > 1:
                mod_value = candidate
                break

        mods = self._mods_from_xterm(mod_value)

        if final == ord('A'):
            keysym = self._apply_modifiers(LC_KEY_UP, LC_KEY_SHIFT_UP, LC_KEY_CTRL_UP, mod_value)
        elif final == ord('B'):
            keysym = self._apply_modifiers(LC_KEY_DOWN, LC_KEY_SHIFT_DOWN, LC_KEY_CTRL_DOWN, mod_value)
        elif final == ord('C'):
            keysym = self._apply_modifiers(LC_KEY_RIGHT, LC_KEY_SHIFT_RIGHT, LC_KEY_CTRL_RIGHT, mod_value)
        elif final == ord('D'):
            keysym = self._apply_modifiers(LC_KEY_LEFT, LC_KEY_SHIFT_LEFT, LC_KEY_CTRL_LEFT, mod_value)
        elif final == ord('F'):
            keysym = self._apply_modifiers(LC_KEY_END, LC_KEY_SHIFT_END, 0, mod_value)
        elif final == ord('H'):
            keysym = self._apply_modifiers(LC_KEY_HOME, LC_KEY_SHIFT_HOME, 0, mod_value)
        elif final == ord('Z'):
            keysym = LC_KEY_BTAB
        elif final == ord('~'):
            if not params:
                return -1

            p0 = params[0]
            if p0 in (1, 7):
                keysym = self._apply_modifiers(LC_KEY_HOME, LC_KEY_SHIFT_HOME, 0, mod_value)
            elif p0 == 2:
                keysym = LC_KEY_INSERT
            elif p0 == 3:
                keysym = LC_KEY_DELETE
            elif p0 in (4, 8):
                keysym = self._apply_modifiers(LC_KEY_END, LC_KEY_SHIFT_END, 0, mod_value)
            elif p0 == 5:
                keysym = self._apply_modifiers(LC_KEY_PGUP, LC_KEY_SHIFT_PGUP, 0, mod_value)
            elif p0 == 6:
                keysym = self._apply_modifiers(LC_KEY_PGDOWN, LC_KEY_SHIFT_PGDOWN, 0, mod_value)
            elif p0 == 15:
                keysym = LC_KEY_F5
            elif p0 == 17:
                keysym = LC_KEY_F6
            elif p0 == 18:
                keysym = LC_KEY_F7
            elif p0 == 19:
                keysym = LC_KEY_F8
            elif p0 == 20:
                keysym = LC_KEY_F9
            elif p0 == 21:
                keysym = LC_KEY_F10
            elif p0 == 23:
                keysym = LC_KEY_F11
            elif p0 == 24:
                keysym = LC_KEY_F12
            elif p0 == 25:
                keysym = LC_KEY_F13
            elif p0 == 26:
                keysym = LC_KEY_F14
            elif p0 == 28:
                keysym = LC_KEY_F15
            elif p0 == 29:
                keysym = LC_KEY_F16
            elif p0 == 31:
                keysym = LC_KEY_F17
            elif p0 == 32:
                keysym = LC_KEY_F18
            elif p0 == 33:
                keysym = LC_KEY_F19
            elif p0 == 34:
                keysym = LC_KEY_F20
            else:
                return -1
        else:
            return -1

        return (mods << 24) | (keysym & 0x00FFFFFF)

    @staticmethod
    def _extract_mods_and_keysym(packed: int) -> tuple[int, int]:
        if packed < 0:
            return -1, 0
        mods = (packed >> 24) & 0xFF
        keysym = packed & 0x00FFFFFF
        return keysym, mods

    def readkey(self, out: LCKey) -> int:
        if out is None:
            return LC_ERR

        out.type = 0
        out.mods = 0
        out.rune = 0
        out.keysym = 0

        rc = lc_check_resize()
        if rc < 0:
            return LC_ERR
        if rc > 0:
            out.type = LC_KT_KEYSYM
            out.keysym = LC_KEY_RESIZE
            return LC_OK

        if lc.nodelay_on and not self.source.input_pending(0):
            return LC_ERR

        uc = self.source.read_byte()
        if uc is None:
            return LC_ERR

        c = uc

        if c != 0x1B:
            if c >= 0x80:
                c = self._decode_utf8(c)
            out.type = LC_KT_CHAR
            out.mods = 0
            out.rune = c
            out.keysym = 0
            return LC_OK

        to_ms = lc.escdelay_ms
        if lc.nodelay_on and to_ms < 0:
            to_ms = 0

        if to_ms < 0:
            uc = self.source.read_byte()
            if uc is None:
                out.type = LC_KT_CHAR
                out.mods = 0
                out.rune = 0x1B
                out.keysym = 0
                return LC_OK
        else:
            if not self.source.input_pending(to_ms):
                out.type = LC_KT_CHAR
                out.mods = 0
                out.rune = 0x1B
                out.keysym = 0
                return LC_OK
            uc = self.source.read_byte()
            if uc is None:
                return LC_ERR

        if uc == ord('['):
            packed = self._decode_csi()
            keysym, mods = self._extract_mods_and_keysym(packed)
            if keysym < 0:
                return LC_ERR
            out.type = LC_KT_KEYSYM
            out.mods = mods
            out.keysym = keysym
            out.rune = 0
            return LC_OK

        if uc == ord('O'):
            keysym = self._decode_ss3()
            if keysym < 0:
                return LC_ERR
            out.type = LC_KT_KEYSYM
            out.mods = 0
            out.keysym = keysym
            out.rune = 0
            return LC_OK

        if lc.meta_on:
            if uc >= 0x80:
                c = self._decode_utf8(uc)
            else:
                c = uc
            out.type = LC_KT_CHAR
            out.mods = LC_MOD_ALT
            out.rune = c
            out.keysym = 0
            return LC_OK

        self.source.unread_byte(uc)
        out.type = LC_KT_CHAR
        out.mods = 0
        out.rune = 0x1B
        out.keysym = 0
        return LC_OK


default_parser = LCKeyParser(default_input)


def lc_readkey(out: LCKey) -> int:
    return default_parser.readkey(out)


def lc_getch() -> int:
    key = LCKey()
    if lc_readkey(key) != LC_OK:
        return -1
    if key.type == LC_KT_CHAR:
        return key.rune
    return key.keysym
