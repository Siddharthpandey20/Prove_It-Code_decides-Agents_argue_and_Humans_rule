"""Shared test helpers: a temporary work directory and fake Switch rooms."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from proveit import config, intake

REPLAYS = Path(__file__).resolve().parent.parent / "reports" / "replays"


def replay(name):
    return (REPLAYS / name).read_text(encoding="utf-8")


class FakeRoom:
    """Stands in for a Switch connection: records every post."""

    def __init__(self):
        self.posts = []

    def post(self, body, thread_id=None):
        self.posts.append((body, thread_id))

    def text(self):
        return "\n".join(body for body, _ in self.posts)


class WorkDirTest(unittest.TestCase):
    def setUp(self):
        self._old = config.WORK_DIR
        self.tmp = Path(tempfile.mkdtemp(prefix="proveit-test-"))
        config.WORK_DIR = self.tmp / "work"

    def tearDown(self):
        config.WORK_DIR = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_intake(self):
        agent = intake.Intake({"agent_name": "prove-it-intake", "maintainers": ["maintainer"]}, source="test")
        agent.intake, agent.triage = FakeRoom(), FakeRoom()
        self._n = getattr(self, "_n", 0)
        return agent

    def report(self, agent, text, sender="reporter", kind="user"):
        self._n = getattr(self, "_n", 0) + 1
        mid = "m%d" % self._n
        agent.on_intake_event(None, "message", {"payload": {"body": text, "message_id": mid, "thread_id": None,
                                                            "sender_name": sender, "sender_kind": kind}})
        return mid

    def reply(self, agent, root, text, sender="reporter"):
        self._n = getattr(self, "_n", 0) + 1
        agent.on_intake_event(None, "message", {"payload": {"body": text, "message_id": "m%d" % self._n,
                                                            "thread_id": root, "sender_name": sender,
                                                            "sender_kind": "user"}})

    def say(self, agent, text, sender="maintainer", kind="user", message_id=None):
        self._n = getattr(self, "_n", 0) + 1
        payload = {"body": text, "message_id": message_id or "t%d" % self._n, "thread_id": None, "sender_name": sender,
                   "sender_kind": kind}
        if kind == "agent":
            payload["sender"] = "@switch-agent-" + sender
        agent.on_triage_event(None, "message", {"payload": payload})


def fake_run(outcome, build="vulnerable", entry="full_load", **extra):
    """A sandbox record for unit tests that must not need Docker. Never used outside tests."""
    versions = {"vulnerable": "5.3.1", "patched": "5.4"}
    run = {"outcome": outcome, "why": "test", "build": build, "target_version": versions[build],
           "entry_point": entry, "payload_sha256": "0" * 64, "payload_bytes": 10, "seconds": 0.5,
           "peak_rss_mb": 14.0, "marker_created": outcome == "CODE_EXECUTION", "events": [], "ran": True,
           "exception_type": None, "exception_frames": []}
    run.update(extra)
    return run


def stub_runs(*outcomes):
    """Patch the sandbox so successive runs return these outcomes (or run records, for full control)."""
    runs = iter(outcomes)

    def run_poc(entry, payload, build):
        nxt = next(runs)
        return dict(nxt) if isinstance(nxt, dict) else fake_run(nxt, build=build, entry=entry)
    return mock.patch("proveit.actions.sandbox.run_poc", side_effect=run_poc)
