"""Tickets on disk, shared by the Intake agent and the agents in #triage.

work/
  R-001/
    ticket.json     structured fields, status, timeline (no reporter prose)
    poc.py          the PoC, run only inside the sandbox
    quarantine.md   the reporter's raw text; only Intake and maintainers read it
    runs/           one JSON record per sandbox run
"""

import json
import re
import time
from pathlib import Path

from .config import WORK_DIR

STATUSES = [
    "awaiting_poc",      # Intake asked the reporter for a runnable PoC
    "quarantined",       # the screen held it; a maintainer decides
    "in_triage",         # ticket posted to #triage
    "reproduced",        # sandbox evidence supports the claim
    "not_reproduced",    # sandbox evidence does not support the claim
    "escalated",         # a maintainer confirmed it as a real bug
    "closed",            # a maintainer closed it
]
TICKET_ID = re.compile(r"\bR-\d{3,}\b")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dir(ticket_id):
    return WORK_DIR / ticket_id


def next_id():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.name[2:]) for p in WORK_DIR.glob("R-*") if p.name[2:].isdigit()]
    return "R-%03d" % (max(numbers, default=0) + 1)


def create(ticket, raw_text, source):
    ticket_id = next_id()
    folder = _dir(ticket_id)
    (folder / "runs").mkdir(parents=True)
    (folder / "quarantine.md").write_text(raw_text, encoding="utf-8")
    if ticket.get("poc"):
        (folder / "poc.py").write_text(ticket["poc"], encoding="utf-8")
    record = {k: v for k, v in ticket.items() if k != "poc"}
    record.update({"id": ticket_id, "status": "new", "source": source,
                   "created_at": now(), "timeline": [], "runs": []})
    save(record)
    return record


def load(ticket_id):
    return json.loads((_dir(ticket_id) / "ticket.json").read_text(encoding="utf-8"))


def save(record):
    folder = _dir(record["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ticket.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


def set_poc(ticket_id, poc):
    (_dir(ticket_id) / "poc.py").write_text(poc, encoding="utf-8")


def poc(ticket_id):
    path = _dir(ticket_id) / "poc.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def append_quarantine(ticket_id, text):
    with open(_dir(ticket_id) / "quarantine.md", "a", encoding="utf-8") as handle:
        handle.write("\n\n---\n\n" + text)


def event(record, what, by, **details):
    record["timeline"].append(dict({"at": now(), "what": what, "by": by}, **details))


def set_status(record, status, by, **details):
    assert status in STATUSES, status
    record["status"] = status
    event(record, "status:" + status, by, **details)
    save(record)


def save_run(ticket_id, run):
    runs = _dir(ticket_id) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    name = "%s-%s.json" % (time.strftime("%H%M%S"), run["build"])
    (runs / name).write_text(json.dumps(run, indent=2), encoding="utf-8")
    return "work/%s/runs/%s" % (ticket_id, name)


def all_tickets():
    if not WORK_DIR.exists():
        return []
    return [load(p.name) for p in sorted(WORK_DIR.glob("R-*")) if (p / "ticket.json").exists()]


def find_by_thread(thread_id):
    for record in all_tickets():
        if record.get("intake_thread") == thread_id:
            return record
    return None
