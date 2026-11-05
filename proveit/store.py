"""Tickets on disk, shared by the Intake agent and the agents in #triage.

work/                      what agents may read (nothing in it is reporter text)
  R-001/
    ticket.json            fixed fields, status, timeline
    runs/                  one sanitized sandbox record per run
~/.proveit/<checkout>/private/
  R-001/                   reporter-controlled material, outside the checkout.
    report.md              Only Intake, the sandbox and maintainers on the host read it;
    payload.yaml           the Skeptic's sandbox profile and the Reproducer's settings
    screen.json            both deny ~/.proveit.
    contact.json

With PROVEIT_WORK_DIR (tests, the rehearsal, e2e) the private folder sits next
to the work folder instead, unless PROVEIT_PRIVATE_DIR says otherwise.
"""

import json
import os
import re
import shutil
import time
from pathlib import Path

from . import config, states

TICKET_ID = re.compile(r"\bR-\d{3,}\b")


def work_dir():
    return Path(config.WORK_DIR)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dir(ticket_id):
    if not re.fullmatch(r"R-\d{3,}", ticket_id or ""):
        raise FileNotFoundError(ticket_id)
    return work_dir() / ticket_id


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def next_id():
    work_dir().mkdir(parents=True, exist_ok=True)
    numbers = [int(p.name[2:]) for p in work_dir().glob("R-*") if p.name[2:].isdigit()]
    return "R-%03d" % (max(numbers, default=0) + 1)


def private_root():
    """Where reporter material lives: ~/.proveit/<checkout>/private for the real ticket store,
    or next to a work folder moved with PROVEIT_WORK_DIR (tests, the rehearsal, e2e)."""
    explicit = os.environ.get("PROVEIT_PRIVATE_DIR")
    if explicit:
        return Path(explicit)
    if work_dir().resolve() == config.DEFAULT_WORK_DIR.resolve():
        return config.PROVEIT_HOME / "private"
    return work_dir().parent / ".proveit-private"


def private_dir(ticket_id):
    """The ticket's private folder, moving one left by an older version out of work/ first."""
    folder = private_root() / _dir(ticket_id).name
    legacy = _dir(ticket_id) / "private"
    if legacy.is_dir() and not folder.exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(folder))
    return folder


def create(fields, raw_text, source):
    """fields: only fixed values (claim, severity, entry_point, ...). raw_text goes to the private folder."""
    ticket_id = next_id()
    folder = _dir(ticket_id)
    (folder / "runs").mkdir(parents=True)
    private = private_dir(ticket_id)
    private.mkdir(parents=True, mode=0o700)
    _write(private / "report.md", raw_text)
    record = dict(fields, id=ticket_id, status="new", source=source, created_at=now(),
                  times={"received": time.time()}, timeline=[], runs=[])
    save(record)
    return record


def load(ticket_id):
    return json.loads((_dir(ticket_id) / "ticket.json").read_text(encoding="utf-8"))


def save(record):
    _write(_dir(record["id"]) / "ticket.json", json.dumps(record, indent=2, sort_keys=True))


def private_path(ticket_id, name):
    return private_dir(ticket_id) / name


def set_payload(ticket_id, payload):
    _write(private_path(ticket_id, "payload.yaml"), payload)


def payload(ticket_id):
    path = private_path(ticket_id, "payload.yaml")
    return path.read_text(encoding="utf-8") if path.exists() else ""


def append_report(ticket_id, text):
    with open(private_path(ticket_id, "report.md"), "a", encoding="utf-8") as handle:
        handle.write("\n\n---\n\n" + text)


def save_private_json(ticket_id, name, data):
    _write(private_path(ticket_id, name), json.dumps(data, indent=2))


def load_private_json(ticket_id, name):
    path = private_path(ticket_id, name)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def event(record, what, by, **details):
    record["timeline"].append(dict({"at": now(), "what": what, "by": by}, **details))


def apply(record, command, actor, by, target=None, **details):
    """Move a ticket through the state machine. Raises states.IllegalTransition."""
    before = record["status"]
    after = states.transition(before, command, actor, target)
    record["status"] = after
    times = record.setdefault("times", {})
    if after == "in_triage" and "triaged" not in times:
        times["triaged"] = time.time()
    if after in states.TERMINAL:
        times["decided"] = time.time()
    event(record, command, by, actor=actor, **{"from": before, "to": after}, **details)
    save(record)
    return after


def save_run(ticket_id, run):
    runs = _dir(ticket_id) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    index = len(list(runs.glob("*.json"))) + 1
    name = "%02d-%s.json" % (index, run["build"])
    _write(runs / name, json.dumps(run, indent=2, sort_keys=True))
    return "work/%s/runs/%s" % (ticket_id, name)


def load_run(display_path):
    """Read a run saved by save_run, from the path it returned (work/R-001/runs/01-...json)."""
    parts = Path(display_path).parts
    return json.loads((work_dir().joinpath(*parts[1:])).read_text(encoding="utf-8"))


def all_tickets():
    if not work_dir().exists():
        return []
    return [load(p.name) for p in sorted(work_dir().glob("R-*")) if (p / "ticket.json").exists()]


def find_by_thread(thread_id):
    for record in all_tickets():
        if load_private_json(record["id"], "contact.json").get("intake_thread") == thread_id:
            return record
    return None
