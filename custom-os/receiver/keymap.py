"""
Pure keymap/protocol logic for the Linux appliance receiver.

Kept free of any dependency on the `uinput` module (or a real /dev/uinput
device) so it can be unit tested on any machine, including ones that
aren't the appliance itself.

Wire protocol (matches android-app/.../MainActivity.kt and
desktop-receiver/receiver_wifi.py exactly):

    newline-delimited JSON objects, each shaped like:
        {"type": "unicode" | "key", "value": "<text>", "modifiers": [...]}
        {"type": "special", "value": "<name>", "modifiers": [...]}
        {"type": "combo", "value": ["<name>", ...], "modifiers": [...]}

Unlike Windows' KEYEVENTF_UNICODE, the Linux input layer has no "type this
codepoint" primitive: a virtual keyboard can only emit key events. So:
  - ASCII text is typed by emitting the matching key (+ Shift) on a
    US QWERTY layout.
  - Non-ASCII text (Gujarati, Hindi, Tamil, Arabic, CJK, ...) is typed
    using the IBus/GTK "Unicode code point" method: Ctrl+Shift+U, the
    codepoint in hex, then Space. This is understood by the focused
    application whenever an IBus-based input method is active, which is
    the common default on Linux desktops; apps without IBus support won't
    receive non-ASCII characters.
"""

import string

_LETTER_MAP = {c: (f"KEY_{c.upper()}", c.isupper()) for c in string.ascii_letters}
_DIGIT_MAP = {d: (f"KEY_{d}", False) for d in string.digits}

_SYMBOL_UNSHIFTED = {
    "`": "GRAVE", "-": "MINUS", "=": "EQUAL", "[": "LEFTBRACE", "]": "RIGHTBRACE",
    "\\": "BACKSLASH", ";": "SEMICOLON", "'": "APOSTROPHE", ",": "COMMA",
    ".": "DOT", "/": "SLASH", " ": "SPACE",
}
_SYMBOL_SHIFTED = {
    "~": "GRAVE", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "_": "MINUS", "+": "EQUAL",
    "{": "LEFTBRACE", "}": "RIGHTBRACE", "|": "BACKSLASH", ":": "SEMICOLON",
    '"': "APOSTROPHE", "<": "COMMA", ">": "DOT", "?": "SLASH",
}

ASCII_MAP = {}
ASCII_MAP.update(_LETTER_MAP)
ASCII_MAP.update(_DIGIT_MAP)
for _ch, _name in _SYMBOL_UNSHIFTED.items():
    ASCII_MAP[_ch] = (f"KEY_{_name}", False)
for _ch, _name in _SYMBOL_SHIFTED.items():
    ASCII_MAP[_ch] = (f"KEY_{_name}", True)

_CONTROL_MAP = {"\n": "KEY_ENTER", "\r": "KEY_ENTER", "\t": "KEY_TAB"}

_HEX_DIGIT_KEYS = {
    **{str(d): f"KEY_{d}" for d in range(10)},
    "a": "KEY_A", "b": "KEY_B", "c": "KEY_C", "d": "KEY_D", "e": "KEY_E", "f": "KEY_F",
}

SPECIAL_KEYS = {
    "backspace": "KEY_BACKSPACE", "tab": "KEY_TAB", "enter": "KEY_ENTER", "escape": "KEY_ESC",
    "space": "KEY_SPACE", "delete": "KEY_DELETE",
    "left": "KEY_LEFT", "up": "KEY_UP", "right": "KEY_RIGHT", "down": "KEY_DOWN",
    "home": "KEY_HOME", "end": "KEY_END", "pageup": "KEY_PAGEUP", "pagedown": "KEY_PAGEDOWN",
    **{f"f{i}": f"KEY_F{i}" for i in range(1, 13)},
}

MODIFIER_KEYS = {
    "shift": "KEY_LEFTSHIFT", "ctrl": "KEY_LEFTCTRL", "alt": "KEY_LEFTALT", "meta": "KEY_LEFTMETA",
}

# What "combo" values (e.g. ["ctrl", "escape"]) may reference. Matches the
# VK_MAP lookup used by receiver_wifi.py's combo handling.
_COMBO_KEYS = {**SPECIAL_KEYS, **MODIFIER_KEYS}


def resolve_ascii(char):
    """Return (uinput key name, needs_shift) for a single ASCII char, or None."""
    return ASCII_MAP.get(char)


def resolve_special(name):
    return SPECIAL_KEYS.get(name)


def resolve_modifier(name):
    return MODIFIER_KEYS.get(name)


def resolve_combo_key(name):
    return _COMBO_KEYS.get(name)


def unicode_chord_sequence(char):
    """Chords to type one non-ASCII char via the IBus Unicode-codepoint method."""
    codepoint_hex = format(ord(char), "x")
    chords = [["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_U"]]
    for digit in codepoint_hex:
        chords.append([_HEX_DIGIT_KEYS[digit]])
    chords.append(["KEY_SPACE"])
    return chords


def build_chords(text):
    """Turn arbitrary text into a list of chords (each a list of key names,
    pressed together then released in reverse order)."""
    chords = []
    for ch in text:
        entry = resolve_ascii(ch)
        if entry:
            key, shift = entry
            chords.append(["KEY_LEFTSHIFT", key] if shift else [key])
            continue
        control_key = _CONTROL_MAP.get(ch)
        if control_key:
            chords.append([control_key])
            continue
        chords.extend(unicode_chord_sequence(ch))
    return chords


def all_key_names():
    """Every uinput key name this module can ever emit (for device capabilities)."""
    names = {key for key, _ in ASCII_MAP.values()}
    names.update(_CONTROL_MAP.values())
    names.update(SPECIAL_KEYS.values())
    names.update(MODIFIER_KEYS.values())
    names.update({"KEY_LEFTSHIFT", "KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_LEFTMETA", "KEY_U", "KEY_SPACE"})
    return sorted(names)
