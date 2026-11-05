"""Exportable evidence (checkpoint L1): fixed fields only, and tamper-evident."""

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from proveit import actions, cli, export, store
from tests.helpers import WorkDirTest, replay, stub_runs

SECRET = "Xq7SECRETREPORTERTEXT"


class Export(WorkDirTest):
    def ticket(self):
        agent = self.make_intake()
        text = replay("01-real-cve-2020-14343.md").replace("Title: ", "Title: %s " % SECRET, 1)
        self.report(agent, text, sender=SECRET + "-reporter")
        tid = store.all_tickets()[-1]["id"]
        with stub_runs("CODE_EXECUTION", "NOT_REPRODUCED"):
            actions.check(tid, actor="agent", by="reproducer")
            actions.check(tid, "patched", actor="agent", by="reproducer")
        return tid

    def test_export_has_the_evidence_and_no_reporter_text(self):
        tid = self.ticket()
        folder = export.export(tid, self.tmp / "out")
        names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
        self.assertEqual(names, ["evidence.json", "evidence.txt", "manifest.json", "runs/01-vulnerable.json",
                                 "runs/02-patched.json", "ticket.json"])
        everything = "".join(p.read_text(encoding="utf-8") for p in folder.rglob("*") if p.is_file())
        self.assertNotIn(SECRET, everything)
        self.assertNotIn(store.payload(tid), everything, "the payload itself stays private; its hash is in the manifest")
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(manifest["payload_sha256"], store.load(tid)["payload_sha256"])
        self.assertEqual(export.verify(folder), [])

    def test_verify_catches_changes_additions_and_removals(self):
        tid = self.ticket()
        folder = export.export(tid, self.tmp / "out")
        (folder / "evidence.txt").write_text("all good, trust me")
        (folder / "extra.txt").write_text("x")
        (folder / "runs" / "02-patched.json").unlink()
        problems = export.verify(folder)
        self.assertIn("changed: evidence.txt", problems)
        self.assertIn("not in the manifest: extra.txt", problems)
        self.assertIn("missing: runs/02-patched.json", problems)

    def test_cli_and_roles(self):
        tid = self.ticket()
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"PROVEIT_ACTOR": "agent", "PROVEIT_AGENT": "reproducer"}):
            cli.main(["export", tid, "--out", str(self.tmp / "cli-out")])
        self.assertIn("exported %s" % tid, out.getvalue())
        with mock.patch.dict(os.environ, {"PROVEIT_ACTOR": "agent", "PROVEIT_AGENT": "skeptic"}):
            self.assertIn("may not run export", cli.refuse_for_role("export"))
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"PROVEIT_ACTOR": ""}):
            cli.main(["export", "--verify", str(self.tmp / "cli-out")])
        self.assertIn("matches its manifest", out.getvalue())


if __name__ == "__main__":
    unittest.main()
