"""Every action on a ticket, shared by the CLI, the Intake agent and the rehearsal.

Each one goes through the state machine in states.py, so the same rules hold
wherever a command comes from.
"""

import re

from . import judge, reasons, sandbox, states, store
from .evidence import current_evidence, is_current, latest_run


def _check_allowed(record, command, actor):
    """Refuse before doing work (a sandbox run) that the state machine would reject."""
    rows = [r for r in states.TABLE if r[0] == command]
    if actor not in set().union(*(r[3] for r in rows)):
        states.transition(record["status"], command, actor, record["status"])  # raises with the actor message
    if not any(record["status"] in r[1] for r in rows):
        states.transition(record["status"], command, actor, record["status"])  # raises with the state message


def check(ticket_id, build="vulnerable", actor="human", by="cli", entry_point=None):
    """Run the ticket's payload on one build, config.CHECK_RUNS times in fresh containers (decision D-011).

    The vulnerable build sets reproduced / not_reproduced / not_reliably_reproduced.
    If Docker cannot start one of the runs, sandbox.SandboxError propagates and
    nothing is recorded.
    """
    record = store.load(ticket_id)
    command = "check" if build == "vulnerable" else "check_patched"
    _check_allowed(record, command, actor)
    entry = entry_point or record.get("entry_point")
    run = sandbox.run_check(entry, store.payload(ticket_id), build)  # minutes at most; not under the lock
    with store.ticket_lock(ticket_id):
        return _record_check(ticket_id, build, command, actor, by, run)


def container_runs(entry):
    """Containers one check started. Checks recorded before repeats ran one."""
    return entry.get("container_runs", 1)


def _record_check(ticket_id, build, command, actor, by, run):
    path = store.save_run(ticket_id, run)
    record = store.load(ticket_id)
    record["runs"].append({"build": build, "file": path, "at": store.now(), "by": by, "actor": actor,
                           "outcome": run.get("outcome"),
                           "seconds": run.get("total_seconds", run.get("seconds")),
                           "container_runs": run.get("runs", 1), "agreeing": run.get("agreeing"),
                           "image_id": run.get("image_id"), "entry_point": run.get("entry_point")})
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


def dispute(ticket_id, code, actor, by, note=""):
    with store.ticket_lock(ticket_id):
        return _dispute(ticket_id, code, actor, by, note)


def latest_patched(record):
    """The latest patched check on the ticket, whatever entry point it used, or None."""
    for entry in reversed(record.get("runs", [])):
        if entry["build"] == "patched":
            return store.load_run(entry["file"])
    return None


def _dispute(ticket_id, code, actor, by, note=""):
    """A dispute with exactly one reason code (decision D-013). The note stays in #proveit-triage."""
    code = (code or "").strip().lower()
    if code not in reasons.CODES:
        raise states.IllegalTransition("give one reason code: %s" % reasons.code_list())
    record = store.load(ticket_id)
    _check_allowed(record, "dispute", actor)
    problem = reasons.contradiction(code, latest_run(record, "vulnerable"), latest_patched(record))
    if problem:
        raise states.IllegalTransition("%s contradicts the recorded evidence (%s)" % (code, problem))
    evidence_now = current_evidence(record)
    note = clean_reason(note)
    store.apply(record, "dispute", actor, by, code=code, evidence=evidence_now)
    record["skeptic"] = {"verdict": "dispute", "code": code, "reason": reasons.meaning(code), "note": note,
                         "by": by, "actor": actor, "at": store.now(), "evidence": evidence_now}
    # A later dispute replaces the code; every one stays in this list and in the timeline.
    record.setdefault("disputes", []).append({"code": code, "by": by, "at": record["skeptic"]["at"]})
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
    skeptic = record.get("skeptic") or {}
    # One override lifts every block the ticket has now: a dispute, and runs that disagreed.
    cleared = []
    if record["status"] == "disputed":
        cleared.append("dispute:%s" % skeptic["code"] if skeptic.get("code") else "dispute")
    if (target or record["status"]) == states.UNRELIABLE:
        cleared.append(states.UNRELIABLE)
    store.apply(record, "override", actor, by, target=target or record["status"], note=clean_reason(note),
                evidence=evidence_now, cleared=cleared)
    record["override"] = {"by": by, "at": store.now(), "note": clean_reason(note), "evidence": evidence_now,
                          "cleared": cleared,
                          "after": "dispute" if skeptic.get("verdict") == "dispute" else "no current concur"}
    if any(item.startswith("dispute") for item in cleared):
        # An overridden dispute never becomes a reporter question (decision D-014).
        record["skeptic"]["overridden"] = True
    store.save(record)
    return record


