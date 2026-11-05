"""Every message Prove It posts, generated from the ticket's real state and evidence.

Reporter-facing text never claims more than the evidence shows: "It reproduced
in the sandbox" is written only when the vulnerable-build outcome reproduced.
Triage-facing text contains only fixed fields.
"""

from . import judge, poc
from .config import POC_FORMAT_HELP, PROOF_CONTRACT, TARGET
from .evidence import latest_run

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
    return "\n\n".join(lines)


def invalid_proof(ticket_id, problem):
    return ("**%s: the proof was not run.** Reason: %s.\n\n%s\n\nReply in this thread with a corrected proof." %
            (ticket_id, poc.PROBLEMS.get(problem, problem), POC_FORMAT_HELP))


def accepted(ticket_id):
    return ("**Received as %s.** Your payload will run in an isolated sandbox against %s %s when a maintainer "
            "asks for it, and the maintainers' decision will be posted in this thread." % (ticket_id, TARGET["name"], VULN))


def cost_line(record):
    runs = record.get("runs", [])
    secs = sum((r.get("seconds") or 0) for r in runs)
    times = record.get("times", {})
    parts = ["%d sandbox run%s (%.2f s of sandbox time)" % (len(runs), "" if len(runs) == 1 else "s", secs)]
    if times.get("triaged") and times.get("decided"):
        parts.append("%.0f s of maintainer time from triage to decision" % (times["decided"] - times["triaged"]))
    cost = record.get("cost")
    parts.append("agent cost %s" % ("$%.2f (source: %s)" % (cost["usd"], cost["source"]) if cost else "not recorded"))
    return "_Cost so far: " + "; ".join(parts) + "._"


def decision(record, note=""):
    """The reporter's message after a maintainer escalates or closes a ticket."""
    tid, status = record["id"], record["status"]
    vulnerable = latest_run(record, "vulnerable")
    patched = latest_run(record, "patched")
    outcome = (vulnerable or {}).get("outcome")
    lines = []
    if status == "escalated":
        if outcome in judge.REPRODUCING:
            lines.append("**%s confirmed by a maintainer.** It reproduced in the sandbox: %s on %s %s via `%s`." % (
                tid, outcome, TARGET["name"], VULN, vulnerable.get("entry_point")))
        else:
            lines.append("**%s escalated by a maintainer for further review.** It did not reproduce in the sandbox "
                         "(outcome %s on %s %s); the maintainer escalated it on their own judgement." % (
                             tid, outcome or "not checked", TARGET["name"], VULN))
    elif status == "closed":
        lines.append("**%s closed by a maintainer.**" % tid)
        if vulnerable is None:
            lines.append("No sandbox check ran for this report.")
        elif outcome in judge.REPRODUCING:
            lines.append("The sandbox recorded %s on %s %s." % (outcome, TARGET["name"], VULN))
        else:
            lines.append("It did not reproduce in the sandbox: %s on %s %s (%s)." % (
                outcome, TARGET["name"], VULN, vulnerable.get("why", "")))
    else:
        raise ValueError("no decision message for status %s" % status)
    if patched is not None:
        lines.append("On the patched %s %s the outcome was %s." % (TARGET["name"], PATCHED, patched.get("outcome")))
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
            "Maintainers decide with `escalate %s`, `close %s <reason>` or `override %s`, addressed to Intake." % (
                record["id"], record.get("claim"), record.get("severity"), record.get("entry_point"),
                (record.get("payload_sha256") or "")[:16], record.get("payload_bytes"),
                ", ".join(record.get("tags") or []) or "none",
                record["id"], record["id"], record["id"], record["id"], record["id"]))


def quarantine_notice(record, mention):
    return ("**%s quarantined** at intake. Screen rules hit: `%s`. The reporter's text was not passed to any "
            "agent; maintainers can read `work/%s/private/report.md` on the host. Reply `%s release %s` to "
            "send it on, or `%s close %s <reason>`." % (
                record["id"], ", ".join(record.get("screen_rules") or []), record["id"], mention, record["id"],
                mention, record["id"]))


def auto_check(record, run):
    return ("**Automatic check by Intake (developer/test mode, not an agent)** %s\n- %s" % (record["id"], judge.describe(run)))

