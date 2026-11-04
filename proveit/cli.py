"""`python -m proveit ...` — the commands the agents in #triage run.

  build                       build the vulnerable and patched sandbox images
  run R-001 [--build NAME]    run a ticket's PoC in the sandbox (default: vulnerable)
  check R-001                 run against both builds and print the verdict
  trace R-001                 show which library functions the PoC reached
  show R-001                  print the ticket (never the reporter's prose)
  list                        list tickets and their status
  tally                       totals for the demo's closing slide
  submit FILE                 create a ticket from a report file, without Switch
"""

import argparse
import json
import sys

from . import judge, reports, sandbox, screen, store
from .config import TARGET


def _print(obj):
    print(json.dumps(obj, indent=2))


def _run(ticket_id, build_name, by="cli"):
    record = store.load(ticket_id)
    code = store.poc(ticket_id)
    if not code:
        sys.exit("%s has no PoC yet" % ticket_id)
    run = sandbox.run_poc(code, build_name)
    path = store.save_run(ticket_id, run)
    record["runs"].append({"build": build_name, "file": path, "at": store.now(), "by": by,
                           "seconds": run.get("seconds")})
    store.save(record)
    return record, run, path


def cmd_build(args):
    built = sandbox.build(force=args.force, quiet=False)
    print("built: %s" % (", ".join(built) or "nothing (images already exist)"))


def cmd_run(args):
    record, run, path = _run(args.ticket, args.build, args.by)
    verdict, reasons = judge.judge_run(record["claim"], run)
    print("%s on %s (PyYAML %s): %s" % (args.ticket, args.build, run["target_version"], verdict.upper()))
    for reason in reasons:
        print("  - " + reason)
    print("evidence: " + path)
    if args.verbose:
        _print(run)


def cmd_check(args):
    record, vuln, vuln_path = _run(args.ticket, "vulnerable", args.by)
    _, patched, patched_path = _run(args.ticket, "patched", args.by)
    summary = judge.compare(record["claim"], vuln, patched)
    record = store.load(args.ticket)
    record["last_check"] = dict(summary, at=store.now(), evidence=[vuln_path, patched_path])
    store.save(record)
    print("%s claim=%s component=%s" % (args.ticket, record["claim"], record["component"]))
    print("vulnerable PyYAML %s: %s" % (TARGET["builds"]["vulnerable"]["version"], summary["vulnerable"].upper()))
    print("patched    PyYAML %s: %s" % (TARGET["builds"]["patched"]["version"], summary["patched"].upper()))
    for reason in summary["reasons"]:
        print("  - " + reason)
    print("evidence: %s, %s" % (vuln_path, patched_path))


def cmd_trace(args):
    record, run, path = _run(args.ticket, args.build, args.by)
    frames = []
    for e in run.get("events", []):
        for f in e.get("library_frames", []):
            if f not in frames:
                frames.append(f)
    print("%s on %s: %d audited events, %d inside the library" % (
        args.ticket, args.build, len(run.get("events", [])), sum(1 for e in run.get("events", []) if e["in_library"])))
    for e in run.get("events", []):
        print("  %-8s %-44s %s" % ("LIBRARY" if e["in_library"] else "poc", e["detail"][:44], " < ".join(e["library_frames"][:3])))
    if run.get("error"):
        err = run["error"]
        print("  raised %s: %s (in library: %s; at %s)" % (err["type"], err["message"], err.get("in_library"), " > ".join(err.get("where", []))))
    print("  peak memory %.1f MB, %.3f s" % (run.get("peak_rss_mb") or 0, run.get("seconds") or 0))
    print("evidence: " + path)


def cmd_show(args):
    record = store.load(args.ticket)
    record["poc_lines"] = len(store.poc(args.ticket).splitlines())
    _print(record)


def cmd_list(args):
    for r in store.all_tickets():
        print("%s  %-15s %-18s %-22s %s" % (r["id"], r["status"], r["claim"] or "-", r["component"], r.get("reporter", "")))


def cmd_tally(args):
    tickets = store.all_tickets()
    counts = {}
    for r in tickets:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    runs = sum(len(r["runs"]) for r in tickets)
    seconds = sum((run.get("seconds") or 0) for r in tickets for run in r["runs"])
    _print({"reports": len(tickets), "by_status": counts, "sandbox_runs": runs,
            "sandbox_seconds": round(seconds, 2)})


def cmd_submit(args):
    text = open(args.file, encoding="utf-8").read()
    result = screen.screen(text)
    ticket = reports.parse(text, args.reporter)
    record = store.create(ticket.to_dict(), text, source="cli:" + args.file)
    if result.blocked:
        record["screen"] = result.findings
        store.set_status(record, "quarantined", "cli", why=result.summary())
    elif not ticket.complete():
        store.set_status(record, "awaiting_poc", "cli", missing=ticket.missing)
    else:
        store.set_status(record, "in_triage", "cli")
    print(record["id"], record["status"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="proveit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_build)
    for name, fn in (("run", cmd_run), ("trace", cmd_trace)):
        p = sub.add_parser(name)
        p.add_argument("ticket")
        p.add_argument("--build", choices=list(TARGET["builds"]), default="vulnerable")
        p.add_argument("--by", default="cli")
        p.add_argument("-v", "--verbose", action="store_true")
        p.set_defaults(fn=fn)
    p = sub.add_parser("check"); p.add_argument("ticket"); p.add_argument("--by", default="cli"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("show"); p.add_argument("ticket"); p.set_defaults(fn=cmd_show)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("tally").set_defaults(fn=cmd_tally)
    p = sub.add_parser("submit"); p.add_argument("file"); p.add_argument("--reporter", default="local"); p.set_defaults(fn=cmd_submit)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