def override_text(record):
    """The triage message after an override, naming every block it lifted."""
    override_ = record["override"]
    parts = []
    for item in override_.get("cleared") or []:
        if item.startswith("dispute"):
            code = item.partition(":")[2]
            parts.append("the dispute (%s)" % code if code else "the dispute")
        elif item == states.UNRELIABLE:
            run = latest_run(record, "vulnerable") or {}
            parts.append("the runs-disagree block (%s)" % judge.repeats(run))
    what = " and ".join(parts) if parts else "the missing Skeptic review"
    return "%s: %s overrode %s; it can now be escalated or closed." % (record["id"], override_["by"], what)


def review_problem(record):
    """Why `record` may not be escalated yet (decisions D-007, D-012), or None.

    Escalation needs the Skeptic's concur on the evidence the ticket has now,
    or a maintainer's override made on that evidence. When the check's clean
    runs disagreed, only an override will do.
    """
    if is_current(record.get("override"), record):
        return None
    if record["status"] == states.UNRELIABLE:
        run = latest_run(record, "vulnerable") or {}
        return ("its clean runs disagreed (%s); a maintainer must override first (a concur is not enough)"
                % judge.repeats(run))
    skeptic = record.get("skeptic")
    if skeptic and skeptic.get("verdict") == "concur" and is_current(skeptic, record):
        return None
    if skeptic and skeptic.get("verdict") == "concur":
        return ("the Skeptic's concur was made on earlier evidence; ask @prove-it-skeptic to review again, "
                "or override (recorded) to escalate without a current review")
    return ("no current Skeptic concur; ask @prove-it-skeptic to review it, or override (recorded) to escalate "
            "without one")


def decide(ticket_id, verdict, actor, by, note="", reason=None):
    with store.ticket_lock(ticket_id):
        return _decide(ticket_id, verdict, actor, by, note, reason)


def current_dispute(record):
    """The Skeptic's dispute if it still stands (not overridden), else None."""
    skeptic = record.get("skeptic") or {}
    if skeptic.get("verdict") == "dispute" and not skeptic.get("overridden"):
        return skeptic
    return None


def close_question(record, requested=None):
    """Which reason code gives the reporter's question on close (decision D-014), or None.

    1. the code the maintainer passed (`close R-001 reason=<code>`)
    2. else the latest dispute's code, if it stands and has a reporter question
    3. else the code the evidence implies: NOT_REPRODUCED -> not_reproduced,
       NOT_RELIABLY_REPRODUCED -> not_clean_reproducible
    4. else none
    """
    if requested:
        return requested
    dispute_ = current_dispute(record)
    if dispute_ and reasons.has_question(dispute_.get("code")):
        return dispute_["code"]
    if record.get("claim") == "info_leak":
        return None  # the sandbox does not decide information leaks, so the evidence implies no question
    return reasons.derived(latest_run(record, "vulnerable"))


def _decide(ticket_id, verdict, actor, by, note="", reason=None):
    """escalate or close. A close may name the reason code whose question the reporter gets."""
    record = store.load(ticket_id)
    _check_allowed(record, verdict, actor)
    note = clean_reason(note)
    if verdict == "escalate" and record["status"] in states.CHECKED:
        problem = review_problem(record)
        if problem:
            raise states.IllegalTransition("cannot escalate %s yet: %s" % (ticket_id, problem))
    question_code = None
    if verdict == "close":
        if reason is not None:
            reason = reason.strip().lower()
            if reason not in reasons.CODES:
                raise states.IllegalTransition("reason= needs one reason code: %s" % reasons.code_list())
            if not reasons.has_question(reason):
                raise states.IllegalTransition("%s never gives the reporter a question; close without reason= "
                                               "or name another code" % reason)
        dispute_ = current_dispute(record)
        if dispute_ and dispute_.get("code") == "also_on_patched" and not note:
            # Humans decide, but a close over a possible new issue must say why, for the record.
            raise states.IllegalTransition("the patched build also reproduced; add a note saying why you are closing")
        code = close_question(record, reason)
        on_patched_too = bool(dispute_) and dispute_.get("code") == "also_on_patched"
        if code and not on_patched_too and reasons.question(code, record, latest_run(record, "vulnerable")):
            question_code = code  # never a rejection question over a possible new issue
    store.apply(record, verdict, actor, by, note=note, **({"question": question_code} if question_code else {}))
    if verdict == "close":
        record["decision_question"] = question_code
        store.save(record)
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
        runs += sum(container_runs(x) for x in r.get("runs", []))  # every container: a 3-run check counts 3
        seconds += sum((x.get("seconds") or 0) for x in r.get("runs", []))  # each check's entry holds all its runs
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
