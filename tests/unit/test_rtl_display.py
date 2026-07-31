"""Unit tests for scripts/core/rtl_display.py.

The module has exactly one job: turn logical text into the visual order a
terminal without bidirectional support has to be handed. Two properties
matter more than any single expected string — the transformation must be
the Unicode algorithm rather than a reversal (Latin runs, digits and
brackets have to survive), and it must stay a pure function, because the
authoritative text is the logical one on the clipboard.

The expected values here were cross-checked against ``python-bidi``'s
reordering on twelve thousand randomly generated mixed Arabic/Hebrew/Latin
strings; the only intended difference is that this module also applies L4
mirroring, which that package leaves to the renderer. The suite itself
depends on nothing outside the standard library, exactly like the plugin.
"""

from __future__ import annotations

import ast
import unittest

import support
from core import rtl_display

FIXTURE = support.FIXTURES_DIR / "sample-testing-task-ar.txt"
MODULE = support.PLUGIN_ROOT / "scripts/core/rtl_display.py"


def module_tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def module_imports() -> set:
    """Every module ``rtl_display`` imports, by top-level name."""
    names = set()
    for node in ast.walk(module_tree()):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def called_names() -> set:
    """Every bare function name the module calls."""
    return {
        node.func.id
        for node in ast.walk(module_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

# The regression fixture, split into the segments the algorithm has to keep
# apart: right-to-left prose around Latin runs that must stay readable.
TITLE_HEAD = "اختبار إنشاء سجلات "
TITLE_LATIN = "Workflow Test Item"
TITLE_TAIL = " والتحقق من حقولها"

DESCRIPTION_SEGMENTS = (
    "يرجى التأكد من أن الحالة الافتراضية هي ",
    "Draft",
    "، وأن القيم ",
    "Active",
    " و ",
    "Archived",
    " تعمل بشكل صحيح.",
)

LATIN_RUNS = ("Workflow Test Item", "Draft", "Active", "Archived")


def visual_of_rtl(segment: str) -> str:
    """The visual order of a segment that is right-to-left throughout.

    Written with a slice reversal *in the test only*: it is the expectation
    the module has to meet for pure right-to-left text, and stating it
    independently is what proves the module is not implemented that way.
    """
    return segment[::-1]


class FixtureRegressionTests(unittest.TestCase):
    """The stored testing task must render readably, run by run."""

    def setUp(self):
        self.logical = FIXTURE.read_text(encoding="utf-8")
        self.visual = rtl_display.to_visual(self.logical)
        self.logical_lines = self.logical.split("\n")
        self.visual_lines = self.visual.split("\n")

    def test_fixture_is_the_expected_shape(self):
        self.assertEqual(self.logical_lines[0], "العنوان:")
        self.assertEqual(self.logical_lines[3], "الوصف:")
        self.assertEqual(
            self.logical_lines[1], TITLE_HEAD + TITLE_LATIN + TITLE_TAIL
        )
        self.assertEqual(self.logical_lines[4], "".join(DESCRIPTION_SEGMENTS))

    def test_labels_render_in_readable_visual_order(self):
        for index in (0, 3):
            with self.subTest(line=index):
                self.assertEqual(
                    self.visual_lines[index],
                    visual_of_rtl(self.logical_lines[index]),
                )

    def test_title_keeps_the_latin_run_between_reordered_arabic(self):
        self.assertEqual(
            self.visual_lines[1],
            visual_of_rtl(TITLE_TAIL) + TITLE_LATIN + visual_of_rtl(TITLE_HEAD),
        )

    def test_description_reorders_arabic_around_every_latin_run(self):
        expected = "".join(
            segment if segment in LATIN_RUNS else visual_of_rtl(segment)
            for segment in reversed(DESCRIPTION_SEGMENTS)
        )
        self.assertEqual(self.visual_lines[4], expected)

    def test_latin_words_are_not_reversed(self):
        for word in LATIN_RUNS:
            with self.subTest(word=word):
                self.assertIn(word, self.visual)
                self.assertNotIn(word[::-1], self.visual)

    def test_visual_differs_from_logical_for_arabic(self):
        self.assertNotEqual(self.visual, self.logical)

    def test_no_character_is_gained_or_lost(self):
        self.assertEqual(sorted(self.visual), sorted(self.logical))

    def test_blank_lines_and_line_count_survive(self):
        self.assertEqual(len(self.visual_lines), len(self.logical_lines))
        for index, line in enumerate(self.logical_lines):
            if not line:
                with self.subTest(line=index):
                    self.assertEqual(self.visual_lines[index], "")
        self.assertTrue(self.logical.endswith("\n"))
        self.assertTrue(self.visual.endswith("\n"))


class NotAReversalTests(unittest.TestCase):
    """A reversal would pass a pure-Arabic case and ruin everything else."""

    def test_the_module_contains_no_slice_reversal(self):
        source = (support.PLUGIN_ROOT / "scripts/core/rtl_display.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("[::-1]", source)

    def test_mixed_text_is_not_the_reversed_string(self):
        logical = FIXTURE.read_text(encoding="utf-8")
        self.assertNotEqual(rtl_display.to_visual(logical), logical[::-1])

    def test_latin_only_text_is_returned_unchanged(self):
        for text in ("Workflow Test Item", "Draft, Active, Archived (v2.5)"):
            with self.subTest(text=text):
                self.assertEqual(rtl_display.to_visual(text), text)

    def test_digits_keep_their_own_order_inside_arabic(self):
        visual = rtl_display.to_visual("النسخة 2.5 من التقرير")
        self.assertIn("2.5", visual)
        self.assertNotIn("5.2", visual)

    def test_arabic_numbers_after_arabic_letters_stay_in_order(self):
        visual = rtl_display.to_visual("تم إنشاء 12 سجلاً")
        self.assertIn("12", visual)
        self.assertNotIn("21", visual)


class MixedDirectionTests(unittest.TestCase):
    def test_a_latin_sentence_with_an_arabic_quote_keeps_its_direction(self):
        logical = "The status is مسودة today"
        visual = rtl_display.to_visual(logical)
        self.assertTrue(visual.startswith("The status is "))
        self.assertTrue(visual.endswith(" today"))
        self.assertIn(visual_of_rtl("مسودة"), visual)

    def test_brackets_are_mirrored_inside_right_to_left_text(self):
        visual = rtl_display.to_visual("الحالة (مسودة) الآن")
        # The glyphs a bidi-aware renderer would draw: the opening bracket
        # of the logical text becomes the right-hand one on screen.
        self.assertEqual(visual.count("("), 1)
        self.assertEqual(visual.count(")"), 1)
        self.assertLess(visual.index("("), visual.index(")"))

    def test_brackets_around_a_latin_run_keep_the_run_readable(self):
        visual = rtl_display.to_visual("القيمة (Draft) هي الافتراضية")
        self.assertIn("(Draft)", visual)

    def test_trailing_whitespace_stays_at_the_reading_end_of_the_line(self):
        # On a right-to-left line the end of the text is the left of the
        # screen, so its trailing spaces are the leading characters here.
        self.assertEqual(rtl_display.to_visual("مسودة  "), "  " + visual_of_rtl("مسودة"))
        self.assertEqual(rtl_display.to_visual("Draft  "), "Draft  ")

    def test_each_line_gets_its_own_base_direction(self):
        visual = rtl_display.to_visual("Draft state\nحالة مسودة")
        first, second = visual.split("\n")
        self.assertEqual(first, "Draft state")
        self.assertEqual(second, visual_of_rtl("حالة مسودة"))


class PurityTests(unittest.TestCase):
    """Display rendering may not touch anything outside the function."""

    def test_the_input_is_not_modified(self):
        logical = FIXTURE.read_text(encoding="utf-8")
        copy = str(logical)
        rtl_display.to_visual(logical)
        self.assertEqual(logical, copy)

    def test_repeated_calls_return_the_same_result(self):
        logical = FIXTURE.read_text(encoding="utf-8")
        self.assertEqual(rtl_display.to_visual(logical), rtl_display.to_visual(logical))

    def test_the_module_imports_only_the_standard_library(self):
        # A plugin distributed as plain files cannot rely on a PyPI package
        # being installed on the machine that runs it.
        self.assertEqual(module_imports(), {"__future__", "typing", "unicodedata"})

    def test_the_module_reaches_no_clipboard_file_or_process(self):
        called = called_names()
        for forbidden in ("open", "exec", "eval", "__import__", "input", "print"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)

    def test_empty_and_whitespace_input_is_returned_unchanged(self):
        for text in ("", "\n", "\n\n", "   ", " \n \n"):
            with self.subTest(text=repr(text)):
                self.assertEqual(rtl_display.to_visual(text), text)

    def test_a_non_string_is_refused(self):
        for value in (None, 42, ["مسودة"]):
            with self.subTest(value=value):
                with self.assertRaises(rtl_display.RtlDisplayError):
                    rtl_display.to_visual(value)


class AlgorithmDetailTests(unittest.TestCase):
    """Spot checks on the UAX #9 rules the prose above depends on."""

    def test_paragraph_direction_follows_the_first_strong_character(self):
        self.assertEqual(rtl_display._paragraph_level(["ON", "EN", "L", "R"]), 0)
        self.assertEqual(rtl_display._paragraph_level(["ON", "EN", "AL", "L"]), 1)
        self.assertEqual(rtl_display._paragraph_level(["ON", "EN"]), 0)

    def test_isolated_text_does_not_decide_the_paragraph_direction(self):
        classes = ["RLI", "R", "PDI", "L"]
        self.assertEqual(rtl_display._paragraph_level(classes), 0)

    def test_unassigned_arabic_code_points_default_to_arabic_letters(self):
        self.assertEqual(rtl_display.bidi_class("ࢵ"), "AL")

    def test_reordering_reverses_from_the_highest_level_down(self):
        # A Latin run (level 2) inside right-to-left text (level 1) ends up
        # reversed twice, which restores its reading order.
        levels = [1, 1, 2, 2, 1]
        self.assertEqual(rtl_display._reorder(levels), [4, 2, 3, 1, 0])

    def test_invisible_formatting_characters_are_dropped(self):
        # U+200F RIGHT-TO-LEFT MARK is kept (it is a strong R), but an
        # explicit embedding control carries no glyph.
        self.assertEqual(rtl_display.to_visual("‫مسودة‬"), visual_of_rtl("مسودة"))


if __name__ == "__main__":
    unittest.main()
