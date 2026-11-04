"""Deciding what a sandbox run proves. Rules, not opinions.

The agents argue about the evidence in the triage room; this module is what
they cite. A verdict here never closes a report: a maintainer does that.
"""

from .config import DOS_MEMORY_MB, DOS_SECONDS

REPRODUCED = "reproduced"
NOT_REPRODUCED = "not_reproduced"
INVALID_PROOF = "invalid_proof"
INCONCLUSIVE = "inconclusive"

ENVIRONMENT_ERRORS = {"SyntaxError", "IndentationError", "ModuleNotFoundError", "ImportError", "FileNotFoundError"}


def judge_run(claim, run):
    """Return (verdict, reasons) for one run of one claim."""
    reasons = []
    if run.get("harness_lost") and not run.get("timed_out") and not run.get("killed"):
        return INCONCLUSIVE, ["the harness produced no record (exit code %s)" % run.get("exit_code")]

    error = run.get("error") or {}
    if error.get("type") in ENVIRONMENT_ERRORS and not error.get("in_library"):
        return INCONCLUSIVE, ["the PoC itself failed before reaching the library: %s: %s" % (error.get("type"), error.get("message"))]

    lib_exec = [e for e in run.get("events", []) if e["in_library"] and e["event"] in ("exec", "compile", "os.system", "subprocess.Popen", "os.exec", "os.posix_spawn")]

    if claim == "code_execution":
        if run.get("marker_written_by_library"):
            reasons.append("the library wrote %s itself (call stack: %s)" % (
                "/tmp/proveit_marker", ", ".join(next(e["library_frames"] for e in run["events"] if e["in_library"] and e["detail"].endswith("proveit_marker"))[:3])))
            return REPRODUCED, reasons
        if run.get("marker_written_by_poc"):
            return INVALID_PROOF, ["the marker was written by the PoC script, not by the library"]
        if lib_exec:
            reasons.append("the library evaluated code (%s) but the marker was never created" % lib_exec[0]["detail"])
        if error:
            reasons.append("the library refused the input: %s: %s" % (error.get("type"), error.get("message")))
        reasons.append("no code ran from inside the library")
        return NOT_REPRODUCED, reasons

    if claim == "denial_of_service":
        rss, secs = run.get("peak_rss_mb") or 0, run.get("seconds") or 0
        if run.get("timed_out") or run.get("killed") or rss > DOS_MEMORY_MB or secs > DOS_SECONDS:
            return REPRODUCED, ["resource limit hit: %.0f MB peak, %.2f s%s" % (rss, secs, ", killed" if run.get("killed") else "")]
        return NOT_REPRODUCED, ["the call finished normally: %.1f MB peak memory, %.3f s" % (rss, secs)]

    if claim == "crash":
        signal = run.get("signal")
        if signal and signal != 9:
            return REPRODUCED, ["the interpreter died with signal %s" % signal]
        if error:
            return NOT_REPRODUCED, ["a Python exception is not a crash: %s: %s" % (error.get("type"), error.get("message"))]
        return NOT_REPRODUCED, ["the process exited normally"]

    if claim == "info_leak":
        return INCONCLUSIVE, ["information leaks need a maintainer to read the output; nothing is decided automatically"]

    return INCONCLUSIVE, ["no rule for claim %r" % claim]


def compare(claim, vulnerable_run, patched_run=None):
    """Verdict across builds: a real bug reproduces before the fix and not after."""
    verdict, reasons = judge_run(claim, vulnerable_run)
    summary = {"verdict": verdict, "reasons": reasons, "vulnerable": verdict}
    if patched_run is not None:
        patched_verdict, patched_reasons = judge_run(claim, patched_run)
        summary["patched"] = patched_verdict
        summary["patched_reasons"] = patched_reasons
        if verdict == REPRODUCED and patched_verdict == REPRODUCED:
            summary["reasons"].append("it also reproduces on the patched build, so this may be a new issue")
        elif verdict == REPRODUCED:
            summary["reasons"].append("it does not reproduce on the patched build (%s)" % patched_reasons[0])
    return summary
