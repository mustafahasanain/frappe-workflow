"""Visual-order rendering of bidirectional text, for terminal display only.

The Claude Code terminal draws a string strictly left to right: it never
applies the Unicode Bidirectional Algorithm itself, so logical-order Arabic
arrives on screen reading backwards. This module produces the *visual* order
that such a terminal has to be handed for the text to read correctly —
nothing else. The result is a display artefact:

* It is **never** copied to a clipboard, written to a file, or stored in the
  workflow state. The authoritative text is always the logical one.
* It must not be used for character counts, validation, or comparison.
* Pasting it into an application that *does* implement bidi would show the
  text reversed, which is exactly why the clipboard keeps the logical form.

### Why a hand-written implementation

The plugin is distributed as plain files (a marketplace clone or a
`git clone`), run by `bin/frappe-workflow` through the system `python3`.
There is no packaging step, no virtualenv, and no install hook, so a PyPI
dependency such as ``python-bidi`` would have to be present on every machine
by luck; on WSL and on native Ubuntu alike, `import bidi` is a
``ModuleNotFoundError`` waiting to happen. Vendoring it is not an option
either: it is LGPL-licensed, and this plugin is MIT. Every other module in
``scripts/core/`` is standard library only, and so is this one.

What is implemented here is the Unicode Bidirectional Algorithm (UAX #9)
itself — rules P2–P3, W1–W7, N0–N2, I1–I2 and L1–L4, driven by the bidi
classes that ``unicodedata`` already ships — not a reversal heuristic. That
distinction is what keeps ``Workflow Test Item`` readable inside an Arabic
sentence: a Latin run is reversed once as part of its own level and once
again with the surrounding right-to-left text, which restores it.

### Deliberate limitations

* **Explicit formatting codes** (``LRE``/``RLE``/``LRO``/``RLO``/``PDF``,
  X1–X8) are not interpreted; they are dropped with the other invisible
  ``BN`` characters, and directional isolates are treated as plain neutrals.
  Generated testing-task text contains none of them, and dropping them
  degrades to the correct rendering of the visible characters.
* **No Arabic shaping.** Contextual letter forms are left to the terminal's
  font stack, which is where they belong; reshaping here would double up
  with terminals that already shape.
* Paired-bracket (N0) and mirroring (L4) tables cover the brackets that
  occur in real prose, not the whole of ``BidiBrackets.txt``.

Each line is resolved independently as its own paragraph, so a blank line
stays blank and a line's own first strong character decides its direction.
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional, Sequence, Tuple

__all__ = ["to_visual", "line_to_visual", "RtlDisplayError"]


class RtlDisplayError(Exception):
    """Raised when a display transformation is asked for the impossible."""


# --------------------------------------------------------------------------
# Bidi classes
# --------------------------------------------------------------------------

# X9: invisible controls that carry no glyph. Not interpreted, not shown.
REMOVED_CLASSES = frozenset({"RLE", "LRE", "RLO", "LRO", "PDF", "BN"})

ISOLATE_CLASSES = frozenset({"LRI", "RLI", "FSI", "PDI"})
ISOLATE_INITIATORS = frozenset({"LRI", "RLI", "FSI"})

# BD13's "neutral or isolate formatting" set, the input to N0–N2.
NEUTRAL_CLASSES = frozenset({"B", "S", "WS", "ON"}) | ISOLATE_CLASSES

STRONG_CLASSES = frozenset({"L", "R", "AL"})

# Default bidi classes for unassigned code points (DerivedBidiClass.txt
# defaults). ``unicodedata.bidirectional`` returns "" for those, and the
# blocks below are the ones where the default is not L.
DEFAULT_R_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x0590, 0x05FF),
    (0x07C0, 0x085F),
    (0xFB1D, 0xFB4F),
    (0x10800, 0x10CFF),
    (0x10D40, 0x10EBF),
    (0x10F00, 0x10F2F),
    (0x10F70, 0x10FFF),
    (0x1E800, 0x1EC6F),
    (0x1ECC0, 0x1ECFF),
    (0x1ED50, 0x1EDFF),
    (0x1EF00, 0x1EFFF),
)
DEFAULT_AL_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x0600, 0x07BF),
    (0x0860, 0x08FF),
    (0xFB50, 0xFDCF),
    (0xFDF0, 0xFDFF),
    (0xFE70, 0xFEFF),
    (0x10D00, 0x10D3F),
    (0x10EC0, 0x10EFF),
    (0x10F30, 0x10F6F),
    (0x1EC70, 0x1ECBF),
    (0x1ED00, 0x1ED4F),
    (0x1EE00, 0x1EEFF),
)
DEFAULT_ET_RANGES: Tuple[Tuple[int, int], ...] = ((0x20A0, 0x20CF),)


def bidi_class(char: str) -> str:
    """Return the bidi class of *char*, defaulted for unassigned code points."""
    cls = unicodedata.bidirectional(char)
    if cls:
        return cls
    code = ord(char)
    for low, high in DEFAULT_AL_RANGES:
        if low <= code <= high:
            return "AL"
    for low, high in DEFAULT_R_RANGES:
        if low <= code <= high:
            return "R"
    for low, high in DEFAULT_ET_RANGES:
        if low <= code <= high:
            return "ET"
    return "L"


# --------------------------------------------------------------------------
# Bracket and mirroring tables
# --------------------------------------------------------------------------

# BD16 pairs, restricted to the brackets that appear in prose. Canonical
# equivalents (U+2329/U+232A vs U+3008/U+3009) are folded together, as BD16
# requires.
BRACKET_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
    ("⁅", "⁆"),  # square brackets with quill
    ("⁽", "⁾"),  # superscript parentheses
    ("₍", "₎"),  # subscript parentheses
    ("⌈", "⌉"),  # ceiling
    ("⌊", "⌋"),  # floor
    ("〈", "〉"),  # CJK angle brackets
    ("《", "》"),  # CJK double angle brackets
    ("（", "）"),  # fullwidth parentheses
    ("［", "］"),  # fullwidth square brackets
    ("｛", "｝"),  # fullwidth curly brackets
)

CANONICAL_BRACKETS = {"〈": "〈", "〉": "〉"}

OPEN_TO_CLOSE = {opening: closing for opening, closing in BRACKET_PAIRS}
CLOSING_BRACKETS = frozenset(closing for _opening, closing in BRACKET_PAIRS)

# L4: characters whose glyph is mirrored when displayed in a right-to-left
# run. ``unicodedata.mirrored`` says *whether* a character mirrors; the
# mapping itself is not in the standard library, so the common pairs live
# here.
_MIRROR_SOURCES: Tuple[Tuple[str, str], ...] = BRACKET_PAIRS + (
    ("<", ">"),
    ("«", "»"),  # guillemets
    ("‹", "›"),  # single guillemets
    ("≤", "≥"),  # less/greater than or equal
    ("≪", "≫"),  # much less/greater than
    ("⟨", "⟩"),  # mathematical angle brackets
    ("⦅", "⦆"),  # white parentheses
    ("〈", "〉"),  # deprecated angle brackets (canonically U+3008/U+3009)
)

MIRROR_MAP = {}
for _left, _right in _MIRROR_SOURCES:
    MIRROR_MAP[_left] = _right
    MIRROR_MAP[_right] = _left


def _canonical(char: str) -> str:
    return CANONICAL_BRACKETS.get(char, char)


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def to_visual(text: str) -> str:
    """Return *text* reordered for display on a terminal that has no bidi.

    Every line is resolved on its own, so a line's first strong character
    decides its base direction and blank lines survive untouched. The input
    string is never modified, no character is added or removed apart from
    invisible directional controls, and nothing outside this module is
    touched: no clipboard, no file, no subprocess.
    """
    if not isinstance(text, str):
        raise RtlDisplayError(f"expected a string, got {type(text).__name__}")
    # split/join on "\n" round-trips exactly: blank lines, CRLF carriage
    # returns, and a trailing newline all keep their place.
    return "\n".join(line_to_visual(line) for line in text.split("\n"))


def line_to_visual(line: str) -> str:
    """Return one line in visual order (see :func:`to_visual`)."""
    if not isinstance(line, str):
        raise RtlDisplayError(f"expected a string, got {type(line).__name__}")
    if not line.strip():
        return line

    chars = [char for char in line if bidi_class(char) not in REMOVED_CLASSES]
    if not chars:
        return ""

    original = tuple(bidi_class(char) for char in chars)
    classes = list(original)

    paragraph_level = _paragraph_level(classes)
    _resolve_weak(classes, paragraph_level)
    _resolve_brackets(chars, classes, original, paragraph_level)
    _resolve_neutrals(classes, paragraph_level)
    levels = _resolve_implicit(classes, paragraph_level)
    _reset_whitespace_levels(original, levels, paragraph_level)

    rendered = []
    for index in _reorder(levels):
        char = chars[index]
        if levels[index] % 2 and unicodedata.mirrored(char):
            char = MIRROR_MAP.get(char, char)  # L4
        rendered.append(char)
    return "".join(rendered)


# --------------------------------------------------------------------------
# P2–P3: the base direction of the line
# --------------------------------------------------------------------------

def _paragraph_level(classes: Sequence[str]) -> int:
    """Return 1 when the first strong character is right-to-left, else 0."""
    depth = 0
    for cls in classes:
        if cls in ISOLATE_INITIATORS:
            depth += 1
        elif cls == "PDI":
            depth = max(depth - 1, 0)
        elif depth == 0:
            if cls in ("R", "AL"):
                return 1
            if cls == "L":
                return 0
    return 0


def _embedding_direction(level: int) -> str:
    return "R" if level % 2 else "L"


def _resolved_direction(cls: str) -> Optional[str]:
    """Map a resolved class to the direction the N rules compare (EN/AN → R)."""
    if cls == "L":
        return "L"
    if cls in ("R", "EN", "AN"):
        return "R"
    return None


# --------------------------------------------------------------------------
# W1–W7: weak types
# --------------------------------------------------------------------------

def _resolve_weak(classes: List[str], paragraph_level: int) -> None:
    sos = eos = _embedding_direction(paragraph_level)
    count = len(classes)

    # W1: a combining mark takes the type of the character it sits on.
    previous = sos
    for index, cls in enumerate(classes):
        if cls == "NSM":
            classes[index] = "ON" if previous in ISOLATE_CLASSES else previous
        previous = classes[index]

    # W2: a European number after an Arabic letter is an Arabic number.
    strong = sos
    for index, cls in enumerate(classes):
        if cls in STRONG_CLASSES:
            strong = cls
        elif cls == "EN" and strong == "AL":
            classes[index] = "AN"

    # W3: Arabic letters are plain right-to-left from here on.
    for index, cls in enumerate(classes):
        if cls == "AL":
            classes[index] = "R"

    # W4: a single separator between two numbers joins them.
    for index in range(1, count - 1):
        cls = classes[index]
        before, after = classes[index - 1], classes[index + 1]
        if cls == "ES" and before == "EN" and after == "EN":
            classes[index] = "EN"
        elif cls == "CS" and before == after and before in ("EN", "AN"):
            classes[index] = before

    # W5: a run of terminators adjacent to a European number joins it.
    index = 0
    while index < count:
        if classes[index] != "ET":
            index += 1
            continue
        end = index
        while end < count and classes[end] == "ET":
            end += 1
        before = classes[index - 1] if index else sos
        after = classes[end] if end < count else eos
        if "EN" in (before, after):
            for position in range(index, end):
                classes[position] = "EN"
        index = end

    # W6: whatever separators and terminators are left are neutral.
    for index, cls in enumerate(classes):
        if cls in ("ET", "ES", "CS"):
            classes[index] = "ON"

    # W7: a European number after a Latin letter is left-to-right.
    strong = sos
    for index, cls in enumerate(classes):
        if cls in ("L", "R"):
            strong = cls
        elif cls == "EN" and strong == "L":
            classes[index] = "L"


# --------------------------------------------------------------------------
# N0: paired brackets
# --------------------------------------------------------------------------

def _bracket_pairs(chars: Sequence[str], classes: Sequence[str]) -> List[Tuple[int, int]]:
    """Return the matched bracket pairs of the line, per BD16."""
    stack: List[Tuple[str, int]] = []
    pairs: List[Tuple[int, int]] = []
    for index, char in enumerate(chars):
        if classes[index] != "ON":
            continue
        closing = OPEN_TO_CLOSE.get(_canonical(char))
        if closing is not None:
            if len(stack) == 63:  # BD16 stops at a full stack.
                break
            stack.append((closing, index))
            continue
        if _canonical(char) in CLOSING_BRACKETS:
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth][0] == _canonical(char):
                    pairs.append((stack[depth][1], index))
                    del stack[depth:]
                    break
    pairs.sort()
    return pairs


def _resolve_brackets(
    chars: Sequence[str],
    classes: List[str],
    original: Sequence[str],
    paragraph_level: int,
) -> None:
    embedding = _embedding_direction(paragraph_level)
    opposite = "L" if embedding == "R" else "R"
    sos = embedding

    for opening, closing in _bracket_pairs(chars, classes):
        inside = {
            _resolved_direction(classes[index])
            for index in range(opening + 1, closing)
        }
        inside.discard(None)
        if not inside:
            continue  # No strong text between them: they stay neutral (N0 d).
        if embedding in inside:
            resolved = embedding
        else:
            preceding = sos
            for index in range(opening - 1, -1, -1):
                direction = _resolved_direction(classes[index])
                if direction:
                    preceding = direction
                    break
            resolved = opposite if preceding == opposite else embedding
        classes[opening] = resolved
        classes[closing] = resolved
        # N0's closing note: combining marks on a bracket follow it.
        for position in (opening, closing):
            index = position + 1
            while index < len(classes) and original[index] == "NSM":
                classes[index] = resolved
                index += 1


# --------------------------------------------------------------------------
# N1–N2: neutrals
# --------------------------------------------------------------------------

def _resolve_neutrals(classes: List[str], paragraph_level: int) -> None:
    embedding = sos = eos = _embedding_direction(paragraph_level)
    count = len(classes)
    index = 0
    while index < count:
        if classes[index] not in NEUTRAL_CLASSES:
            index += 1
            continue
        end = index
        while end < count and classes[end] in NEUTRAL_CLASSES:
            end += 1
        before = _resolved_direction(classes[index - 1]) if index else sos
        after = _resolved_direction(classes[end]) if end < count else eos
        # N1 when both sides agree, N2 (the embedding direction) otherwise.
        resolved = before if before == after and before is not None else embedding
        for position in range(index, end):
            classes[position] = resolved
        index = end


# --------------------------------------------------------------------------
# I1–I2, L1–L2: levels and reordering
# --------------------------------------------------------------------------

def _resolve_implicit(classes: Sequence[str], paragraph_level: int) -> List[int]:
    levels = []
    for cls in classes:
        if paragraph_level % 2 == 0:
            if cls == "R":
                levels.append(paragraph_level + 1)
            elif cls in ("AN", "EN"):
                levels.append(paragraph_level + 2)
            else:
                levels.append(paragraph_level)
        else:
            if cls in ("L", "AN", "EN"):
                levels.append(paragraph_level + 1)
            else:
                levels.append(paragraph_level)
    return levels


def _reset_whitespace_levels(
    original: Sequence[str], levels: List[int], paragraph_level: int
) -> None:
    """L1: separators, and the whitespace before them or at the end of the line."""
    trailing = True
    for index in range(len(levels) - 1, -1, -1):
        cls = original[index]
        if cls in ("S", "B"):
            levels[index] = paragraph_level
            trailing = True
        elif cls == "WS" or cls in ISOLATE_CLASSES:
            if trailing:
                levels[index] = paragraph_level
        else:
            trailing = False


def _reorder(levels: Sequence[int]) -> List[int]:
    """L2: reverse each level's runs, from the highest level down."""
    order = list(range(len(levels)))
    odd_levels = [level for level in levels if level % 2]
    if not odd_levels:
        return order
    highest = max(levels)
    lowest_odd = min(odd_levels)
    for level in range(highest, lowest_odd - 1, -1):
        index = 0
        while index < len(order):
            if levels[order[index]] < level:
                index += 1
                continue
            end = index
            while end < len(order) and levels[order[end]] >= level:
                end += 1
            order[index:end] = reversed(order[index:end])
            index = end
    return order
