"""What a sandbox run proves. Rules, not opinions.

The harness's parent process classifies each run into one outcome class
from what it observed itself. This module maps outcomes to ticket states and
builds the evidence pack the agents argue over. Every string it produces
comes from fixed templates and allowlisted values: no reporter text.
"""

CODE_EXECUTION = "CODE_EXECUTION"
CRASH = "CRASH"
RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
NOT_REPRODUCED = "NOT_REPRODUCED"
INVALID_PROOF = "INVALID_PROOF"
INCONCLUSIVE = "INCONCLUSIVE"
REPRODUCING = (CODE_EXECUTION, CRASH, RESOURCE_EXHAUSTION)

CLAIM_FOR_OUTCOME = {CODE_EXECUTION: "code_execution", CRASH: "crash", RESOURCE_EXHAUSTION: "denial_of_service"}
# The highest severity each outcome can support. Resource exhaustion is never code execution.
SEVERITY_CEILING = {CODE_EXECUTION: "critical", CRASH: "high", RESOURCE_EXHAUSTION: "medium"}
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

RUN_FIELDS = ("build", "target_version", "entry_point", "payload_sha256", "payload_bytes", "outcome", "why",
              "exit_code", "signal", "timed_out", "seconds", "cpu_seconds", "peak_rss_mb", "marker_created",
              "exception_type", "exception_sha256", "exception_frames", "dropped_values", "ran")


CONCLUSIVE = REPRODUCING + (NOT_REPRODUCED,)


def status_for(run):
    """The ticket state a vulnerable-build run supports, or None if it proves nothing either way.

    INVALID_PROOF (the sandbox refused the proof) and INCONCLUSIVE leave the
    ticket where it was: neither is evidence that the bug does not exist.
    """
    outcome = run.get("outcome")
    if outcome in REPRODUCING:
        return "reproduced"
    if outcome == NOT_REPRODUCED:
        return "not_reproduced"
    return None


def library_frames(run):
    frames = []
    for event in run.get("events") or []:
        for frame in event.get("library_frames") or []:
            if frame not in frames:
                frames.append(frame)
    return frames[:8]


def summary(run):
    """The fixed fields of one run."""
    out = {k: run.get(k) for k in RUN_FIELDS if k in run}
    out["library_frames"] = library_frames(run)
    out["events"] = [{"event": e["event"], "in_library": e["in_library"]} for e in run.get("events") or []][:20]
    return out


def describe(run):
    """One line per run, from fixed templates."""
    text = "%s on PyYAML %s via %s: %s" % (run.get("build"), run.get("target_version"), run.get("entry_point"),
                                          run.get("outcome"))
    details = []
    if run.get("why"):
        details.append(run["why"])
    if run.get("exception_type"):
        details.append("raised %s (message sha256 %s...)" % (run["exception_type"], (run.get("exception_sha256") or "?")[:12]))
    frames = library_frames(run)
    if frames:
        details.append("library frames: " + " < ".join(frames[:3]))
    if run.get("seconds") is not None:
        details.append("%.3f s, %.1f MB peak" % (run.get("seconds") or 0, run.get("peak_rss_mb") or 0))
    return text + ("; " + "; ".join(details) if details else "")


def facts(record, vulnerable, patched):
    """The Skeptic's checklist, answered from the evidence. None means "not known yet"."""
    outcome = (vulnerable or {}).get("outcome")
    claimed = record.get("claim")
    severity = record.get("severity")
    ceiling = SEVERITY_CEILING.get(outcome)
    in_library = None
    if vulnerable and vulnerable.get("ran"):
        in_library = bool(library_frames(vulnerable) or vulnerable.get("exception_frames"))
    patched_outcome = (patched or {}).get("outcome")
    same_input = None if patched is None or vulnerable is None else (
        vulnerable.get("entry_point") == patched.get("entry_point")
        and vulnerable.get("payload_sha256") == patched.get("payload_sha256"))
    # The patched build counts as checked only through the same entry point, on the same payload, with a result.
    checked = bool(same_input) and patched_outcome in CONCLUSIVE
    return {
        "entry_point_allowlisted": bool(record.get("entry_point")) and not record.get("poc_problem"),
        "vulnerable_entry_point": (vulnerable or {}).get("entry_point"),
        "vulnerable_outcome": outcome,
        "outcome_matches_claim": None if outcome is None else CLAIM_FOR_OUTCOME.get(outcome) == claimed,
        "library_frames_recorded": in_library,
        "code_execution_proven_by_marker": None if vulnerable is None else bool(vulnerable.get("marker_created")),
        "patched_run_present": patched is not None,
        "patched_comparable": same_input,
        "patched_entry_point": (patched or {}).get("entry_point"),
        "patched_build_checked": checked,
        "patched_outcome": patched_outcome,
        "reproduces_on_patched_too": None if not checked or outcome is None else (
            outcome in REPRODUCING and patched_outcome in REPRODUCING),
        "claim_decidable_by_sandbox": claimed != "info_leak",
        "claimed_severity": severity,
        "severity_supported_by_outcome": None if outcome not in REPRODUCING or severity in (None, "unrated") else (
            SEVERITY_RANK.get(severity, 0) <= SEVERITY_RANK[ceiling]),
    }


def notes(facts_, vulnerable=None, patched=None):
    """Fixed sentences a human should read before deciding."""
    out = []
    if not facts_.get("claim_decidable_by_sandbox", True):
        out.append("information-leak claims are not decided by the sandbox: a maintainer reads the evidence")
    if facts_["vulnerable_outcome"] == INVALID_PROOF:
        out.append("the sandbox refused the proof as invalid; that is not evidence either way")
    elif facts_["vulnerable_outcome"] == INCONCLUSIVE:
        out.append("the vulnerable-build run was inconclusive (%s); run check again" % ((vulnerable or {}).get("why") or "no reason"))
    if facts_["reproduces_on_patched_too"]:
        out.append("reproduces on the patched build too: possible new issue, human review required")
    if facts_.get("patched_comparable") is False:
        out.append("the patched run used %s while the vulnerable run used %s%s, so it is not a comparison: "
                   "run check --build patched with the same loader" % (
                       facts_.get("patched_entry_point"), facts_.get("vulnerable_entry_point"),
                       "" if (vulnerable or {}).get("payload_sha256") == (patched or {}).get("payload_sha256")
                       else " on a different payload"))
    elif facts_.get("patched_comparable") and facts_["patched_outcome"] not in CONCLUSIVE:
        out.append("the patched run was %s (%s), so it does not show whether %s fixed it" % (
            facts_["patched_outcome"], (patched or {}).get("why") or "no reason", (patched or {}).get("target_version") or "the patch"))
    if facts_["vulnerable_outcome"] in REPRODUCING and not facts_["patched_build_checked"] and facts_.get("patched_comparable") is None:
        out.append("the patched build has not been checked yet")
    if facts_["outcome_matches_claim"] is False and facts_["vulnerable_outcome"] in REPRODUCING:
        out.append("the outcome class does not match the claimed impact")
    if facts_["severity_supported_by_outcome"] is False:
        out.append("the claimed severity is higher than this outcome supports")
    return out
