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
              "exit_code", "signal", "timed_out", "seconds", "peak_rss_mb", "marker_created",
              "exception_type", "exception_sha256", "exception_frames", "dropped_values", "ran")


def status_for(run):
    """The ticket state a vulnerable-build run supports, or None if it proves nothing either way."""
    outcome = run.get("outcome")
    if outcome in REPRODUCING:
        return "reproduced"
    if outcome in (NOT_REPRODUCED, INVALID_PROOF):
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
    return {
        "entry_point_allowlisted": bool(record.get("entry_point")) and not record.get("poc_problem"),
        "vulnerable_outcome": outcome,
        "outcome_matches_claim": None if outcome is None else CLAIM_FOR_OUTCOME.get(outcome) == claimed,
        "library_frames_recorded": in_library,
        "code_execution_proven_by_marker": None if vulnerable is None else bool(vulnerable.get("marker_created")),
        "patched_build_checked": patched is not None,
        "patched_outcome": patched_outcome,
        "reproduces_on_patched_too": None if patched is None or outcome is None else (
            outcome in REPRODUCING and patched_outcome in REPRODUCING),
        "claimed_severity": severity,
        "severity_supported_by_outcome": None if outcome is None or severity in (None, "unrated") else (
            ceiling is not None and SEVERITY_RANK.get(severity, 0) <= SEVERITY_RANK[ceiling]),
    }


def notes(facts_):
    """Fixed sentences a human should read before deciding."""
    out = []
    if facts_["reproduces_on_patched_too"]:
        out.append("reproduces on the patched build too: possible new issue, human review required")
    if facts_["vulnerable_outcome"] in REPRODUCING and not facts_["patched_build_checked"]:
        out.append("the patched build has not been checked yet")
    if facts_["outcome_matches_claim"] is False and facts_["vulnerable_outcome"] in REPRODUCING:
        out.append("the outcome class does not match the claimed impact")
    if facts_["severity_supported_by_outcome"] is False:
        out.append("the claimed severity is higher than this outcome supports")
    return out
