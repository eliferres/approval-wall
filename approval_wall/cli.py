"""The command line: check a text file, or render a card from JSON."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields
from typing import List, Optional, Tuple

from . import __version__
from .card import LIMIT, Card, Refused
from .text import NOTICE_WORDS, REPLY_WORDS, has_marker, hidden_refusal, skeleton, starts_header

PROG = "approval-wall"
CARD_FIELDS = [f.name for f in fields(Card)]
REQUIRED = ("id", "expires", "body")


class UsageError(Exception):
    """Something the command was given cannot be read: exit 2."""


def findings(text: str) -> List[Tuple[int, str]]:
    """(line number, refusal) for every finding in a text, sorted by line.

    Hidden characters, header lines and comment markers are found line by
    line. The reply words and the notice words are found on the skeleton of
    the whole text, so a phrase broken across two lines is still caught; the
    skeleton keeps every newline and adds none, so its line numbers are the
    text's.
    """
    found = []
    for n, line in enumerate(text.split("\n"), 1):
        why = hidden_refusal(line)
        if why:
            found.append((n, why))
        if starts_header(line):
            found.append((n, "a line starting with #"))
        if has_marker(line):
            found.append((n, "an HTML comment marker"))
    shape = skeleton(text)
    for rx, what in ((REPLY_WORDS, "a card's reply words"), (NOTICE_WORDS, "a protected phrase")):
        for m in rx.finditer(shape):
            found.append((shape.count("\n", 0, m.start()) + 1, "%s (%s)" % (what, " ".join(m.group(0).split()))))
    return sorted(found, key=lambda f: f[0])


def _read(path: str) -> str:
    try:
        # newline="" keeps a carriage return, which is a control character like any other.
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise UsageError("%s is not UTF-8 text" % path)
    except OSError as e:
        raise UsageError("cannot read %s: %s" % (path, e.strerror or e))


def check(path: str, as_json: bool) -> int:
    found = findings(_read(path))
    if as_json:
        print(json.dumps({"version": __version__, "file": path,
                          "findings": [{"line": n, "refusal": why} for n, why in found]}, indent=2))
    else:
        for n, why in found:
            print("%s:%d: %s" % (path, n, why))
    return 1 if found else 0


def load_card(path: str) -> Card:
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError as e:
        raise UsageError("%s is not valid JSON: %s" % (path, e))
    if not isinstance(data, dict):
        raise UsageError("%s must hold one JSON object" % path)
    unknown = sorted(set(data) - set(CARD_FIELDS))
    if unknown:
        raise UsageError("%s has unknown fields: %s (known: %s)" % (path, ", ".join(unknown), ", ".join(CARD_FIELDS)))
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise UsageError("%s is missing: %s" % (path, ", ".join(missing)))
    wrong = [k for k, v in data.items() if not isinstance(v, str)]
    if wrong:
        raise UsageError("%s: these fields must be strings: %s" % (path, ", ".join(sorted(wrong))))
    return Card(**data)


def render(path: str, limit: int) -> int:
    card = load_card(path)
    try:
        pieces = card.render(limit)
    except Refused as e:
        print("%s: %s" % (path, e))
        return 1
    for i, piece in enumerate(pieces, 1):
        if len(pieces) > 1:
            print("[piece %d of %d]" % (i, len(pieces)))
        print(piece)
    return 0


def _limit(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("not a whole number: %r" % value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be 1 or more: %r" % value)
    return number


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:   # one line on stderr, exit 2
        self.exit(2, "%s: %s (see --help)\n" % (PROG, message))


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = _Parser(prog=PROG, description="Refuse text that could forge an approval card, "
                                            "and render cards whose frame no body can imitate.")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    commands = parser.add_subparsers(dest="command", metavar="{check,render}", parser_class=_Parser)
    commands.required = True
    c = commands.add_parser("check", help="refuse hidden characters and protected shapes in a text file")
    c.add_argument("file")
    c.add_argument("--json", action="store_true", help="print the findings as JSON")
    r = commands.add_parser("render", help="print the card a JSON object describes")
    r.add_argument("file")
    r.add_argument("--limit", type=_limit, default=LIMIT,
                   help="UTF-16 units per piece (default: %(default)d)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        code = check(args.file, args.json) if args.command == "check" else render(args.file, args.limit)
    except UsageError as e:
        print("%s: %s" % (PROG, e), file=sys.stderr)
        sys.exit(2)
    except Exception as e:   # a bug must still end in one line and exit 2, never a traceback
        print("%s: internal error: %s: %s" % (PROG, type(e).__name__, e), file=sys.stderr)
        sys.exit(2)
    sys.exit(code)
