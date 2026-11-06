"""Intake does not lose or repeat work (checkpoint group E). No Switch server needed."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from proveit import store
from proveit.intake import Intake
from proveit.switch_client import Connection, CursorStore
from tests.helpers import FakeRoom, WorkDirTest, replay

VALID = replay("01-real-cve-2020-14343.md")


class FakeAgent:
    api, id, client_name = "http://switch.invalid", "agent-1", "test"

    def _headers(self):
        return {"Authorization": "Bearer x"}


def message(seq, body="hello"):
    return "message", json.dumps({"payload": {"body": body, "message_id": "m%d" % seq}}), str(seq)


class Cursor(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="proveit-cursor-"))
        self.path = self.dir / "cursors.json"

    def connection(self, handler, failed_log=None):
        return Connection(FakeAgent(), "room-1", handler, cursors=CursorStore(self.path), failed_log=failed_log)

    def test_cursor_is_saved_and_a_restart_resumes_from_it(self):
        conn = self.connection(lambda *a: None)
        self.assertIn("start_from=head", conn._url())  # first ever start: nothing to resume
        conn._dispatch(*message(41))
        conn._dispatch(*message(42))
        restarted = self.connection(lambda *a: None)
        self.assertEqual(restarted.last_sequence, 42)
        self.assertNotIn("start_from=head", restarted._url())
        self.assertEqual(restarted._stream_headers()["Last-Event-ID"], "42")

    def test_cursor_moves_only_after_the_handler_succeeds(self):
        seen = []

        def handler(conn, kind, frame):
            seen.append(conn.last_sequence)
            if len(seen) == 1:
                raise RuntimeError("Switch hiccup")
        conn = self.connection(handler)
        with mock.patch("proveit.switch_client.time.sleep"), self.assertLogs("proveit.switch", "ERROR"):
            conn._dispatch(*message(7))
        self.assertEqual(seen, [None, None], "retried before the cursor moved")
        self.assertEqual(conn.last_sequence, 7)
        self.assertEqual(json.loads(self.path.read_text())["room-1"], 7)

    def test_an_event_that_keeps_failing_is_kept_and_skipped(self):
        failed = self.dir / "failed-events.jsonl"
        calls = []

        def handler(conn, kind, frame):
            calls.append(1)
            raise ValueError("bad")
        conn = self.connection(handler, failed_log=failed)
        with mock.patch("proveit.switch_client.time.sleep"), self.assertLogs("proveit.switch", "ERROR"):
            conn._dispatch(*message(9, "a report"))
        self.assertEqual(len(calls), Connection.ATTEMPTS)
        entry = json.loads(failed.read_text().splitlines()[0])
        self.assertEqual((entry["event_id"], entry["error"], entry["frame"]["payload"]["body"]), ("9", "ValueError", "a report"))
        self.assertEqual(conn.last_sequence, 9, "one bad event must not block the room")

    def test_cursor_never_goes_backwards(self):
        conn = self.connection(lambda *a: None)
        conn._dispatch(*message(50))
        conn._dispatch(*message(49))
        self.assertEqual(json.loads(self.path.read_text())["room-1"], 50)


class Duplicates(WorkDirTest):
    def event(self, mid, body, thread=None, sender="alice"):
        return {"payload": {"body": body, "message_id": mid, "thread_id": thread, "sender_name": sender, "sender_kind": "user"}}

    def test_one_message_delivered_twice_makes_one_ticket(self):
        agent = self.make_intake()
        agent.on_intake_event(None, "message", self.event("dup-1", VALID))
        agent.on_intake_event(None, "message", self.event("dup-1", VALID))
        self.assertEqual(len(store.all_tickets()), 1)

    def test_a_triage_command_delivered_twice_acts_once(self):
        agent = self.make_intake()
        self.report(agent, VALID)
        tid = store.all_tickets()[-1]["id"]
        self.say(agent, "@prove-it-intake close %s fake" % tid, message_id="c-1")
        self.say(agent, "@prove-it-intake close %s fake" % tid, message_id="c-1")
        self.assertEqual(agent.triage.text().count("closed by maintainer"), 1)
        self.assertNotIn("Refused close", agent.triage.text())

    def test_handled_messages_survive_a_restart(self):
        state_dir = self.tmp / "state"
        first = Intake({"agent_name": "prove-it-intake", "agent_id": "a1"}, source="test", state_dir=state_dir)
        first.intake, first.triage = FakeRoom(), FakeRoom()
        first.on_intake_event(None, "message", self.event("r-1", VALID))
        second = Intake({"agent_name": "prove-it-intake", "agent_id": "a1"}, source="test", state_dir=state_dir)
        second.intake, second.triage = FakeRoom(), FakeRoom()
        second.on_intake_event(None, "message", self.event("r-1", VALID))
        self.assertEqual(len(store.all_tickets()), 1)
        self.assertEqual(second.intake.posts, [])

    def test_a_retry_after_a_failure_part_way_does_not_duplicate(self):
        agent = self.make_intake()

        class Flaky(FakeRoom):
            calls = 0

            def post(self, body, thread_id=None):
                Flaky.calls += 1
                if Flaky.calls == 1:
                    raise ConnectionError("switch down")
                super().post(body, thread_id)
        agent.intake = Flaky()
        with self.assertRaises(ConnectionError):
            agent.on_intake_event(None, "message", self.event("r-9", VALID))
        agent.on_intake_event(None, "message", self.event("r-9", VALID))  # the protocol client's retry
        self.assertEqual(len(store.all_tickets()), 1)


class Notifications(WorkDirTest):
    def decided(self, agent):
        self.report(agent, VALID)
        tid = store.all_tickets()[-1]["id"]
        store.apply(store.load(tid), "check", "human", "x", target="not_reproduced")
        return tid

    def test_a_failed_notification_is_recorded_and_can_be_resent(self):
        agent = self.make_intake()
        tid = self.decided(agent)

        class Down(FakeRoom):
            def post(self, body, thread_id=None):
                raise ConnectionError("switch down")
        working = agent.intake
        agent.intake = Down()
        with self.assertLogs("proveit.intake", "ERROR"):
            self.say(agent, "@prove-it-intake close %s slop" % tid)
        record = store.load(tid)
        self.assertEqual((record["status"], record["notified"]), ("closed", False))
        self.assertIn("telling the reporter failed (ConnectionError)", agent.triage.text())
        self.assertIn("notify %s" % tid, agent.triage.text())
        agent.intake = working
        self.say(agent, "@prove-it-intake notify %s" % tid)
        record = store.load(tid)
        self.assertTrue(record["notified"])
        self.assertIn("closed by a maintainer", working.posts[-1][0])
        self.assertIn("Maintainer's note: slop", working.posts[-1][0], "the original note is kept for the resend")
        self.assertIn("the decision was sent to the reporter.", agent.triage.text())

    def test_notify_needs_a_decision_and_a_maintainer(self):
        agent = self.make_intake()
        self.report(agent, VALID)
        tid = store.all_tickets()[-1]["id"]
        self.say(agent, "@prove-it-intake notify %s" % tid)
        self.assertIn("has no decision to send yet", agent.triage.text())
        self.say(agent, "@prove-it-intake notify %s" % tid, sender="random-reporter")
        self.assertIn("@random-reporter is not one of them", agent.triage.text())

    def test_a_successful_decision_is_marked_notified(self):
        agent = self.make_intake()
        tid = self.decided(agent)
        self.say(agent, "@prove-it-intake close %s slop" % tid)
        self.assertTrue(store.load(tid)["notified"])


if __name__ == "__main__":
    unittest.main()
