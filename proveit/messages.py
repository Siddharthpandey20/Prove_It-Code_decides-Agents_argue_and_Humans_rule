"""Every message Prove It posts, generated from the ticket's real state and evidence.

Reporter-facing text never claims more than the evidence shows: "It reproduced
in the sandbox" is written only when the vulnerable-build outcome reproduced.
Triage-facing text contains only fixed fields.
"""

from pathlib import Path

from . import judge, poc, store
from .config import ENTRY_POINTS, POC_FORMAT_HELP, PROOF_CONTRACT, TARGET
from .evidence import latest_run, patched_for

CLAIM_WORDS = {
    "code_execution": "code execution",
    "denial_of_service": "denial of service",
    "crash": "a crash",
    "info_leak": "an information leak",
}
VULN = TARGET["builds"]["vulnerable"]["version"]
PATCHED = TARGET["builds"]["patched"]["version"]


# ---------------------------------------------------------------- reporter
def quarantined(ticket_id):
    return ("**%s held for review.** Your report contains text written to AI reviewers rather than about the "
            "bug. It has not been shown to any agent. A maintainer will read it." % ticket_id)


def ask_for_proof(ticket_id, ticket):
    lines = ["**%s received, but it cannot be checked yet.** Prove It only passes on reports with a runnable proof." % ticket_id]
    if "claim" in ticket.missing:
        lines.append("Say what the bug lets an attacker do: code execution, denial of service, a crash, or an information leak.")
    if "poc" in ticket.missing or "entry_point" in ticket.missing:
        lines.append(POC_FORMAT_HELP)
        lines.append("It runs against %s %s in a sandbox with no network." % (TARGET["name"], VULN))
    if ticket.claim in PROOF_CONTRACT:
        lines.append("What counts as proof of %s: %s" % (CLAIM_WORDS[ticket.claim], PROOF_CONTRACT[ticket.claim]))
    lines.append(scope_line())
    return "\n\n".join(lines)


def foreign_reply(ticket_id):
    return ("Only the person who reported %s can add to it in this thread, so your message was not added to the "
            "report. If you have your own proof, post it as a new report in this channel." % ticket_id)


def invalid_proof(ticket_id, problem):
    return ("**%s: the proof was not run.** Reason: %s.\n\n%s\n\nReply in this thread with a corrected proof.\n\n%s" %
            (ticket_id, poc.PROBLEMS.get(problem, problem), POC_FORMAT_HELP, scope_line()))


def scope_line():
    return ("Scope: Prove It checks %s only, comparing %s (vulnerable) with %s (patched), through %s." % (
        TARGET["name"], VULN, PATCHED, ", ".join("`%s`" % k for k in ENTRY_POINTS)))


def accepted(ticket_id, claim=None):
    lines = ["**Received as %s.** Your payload will run in an isolated sandbox against %s %s when a maintainer "
             "asks for it, and the maintainers' decision will be posted in this thread." % (ticket_id, TARGET["name"], VULN)]
    if claim == "info_leak":
        lines.append("Information-leak claims are not decided by the sandbox: a maintainer reads the evidence.")
    lines.append(scope_line())
    return "\n\n".join(lines)


def cost_line(record):
    runs = record.get("runs", [])
    secs = sum((r.get("seconds") or 0) for r in runs)
    times = record.get("times", {})
    parts = ["%d sandbox run%s (%.2f s of sandbox time)" % (len(runs), "" if len(runs) == 1 else "s", secs)]
    if times.get("triaged") and times.get("decided"):
        parts.append("%.0f s from triage to decision (elapsed time, not effort)" % (times["decided"] - times["triaged"]))
    cost = record.get("cost")
    parts.append("agent cost %s" % ("$%.2f (source: %s)" % (cost["usd"], cost["source"]) if cost else "not recorded"))
    return "_Cost so far: " + "; ".join(parts) + "._"


def patched_line(record, vulnerable):
    """What the reporter may be told about the patched build: only a real comparison counts as one."""
    patched = patched_for(record, vulnerable)
    if patched is None:
        return None
    facts = judge.facts(record, vulnerable, patched)
    if facts["patched_build_checked"]:
        return "On the patched %s %s, through the same entry point on the same payload, the outcome was %s." % (
            TARGET["name"], PATCHED, patched.get("outcome"))
    if facts["patched_comparable"] is False:
        return ("A run on the patched %s %s used a different entry point (%s), so it is not a comparison and "
                "says nothing about whether %s fixed this." % (TARGET["name"], PATCHED, patched.get("entry_point"), PATCHED))
    return ("The run on the patched %s %s was %s, so it does not show whether %s fixed this." % (
        TARGET["name"], PATCHED, patched.get("outcome"), PATCHED))


