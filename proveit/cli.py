"""`python -m proveit ...`: the commands the agents in #triage and maintainers run.

  build                          build the vulnerable and patched sandbox images
  check R-001 [--build patched]  run the ticket's payload on one build (default: vulnerable)
        [--loader full_load]     ...optionally through another allowlisted entry point
  evidence R-001                 the evidence pack: fixed fields only, never reporter text
  show R-001                     the ticket record
  list                           tickets and their status
  concur R-001                   the Skeptic could not disprove the evidence
  dispute R-001 --reason TEXT    the Skeptic disputes it; blocks escalation until a human overrides
  override R-001 --by NAME       a maintainer overrides a dispute (humans only)
  cost R-001 --usd X --source S  a maintainer records agent cost from Switch ROI or a dashboard (humans only)
  tally                          totals for the demo's closing slide
  submit FILE                    create a ticket from a report file, without Switch

Agents run these with PROVEIT_ACTOR=agent (set in .claude/settings.json and
.codex/config.toml); override and cost then refuse.
"""

import argparse
import json
import os
import sys

from . import actions, evidence, judge, reports, sandbox, screen, states, store
from .config import ENTRY_POINTS, TARGET


def actor():
    return "agent" if os.environ.get("PROVEIT_ACTOR", "").strip().lower() == "agent" else "human"


def _print(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_build(args):
    built = sandbox.build(force=args.force, quiet=False)
    print("built: %s" % (", ".join(built) or "nothing (images are current)"))


def cmd_check(args):
    record, run, path = actions.check(args.ticket, args.build, actor(), args.by, args.loader)
    print("%s %s build (PyYAML %s) via %s: %s" % (args.ticket, args.build, run["target_version"],
                                                 run.get("entry_point"), run.get("outcome")))
    print("  - " + judge.describe(run))
    print("ticket status: %s" % record["status"])
    for note in judge.notes(judge.facts(record, evidence.latest_run(record, "vulnerable"),
                                        evidence.latest_run(record, "patched"))):
        print("note: " + note)
    print("evidence: " + path)


def cmd_evidence(args):
    pack = evidence.pack(store.load(args.ticket))
    if args.json:
        _print(pack)
    else:
        print(evidence.text(pack))


def cmd_show(args):
    _print(store.load(args.ticket))


def cmd_list(args):
    for r in store.all_tickets():
        print("%s  %-15s %-18s %s" % (r["id"], r["status"], r.get("claim") or "-", r.get("entry_point") or "-"))


def cmd_concur(args):
    record = actions.concur(args.ticket, actor(), args.by)
    print("%s: %s concurs; status %s" % (args.ticket, args.by, record["status"]))


def cmd_dispute(args):
    record = actions.dispute(args.ticket, args.reason, actor(), args.by)
    print("%s: disputed by %s; escalation is blocked until a maintainer overrides" % (record["id"], args.by))


def cmd_override(args):
    record = actions.override(args.ticket, actor(), args.by, args.note or "")
    print("%s: override by %s recorded; status %s" % (record["id"], args.by, record["status"]))


def cmd_cost(args):
    record = actions.record_cost(args.ticket, args.usd, args.source, actor(), args.by)
    print("%s: agent cost $%.2f recorded (source: %s)" % (record["id"], record["cost"]["usd"], record["cost"]["source"]))


def cmd_tally(args):
    t = actions.tally()
    if args.json:
        _print(t)
    else:
        print(actions.tally_text(t))


def cmd_submit(args):
    """Offline intake for one report file: the same parsing and screening as the agent."""
    from .intake import fill, target_for
    text = open(args.file, encoding="utf-8").read()
    result = screen.screen(text)
    ticket = reports.parse(text)
    record = store.create({}, text, source="cli")
    fill(record, ticket)
    if result.blocked:
        record["screen_rules"] = sorted({f["rule"] for f in result.findings})
        store.save_private_json(record["id"], "screen.json", result.findings)
        target = "quarantined"
    else:
        target = target_for(ticket)
    store.apply(record, "receive", "human", "cli", target=target)
    print(record["id"], record["status"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m proveit", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("check")
    p.add_argument("ticket")
    p.add_argument("--build", choices=list(TARGET["builds"]), default="vulnerable")
    p.add_argument("--loader", choices=list(ENTRY_POINTS), help="run through another allowlisted entry point")
    p.add_argument("--by", default="cli")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("evidence"); p.add_argument("ticket"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_evidence)
    p = sub.add_parser("show"); p.add_argument("ticket"); p.set_defaults(fn=cmd_show)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("concur"); p.add_argument("ticket"); p.add_argument("--by", default="skeptic"); p.set_defaults(fn=cmd_concur)
    p = sub.add_parser("dispute"); p.add_argument("ticket"); p.add_argument("--reason", required=True)
    p.add_argument("--by", default="skeptic"); p.set_defaults(fn=cmd_dispute)
    p = sub.add_parser("override"); p.add_argument("ticket"); p.add_argument("--by", required=True)
    p.add_argument("--note"); p.set_defaults(fn=cmd_override)
    p = sub.add_parser("cost"); p.add_argument("ticket"); p.add_argument("--usd", type=float, required=True)
    p.add_argument("--source", required=True); p.add_argument("--by", default="maintainer"); p.set_defaults(fn=cmd_cost)
    p = sub.add_parser("tally"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_tally)
    p = sub.add_parser("submit"); p.add_argument("file"); p.set_defaults(fn=cmd_submit)
    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except states.IllegalTransition as exc:
        sys.exit("refused: %s" % exc)
    except FileNotFoundError as exc:
        sys.exit("no such ticket: %s" % exc)


if __name__ == "__main__":
    main()
