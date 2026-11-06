"""Every action on a ticket, shared by the CLI, the Intake agent and the rehearsal.

Each one goes through the state machine in states.py, so the same rules hold
wherever a command comes from.
"""

import re

from . import judge, sandbox, states, store
from .evidence import current_evidence, is_current, latest_run


def _check_allowed(record, command, actor):
    """Refuse before doing work (a sandbox run) that the state machine would reject."""
    rows = [r for r in states.TABLE if r[0] == command]
    if actor not in set().union(*(r[3] for r in rows)):
        states.transition(record["status"], command, actor, record["status"])  # raises with the actor message
    if not any(record["status"] in r[1] for r in rows):
        states.transition(record["status"], command, actor, record["status"])  # raises with the state message


def check(ticket_id, build="vulnerable", actor="human", by="cli", entry_point=None):
    """Run the ticket's payload on one build. The vulnerable build sets reproduced / not_reproduced."""
    record = store.load(ticket_id)
    command = "check" if build == "vulnerable" else "check_patched"
    _check_allowed(record, command, actor)
    entry = entry_point or record.get("entry_point")
    run = sandbox.run_poc(entry, store.payload(ticket_id), build)  # minutes at most; not under the lock
    with store.ticket_lock(ticket_id):
        return _record_check(ticket_id, build, command, actor, by, run)


def _record_check(ticket_id, build, command, actor, by, run):
    path = store.save_run(ticket_id, run)
    record = store.load(ticket_id)
    record["runs"].append({"build": build, "file": path, "at": store.now(), "by": by, "actor": actor,
                           "outcome": run.get("outcome"), "seconds": run.get("seconds"),
                           "entry_point": run.get("entry_point")})
    if command == "check" and record["status"] != "disputed":
        target = judge.status_for(run) or record["status"]
    else:
        target = record["status"]
    for key in ("skeptic", "override"):
        review = record.get(key)
        if review and not review.get("stale") and not is_current(review, record):
            review["stale"] = True  # it was made on evidence the ticket no longer has as its latest
            store.event(record, key + "_stale", by, run=path)
    store.apply(record, command, actor, by, target=target, build=build, outcome=run.get("outcome"))
    return record, run, path


