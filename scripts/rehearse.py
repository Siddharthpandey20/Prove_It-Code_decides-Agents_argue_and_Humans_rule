"""Offline rehearsal of the demo: all four replays, Docker but no Switch.

Replays every fixture through the Intake agent's own logic (with stand-in
rooms that print what would be posted), runs the same `python -m proveit`
commands the Reproducer and Skeptic run, sends the maintainer's decisions as
room commands, and prints the tally.

Two parts are scripted stand-ins, and are labelled so in the output:
  * the Reproducer's and Skeptic's *choices* (which command to run, and
    concur or dispute) follow a fixed rule from the evidence checklist.
    In the room an LLM makes those choices; the commands are identical.
  * the maintainer's messages are fixed.
Everything else (parsing, screening, the sandbox, verdicts, state machine,
messages) is the real code.

  python scripts/rehearse.py           run once
  python scripts/rehearse.py --twice   run twice and compare outcomes (the Gate 2 check)
"""

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# The scripted Skeptic's fixed rule: checklist note -> reason code, first match wins.
NOTE_CODES = [
    ("reproduces on the patched build too", "also_on_patched"),
    ("runs disagreed", "not_clean_reproducible"),
    ("patched build has not been checked", "patched_not_checked"),
    ("so it is not a comparison", "patched_not_checked"),
    ("outcome class does not match", "outcome_mismatch"),
    ("claimed severity is higher", "severity_overclaimed"),
]


class Room:
    def __init__(self, name):
        self.name = name

    def post(self, body, thread_id=None):
        where = "#%s%s" % (self.name, " (thread)" if thread_id else "")
        print("  [%s] %s" % (where, body.replace("\n", "\n      ")))


def proveit(args, work, agent):
    """Run `python -m proveit ...` exactly as an agent would (agent="reproducer" or "skeptic": PROVEIT_ACTOR=agent
    and PROVEIT_AGENT=<role>, as their configs set them) or as a maintainer (agent=False)."""
    env = dict(os.environ, PROVEIT_WORK_DIR=str(work), PROVEIT_ACTOR="agent" if agent else "",
               PROVEIT_AGENT=agent or "")
    print("  $ python -m proveit " + " ".join(args) + ("   # as the " + agent if agent else "   # as maintainer"))
    proc = subprocess.run([sys.executable, "-m", "proveit"] + args, cwd=ROOT, env=env, capture_output=True, text=True)
    for line in (proc.stdout + proc.stderr).strip().splitlines():
        print("    " + line)
    return proc


