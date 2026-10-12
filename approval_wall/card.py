"""The approval card: a frame no text inside it can imitate.

A card shows a person what they are about to approve, then asks for a reply.
Everything between the two rule lines came from someone else (a model, a
form, an inbound message), so none of it may pass as the card's own lines:

- every body line, blank ones included, starts with a gutter mark, so no body
  line can sit flush with the frame or push a fake footer out of view;
- the rule line's glyphs, and runs of box-drawing and block characters, are
  refused inside the body and every field;
- every body line is wrapped to the card's width before the gutter goes on,
  so a long line never wraps on the phone into a continuation with no
  gutter, where it could draw a rule or a footer flush with the frame;
- a run of three or more spaces is shown as a mark naming its length, since a
  long run wraps on a phone and puts the words after it on a line of their own;
- the one-line fields refuse anything that could end their line or change
  what they say once a client decodes them;
- the body is cut to the transport's limit on UTF-16 units, the unit Telegram
  and JavaScript count in, and the frame is never cut: the head stays in the
  first piece, the release line ends the last.

Pure rendering: the caller supplies the id and the expiry text, and sends the
pieces. A card is releasable only when every piece arrived.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, fields
from typing import Iterator, List, Optional

from .text import REPLY_WORDS, hidden_refusal, skeleton

RULE = chr(0x2014) * 4                       # four em dashes
# A left-to-right mark keeps a right-to-left body line from flipping the bar
# to the far side, then a heavy vertical bar and a space.
GUTTER = chr(0x200E) + chr(0x2503) + " "
LIMIT = 4000                                 # Telegram's message cap is 4096; leave room for its own wrapping
# The characters that look blank: whitespace plus the no-break and fixed-width spaces.
BLANKS = "".join(map(chr, (0x00A0, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007,
                           0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000, 0xFEFF)))
SPACE_RUN = re.compile("[\\s%s]{3,}" % BLANKS)
SPACE_MARK = chr(0x27E8) + "%d spaces" + chr(0x27E9)
INDENT_KEPT = 8
WIDTH = 36                                   # characters per shown line, the gutter's two included
MIN_WIDTH = 20
ID = re.compile(r"[0-9a-f]{6,32}")
# An RFC 2047 encoded word: a mail client shows the decoded text, the card would show this.
ENCODED_WORD = re.compile(r"=\?[^?\s]+\?[bBqQ]\?[^?\s]*\?=")
# An HTML character reference: a transport in HTML mode turns &#x2014; into the rule's glyph.
ENTITY = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);?")
# Two or more dash glyphs in a row, after NFKC: the em dash, the horizontal
# bar, and the two- and three-em dashes, so a body cannot draw the rule.
RULE_GLYPHS = re.compile("[%s]{2,}" % "".join(map(chr, (0x2014, 0x2015, 0x2E3A, 0x2E3B))))
# Three or more box-drawing or block-element glyphs in a row (U+2500 to
# U+259F), after NFKC: a run of them draws a line as well as the dashes do.
LINE_DRAWING = re.compile("[%s-%s]{3,}" % (chr(0x2500), chr(0x259F)))
ONE_LINE = ("title", "sender", "sender_name", "recipient", "subject", "author", "expires")
NAMES = ("sender_name", "author")


class Refused(ValueError):
    """The card cannot be shown as given; the message says which field and why."""


def units(text: str) -> int:
    """Length in UTF-16 code units: two for a character outside the BMP."""
    return len(text) + sum(1 for c in text if ord(c) > 0xFFFF)


def _draws_rule(text: str) -> bool:
    return bool(RULE_GLYPHS.search(unicodedata.normalize("NFKC", text)))


def _draws_line(text: str) -> bool:
    return bool(LINE_DRAWING.search(unicodedata.normalize("NFKC", text)))


def spaces_shown(line: str, indent: int = INDENT_KEPT) -> str:
    """Each run of 3 or more blank characters becomes one mark naming its
    length, except a leading run of up to `indent`, so an indented list still
    reads. Display only: the text sent is never changed."""
    lead = len(line) - len(line.lstrip(" "))
    keep = lead if lead <= indent else 0
    return line[:keep] + SPACE_RUN.sub(lambda m: SPACE_MARK % len(m.group(0)), line[keep:])


def one_line_refusal(key: str, value: str) -> Optional[str]:
    """Why a one-line field is refused, or None. An empty field is left out of the card."""
    if not value:
        return None
    if value.splitlines() not in ([], [value]):
        return "%s holds a line break, and the card shows it on one line" % key
    why = hidden_refusal(value)
    if why:
        return "%s holds %s" % (key, why)
    if SPACE_RUN.search(value):
        return "%s holds a run of 3 or more spaces, which can push words onto a line of their own" % key
    if ENCODED_WORD.search(value):
        return "%s holds an encoded word (=?charset?...?=), which a mail client shows decoded" % key
    if ENTITY.search(value):
        return "%s holds an HTML character reference, which an HTML transport shows decoded" % key
    if _draws_rule(value):
        return "%s holds the card's rule glyphs" % key
    if _draws_line(value):
        return "%s holds a run of 3 or more line-drawing characters (U+2500 to U+259F)" % key
    shape = skeleton(value)
    if REPLY_WORDS.search(shape):
        return "%s holds the card's own reply words (yes, no or send and an id)" % key
    if key in NAMES and ("@" in shape or not any(c.isalpha() for c in shape)):
        return "%s reads as a number or an address, not a name" % key
    return None


@dataclass(frozen=True)
class Card:
    """One approval card. `id` is the caller's (6 to 32 lowercase hex
    characters) and `expires` its text, as in "in 60 minutes (14:05 UTC)".
    `width` is the most characters a shown body line holds, the gutter's two
    included: a phone narrower than that wraps the card's lines itself."""
    id: str
    expires: str
    body: str
    title: str = "Ready to send"
    sender: str = ""
    sender_name: str = ""
    recipient: str = ""
    subject: str = ""
    author: str = ""
    width: int = WIDTH

    def refusal(self) -> Optional[str]:
        """Why this card cannot be shown, or None."""
        if not ID.fullmatch(self.id):
            return "id must be 6 to 32 lowercase hex characters"
        if isinstance(self.width, bool) or not isinstance(self.width, int) or self.width < MIN_WIDTH:
            return "width must be a whole number of at least %d" % MIN_WIDTH
        for f in fields(self):
            if f.name != "width" and not isinstance(getattr(self, f.name), str):
                return "%s must be text" % f.name
        if not self.title or not self.expires:
            return "title and expires must not be empty"
        for key in ONE_LINE:
            why = one_line_refusal(key, getattr(self, key))
            if why:
                return why
        why = hidden_refusal(self.body)
        if why:
            return "body holds " + why
        if _draws_rule(self.body):
            return "body holds the card's rule glyphs"
        if _draws_line(self.body):
            return "body holds a run of 3 or more line-drawing characters (U+2500 to U+259F)"
        return None

    def head(self) -> List[str]:
        lines = [self.title]
        if self.sender_name:
            lines.append("From: %s (%s)" % (self.sender_name, self.sender) if self.sender
                         else "From: " + self.sender_name)
        elif self.sender:
            lines.append("From: " + self.sender)
        if self.recipient:
            lines.append("To: " + self.recipient)
        if self.subject:
            lines.append("Subject: " + self.subject)
        return lines + [RULE]

    def foot(self) -> List[str]:
        lines = [RULE]
        if self.author:
            lines.append("Written by: " + self.author)
        # The expiry and the release on lines of their own, the release split
        # at its comma: with an id of up to 12 characters and an expiry of up to
        # 26, no line the card writes itself is wider than 36 characters.
        return lines + ["Expires %s." % self.expires,
                        'Reply "yes %s" to approve,' % self.id, '"no %s" to drop.' % self.id]

    def _fits(self, limit: int) -> bool:
        return (units("\n".join(self.head())) <= limit and units("\n".join(self.foot())) <= limit
                and units(GUTTER) + 2 <= limit)

    def is_whole(self, limit: int = LIMIT) -> bool:
        """Whether the card renders at this limit with its frame whole: every
        field passes, and the head and the footer each fit in one piece."""
        return self.refusal() is None and self._fits(limit)

    def render(self, limit: int = LIMIT) -> List[str]:
        """The card as pieces of at most `limit` UTF-16 units each, in order.
        Raises Refused when a field is refused or the frame cannot fit."""
        why = self.refusal()
        if why:
            raise Refused(why)
        if not self._fits(limit):
            raise Refused("the card's head or footer does not fit in %d UTF-16 units" % limit)
        pieces: List[str] = []
        current, size = list(self.head()), units("\n".join(self.head()))
        for line in _gutter_lines(self.body, self.width, limit):
            need = units(line) + 1
            if size + need > limit:
                pieces.append("\n".join(current))
                current, size = [line], units(line)
            else:
                current.append(line)
                size += need
        foot = "\n".join(self.foot())
        if size + 1 + units(foot) > limit:
            pieces.append("\n".join(current))
            current = [foot]
        else:
            current.append(foot)
        pieces.append("\n".join(current))
        return pieces


def _gutter_lines(body: str, width: int, limit: int) -> Iterator[str]:
    """Every body line wrapped to `width` shown characters, each piece with
    its gutter. A line breaks at its last space that fits, or is cut hard
    when no space does. Each piece also fits in `limit` UTF-16 units, and a
    cut never splits a surrogate pair."""
    cols = width - 2                # the bar and its space; the left-to-right mark takes no column
    room = limit - units(GUTTER)
    for line in body.split("\n"):
        shown, start = spaces_shown(line), 0
        while True:
            end, size = start, 0
            while end < len(shown) and end - start < cols:
                size += 2 if ord(shown[end]) > 0xFFFF else 1
                if size > room:
                    break
                end += 1
            if end >= len(shown):
                yield GUTTER + shown[start:]
                break
            space = shown.rfind(" ", start + 1, end + 1)
            if space > start:       # break at the space and drop it
                yield GUTTER + shown[start:space]
                start = space + 1
            else:
                yield GUTTER + shown[start:end]
                start = end
