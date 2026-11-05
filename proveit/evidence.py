"""The evidence pack: everything an agent may know about a ticket, and nothing a reporter wrote."""

from . import judge, store
from .config import TARGET

TICKET_FIELDS = ("id", "status", "claim", "severity", "entry_point", "payload_sha256", "payload_bytes", "tags",
                 "poc_problem", "missing", "screen_rules")


def latest_run(record, build):
    for entry in reversed(record.get("runs", [])):
        if entry["build"] == build:
            return store.load_run(entry["file"])
    return None


def pack(record):
    vulnerable = latest_run(record, "vulnerable")
    patched = latest_run(record, "patched")
    facts = judge.facts(record, vulnerable, patched)
    return {
        "ticket": {k: record.get(k) for k in TICKET_FIELDS if k in record},
        "target": {name: spec["version"] for name, spec in TARGET["builds"].items()},
        "vulnerable_run": judge.summary(vulnerable) if vulnerable else None,
        "patched_run": judge.summary(patched) if patched else None,
        "runs": [{"build": r["build"], "file": r["file"], "outcome": r.get("outcome"), "by": r.get("by")}
                 for r in record.get("runs", [])],
        "checklist": facts,
        "notes": judge.notes(facts),
        "skeptic": record.get("skeptic"),
        "override": record.get("override"),
    }


def text(p):
    t = p["ticket"]
    lines = ["Evidence pack %s (status: %s)" % (t["id"], t["status"]),
             "claim %s | claimed severity %s | entry point %s | payload sha256 %s (%s bytes)" % (
                 t.get("claim") or "-", t.get("severity") or "-", t.get("entry_point") or "-",
                 (t.get("payload_sha256") or "-")[:16], t.get("payload_bytes")),
             "tags: %s" % (", ".join(t.get("tags") or []) or "none")]
    for key in ("vulnerable_run", "patched_run"):
        run = p[key]
        if run:
            lines.append("- " + judge.describe(run))
        else:
            lines.append("- %s build: not run yet" % key.split("_")[0])
    lines.append("checklist:")
    for name, value in p["checklist"].items():
        lines.append("  %-34s %s" % (name, "unknown" if value is None else value))
    for note in p["notes"]:
        lines.append("note: " + note)
    if p.get("skeptic"):
        s = p["skeptic"]
        lines.append("skeptic: %s by %s%s" % (s["verdict"], s["by"], (": " + s["reason"]) if s.get("reason") else ""))
    if p.get("override"):
        lines.append("override by %s" % p["override"]["by"])
    return "\n".join(lines)
