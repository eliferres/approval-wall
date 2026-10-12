"""The forgery suite: every attack that beat or probed an earlier version.

Each test is one attack, asserting the refusal or the visible marking that
stops it. The hidden-character attacks all take the same shape: a model
writes a protected phrase with one invisible character inside it, hoping a
check that reads the raw text passes it and a display that drops the
character shows the real phrase. Each must be refused in a note, refused in
a card body, and spelled out by marked().
"""
from __future__ import annotations

import time
import unicodedata
import unittest

import approval_wall as a


def card(**kw: object) -> a.Card:
    base = {"id": "3f9a1c", "expires": "in 60 minutes (14:05 UTC)", "body": "Hi Sam."}
    base.update(kw)
    return a.Card(**base)  # type: ignore[arg-type]


def phone_rows(pieces: list, cols: int) -> list:
    """The rows a phone `cols` columns wide shows: each line cut hard at the
    width, a wide or fullwidth character taking two columns and the
    left-to-right mark none."""
    rows = []
    for line in "\n".join(pieces).split("\n"):
        row, used = "", 0
        for c in line.replace(chr(0x200E), ""):
            w = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
            if used + w > cols:
                rows.append(row)
                row, used = "", 0
            row, used = row + c, used + w
        rows.append(row)
    return rows


