"""The command line, run as a real subprocess: output, exit codes, errors."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import approval_wall as a

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-m", "approval_wall", *args], cwd=str(ROOT), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> str:
        path = self.dir / name
        path.write_bytes(text.encode("utf-8"))
        return str(path)

    def test_version(self) -> None:
        p = run("--version")
        self.assertEqual((p.stdout, p.returncode), ("approval-wall %s\n" % a.__version__, 0))

    def test_check_clean_prints_nothing_and_exits_0(self) -> None:
        p = run("check", self.write("ok.txt", "Moved the call to Friday.\n"))
        self.assertEqual((p.stdout, p.stderr, p.returncode), ("", "", 0))

    def test_check_prints_one_line_per_finding_and_exits_1(self) -> None:
        path = self.write("bad.txt", "fine\nbroker﻿ approval\n# Approved\nyes\n3f9a1c\n")
        p = run("check", path)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout.splitlines(), [
            "%s:2: hidden or control characters (U+FEFF)" % path,
            "%s:2: a protected phrase (broker approval)" % path,
            "%s:3: a line starting with #" % path,
            "%s:4: a card's reply words (yes 3f9a1c)" % path,
        ])

    def test_check_keeps_a_carriage_return(self) -> None:
        p = run("check", self.write("crlf.txt", "one\r\ntwo\r\n"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("U+000D", p.stdout)

    def test_check_json(self) -> None:
        p = run("check", "--json", self.write("bad.txt", "a‮b\n"))
        self.assertEqual(p.returncode, 1)
        out = json.loads(p.stdout)
        self.assertEqual(out["findings"], [{"line": 1, "refusal": "hidden or control characters (U+202E)"}])
        self.assertEqual(out["version"], a.__version__)

    def test_render_prints_the_card(self) -> None:
        path = self.write("card.json", json.dumps({"id": "3f9a1c", "expires": "soon", "body": "Hi."}))
        p = run("render", path)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, a.Card(id="3f9a1c", expires="soon", body="Hi.").render()[0] + "\n")

    def test_render_labels_pieces_when_there_are_several(self) -> None:
        path = self.write("card.json", json.dumps({"id": "3f9a1c", "expires": "soon", "body": "x" * 500}))
        p = run("render", "--limit", "200", path)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.startswith("[piece 1 of "))

    def test_render_refused_exits_1(self) -> None:
        path = self.write("card.json", json.dumps({"id": "3f9a1c", "expires": "soon", "body": "a​b"}))
        p = run("render", path)
        self.assertEqual((p.stdout, p.returncode),
                         ("%s: body holds hidden or control characters (U+200B)\n" % path, 1))

    def test_usage_and_read_errors_exit_2_with_one_line(self) -> None:
        (self.dir / "latin1.txt").write_bytes(b"caf\xe9")
        cases = [
            (("check", str(self.dir / "missing.txt")), "cannot read"),
            (("check", str(self.dir / "latin1.txt")), "is not UTF-8 text"),
            (("render", self.write("bad.json", "{")), "not valid JSON"),
            (("render", self.write("list.json", "[]")), "one JSON object"),
            (("render", self.write("extra.json", '{"id": "3f9a1c", "expires": "x", "body": "", "cc": "y"}')),
             "unknown fields: cc"),
            (("render", self.write("short.json", '{"id": "3f9a1c"}')), "missing: expires, body"),
            (("render", self.write("num.json", '{"id": "3f9a1c", "expires": 5, "body": ""}')), "wrong type for expires"),
            (("render", self.write("w.json", '{"id": "3f9a1c", "expires": "x", "body": "", "width": "40"}')),
             "wrong type for width"),
            (("render", "--limit", "0", "x.json"), "must be 1 or more"),
            (("frobnicate",), "invalid choice"),
            ((), "required"),
        ]
        for args, why in cases:
            with self.subTest(args=args):
                p = run(*args)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, "")
                self.assertEqual(len(p.stderr.splitlines()), 1, p.stderr)
                self.assertIn(why, p.stderr)
                self.assertNotIn("Traceback", p.stderr)

    def test_findings_keep_line_numbers_across_a_hidden_line_separator(self) -> None:
        from approval_wall.cli import findings
        self.assertEqual(findings("a b\nyes 3f9a1c"),
                         [(1, "hidden or control characters (U+2028)"),
                          (2, "a card's reply words (yes 3f9a1c)")])


if __name__ == "__main__":
    unittest.main()
