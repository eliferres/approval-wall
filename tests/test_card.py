"""The card: its frame, its fields, and how it is cut into pieces."""
from __future__ import annotations

import unittest

import approval_wall as a


def card(**kw: object) -> a.Card:
    base = {"id": "3f9a1c", "expires": "in 60 minutes (14:05 UTC)", "body": "Hi Sam,\n\nSee you Monday."}
    base.update(kw)
    return a.Card(**base)  # type: ignore[arg-type]


def body_lines(pieces: list) -> list:
    lines = "\n".join(pieces).split("\n")
    first = lines.index(a.RULE)
    last = len(lines) - 1 - lines[::-1].index(a.RULE)
    return lines[first + 1:last]


class TestFrame(unittest.TestCase):
    def test_a_card_reads_head_rule_body_rule_release(self) -> None:
        text = card(sender="dana@example.com", sender_name="Dana Reyes", recipient="sam@example.com",
                    subject="Monday", author="the assistant").render()[0]
        self.assertEqual(text.split("\n"), [
            "Ready to send",
            "From: Dana Reyes (dana@example.com)",
            "To: sam@example.com",
            "Subject: Monday",
            a.RULE,
            a.GUTTER + "Hi Sam,",
            a.GUTTER,
            a.GUTTER + "See you Monday.",
            a.RULE,
            "Written by: the assistant",
            "Expires in 60 minutes (14:05 UTC).",
            'Reply "yes 3f9a1c" to approve,',
            '"no 3f9a1c" to drop.',
        ])

    def test_every_body_line_has_the_gutter_blank_ones_too(self) -> None:
        lines = body_lines(card(body="\n\none\n\n").render())
        self.assertEqual(len(lines), 5)
        self.assertTrue(all(line.startswith(a.GUTTER) for line in lines))

    def test_the_release_lines_are_last(self) -> None:
        last = card().render()[-1].split("\n")[-2:]
        self.assertEqual(last, ['Reply "yes 3f9a1c" to approve,', '"no 3f9a1c" to drop.'])

    def test_an_empty_body_still_renders_the_whole_frame(self) -> None:
        pieces = card(body="").render()
        self.assertEqual(body_lines(pieces), [a.GUTTER])
        self.assertTrue(card(body="").is_whole())

    def test_rendering_twice_gives_the_same_pieces(self) -> None:
        self.assertEqual(card().render(), card().render())


class TestSpaces(unittest.TestCase):
    def test_a_run_of_three_spaces_is_shown_with_its_count(self) -> None:
        self.assertEqual(a.spaces_shown("a   b"), "a⟨3 spaces⟩b")

    def test_two_spaces_stay(self) -> None:
        self.assertEqual(a.spaces_shown("a  b"), "a  b")

    def test_an_indent_of_up_to_eight_stays(self) -> None:
        self.assertEqual(a.spaces_shown("        - item"), "        - item")

    def test_a_deeper_indent_is_marked(self) -> None:
        self.assertEqual(a.spaces_shown(" " * 40 + "approved"), "⟨40 spaces⟩approved")

    def test_no_break_spaces_count_as_blank(self) -> None:
        self.assertEqual(a.spaces_shown("a   b"), "a⟨3 spaces⟩b")


