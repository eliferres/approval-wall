"""The text rule: what a reader cannot see, and what a text reads as.

An approval message is only as honest as its least visible character. A
display that drops a byte-order mark turns "approval<U+FEFF> granted" into
"approval granted", so a check that passed the first and a reader who sees
the second disagree about what the text says. The rule here is to refuse such
text, never to strip it: stripping is what turns a forgery into the real
wording.

  hidden(ch, before)  a character a reader cannot see or that reorders text
  hidden_in(text)     the distinct hidden characters in a text, in order
  refusal(text)       why a text is refused, or None
  skeleton(text)      what a reader takes the text to say
  reads_as(text, ...) whether the text would read as a protected phrase
  marked(text, fmt)   every hidden character written out, nothing dropped

The look-alike table is short on purpose and is not the defence. A review of
an earlier version beat a longer list with letters from scripts nobody had
listed and with plain-ASCII rewording. What holds without any list is the
card's frame (card.py) and the entry grammar (entry.py); the checks here
are the first line, and refuse what they know.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Optional, Pattern, Sequence, Union

# Code points are written as numbers throughout: a tool that rewrites this
# file can turn an escape into the character itself, and an invisible
# character in the source is the very thing this module refuses.
HIDDEN_CATEGORIES = ("Cf", "Cc", "Co", "Cs", "Zl", "Zp")
# Invisible characters whose category is a letter or a mark, so no category
# test finds them: the combining grapheme joiner, the Hangul fillers, the
# Khmer inherent vowels and the Mongolian free variation selectors.
INVISIBLE = frozenset(map(chr, (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180F,
                                0x3164, 0xFFA0)))
# Unassigned code points Unicode already lists as default-ignorable, which a
# display draws as nothing once a font learns them: U+2065, U+FFF0 to U+FFF8,
# and the gaps of the tag block. U+E0000 slipped an earlier version.
IGNORABLE_RANGES = ((0x2065, 0x2065), (0xFFF0, 0xFFF8), (0xE0000, 0xE0FFF))
# Variation selectors (category Mn) draw as nothing and a run of them can
# spell out text no reader sees. U+FE0F is allowed only where it does its
# job: once, straight after a non-ASCII symbol, picking that symbol's emoji
# style. After a letter, or after another U+FE0F, it is hidden.
VARIATION_HIDDEN = ((0xFE00, 0xFE0E), (0xE0100, 0xE01EF))
EMOJI_STYLE = chr(0xFE0F)

# Look-alikes of the Latin letters and the # sign, after NFKC: Cyrillic,
# Greek, Armenian and a few Latin variants. Only the letters the protected
# phrases use. ASCII look-alikes (0 for o, I for l) stay distinct, since a
# monospace display tells them apart.
_LOOKALIKES = {
    "a": (0x0430, 0x0410, 0x03B1, 0x0391, 0x0251),
    "b": (0x044C, 0x042C, 0x0412, 0x03B2, 0x0392),
    "c": (0x0441, 0x0421, 0x03F2),
    "d": (0x0501,),
    "e": (0x0435, 0x0415, 0x03B5, 0x0395),
    "g": (0x0261,),
    "h": (0x04BB, 0x041D, 0x0397),
    "i": (0x0456, 0x0406, 0x03B9, 0x0399, 0x0131),
    "j": (0x0458, 0x0408, 0x03F3),
    "k": (0x043A, 0x041A, 0x03BA, 0x039A),
    "l": (0x04CF, 0x04C0),
    "m": (0x043C, 0x041C, 0x039C),
    "n": (0x043F, 0x0578, 0x03B7, 0x039D),
    "o": (0x043E, 0x041E, 0x03BF, 0x039F, 0x0585),
    "p": (0x0440, 0x0420, 0x03C1, 0x03A1),
    "q": (0x051B,),
    "r": (0x0433, 0x0280),
    "s": (0x0455, 0x0405),
    "t": (0x0442, 0x0422, 0x03C4, 0x03A4),
    "u": (0x057D, 0x03C5),
    "v": (0x0475, 0x0474, 0x03BD),
    "w": (0x051D, 0x03C9),
    "x": (0x0445, 0x0425, 0x03C7, 0x03A7),
    "y": (0x0443, 0x0423, 0x03A5),
    "#": (0x266F,),
}
CONFUSABLES = {cp: latin for latin, cps in _LOOKALIKES.items() for cp in cps}

# The default protected phrases: the words an approval bot's own notices use.
# A note written by a model must never read as one of them. Pass your own
# phrases to reads_as() and refusal() for your bot's wording.
NOTICE_WORDS = re.compile(
    r"approved\s+broker\s+request|broker\s+request\s+\S+\s+approved|approved\s+with\s+the\s+code"
    r"|approved\s+on\s+a\s+plain\s+yes|broker\s+approval|wrong\s+codes"
    r"|sends\s+(?:and\s+approvals\s+)?locked")
# The words a person replies with on an approval card, and an id. Read on the
# skeleton, so a Cyrillic "yes" counts too.
REPLY_WORDS = re.compile(r"\b(?:yes|no|send)\W+[0-9a-f]{6,}\b")

Phrase = Union[str, Pattern[str]]


def hidden(ch: str, before: str = "") -> bool:
    """Whether a reader cannot see ch, or ch reorders the text around it.

    The newline is the one control a text may hold. `before`, the character
    just ahead of ch, matters only for U+FE0F; without it U+FE0F is hidden.
    """
    if ch == "\n":
        return False
    if ch == EMOJI_STYLE:
        return not (before and ord(before) > 0x7F and unicodedata.category(before).startswith("S"))
    category = unicodedata.category(ch)
    return (ch in INVISIBLE or category in HIDDEN_CATEGORIES
            or category == "Cn" and any(lo <= ord(ch) <= hi for lo, hi in IGNORABLE_RANGES)
            or any(lo <= ord(ch) <= hi for lo, hi in VARIATION_HIDDEN))


def _with_before(text: str) -> Iterable:
    """Each character of the text with the one just ahead of it ("" for the first)."""
    return zip([""] + list(text), text)


def hidden_in(text: str) -> List[str]:
    """The distinct hidden characters in the text, in the order they first appear.

    NFKC neither makes nor removes one (the suite checks every code point on
    the running Python's Unicode), so a text and its NFKC form agree.
    """
    found: List[str] = []
    for before, ch in _with_before(text):
        if hidden(ch, before) and ch not in found:
            found.append(ch)
    return found


def names(chars: Sequence[str]) -> str:
    """"U+FEFF, U+200B": the first five code points, then "and more"."""
    return ", ".join("U+%04X" % ord(c) for c in chars[:5]) + (" and more" if len(chars) > 5 else "")


def skeleton(text: str) -> str:
    """What a reader takes the text to say: NFKC, hidden characters dropped,
    accents and other marks dropped (after NFD), look-alikes folded to Latin,
    case folded. Checks of shape run on this, so a fullwidth or Cyrillic copy
    of a phrase is caught with the phrase."""
    # The table is applied before NFKC too: NFKC turns the lunate sigma, which
    # looks like c, into a final sigma, which does not.
    text = unicodedata.normalize("NFKC", text.translate(CONFUSABLES))
    text = "".join(c for c in text if not hidden(c))
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) not in ("Mn", "Me"))
    return text.translate(CONFUSABLES).casefold()


def starts_header(line: str) -> bool:
    """The line reads as a markdown header once hidden characters and look-alikes go."""
    return skeleton(line).lstrip().startswith("#")


def has_marker(line: str) -> bool:
    """The line holds an HTML comment marker in its skeleton, so in its NFKC form too."""
    text = skeleton(line)
    return "<!--" in text or "-->" in text


def hidden_refusal(text: str) -> Optional[str]:
    """Why the text is refused for hidden characters, or None."""
    found = hidden_in(text)
    return "hidden or control characters (%s)" % names(found) if found else None


def _phrase(p: Phrase) -> Pattern[str]:
    """A plain phrase matches with any run of whitespace between its words."""
    if isinstance(p, str):
        return re.compile(r"\s+".join(re.escape(w) for w in skeleton(p).split()))
    return p


def reads_as(text: str, phrases: Iterable[Phrase] = (NOTICE_WORDS,)) -> Optional[str]:
    """What protected shape the text would read as once skeletonized, or None:
    a markdown header line, an HTML comment marker, a card's reply words with
    an id, or one of the phrases (plain strings, or patterns written for the
    skeleton's lower case)."""
    if any(starts_header(line) for line in text.split("\n")):
        return "a line starting with #"
    if has_marker(text):
        return "an HTML comment marker"
    shape = skeleton(text)
    if REPLY_WORDS.search(shape):
        return "a card's reply words (yes, no or send and an id)"
    for p in phrases:
        m = _phrase(p).search(shape)
        if m:
            return "a protected phrase (%s)" % " ".join(m.group(0).split())
    return None


def refusal(text: str, phrases: Iterable[Phrase] = (NOTICE_WORDS,)) -> Optional[str]:
    """Why a text is refused, or None: hidden characters first, then any
    protected shape it reads as."""
    return hidden_refusal(text) or reads_as(text, phrases)


def note_refusal(text: str) -> Optional[str]:
    """The note check in its original form: hidden characters, a header
    line, a comment marker, or the default notice words, in that order."""
    why = hidden_refusal(text)
    if why:
        return why
    if any(starts_header(line) for line in text.split("\n")):
        return "a line starting with #"
    if has_marker(text):
        return "an HTML comment marker"
    if NOTICE_WORDS.search(skeleton(text)):
        return "the words of the bot's own notices (approvals, code lockouts)"
    return None


def marked(text: str, fmt: str = "\\u{%04X}") -> str:
    """The text with each hidden character (the newline aside) written as
    fmt % its code point, for a display that must never drop a character."""
    return "".join(fmt % ord(c) if hidden(c, before) else c for before, c in _with_before(text))