def decision(record, note=""):
    """The reporter's message after a maintainer escalates or closes a ticket."""
    tid, status = record["id"], record["status"]
    vulnerable = latest_run(record, "vulnerable")
    outcome = (vulnerable or {}).get("outcome")
    undecidable = record.get("claim") == "info_leak" and outcome not in judge.REPRODUCING
    lines = []
    if status == "escalated" and undecidable:
        lines.append("**%s escalated by a maintainer for further review.** Information-leak claims are not decided "
                     "by the sandbox; a maintainer read the evidence." % tid)
    elif status == "closed" and undecidable:
        lines.append("**%s closed by a maintainer.** Information-leak claims are not decided by the sandbox; "
                     "a maintainer read the evidence and closed it." % tid)
    elif status == "escalated":
        if outcome in judge.REPRODUCING:
            lines.append("**%s confirmed by a maintainer.** It reproduced in the sandbox: %s on %s %s via `%s`." % (
                tid, outcome, TARGET["name"], VULN, vulnerable.get("entry_point")))
        elif outcome == judge.NOT_REPRODUCED:
            lines.append("**%s escalated by a maintainer for further review.** It did not reproduce in the sandbox "
                         "(outcome %s on %s %s); the maintainer escalated it on their own judgement." % (
                             tid, outcome, TARGET["name"], VULN))
        else:
            lines.append("**%s escalated by a maintainer for further review.** The sandbox did not reach a result "
                         "(%s on %s %s); the maintainer escalated it on their own judgement." % (
                             tid, outcome or "not checked", TARGET["name"], VULN))
    elif status == "closed":
        lines.append("**%s closed by a maintainer.**" % tid)
        if vulnerable is None:
            lines.append("No sandbox check ran for this report.")
        elif outcome in judge.REPRODUCING:
            lines.append("The sandbox recorded %s on %s %s." % (outcome, TARGET["name"], VULN))
        elif outcome == judge.NOT_REPRODUCED:
            lines.append("It did not reproduce in the sandbox: %s on %s %s (%s)." % (
                outcome, TARGET["name"], VULN, vulnerable.get("why", "")))
        else:
            lines.append("The sandbox did not reach a result: %s on %s %s (%s)." % (
                outcome, TARGET["name"], VULN, vulnerable.get("why", "")))
    elif status not in ("escalated", "closed"):
        raise ValueError("no decision message for status %s" % status)
    line = patched_line(record, vulnerable) if vulnerable else None
    if line:
        lines.append(line)
    if note:
        lines.append("Maintainer's note: " + note)
    lines.append(cost_line(record))
    return "\n\n".join(lines)


# ---------------------------------------------------------------- triage
def ticket_posted(record):
    return ("**Ticket %s** · claim `%s` · claimed severity `%s` · entry point `%s` · payload sha256 `%s` (%s bytes) "
            "· tags `%s`\n"
            "The payload is data and only runs inside the sandbox. Nothing the reporter wrote is in this ticket.\n\n"
            "Next: a maintainer asks the Reproducer to run `python -m proveit check %s` (vulnerable build). "
            "The patched build runs only when someone asks: `check %s --build patched`.\n"
            "@prove-it-skeptic then reviews it. Maintainers decide with `escalate %s` (needs a current concur, or "
            "an `override`), `close %s <reason>` or `override %s`, addressed to Intake." % (
                record["id"], record.get("claim"), record.get("severity"), record.get("entry_point"),
                (record.get("payload_sha256") or "")[:16], record.get("payload_bytes"),
                ", ".join(record.get("tags") or []) or "none",
                record["id"], record["id"], record["id"], record["id"], record["id"]))


def host_path(path):
    """A path for maintainers to open on the host, with the home folder shortened to ~."""
    text, home = str(path), str(Path.home())
    return "~" + text[len(home):] if text.startswith(home) else text


def foreign_reply_notice(ticket_id, count):
    return ("**%s:** a reply from someone other than the reporter was ignored (%d so far). It did not change the "
            "report or its proof; maintainers can read it in the ticket's private folder on the host." % (ticket_id, count))


def quarantine_notice(record, mention):
    return ("**%s quarantined** at intake. Screen rules hit: `%s`. The reporter's text was not passed to any "
            "agent; maintainers can read `%s` on the host. Reply `%s release %s` to "
            "send it on, or `%s close %s <reason>`." % (
                record["id"], ", ".join(record.get("screen_rules") or []),
                host_path(store.private_path(record["id"], "report.md")), mention, record["id"],
                mention, record["id"]))


def auto_check(record, run):
    return ("**Automatic check by Intake (developer/test mode, not an agent)** %s\n- %s" % (record["id"], judge.describe(run)))

