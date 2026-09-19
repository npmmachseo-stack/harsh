import unittest

from keymap import (
    build_chords,
    resolve_combo_key,
    resolve_modifier,
    resolve_special,
    unicode_chord_sequence,
)
from linux_receiver import KeyInjector


class FakeDevice:
    def __init__(self):
        self.calls = []

    def emit(self, key, value):
        self.calls.append((key, value))


def identity_resolver(name):
    return name


class BuildChordsTest(unittest.TestCase):
    def test_lowercase_letter_no_shift(self):
        self.assertEqual(build_chords("a"), [["KEY_A"]])

    def test_uppercase_letter_needs_shift(self):
        self.assertEqual(build_chords("A"), [["KEY_LEFTSHIFT", "KEY_A"]])

    def test_digit(self):
        self.assertEqual(build_chords("5"), [["KEY_5"]])

    def test_shifted_symbol(self):
        # '!' is Shift+1 on a US QWERTY layout.
        self.assertEqual(build_chords("!"), [["KEY_LEFTSHIFT", "KEY_1"]])

    def test_unshifted_symbol(self):
        self.assertEqual(build_chords("-"), [["KEY_MINUS"]])

    def test_mixed_string(self):
        self.assertEqual(
            build_chords("Hi!"),
            [
                ["KEY_LEFTSHIFT", "KEY_H"],
                ["KEY_I"],
                ["KEY_LEFTSHIFT", "KEY_1"],
            ],
        )

    def test_newline_maps_to_enter(self):
        self.assertEqual(build_chords("\n"), [["KEY_ENTER"]])

    def test_non_ascii_uses_ibus_unicode_sequence(self):
        # U+0A85 = Gujarati letter A ('અ') -> hex codepoint "a85"
        self.assertEqual(
            build_chords("અ"),
            [
                ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_U"],
                ["KEY_A"],
                ["KEY_8"],
                ["KEY_5"],
                ["KEY_SPACE"],
            ],
        )


class UnicodeChordSequenceTest(unittest.TestCase):
    def test_ascii_codepoint(self):
        # 'A' = U+0041
        self.assertEqual(
            unicode_chord_sequence("A"),
            [
                ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_U"],
                ["KEY_4"],
                ["KEY_1"],
                ["KEY_SPACE"],
            ],
        )


class ResolversTest(unittest.TestCase):
    def test_resolve_special_known(self):
        self.assertEqual(resolve_special("backspace"), "KEY_BACKSPACE")

    def test_resolve_special_unknown(self):
        self.assertIsNone(resolve_special("nope"))

    def test_resolve_modifier(self):
        self.assertEqual(resolve_modifier("ctrl"), "KEY_LEFTCTRL")

    def test_resolve_combo_key_includes_modifiers_and_specials(self):
        self.assertEqual(resolve_combo_key("ctrl"), "KEY_LEFTCTRL")
        self.assertEqual(resolve_combo_key("escape"), "KEY_ESC")
        self.assertIsNone(resolve_combo_key("c"))  # matches receiver_wifi.py parity


class KeyInjectorTest(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.injector = KeyInjector(self.device, resolver=identity_resolver)

    def test_unicode_message(self):
        self.injector.inject({"type": "unicode", "value": "a"})
        self.assertEqual(self.device.calls, [("KEY_A", 1), ("KEY_A", 0)])

    def test_special_message(self):
        self.injector.inject({"type": "special", "value": "enter"})
        self.assertEqual(self.device.calls, [("KEY_ENTER", 1), ("KEY_ENTER", 0)])

    def test_special_message_unknown_is_noop(self):
        self.injector.inject({"type": "special", "value": "bogus"})
        self.assertEqual(self.device.calls, [])

    def test_combo_message(self):
        self.injector.inject({"type": "combo", "value": ["ctrl", "escape"]})
        self.assertEqual(
            self.device.calls,
            [("KEY_LEFTCTRL", 1), ("KEY_ESC", 1), ("KEY_ESC", 0), ("KEY_LEFTCTRL", 0)],
        )

    def test_modifiers_wrap_the_whole_message(self):
        self.injector.inject({"type": "unicode", "value": "a", "modifiers": ["shift"]})
        self.assertEqual(
            self.device.calls,
            [
                ("KEY_LEFTSHIFT", 1),
                ("KEY_A", 1),
                ("KEY_A", 0),
                ("KEY_LEFTSHIFT", 0),
            ],
        )

    def test_modifiers_released_even_if_type_unknown(self):
        self.injector.inject({"type": "bogus", "value": "x", "modifiers": ["ctrl"]})
        self.assertEqual(self.device.calls, [("KEY_LEFTCTRL", 1), ("KEY_LEFTCTRL", 0)])


if __name__ == "__main__":
    unittest.main()
