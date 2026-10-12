"""What the README states is what the code and the suite do."""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


class TestReadme(unittest.TestCase):
    def test_the_forgery_count_is_the_number_of_forgery_tests(self) -> None:
        tree = ast.parse((ROOT / "tests" / "test_forgery.py").read_text(encoding="utf-8"))
        count = sum(1 for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
        self.assertIn("holds %d named tests" % count, README)

    def test_the_first_run_output_is_the_recorded_demo_output(self) -> None:
        shown = re.search(r"python3 -m approval_wall check demo/forged.txt\n```\n\n```text\n(.*?)\n```",
                          README, re.S).group(1)
        recorded = json.loads((ROOT / "demo" / "transcript.json").read_text(encoding="utf-8"))[0]["out"]
        self.assertEqual(shown, recorded.rsplit("\nexit ", 1)[0])

    def test_the_opener_is_under_forty_words(self) -> None:
        opener = README.split("\n\n")[1]
        self.assertLess(len(opener.split()), 40)

    def test_the_prose_holds_no_em_or_en_dash(self) -> None:
        self.assertNotIn(chr(0x2014), README)
        self.assertNotIn(chr(0x2013), README)


if __name__ == "__main__":
    unittest.main()
