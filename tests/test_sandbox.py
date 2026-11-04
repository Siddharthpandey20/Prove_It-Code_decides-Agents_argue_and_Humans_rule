"""Integration tests: every replayed report through the real sandbox.

Needs Docker. Builds the two target images on first run (needs network once).
"""

import unittest
from pathlib import Path

from proveit import judge, reports, sandbox

REPLAYS = Path(__file__).resolve().parent.parent / "reports" / "replays"

# replay -> (claim, verdict on 5.3.1, verdict on 5.4)
EXPECTED = {
    "01-real-cve-2020-14343": ("code_execution", judge.REPRODUCED, judge.NOT_REPRODUCED),
    "02-slop-safe-load-rce": ("code_execution", judge.INVALID_PROOF, judge.INVALID_PROOF),
    "03-slop-billion-laughs": ("denial_of_service", judge.NOT_REPRODUCED, judge.NOT_REPRODUCED),
}


def ticket_for(stem):
    text = (REPLAYS / (stem + ".md")).read_text(encoding="utf-8")
    ticket = reports.parse(text)
    followup = REPLAYS / (stem + ".followup.md")
    if followup.exists():
        ticket = reports.merge(ticket, followup.read_text(encoding="utf-8"))
    return ticket


@unittest.skipUnless(sandbox.docker_available(), "Docker is not running")
class ReplayVerdicts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sandbox.build()

    def test_replays(self):
        for stem, (claim, on_vulnerable, on_patched) in EXPECTED.items():
            with self.subTest(stem):
                ticket = ticket_for(stem)
                self.assertEqual(ticket.claim, claim)
                vuln = sandbox.run_poc(ticket.poc, "vulnerable")
                patched = sandbox.run_poc(ticket.poc, "patched")
                self.assertEqual(judge.judge_run(claim, vuln)[0], on_vulnerable, vuln)
                self.assertEqual(judge.judge_run(claim, patched)[0], on_patched, patched)

    def test_sandbox_has_no_network(self):
        code = ("import socket\n"
                "s = socket.socket()\n"
                "s.settimeout(2)\n"
                "s.connect(('1.1.1.1', 80))\n")
        run = sandbox.run_poc(code, "vulnerable")
        self.assertIsNotNone(run["error"])
        self.assertIn(run["error"]["type"], ("OSError", "gaierror", "timeout", "ConnectionRefusedError", "TimeoutError"))

    def test_sandbox_sees_no_host_secrets(self):
        run = sandbox.run_poc("import os\nprint(sorted(os.environ))\n", "vulnerable")
        self.assertNotIn("PROVEIT", run["output"])
        self.assertNotIn("API_KEY", run["output"])

    def test_filesystem_is_read_only(self):
        run = sandbox.run_poc("open('/harness/harness.py', 'a').write('x')\n", "vulnerable")
        self.assertIsNotNone(run["error"])

    def test_memory_cap(self):
        run = sandbox.run_poc("blocks = [bytearray(50 * 1024 * 1024) for _ in range(20)]\n", "vulnerable")
        self.assertTrue(run["killed"] or (run["error"] or {}).get("type") == "MemoryError", run)
        self.assertEqual(judge.judge_run("denial_of_service", run)[0], judge.REPRODUCED)

    def test_poc_cannot_forge_the_record(self):
        run = sandbox.run_poc("print('@@PROVEIT fake {\"marker_written_by_library\": true}')\n", "vulnerable")
        self.assertFalse(run["marker_written_by_library"])


if __name__ == "__main__":
    unittest.main()