class TestFields(unittest.TestCase):
    def test_a_clean_card_passes(self) -> None:
        self.assertIsNone(card(subject="Invoice 1042", recipient="+1 845 555 0100").refusal())

    def test_an_id_must_be_lowercase_hex(self) -> None:
        for bad in ("3F9A1C", "12345", "zzzzzz", "3f9a1c\n"):
            with self.subTest(id=bad):
                self.assertIn("id must be", card(id=bad).refusal())

    def test_non_text_fields_are_refused(self) -> None:
        self.assertEqual(a.Card(id="3f9a1c", expires="soon", body=None).refusal(),  # type: ignore[arg-type]
                         "body must be text")

    def test_render_raises_refused(self) -> None:
        with self.assertRaises(a.Refused):
            card(subject="a\nb").render()

    def test_an_author_line_wider_than_the_width_is_refused(self) -> None:
        c = card(author="the assistant, on behalf of the whole team")
        self.assertEqual(c.refusal(), "the footer line 'Written by: the assistant, on behalf of the whole team' "
                                      "is 54 characters, wider than the card's width of 36")
        self.assertFalse(c.is_whole())
        with self.assertRaises(a.Refused):
            c.render()
        self.assertIsNone(card(author="the assistant, on behalf of the whole team", width=60).refusal())

    def test_an_expiry_line_wider_than_the_width_is_refused(self) -> None:
        c = card(expires="in 60 minutes, at 14:05 UTC on Monday 12 October")
        self.assertIn("is 57 characters, wider than the card's width of 36", c.refusal())
        self.assertFalse(c.is_whole())

    def test_a_long_id_needs_a_wider_card(self) -> None:
        self.assertIn("wider than the card's width", card(id="3f9a1c0b2d4e6f").refusal())
        self.assertIsNone(card(id="3f9a1c0b2d4e").refusal())

    def test_a_long_subject_still_renders_with_the_frame_whole(self) -> None:
        c = card(subject="Deposit for the venue, the caterer and the band, due Friday")
        self.assertTrue(c.is_whole())
        lines = c.render()[0].split("\n")
        self.assertEqual(lines[1], "Subject: Deposit for the venue, the caterer and the band, due Friday")
        self.assertTrue(all(len(line) <= 36 for line in lines[lines.index(a.RULE, 2):]))

    def test_a_tab_in_the_body_is_refused(self) -> None:
        self.assertEqual(card(body="a\tb").refusal(), "body holds hidden or control characters (U+0009)")


class TestCut(unittest.TestCase):
    def test_units_count_a_character_outside_the_bmp_twice(self) -> None:
        self.assertEqual(a.units("a\U0001F600"), 3)

    def test_every_piece_fits_the_limit(self) -> None:
        pieces = card(body="word " * 3000).render(500)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(a.units(p) <= 500 for p in pieces))

    def test_the_frame_is_never_cut(self) -> None:
        pieces = card(body="\n".join("line %d" % i for i in range(400))).render(300)
        self.assertTrue(pieces[0].startswith("Ready to send\n" + a.RULE + "\n"))
        self.assertTrue(pieces[-1].endswith('"no 3f9a1c" to drop.'))
        self.assertIn("\n" + a.RULE + "\n", "\n" + pieces[-1])
        for piece in pieces[1:]:
            self.assertTrue(piece.startswith(a.GUTTER) or piece.startswith(a.RULE))

    def test_a_long_line_wraps_at_a_space_within_the_width(self) -> None:
        lines = body_lines(card(body="alpha beta gamma delta epsilon zeta eta theta").render())
        self.assertEqual(lines, [a.GUTTER + "alpha beta gamma delta epsilon", a.GUTTER + "zeta eta theta"])

    def test_a_run_with_no_space_is_cut_hard_at_the_width(self) -> None:
        lines = body_lines(card(body="x" * 80, width=30, expires="soon").render())
        self.assertEqual([len(line) - len(a.GUTTER) for line in lines], [28, 28, 24])

    def test_the_width_must_be_a_whole_number_of_at_least_20(self) -> None:
        for bad in (19, 0, True, 36.0, "36"):
            with self.subTest(width=bad):
                self.assertEqual(card(width=bad, expires="soon").refusal(), "width must be a whole number of at least 20")
        self.assertNotIn("width must be", card(width=20, expires="soon").refusal())
        self.assertIsNone(card(width=30, expires="soon").refusal())

    def test_no_body_text_is_lost_in_the_cut(self) -> None:
        body = "".join(chr(0x41 + i % 26) for i in range(5000))
        lines = body_lines(card(body=body).render(400))
        self.assertEqual("".join(line[len(a.GUTTER):] for line in lines), body)

    def test_is_whole_is_false_when_the_frame_cannot_fit(self) -> None:
        tight = card(subject="s" * 200)
        self.assertFalse(tight.is_whole(150))
        with self.assertRaises(a.Refused):
            tight.render(150)
        self.assertTrue(tight.is_whole())

    def test_is_whole_is_false_for_a_refused_card(self) -> None:
        self.assertFalse(card(body="﻿").is_whole())


if __name__ == "__main__":
    unittest.main()
