"""End-to-end test of Prove It over a real Switch server and Mattermost.

Registers the Intake agent, creates and links the rooms, starts Intake (with
--auto-check, standing in for the Reproducer), replays all four reports as a
real Mattermost user, has a "maintainer" close and escalate, and checks every
ticket ends where it should and every reporter thread got its answer.

  scripts/switch-server.sh up
  python scripts/e2e.py --env-file .proveit/switch-server/.env

Uses its own work directory and agent name, so it does not touch a demo setup.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:18000")
    args = parser.parse_args()

    tag = time.strftime("%H%M%S")
    tmp = Path(tempfile.mkdtemp(prefix="proveit-e2e-"))
    env = dict(os.environ, PROVEIT_WORK_DIR=str(tmp / "work"), PROVEIT_STATE=str(tmp / "state" / "intake.json"),
               PYTHONUNBUFFERED="1")
    intake_room, triage_room, agent = "e2e-intake-" + tag, "e2e-triage-" + tag, "e2e-intake-" + tag
    py = [sys.executable, "-m"]

    def run(cmd, **kw):
        print("$", " ".join(cmd[2:] if cmd[:2] == py else cmd))
        return subprocess.run(cmd, cwd=ROOT, env=env, check=True, **kw)

    os.environ["PROVEIT_WORK_DIR"] = env["PROVEIT_WORK_DIR"]  # before proveit is imported
    from proveit.intake import read_env
    server_env = read_env(args.env_file)
    run(py + ["proveit.intake", "setup", "--env-file", args.env_file, "--api-url", args.api_url,
              "--agent-name", agent, "--intake-room", intake_room, "--triage-room", triage_room,
              "--create-rooms", "--users", server_env["MATTERMOST_USER"]])

    log = open(tmp / "intake.log", "w")
    intake = subprocess.Popen(py + ["proveit.intake", "run", "--auto-check"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            if "listening" in (tmp / "intake.log").read_text():
                break
            time.sleep(1)
        else:
            sys.exit("Intake did not start:\n" + (tmp / "intake.log").read_text())

        from replay import Mattermost
        mm = Mattermost("http://127.0.0.1:%s" % server_env.get("MATTERMOST_HOST_PORT", "8065"),
                        server_env["MATTERMOST_USER"], server_env["MATTERMOST_USER_PASSWORD"])
        intake_ch, triage_ch = mm.channel(intake_room), mm.channel(triage_room)
        replays = ROOT / "reports" / "replays"
        roots = {}
        for n in ("01", "02", "03", "04"):
            path = next(p for p in sorted(replays.glob(n + "-*.md")) if not p.name.endswith(".followup.md"))
            roots[n] = mm.post(intake_ch, path.read_text(encoding="utf-8"))["id"]
            print("reporter posted", path.name)
        time.sleep(6)
        mm.post(intake_ch, (replays / "02-slop-safe-load-rce.followup.md").read_text(encoding="utf-8"), root_id=roots["02"])
        print("reporter posted the follow-up PoC for 02")
        time.sleep(15)

        from proveit import store
        # Intake stores Switch's message ids, not Mattermost's; reports are
        # handled one at a time in arrival order, so R-001 is replay 01.
        tickets = store.all_tickets()
        if len(tickets) != len(roots):
            sys.exit("expected %d tickets, found %d:\n%s" % (len(roots), len(tickets), (tmp / "intake.log").read_text()))
        ids = {n: t["id"] for n, t in zip(sorted(roots), tickets)}
        mm.post(triage_ch, "@%s close %s the PoC wrote the marker itself" % (agent, ids["02"]))
        mm.post(triage_ch, "@%s close %s finished in milliseconds with 12 MB" % (agent, ids["03"]))
        mm.post(triage_ch, "@%s escalate %s confirmed, CVE-2020-14343" % (agent, ids["01"]))
        time.sleep(6)

        expected = {"01": "escalated", "02": "closed", "03": "closed", "04": "quarantined"}
        failures = []
        for n, status in expected.items():
            record = store.load(ids[n])
            ok = record["status"] == status
            print("%s %s: %s (expected %s)%s" % ("PASS" if ok else "FAIL", ids[n], record["status"], status,
                                                ", check: %s" % record.get("last_check", {}).get("vulnerable") if record.get("last_check") else ""))
            if not ok:
                failures.append(n)
            thread = mm.call("GET", "/posts/%s/thread" % roots[n])
            replies = [p["message"] for p in thread["posts"].values() if p["id"] != roots[n]]
            needle = {"01": "confirmed by a maintainer", "02": "closed by a maintainer",
                      "03": "closed by a maintainer", "04": "held for review"}[n]
            if not any(needle in r for r in replies):
                failures.append(n + "-thread")
                print("FAIL reporter thread %s has no %r" % (n, needle))
            else:
                print("PASS reporter thread %s got %r" % (n, needle))
        if failures:
            print("\nintake log:\n" + (tmp / "intake.log").read_text()[-3000:])
            sys.exit("E2E FAILED: %s" % failures)
        print("\nE2E PASSED (work dir %s)" % tmp)
    finally:
        intake.terminate()


if __name__ == "__main__":
    main()
