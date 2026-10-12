"""The entry grammar: notes one program writes and another reads back.

A bot appends entries to a file, and some of an entry's text is a model's
words. The reader must tell the bot's own lines from the model's, and no list
of characters can decide that: a review of an earlier version beat a deny
list with look-alikes from unlisted scripts and with plain ASCII. So the
reader fails closed on grammar instead. An entry is exactly

    ## 2026-10-12T09:30:00Z - <title>
    <!-- begin <name> k=<key> -->
    <text, any number of lines>
    <!-- end <name> k=<key> -->

byte for byte, in ASCII, and every line that is not part of an exact entry
is labelled as the model's. The key is drawn after the text is fixed, so no
text can hold its own entry's end line and close the entry early. A begin
line with no end line after it leaves the rest of the file as the model's.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import List, NamedTuple, Optional

from .text import hidden_refusal, marked

# ASCII only: [0-9], never \d, which takes any script's digits.
TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
NAME = re.compile(r"[A-Za-z0-9._-]+")
HEADER = re.compile(r"## (%s) - (.*)" % TIME.pattern)
BEGIN = re.compile(r"<!-- begin (%s) k=([0-9a-f]{8}) -->" % NAME.pattern)
END = "<!-- end %s k=%s -->"
FRAME, ENTRY, MODEL = "frame", "entry", "model"


class Line(NamedTuple):
    """One line of a notes file: its role (FRAME for an entry's header, begin
    and end lines, ENTRY for its text, MODEL for every other line), the entry
    name for FRAME and ENTRY lines, the line as written, and the line as
    shown, each hidden character written out."""
    role: str
    entry: Optional[str]
    text: str
    shown: str


@dataclass(frozen=True)
class Entry:
    """One entry, written by render(). `time` is UTC as 2026-10-12T09:30:00Z."""
    time: str
    title: str
    name: str
    text: str

    def refusal(self) -> Optional[str]:
        if not isinstance(self.time, str) or not TIME.fullmatch(self.time):
            return "time must read like 2026-10-12T09:30:00Z"
        if not isinstance(self.name, str) or not NAME.fullmatch(self.name):
            return "name must be ASCII letters, digits, dot, underscore or hyphen"
        if not isinstance(self.title, str) or self.title.splitlines() not in ([], [self.title]):
            return "title must be one line of text"
        why = hidden_refusal(self.title)
        if why:
            return "title holds " + why
        if not isinstance(self.text, str):
            return "text must be text"
        return None

    def render(self) -> str:
        """The entry as lines ending in a newline, ready to append. Raises
        ValueError when a field is refused."""
        why = self.refusal()
        if why:
            raise ValueError(why)
        key = secrets.token_hex(4)
        # 1 in 4 billion, and still never: a key whose end line the text holds is drawn again.
        while END % (self.name, key) in self.text:
            key = secrets.token_hex(4)
        return "## %s - %s\n<!-- begin %s k=%s -->\n%s\n%s\n" % (
            self.time, self.title, self.name, key, self.text, END % (self.name, key))


def label_lines(text: str) -> List[Line]:
    """Every line of a notes file with its role. Lines split on the newline
    only, so a line separator or a carriage return stays inside its line (and
    shows as a marked hidden character)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    roles: List[tuple] = [(MODEL, None)] * len(lines)
    i = 0
    while i + 1 < len(lines):
        header, begin = HEADER.fullmatch(lines[i]), BEGIN.fullmatch(lines[i + 1])
        if not (header and begin):
            i += 1
            continue
        name = begin.group(1)
        try:
            j = lines.index(END % begin.groups(), i + 2)
        except ValueError:
            break                       # never closed: the rest stays the model's
        roles[i] = roles[i + 1] = roles[j] = (FRAME, name)
        for k in range(i + 2, j):
            roles[k] = (ENTRY, name)
        i = j + 1
    return [Line(role, name, line, marked(line)) for (role, name), line in zip(roles, lines)]
