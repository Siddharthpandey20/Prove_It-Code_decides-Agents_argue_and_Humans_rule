"""The Skeptic's Codex rules, checked with Codex's own policy engine when it is installed."""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

RULES = Path(__file__).resolve().parent.parent / "agents" / "skeptic" / ".codex" / "rules" / "proveit.rules"
CODEX = shutil.which("codex")


def decision(*command):
    out = subprocess.run([CODEX, "execpolicy", "check", "--rules", str(RULES), *command],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out).get("decision")


@unittest.skipUnless(CODEX, "Codex CLI is not installed")
class SkepticRules(unittest.TestCase):
    def test_its_own_commands_are_allowed(self):
        for cmd in (["python", "-m", "proveit", "evidence", "R-001"], ["python3", "-m", "proveit", "show", "R-001"],
                    ["python", "-m", "proveit", "list"], ["python", "-m", "proveit", "tally"],
                    ["python", "-m", "proveit", "concur", "R-001", "--by", "skeptic"],
                    ["python", "-m", "proveit", "dispute", "R-001", "--reason", "x", "--by", "skeptic"]):
            self.assertIsNone(decision(*cmd), cmd)

    def test_private_files_cannot_be_read_from_its_folder(self):
        # The Skeptic starts in agents/skeptic, so the files are at ../../work.
        for cmd in (["cat", "../../work/R-001/private/report.md"], ["head", "../../work/R-001/private/payload.yaml"],
                    ["grep", "-r", "x", "../../work"], ["python3", "-c", "print(open('x').read())"],
                    ["python", "-"], ["python3", "-m", "json.tool", "../../work/R-001/private/contact.json"],
                    ["bash", "-c", "cat x"]):
            self.assertEqual(decision(*cmd), "forbidden", cmd)

    def test_human_only_and_producing_commands_are_forbidden(self):
        for sub in ("check", "override", "cost"):
            for py in ("python", "python3"):
                self.assertEqual(decision(py, "-m", "proveit", sub, "R-001"), "forbidden", (py, sub))


if __name__ == "__main__":
    unittest.main()