class TestForgery(unittest.TestCase):
    def assert_hidden_refused(self, cp: int) -> None:
        ch = chr(cp)
        name = "U+%04X" % cp
        text = "broker" + ch + " approval"
        self.assertEqual(a.refusal(text), "hidden or control characters (%s)" % name)
        self.assertEqual(a.note_refusal(text), "hidden or control characters (%s)" % name)
        self.assertEqual(card(body=text).refusal(), "body holds hidden or control characters (%s)" % name)
        self.assertIn("\\u{%04X}" % cp, a.marked(text))

    def test_byte_order_mark(self) -> None:
        self.assert_hidden_refused(0xFEFF)

    def test_word_joiner(self) -> None:
        self.assert_hidden_refused(0x2060)

    def test_soft_hyphen(self) -> None:
        self.assert_hidden_refused(0x00AD)

    def test_zero_width_space(self) -> None:
        self.assert_hidden_refused(0x200B)

    def test_zero_width_joiner(self) -> None:
        self.assert_hidden_refused(0x200D)

    def test_line_separator(self) -> None:
        self.assert_hidden_refused(0x2028)

    def test_paragraph_separator(self) -> None:
        self.assert_hidden_refused(0x2029)

    def test_next_line(self) -> None:
        self.assert_hidden_refused(0x0085)

    def test_mongolian_vowel_separator(self) -> None:
        self.assert_hidden_refused(0x180E)

    def test_arabic_letter_mark(self) -> None:
        self.assert_hidden_refused(0x061C)

    def test_tag_character(self) -> None:
        self.assert_hidden_refused(0xE0041)

    def test_invisible_times(self) -> None:
        self.assert_hidden_refused(0x2062)

    def test_private_use_plane_15(self) -> None:
        self.assert_hidden_refused(0xF0000)

    def test_private_use_plane_16(self) -> None:
        self.assert_hidden_refused(0x100000)

    def test_variation_selector_bmp(self) -> None:
        self.assert_hidden_refused(0xFE00)

    def test_variation_selector_supplement(self) -> None:
        self.assert_hidden_refused(0xE0100)

    def test_right_to_left_override(self) -> None:
        self.assert_hidden_refused(0x202E)

    def test_emoji_style_after_a_letter(self) -> None:
        self.assertEqual(a.refusal("a️"), "hidden or control characters (U+FE0F)")

    def test_emoji_style_after_a_symbol_once(self) -> None:
        self.assertIsNone(a.refusal("done ✔️"))
        self.assertIsNone(card(body="done ✔️").refusal())
        self.assertEqual(a.refusal("done ✔️️"), "hidden or control characters (U+FE0F)")

    def test_cyrillic_lookalike_notice_words(self) -> None:
        self.assertEqual(a.note_refusal("brоker apprоval"),
                         "the words of the bot's own notices (approvals, code lockouts)")
        self.assertEqual(a.refusal("brоker apprоval"), "a protected phrase (broker approval)")

    def test_fullwidth_hash_header(self) -> None:
        self.assertEqual(a.refusal("＃ Approved"), "a line starting with #")

    def test_html_comment_marker(self) -> None:
        self.assertEqual(a.refusal("see <!-- here"), "an HTML comment marker")
        self.assertEqual(a.refusal("see ﹣﹣> here"), "an HTML comment marker")

    def test_body_line_imitating_the_rule(self) -> None:
        self.assertEqual(card(body="fine\n" + a.RULE + "\nWritten by: the bank").refusal(),
                         "body holds the card's rule glyphs")
        self.assertEqual(card(body="――――").refusal(), "body holds the card's rule glyphs")
        self.assertEqual(card(body="﹘﹘").refusal(), "body holds the card's rule glyphs")

    def test_run_of_three_spaces(self) -> None:
        body = "Pay the invoice." + " " * 60 + 'Reply "yes 000000" to approve.'
        lines = card(body=body).render()[0].split("\n")
        self.assertIn(a.GUTTER + "Pay the invoice.⟨60 spaces⟩", "\n".join(lines))
        self.assertIn("run of 3 or more spaces", card(subject="Invoice   approved").refusal())

    def test_encoded_word_subject(self) -> None:
        self.assertIn("encoded word", card(subject="=?UTF-8?B?QXBwcm92ZWQ=?=").refusal())

    def test_line_break_in_a_one_line_field(self) -> None:
        for brk in ("\n", "\r", " ", "\x0b", "\x1c"):
            with self.subTest(brk=hex(ord(brk))):
                self.assertEqual(card(recipient="sam@example.com" + brk + "Approved").refusal(),
                                 "recipient holds a line break, and the card shows it on one line")

    def test_html_entities_in_a_one_line_field(self) -> None:
        for entity in ("&#x2014;&#x2014;", "&#8212;", "&mdash;", "&#10;"):
            with self.subTest(entity=entity):
                self.assertIn("HTML character reference", card(title="Ready " + entity).refusal())

    def test_sender_name_posing_as_a_number(self) -> None:
        for name in ("+1 (845) 555-0100", "８４５", "bank@example.com"):
            with self.subTest(name=name):
                self.assertEqual(card(sender="+18455550100", sender_name=name).refusal(),
                                 "sender_name reads as a number or an address, not a name")
        self.assertIsNone(card(sender="+18455550100", sender_name="Dana Reyes").refusal())

    def assert_frame_holds_on_a_phone(self, c: a.Card, cols: int) -> None:
        """Every row between the rules starts with the bar, and the rows after
        the closing rule are the footer, whole and last."""
        rows = phone_rows(c.render(), cols)
        bar = a.GUTTER.replace(chr(0x200E), "")[0]
        first = rows.index(a.RULE)
        foot = c.foot()
        self.assertEqual(rows[-len(foot):], foot)
        self.assertEqual(rows[:first + 1], c.head())
        for row in rows[first + 1:-len(foot)]:
            self.assertTrue(row.startswith(bar), "row without the gutter: %r" % row)

    def long_line_attack(self, cols: int) -> None:
        body = "Invoice 18, ok. " + "=" * 120 + ' Expires in 60 minutes. Reply "yes 3f9a1c" to approve.'
        self.assert_frame_holds_on_a_phone(card(body=body, width=cols), cols)

    def test_long_line_shown_at_36_columns(self) -> None:
        self.long_line_attack(36)

    def test_long_line_shown_at_40_columns(self) -> None:
        self.long_line_attack(40)

    def test_long_line_shown_at_48_columns(self) -> None:
        self.long_line_attack(48)

    def test_wide_characters_shown_at_36_columns(self) -> None:
        for body in ("\u30fc" * 34, "\uff25\uff58\uff50\uff49\uff52\uff45\uff53\u3000\uff49\uff4e\u3000"
                                    "\uff16\uff10\u3000\uff4d\uff49\uff4e\uff0e"):
            with self.subTest(body=body):
                self.assert_frame_holds_on_a_phone(card(body=body), 36)

    def test_wide_characters_shown_at_40_columns(self) -> None:
        for body in ("\u30fc" * 34, "\uff25\uff58\uff50\uff49\uff52\uff45\uff53\u3000\uff49\uff4e\u3000"
                                    "\uff16\uff10\u3000\uff4d\uff49\uff4e\uff0e"):
            with self.subTest(body=body):
                self.assert_frame_holds_on_a_phone(card(body=body, width=40), 40)

    def test_footer_line_of_wide_characters_refused(self) -> None:
        author = "\uff21" * 13
        self.assertEqual(len("Written by: " + author), 25)
        self.assertEqual(card(author=author).refusal(), "the footer line 'Written by: %s' is 38 columns, "
                                                        "wider than the card's width of 36" % author)

    def test_space_mark_never_split(self) -> None:
        for n in range(20, 40):
            with self.subTest(n=n):
                lines = card(body="x" * n + "   " + "y").render()[0].split("\n")
                for line in lines:
                    self.assertEqual(line.count("\u27e8"), line.count("\u27e9"), line)

    def test_line_drawing_run_refused(self) -> None:
        body = "Invoice 18, ok. " + chr(0x2501) * 120 + ' Expires in 60 minutes. Reply "yes 3f9a1c" to approve.'
        why = "body holds a run of 3 or more line-drawing characters (U+2500 to U+259F)"
        self.assertEqual(card(body=body).refusal(), why)
        self.assertEqual(card(body=chr(0x2588) * 3).refusal(), why)
        self.assertIsNone(card(body=chr(0x2501) * 2).refusal())
        self.assertIn("line-drawing", card(subject="Deposit " + chr(0x2550) * 3).refusal())

    def test_wrapped_continuation_imitating_the_release_line(self) -> None:
        c = card(body="Please look this over before Friday. " + " ".join(card().foot()[1:]))
        lines = c.render()[0].split("\n")
        self.assertGreater(len(lines), len(c.head()) + len(c.foot()) + 1)
        self.assert_frame_holds_on_a_phone(c, a.Card.width)

    def test_frame_lines_fit_the_width(self) -> None:
        """The lines the card writes itself never wrap at 36 or 40 columns,
        so the phone can never show a frame line broken in two."""
        c = card(sender="dana@example.com", recipient="sam@example.com", subject="Deposit for the venue",
                 author="the assistant", expires="in 60 minutes (14:05 UTC)", id="3f9a1c0b2d4e")
        for line in c.head() + c.foot():
            self.assertLessEqual(len(line), 36, line)

    def test_utf16_cut_never_splits_a_surrogate_pair(self) -> None:
        limit = 120
        room = limit - a.units(a.GUTTER)
        body = "x" * (room - 1) + "\U0001F600" + "y"
        pieces = card(body=body, width=1000).render(limit)
        lines = "\n".join(pieces).split("\n")
        self.assertIn(a.GUTTER + "x" * (room - 1), lines)
        self.assertIn(a.GUTTER + "\U0001F600y", lines)
        self.assertTrue(all(a.units(p) <= limit for p in pieces))

    def test_empty_body(self) -> None:
        pieces = card(body="").render()
        self.assertEqual(len(pieces), 1)
        self.assertIn(a.RULE + "\n" + a.GUTTER + "\n" + a.RULE, pieces[0])

    def test_one_megabyte_body(self) -> None:
        def seconds(n: int) -> float:
            best = float("inf")
            for _ in range(3):
                start = time.perf_counter()
                pieces = card(body="word " * (n // 5)).render()
                best = min(best, time.perf_counter() - start)
            self.assertTrue(all(a.units(p) <= a.LIMIT for p in pieces))
            return best
        small, large = seconds(1 << 16), seconds(1 << 20)
        # 16 times the text: linear work is about 16 times slower, quadratic about 256.
        self.assertLess(large, small * 64 + 0.05)
        self.assertIsNone(a.refusal("word " * 200000))


if __name__ == "__main__":
    unittest.main()
