"""The text rule: hidden characters, the skeleton, protected shapes."""
from __future__ import annotations

import unicodedata
import unittest

import approval_wall as a


class TestHidden(unittest.TestCase):
    def test_each_hidden_category_is_hidden(self) -> None:
        for cp, category in ((0x200B, "Cf"), (0x0007, "Cc"), (0xE000, "Co"), (0x2028, "Zl"), (0x2029, "Zp")):
            with self.subTest(cp=hex(cp)):
                self.assertEqual(unicodedata.category(chr(cp)), category)
                self.assertTrue(a.hidden(chr(cp)))

    def test_the_newline_is_the_one_control_allowed(self) -> None:
        self.assertFalse(a.hidden("\n"))
        self.assertTrue(a.hidden("\r"))
        self.assertTrue(a.hidden("\t"))

    def test_invisible_letters_outside_the_categories_are_hidden(self) -> None:
        for cp in (0x034F, 0x115F, 0x1160, 0x17B4, 0x3164, 0xFFA0):
            with self.subTest(cp=hex(cp)):
                self.assertNotIn(unicodedata.category(chr(cp))[0], "C")
                self.assertTrue(a.hidden(chr(cp)))

    def test_unassigned_default_ignorables_are_hidden(self) -> None:
        for cp in (0x2065, 0xFFF0, 0xE0000, 0xE0002, 0xE0FFF):
            with self.subTest(cp=hex(cp)):
                self.assertTrue(a.hidden(chr(cp)))

    def test_visible_text_is_not_hidden(self) -> None:
        for text in ("plain", "5 µs, 10 kΩ", "שלום and hello", "café", ""):
            with self.subTest(text=text):
                self.assertEqual(a.hidden_in(text), [])
                self.assertIsNone(a.refusal(text))

    def test_hidden_in_lists_each_character_once_in_order(self) -> None:
        text = "a​b﻿c​"
        self.assertEqual(a.hidden_in(text), ["​", "﻿"])

    def test_nfkc_neither_makes_nor_removes_a_hidden_character(self) -> None:
        """Over every code point of this Python's Unicode version: a check
        that reads the NFKC form and one that reads the raw text agree, and
        NFKC never makes a newline, so a skeleton keeps the text's lines."""
        bad = []
        for cp in range(0x110000):
            if 0xD800 <= cp <= 0xDFFF:
                continue
            ch = chr(cp)
            folded = unicodedata.normalize("NFKC", ch)
            if bool(a.hidden_in(ch)) != bool(a.hidden_in(folded)) or (ch != "\n" and "\n" in folded):
                bad.append("U+%04X" % cp)
        self.assertEqual(bad, [], "Unicode %s" % unicodedata.unidata_version)


class TestNames(unittest.TestCase):
    def test_names_shows_five_then_and_more(self) -> None:
        self.assertEqual(a.names(["​"]), "U+200B")
        self.assertEqual(a.names([chr(0x200B + i) for i in range(6)]),
                         "U+200B, U+200C, U+200D, U+200E, U+200F and more")

    def test_refusal_names_code_points_beyond_the_bmp(self) -> None:
        self.assertEqual(a.refusal("x" + chr(0xE0041)), "hidden or control characters (U+E0041)")


class TestSkeleton(unittest.TestCase):
    def test_fullwidth_folds_to_ascii(self) -> None:
        self.assertEqual(a.skeleton("Ａｐｐｒｏｖｅ"), "approve")

    def test_accents_drop(self) -> None:
        self.assertEqual(a.skeleton("apprövéd"), "approved")

    def test_cyrillic_lookalikes_fold_to_latin(self) -> None:
        self.assertEqual(a.skeleton("аpprоved"), "approved")

    def test_hidden_characters_drop_from_the_skeleton(self) -> None:
        self.assertEqual(a.skeleton("appro​ved"), "approved")

    def test_every_table_entry_folds_to_its_latin_letter(self) -> None:
        for cp, latin in a.CONFUSABLES.items():
            with self.subTest(cp=hex(cp)):
                self.assertEqual(a.skeleton(chr(cp)), latin)


class TestReadsAs(unittest.TestCase):
    def test_a_plain_phrase_matches_across_whitespace_and_case(self) -> None:
        self.assertEqual(a.reads_as("Approval\n  GRANTED", ["approval granted"]),
                         "a protected phrase (approval granted)")

    def test_a_phrase_in_lookalikes_is_still_the_phrase(self) -> None:
        self.assertIsNotNone(a.reads_as("аpprovаl granted", ["approval granted"]))

    def test_unrelated_text_reads_as_nothing(self) -> None:
        self.assertIsNone(a.reads_as("the approval is pending", ["approval granted"]))

    def test_default_phrases_are_the_notice_words(self) -> None:
        self.assertEqual(a.reads_as("broker approval for request 12"), "a protected phrase (broker approval)")

    def test_reply_words_need_an_id(self) -> None:
        self.assertIsNone(a.reads_as("no problem, send it"))
        self.assertIsNotNone(a.reads_as("reply yes 3f9a1c now"))

    def test_hidden_characters_come_first_in_refusal(self) -> None:
        self.assertEqual(a.refusal("# title​"), "hidden or control characters (U+200B)")


class TestMarked(unittest.TestCase):
    def test_marked_writes_out_every_hidden_character(self) -> None:
        self.assertEqual(a.marked("a‮b\nc"), "a\\u{202E}b\nc")

    def test_marked_takes_a_format(self) -> None:
        self.assertEqual(a.marked("a﻿b", "<U+%04X>"), "a<U+FEFF>b")


class TestOriginalNames(unittest.TestCase):
    def test_star_import_carries_the_original_names(self) -> None:
        namespace: dict = {}
        exec("from approval_wall import *", namespace)
        for name in ("hidden", "hidden_in", "skeleton", "marked", "note_refusal", "hidden_refusal",
                     "starts_header", "has_marker", "names", "CONFUSABLES", "NOTICE_WORDS"):
            self.assertIn(name, namespace)

    def test_note_refusal_keeps_its_original_answers(self) -> None:
        self.assertIsNone(a.note_refusal("Moved the brief to Friday.\nTwo items left."))
        self.assertEqual(a.note_refusal("fine first line\n## Approved"), "a line starting with #")
        self.assertEqual(a.note_refusal("see <!-- here"), "an HTML comment marker")
        self.assertEqual(a.note_refusal("broker approval for request 12"),
                         "the words of the bot's own notices (approvals, code lockouts)")


if __name__ == "__main__":
    unittest.main()