def rehearse(work):
    os.environ["PROVEIT_WORK_DIR"] = str(work)
    from proveit import config, evidence, store
    from proveit.intake import Intake
    config.WORK_DIR = work
    replays = ROOT / "reports" / "replays"

    intake = Intake({"agent_name": "prove-it-intake", "maintainers": ["maintainer"]}, source="rehearsal")
    intake.intake, intake.triage = Room("proveit-intake"), Room("proveit-triage")
    counter = {"n": 0}

    def reporter(text, thread=None):
        counter["n"] += 1
        mid = "msg-%d" % counter["n"]
        intake.on_intake_event(None, "message", {"payload": {
            "body": text, "message_id": mid, "thread_id": thread, "sender_name": "replay-reporter", "sender_kind": "user"}})
        return mid

    said = itertools.count(1)

    def maintainer(text, who="maintainer"):
        print("  [%s in #proveit-triage] %s" % (who, text))
        intake.on_triage_event(None, "message", {"payload": {
            "body": text, "message_id": "t-%d" % next(said), "thread_id": None, "sender_name": who, "sender_kind": "user"}})

    def skeptic(tid):
        """Scripted stand-in for the Skeptic: dispute with the reason code for the checklist's first
        note, else concur. Like the real one, it reads with the CLI and records its verdict by posting to Intake."""
        proveit(["evidence", tid], work, agent="skeptic")
        notes = evidence.pack(store.load(tid))["notes"]
        code = next((c for phrase, c in NOTE_CODES for note in notes if phrase in note), None)
        if notes and not code:
            print("  [prove-it-skeptic] no verdict: the notes have no reason code; a maintainer reads them")
            return
        text = ("@prove-it-intake dispute %s %s" % (tid, code)) if code else ("@prove-it-intake concur %s" % tid)
        print("  [prove-it-skeptic in #proveit-triage] " + text)
        intake.on_triage_event(None, "message", {"payload": {
            "body": text, "message_id": "s-" + tid, "thread_id": None, "sender_name": "prove-it-skeptic",
            "sender_kind": "agent", "sender": "@switch-agent-prove-it-skeptic"}})

    print("\n== 1. Reports arrive in #proveit-intake")
    print("-- replay 01 (real CVE-2020-14343)")
    reporter((replays / "01-real-cve-2020-14343.md").read_text(encoding="utf-8"))
    print("-- replay 02 (synthetic slop, no proof)")
    root02 = reporter((replays / "02-slop-safe-load-rce.md").read_text(encoding="utf-8"))
    print("-- replay 02 follow-up in the thread (the 'proof')")
    reporter((replays / "02-slop-safe-load-rce.followup.md").read_text(encoding="utf-8"), thread=root02)
    print("-- replay 03 (synthetic slop, billion laughs)")
    reporter((replays / "03-slop-billion-laughs.md").read_text(encoding="utf-8"))
    print("-- replay 04 (injection attempt)")
    reporter((replays / "04-injection-attempt.md").read_text(encoding="utf-8"))

    print("\n== 2. Reproducer (scripted stand-in) checks each ticket on the vulnerable build")
    for tid in ("R-001", "R-002", "R-003"):
        proveit(["check", tid], work, agent="reproducer")

    print("\n== 3. Skeptic (scripted stand-in) reads the evidence and concurs or disputes")
    for tid in ("R-001", "R-002", "R-003"):
        skeptic(tid)

    print("\n== 4. Maintainer decides")
    maintainer("@prove-it-intake close R-001 not a bug", who="someone-else")  # refused: not a maintainer
    maintainer("@prove-it-intake escalate R-001")           # refused: disputed
    print("-- maintainer: @prove-it-reproducer retry R-001 on the patched build")
    proveit(["check", "R-001", "--build", "patched"], work, agent="reproducer")
    proveit(["evidence", "R-001"], work, agent="reproducer")
    maintainer("@prove-it-intake override R-001 patched build checked: fixed in 5.4")
    maintainer("@prove-it-intake escalate R-001 confirmed, CVE-2020-14343")
    maintainer("@prove-it-intake close R-002 safe_load refused the tag; nothing ran")
    maintainer("@prove-it-intake close R-003 finished normally, no exhaustion")
    maintainer("@prove-it-intake escalate R-004")           # refused: quarantined

    print("\n== 5. Tally")
    proveit(["tally"], work, agent=False)

    print("\n-- the advisory pack written when R-001 was escalated (DRAFT)")
    pack = work / "R-001" / "advisory"
    osv = json.loads((pack / "osv-draft.json").read_text(encoding="utf-8"))
    print("  %s: id %s, aliases %s, affected versions %s, not reproduced on %s" % (
        ", ".join(sorted(p.name for p in pack.glob("*"))), osv["id"], osv.get("aliases", []),
        osv["affected"][0]["versions"], osv["database_specific"].get("not_reproduced_on", [])))

    outcomes = []
    for record in store.all_tickets():
        runs = {r["build"]: r.get("outcome") for r in record.get("runs", [])}
        # n/N per build: how many of the check's clean runs agreed, out of how many containers ran.
        clean = {r["build"]: "%s/%s" % (r.get("agreeing"), r.get("container_runs")) for r in record.get("runs", [])}
        outcomes.append({"id": record["id"], "status": record["status"], "vulnerable": runs.get("vulnerable"),
                         "patched": runs.get("patched"), "clean_runs": clean,
                         "skeptic": (record.get("skeptic") or {}).get("verdict"),
                         "dispute_code": (record.get("skeptic") or {}).get("code"),
                         "question": record.get("decision_question"),
                         "advisory": sorted(p.name for p in (work / record["id"] / "advisory").glob("*")),
                         "overridden": bool(record.get("override"))})
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--twice", action="store_true", help="run twice and compare outcomes")
    args = parser.parse_args()
    from proveit import sandbox
    if not sandbox.docker_available():
        sys.exit("The rehearsal needs Docker running.")
    sandbox.build()
    digests = []
    for n in range(2 if args.twice else 1):
        with tempfile.TemporaryDirectory(prefix="proveit-rehearsal-") as tmp:
            print("\n######## Rehearsal run %d (work dir %s)" % (n + 1, tmp))
            outcomes = rehearse(Path(tmp) / "work")
        text = json.dumps(outcomes, sort_keys=True)
        digests.append(hashlib.sha256(text.encode()).hexdigest()[:16])
        print("\nOUTCOMES run %d: %s" % (n + 1, text))
        print("OUTCOMES digest run %d: %s" % (n + 1, digests[-1]))
    expected = {"R-001": "escalated", "R-002": "closed", "R-003": "closed", "R-004": "quarantined"}
    final = {o["id"]: o["status"] for o in outcomes}
    if final != expected:
        sys.exit("REHEARSAL FAILED: expected %s, got %s" % (expected, final))
    if len(set(digests)) != 1:
        sys.exit("REHEARSAL FAILED: runs differ: %s" % digests)
    print("\nREHEARSAL PASSED%s" % (" (both runs identical)" if args.twice else ""))


if __name__ == "__main__":
    main()