def clean_reason(text):
    """An agent's or maintainer's reason: one line, plain, at most 300 characters."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:300]


def concur(ticket_id, actor, by):
    with store.ticket_lock(ticket_id):
        return _concur(ticket_id, actor, by)


def _concur(ticket_id, actor, by):
    record = store.load(ticket_id)
    if latest_run(record, "vulnerable") is None:
        raise states.IllegalTransition("nothing to concur with: no check has run on %s" % ticket_id)
    evidence_now = current_evidence(record)
    store.apply(record, "concur", actor, by, evidence=evidence_now)
    record["skeptic"] = {"verdict": "concur", "by": by, "actor": actor, "at": store.now(), "evidence": evidence_now}
    store.save(record)
    return record


def dispute(ticket_id, reason, actor, by):
    with store.ticket_lock(ticket_id):
        return _dispute(ticket_id, reason, actor, by)


def _dispute(ticket_id, reason, actor, by):
    reason = clean_reason(reason)
    if not reason:
        raise states.IllegalTransition("a dispute needs a reason")
    record = store.load(ticket_id)
    evidence_now = current_evidence(record)
    store.apply(record, "dispute", actor, by, reason=reason, evidence=evidence_now)
    record["skeptic"] = {"verdict": "dispute", "reason": reason, "by": by, "actor": actor, "at": store.now(),
                         "evidence": evidence_now}
    store.save(record)
    return record


def override(ticket_id, actor, by, note=""):
    with store.ticket_lock(ticket_id):
        return _override(ticket_id, actor, by, note)


def _override(ticket_id, actor, by, note=""):
    record = store.load(ticket_id)
    run = latest_run(record, "vulnerable")
    target = judge.status_for(run) if run else None
    if record["status"] == "disputed" and target is None:
        raise states.IllegalTransition("the last vulnerable-build check was inconclusive; run check again first")
    if record["status"] in states.CHECKED:
        target = record["status"]
    evidence_now = current_evidence(record)
    store.apply(record, "override", actor, by, target=target or record["status"], note=clean_reason(note),
                evidence=evidence_now)
    record["override"] = {"by": by, "at": store.now(), "note": clean_reason(note), "evidence": evidence_now,
                          "after": "dispute" if (record.get("skeptic") or {}).get("verdict") == "dispute" else "no current concur"}
    store.save(record)
    return record


def review_problem(record):
    """Why `record` may not be escalated yet (decision D-007), or None.

    Escalation needs the Skeptic's concur on the evidence the ticket has now,
    or a maintainer's override made on that evidence.
    """
    if is_current(record.get("override"), record):
        return None
    skeptic = record.get("skeptic")
    if skeptic and skeptic.get("verdict") == "concur" and is_current(skeptic, record):
        return None
    if skeptic and skeptic.get("verdict") == "concur":
        return ("the Skeptic's concur was made on earlier evidence; ask @prove-it-skeptic to review again, "
                "or override (recorded) to escalate without a current review")
    return ("no current Skeptic concur; ask @prove-it-skeptic to review it, or override (recorded) to escalate "
            "without one")


def decide(ticket_id, verdict, actor, by, note=""):
    with store.ticket_lock(ticket_id):
        return _decide(ticket_id, verdict, actor, by, note)


def _decide(ticket_id, verdict, actor, by, note=""):
    """escalate or close."""
    record = store.load(ticket_id)
    if verdict == "escalate" and record["status"] in states.CHECKED:
        problem = review_problem(record)
        if problem:
            raise states.IllegalTransition("cannot escalate %s yet: %s" % (ticket_id, problem))
    store.apply(record, verdict, actor, by, note=clean_reason(note))
    return record


def record_cost(ticket_id, usd, source, actor, by):
    with store.ticket_lock(ticket_id):
        return _record_cost(ticket_id, usd, source, actor, by)


def _record_cost(ticket_id, usd, source, actor, by):
    """A human records agent cost from Switch ROI or a provider dashboard. Never estimated."""
    if actor != "human":
        raise states.IllegalTransition("only humans may record cost")
    if usd < 0:
        raise ValueError("cost cannot be negative")
    source = clean_reason(source)
    if not source:
        raise ValueError("say where the number came from with --source")
    record = store.load(ticket_id)
    record["cost"] = {"usd": round(float(usd), 4), "source": source, "by": by, "at": store.now()}
    store.event(record, "cost", by, usd=record["cost"]["usd"], source=source)
    store.save(record)
    return record


def decision_seconds(record):
    """Elapsed time from reaching triage to a maintainer's decision. Not effort: nobody times the work itself."""
    times = record.get("times", {})
    if times.get("triaged") is None or times.get("decided") is None:
        return None
    return max(0.0, times["decided"] - times["triaged"])


def tally():
    tickets = store.all_tickets()
    by_status, by_outcome, per_report = {}, {}, []
    runs = seconds = 0
    for r in tickets:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        vuln = [x for x in r.get("runs", []) if x["build"] == "vulnerable"]
        outcome = vuln[-1]["outcome"] if vuln else "not run"
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        runs += len(r.get("runs", []))
        seconds += sum((x.get("seconds") or 0) for x in r.get("runs", []))
        ms = decision_seconds(r)
        cost = r.get("cost")
        per_report.append({"id": r["id"], "status": r["status"], "outcome": outcome,
                           "seconds_to_decision": None if ms is None else round(ms, 1),
                           "agent_cost": ("$%.2f (%s)" % (cost["usd"], cost["source"])) if cost else "not recorded"})
    return {"reports": len(tickets), "by_status": by_status, "by_outcome": by_outcome,
            "sandbox_runs": runs, "sandbox_seconds": round(seconds, 2), "per_report": per_report}


def tally_text(t=None):
    t = t or tally()
    lines = ["**Tally:** %d reports. By status: %s. By outcome: %s. %d sandbox runs, %.2f s of sandbox time." % (
        t["reports"], ", ".join("%d %s" % (n, s.replace("_", " ")) for s, n in sorted(t["by_status"].items())) or "none",
        ", ".join("%d %s" % (n, o) for o, n in sorted(t["by_outcome"].items())) or "none",
        t["sandbox_runs"], t["sandbox_seconds"])]
    for row in t["per_report"]:
        ms = row["seconds_to_decision"]
        lines.append("- %s %s | %s | time to decision %s | agent cost %s" % (
            row["id"], row["status"].replace("_", " "), row["outcome"],
            "not decided" if ms is None else "%.1f s" % ms, row["agent_cost"]))
    return "\n".join(lines)
