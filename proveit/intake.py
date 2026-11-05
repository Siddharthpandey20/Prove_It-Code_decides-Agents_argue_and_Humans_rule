"""The Intake agent: Prove It's own Switch agent, built on the agent protocol.

It sits in two linked rooms:

  #proveit-intake   anyone can post a report here. Intake is the only agent
                    in the room, and it runs no code and has no shell.
  #proveit-triage   maintainers, the Reproducer (Claude Code) and the Skeptic
                    (Codex). Intake posts structured tickets here and relays
                    the maintainers' decisions back to the reporter's thread.

It deliberately has no language model. The one component that reads
attacker-controlled prose is plain code that cannot be talked into anything:
it screens the text, demands a runnable proof, and hands the agents in triage
a ticket of fixed fields plus a PoC file that only ever runs in the sandbox.

  python -m proveit.intake setup   register the agent with a Switch server
  python -m proveit.intake run     connect to the rooms and work
"""

import argparse
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

from . import judge, reports, sandbox, screen, store
from .config import PROOF_CONTRACT, REPO_ROOT, TARGET
from .switch_client import Agent, SwitchError, open_to_everyone, register_agent

log = logging.getLogger("proveit.intake")
STATE_FILE = Path(os.environ.get("PROVEIT_STATE", REPO_ROOT / ".proveit" / "intake.json"))

DEFAULTS = {
    "agent_name": "prove-it-intake",
    "intake_room": "proveit-intake",
    "triage_room": "proveit-triage",
    "reproducer": "prove-it-reproducer",
    "skeptic": "prove-it-skeptic",
}

CLAIM_WORDS = {
    "code_execution": "code execution",
    "denial_of_service": "denial of service",
    "crash": "crash",
    "info_leak": "information leak",
}


# --------------------------------------------------------------------------
# Finding the Switch server Console runs, so nobody copies secrets by hand.
# --------------------------------------------------------------------------
def console_env_candidates():
    home = Path.home()
    roots = [Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")),
             home / "Library" / "Application Support",
             Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))]
    found = []
    for root in roots:
        if root.exists():
            found.extend(root.glob("*/local-switch-server/.env"))
            found.extend(root.glob("*/local-switch-server/native/run/switch-core.env"))
    return found


def read_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    return values


def load_state():
    if not STATE_FILE.exists():
        sys.exit("No agent registered yet. Run: python -m proveit.intake setup")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    (STATE_FILE.parent / ".gitignore").write_text("*\n")
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def cmd_setup(args):
    env_file = args.env_file
    if not env_file:
        candidates = console_env_candidates()
        if not candidates:
            sys.exit("Could not find Switch Console's local server. Start it in Switch Console "
                     "(Add a server > Run a server on this computer), or pass --env-file.")
        env_file = str(candidates[0])
    env = read_env(env_file)
    api_url = args.api_url or "http://127.0.0.1:%s" % env.get("API_HOST_PORT", env.get("SERVER_PORT", "8000"))
    token = env.get("AGENT_REGISTRATION_TOKEN")
    if not token:
        sys.exit("%s has no AGENT_REGISTRATION_TOKEN" % env_file)
    print("Switch server: %s (settings from %s)" % (api_url, env_file))

    name = args.agent_name
    try:
        reg = register_agent(api_url, token, name,
                             "Prove It intake: screens bug reports and asks for a runnable proof before any human reads them.",
                             display_name="Prove It Intake", overwrite=args.overwrite)
    except SwitchError as exc:
        if exc.status == 409:
            sys.exit("An agent named %s already exists. Re-run with --overwrite to replace its key." % name)
        raise
    print("Registered agent %s (%s)" % (name, reg["id"]))

    if env.get("GATEWAY_ADMIN_EMAIL") and env.get("GATEWAY_ADMIN_PASSWORD"):
        open_to_everyone(api_url, env["GATEWAY_ADMIN_EMAIL"], env["GATEWAY_ADMIN_PASSWORD"], reg["id"])
        print("Opened %s to everyone in its rooms, so reporters can reach it" % name)
    else:
        print("WARNING: no Gateway admin login in %s. In Switch Console, set this agent's "
              "'Who can talk to your agent' to everyone." % env_file)

    state = dict(DEFAULTS, agent_name=name, api_url=api_url, agent_id=reg["id"], api_key=reg["api_key"])
    for key in ("intake_room", "triage_room", "reproducer", "skeptic"):
        if getattr(args, key):
            state[key] = getattr(args, key)
    save_state(state)
    print("Saved credentials to %s (git-ignored)" % STATE_FILE)

    if args.create_rooms:
        agent = Agent(api_url, reg["id"], reg["api_key"])
        users = args.users.split(",") if args.users else None
        intake = agent.room_id(state["intake_room"]) or agent.create_room(
            state["intake_room"], "Report a security bug here. Prove It asks for a runnable proof before any maintainer reads it.",
            [name], users)["id"]
        triage_agents = [name] + [a for a in (state["reproducer"], state["skeptic"]) if a and args.with_agents]
        triage = agent.room_id(state["triage_room"]) or agent.create_room(
            state["triage_room"], "Maintainers and agents: tickets arrive here with proof, not opinions.",
            triage_agents, users)["id"]
        try:
            agent.link_rooms(intake, triage, "triage")
        except SwitchError as exc:
            print("note: could not link rooms (%s)" % exc)
        print("Rooms ready: %s, %s" % (state["intake_room"], state["triage_room"]))
    print("\nNext: python -m proveit.intake run")


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------
class Intake:
    def __init__(self, state, auto_check=False):
        self.state = state
        self.agent = Agent(state["api_url"], state["agent_id"], state["api_key"])
        self.auto_check = auto_check
        self.names = {state["agent_name"]}
        self.lock = threading.Lock()
        self.intake = None
        self.triage = None

    # -- helpers -------------------------------------------------------------
    def mention(self, who):
        return "@" + self.state[who]

    def is_self(self, payload):
        return payload.get("sender_name") in self.names

    @staticmethod
    def is_system(payload):
        return payload.get("sender_kind") == "platform" and not payload.get("on_behalf_of")

    def start(self):
        detail = self.agent.op("get_agent_detail", {"agent_id": self.agent.id}) or {}
        for key in ("name", "display_name"):
            if detail.get(key):
                self.names.add(detail[key])
        intake_id = self.agent.room_id(self.state["intake_room"])
        triage_id = self.agent.room_id(self.state["triage_room"])
        if not intake_id or not triage_id:
            sys.exit("Rooms %s / %s not found or %s is not in them. Deploy switch/prove-it.template.yaml "
                     "in Switch Console, or run setup with --create-rooms." % (
                         self.state["intake_room"], self.state["triage_room"], self.state["agent_name"]))
        self.intake = self.agent.connect(intake_id, self.on_intake_event)
        self.triage = self.agent.connect(triage_id, self.on_triage_event)
        for conn in (self.intake, self.triage):
            if not conn.ready.wait(20):
                sys.exit("Could not open the event stream for room %s" % conn.room_id)
        log.info("Intake is listening in #%s and #%s", self.state["intake_room"], self.state["triage_room"])

    # -- #proveit-intake -----------------------------------------------------
    def on_intake_event(self, conn, kind, frame):
        if kind != "message":
            return
        payload = frame["payload"]
        if self.is_self(payload) or self.is_system(payload) or not payload.get("body", "").strip():
            return
        with self.lock:
            thread = payload.get("thread_id")
            if thread and thread != payload["message_id"]:
                record = store.find_by_thread(thread)
                if record:
                    self.followup(record, payload)
                return
            self.new_report(payload)

    def new_report(self, payload):
        text, reporter, thread = payload["body"], payload.get("sender_name", "unknown"), payload["message_id"]
        result = screen.screen(text)
        ticket = reports.parse(text, reporter)
        record = store.create(ticket.to_dict(), text, source="switch")
        record["intake_thread"] = thread
        store.event(record, "received", "intake", reporter=reporter)

        if result.blocked:
            record["screen"] = result.findings
            store.set_status(record, "quarantined", "intake", why=result.summary())
            self.intake.post(
                "**%s held for review.** Your report contains text written to our AI reviewers rather than "
                "about the bug (%s). It has not been shown to any agent. A maintainer will read it." %
                (record["id"], result.summary()), thread)
            rules = ", ".join(sorted({f["rule"] for f in result.findings}))
            self.triage.post(
                "**%s quarantined** at intake. Screen rules hit: `%s`. The reporter's text was not passed to any agent; "
                "maintainers can read `work/%s/quarantine.md` on the host. Reply `%s release %s` to send it on, "
                "or `%s close %s <reason>`." % (record["id"], rules, record["id"], self.mention("agent_name"), record["id"],
                                                 self.mention("agent_name"), record["id"]))
            return

        if not ticket.complete():
            store.set_status(record, "awaiting_poc", "intake", missing=ticket.missing)
            self.intake.post(self.ask_for_proof(record["id"], ticket), thread)
            return

        self.accept(record, thread)

    def followup(self, record, payload):
        if record["status"] != "awaiting_poc":
            self.intake.post("%s is %s. A maintainer will reply in this thread." % (record["id"], record["status"].replace("_", " ")),
                             record["intake_thread"])
            return
        text = payload["body"]
        result = screen.screen(text)
        store.append_quarantine(record["id"], text)
        if result.blocked:
            record["screen"] = result.findings
            store.set_status(record, "quarantined", "intake", why=result.summary())
            self.intake.post("**%s held for review**: your follow-up contains text written to our AI reviewers (%s)." %
                             (record["id"], result.summary()), record["intake_thread"])
            self.triage.post("**%s quarantined** at intake (follow-up). Reply `%s release %s` to send it on." %
                             (record["id"], self.mention("agent_name"), record["id"]))
            return
        previous = reports.Ticket(title=record.get("title", ""), reporter=record.get("reporter", ""),
                                  claim=record.get("claim", ""), severity=record.get("severity", ""),
                                  component=record.get("component", ""), poc=store.poc(record["id"]),
                                  missing=record.get("missing", []))
        merged = reports.merge(previous, text)
        record.update({k: v for k, v in merged.to_dict().items() if k != "poc"})
        if merged.poc:
            store.set_poc(record["id"], merged.poc)
        if not merged.complete():
            store.set_status(record, "awaiting_poc", "intake", missing=merged.missing)
            self.intake.post(self.ask_for_proof(record["id"], merged), record["intake_thread"])
            return
        self.accept(record, record["intake_thread"])

    def ask_for_proof(self, ticket_id, ticket):
        lines = ["**%s received, but it cannot be checked yet.** Prove It only passes on reports with a runnable proof." % ticket_id]
        if "claim" in ticket.missing:
            lines.append("Say what the bug lets an attacker do: code execution, denial of service, a crash, or an information leak.")
        if "poc" in ticket.missing:
            lines.append("Reply in this thread with a Python proof of concept in a ```python block. It runs against "
                         "%s %s in a sandbox with no network." % (TARGET["name"], TARGET["builds"]["vulnerable"]["version"]))
        if ticket.claim in PROOF_CONTRACT:
            lines.append("What counts as proof for %s: %s" % (CLAIM_WORDS[ticket.claim], PROOF_CONTRACT[ticket.claim]))
        return "\n\n".join(lines)

    def accept(self, record, thread):
        store.set_status(record, "in_triage", "intake")
        self.intake.post(
            "**Received as %s.** Your proof of concept will run in an isolated sandbox against %s %s and the patched %s, "
            "and the result will be posted in this thread after a maintainer reviews it." % (
                record["id"], TARGET["name"], TARGET["builds"]["vulnerable"]["version"], TARGET["builds"]["patched"]["version"]), thread)
        self.post_ticket(record)

    def post_ticket(self, record):
        tid = record["id"]
        msg = (
            "**Ticket %s** · claim `%s` · component `%s` · claimed severity `%s` · reporter `%s`\n"
            "PoC: `work/%s/poc.py` (untrusted code: run it only through the sandbox commands below)\n\n"
            "%s run `python -m proveit check %s --by reproducer` and post the verdict with its evidence.\n"
            "%s once the Reproducer has posted, try to disprove it: `python -m proveit trace %s --by skeptic`. "
            "Is the claimed code path reached inside the library, or did the PoC fake it?\n\n"
            "Maintainers decide: `%s escalate %s` or `%s close %s <reason>`." % (
                tid, record["claim"], record["component"], record["severity"], record.get("reporter", "?"), tid,
                self.mention("reproducer"), tid, self.mention("skeptic"), tid,
                self.mention("agent_name"), tid, self.mention("agent_name"), tid))
        self.triage.post(msg)
        if self.auto_check:
            threading.Thread(target=self.run_check, args=(tid,), daemon=True).start()

    def run_check(self, ticket_id):
        """Without a Reproducer agent in the room, Intake runs the check itself."""
        try:
            record = store.load(ticket_id)
            code = store.poc(ticket_id)
            vuln = sandbox.run_poc(code, "vulnerable")
            patched = sandbox.run_poc(code, "patched")
            paths = [store.save_run(ticket_id, vuln), store.save_run(ticket_id, patched)]
            summary = judge.compare(record["claim"], vuln, patched)
            record = store.load(ticket_id)
            record["runs"] += [{"build": r["build"], "file": p, "at": store.now(), "by": "intake", "seconds": r.get("seconds")}
                               for r, p in zip((vuln, patched), paths)]
            record["last_check"] = dict(summary, at=store.now(), evidence=paths)
            store.set_status(record, "reproduced" if summary["verdict"] == judge.REPRODUCED else "not_reproduced", "intake")
            self.triage.post(self.format_check(ticket_id, summary, paths))
        except Exception as exc:
            log.exception("check failed")
            self.triage.post("Sandbox check for %s failed: %s" % (ticket_id, exc))

    @staticmethod
    def format_check(ticket_id, summary, paths):
        lines = ["**Sandbox check %s**" % ticket_id,
                 "- vulnerable %s %s: **%s**" % (TARGET["name"], TARGET["builds"]["vulnerable"]["version"], summary["vulnerable"].upper()),
                 "- patched %s %s: **%s**" % (TARGET["name"], TARGET["builds"]["patched"]["version"], summary.get("patched", "-").upper())]
        lines += ["- " + r for r in summary["reasons"]]
        lines.append("Evidence: " + ", ".join("`%s`" % p for p in paths))
        return "\n".join(lines)

    # -- #proveit-triage -------------------------------------------------------
    COMMAND = re.compile(r"\b(escalate|close|release|status|tally)\b\s*(R-\d{3,})?\s*(.*)", re.I | re.S)

    def on_triage_event(self, conn, kind, frame):
        if kind != "message":
            return
        payload = frame["payload"]
        if self.is_self(payload) or self.is_system(payload):
            return
        body = payload.get("body", "")
        if not any(("@" + n) in body for n in self.names):
            return
        if payload.get("sender_kind") == "agent" or str(payload.get("sender", "")).startswith("@switch-agent"):
            return  # only people decide; agents' opinions stay opinions
        match = self.COMMAND.search(body)
        with self.lock:
            if not match:
                self.triage.post("Commands: `escalate R-001 [note]`, `close R-001 <reason>`, `release R-001`, `status`, `tally`.",
                                 payload.get("thread_id"))
                return
            verb, ticket_id, rest = match.group(1).lower(), match.group(2), match.group(3).strip()
            who = payload.get("sender_name", "a maintainer")
            if verb == "status":
                self.triage.post(self.status_text(), payload.get("thread_id"))
                return
            if verb == "tally":
                self.triage.post(self.tally_text(), payload.get("thread_id"))
                return
            if not ticket_id:
                self.triage.post("Which ticket? For example `%s %s R-001`." % (self.mention("agent_name"), verb))
                return
            try:
                record = store.load(ticket_id)
            except FileNotFoundError:
                self.triage.post("There is no ticket %s." % ticket_id)
                return
            getattr(self, "do_" + verb)(record, who, rest)

    def do_release(self, record, who, note):
        if record["status"] != "quarantined":
            self.triage.post("%s is not quarantined (it is %s)." % (record["id"], record["status"]))
            return
        store.event(record, "released", who, note=note)
        if not store.poc(record["id"]) or not record.get("claim"):
            store.set_status(record, "awaiting_poc", who)
            self.intake.post(self.ask_for_proof(record["id"], reports.Ticket(**{**{k: record.get(k, "") for k in ("title", "reporter", "claim", "severity", "component")}, "missing": record.get("missing", [])})), record.get("intake_thread"))
            return
        self.triage.post("%s released by %s." % (record["id"], who))
        self.accept(record, record.get("intake_thread"))

    def do_escalate(self, record, who, note):
        store.set_status(record, "escalated", who, note=note)
        check = record.get("last_check") or {}
        evidence = "; ".join(check.get("reasons", [])[:2]) or "see the maintainer's note"
        self.triage.post("%s escalated by %s. Telling the reporter." % (record["id"], who))
        if record.get("intake_thread"):
            self.intake.post(
                "**%s confirmed by a maintainer.** It reproduced in the sandbox: %s.%s\n\n%s" % (
                    record["id"], evidence, (" Maintainer's note: " + note) if note else "", self.cost_line(record)),
                record["intake_thread"])

    def do_close(self, record, who, note):
        store.set_status(record, "closed", who, note=note)
        check = record.get("last_check") or {}
        reasons = check.get("reasons") or []
        self.triage.post("%s closed by %s. Telling the reporter." % (record["id"], who))
        if record.get("intake_thread"):
            text = "**%s closed by a maintainer.**" % record["id"]
            if note:
                text += " Reason: " + note
            if reasons:
                text += "\n\nWhat the sandbox recorded: " + "; ".join(reasons[:3]) + "."
            text += "\n\n" + self.cost_line(record)
            self.intake.post(text, record["intake_thread"])

    @staticmethod
    def cost_line(record):
        runs = record.get("runs", [])
        secs = sum((r.get("seconds") or 0) for r in runs)
        decisions = sum(1 for e in record.get("timeline", []) if e["what"] in ("status:escalated", "status:closed"))
        return "_Cost of this decision: %d sandbox runs (%.2f s of sandbox time) and %d maintainer message._" % (len(runs), secs, max(decisions, 1))

    @staticmethod
    def status_text():
        tickets = store.all_tickets()
        if not tickets:
            return "No tickets yet."
        return "\n".join("- **%s** %s · %s · `%s`" % (r["id"], r["status"].replace("_", " "), r["claim"] or "?", r["component"]) for r in tickets)

    @staticmethod
    def tally_text():
        tickets = store.all_tickets()
        by = {}
        for r in tickets:
            by[r["status"]] = by.get(r["status"], 0) + 1
        runs = sum(len(r["runs"]) for r in tickets)
        secs = sum((x.get("seconds") or 0) for r in tickets for x in r["runs"])
        parts = ", ".join("%d %s" % (n, s.replace("_", " ")) for s, n in sorted(by.items()))
        return "**Tally:** %d reports (%s). %d sandbox runs, %.2f s of sandbox time." % (len(tickets), parts, runs, secs)


def cmd_run(args):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    state = load_state()
    if args.auto_check and not sandbox.docker_available():
        sys.exit("--auto-check needs Docker running")
    if args.auto_check:
        sandbox.build()
    intake = Intake(state, auto_check=args.auto_check)
    intake.start()
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        intake.agent.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m proveit.intake", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup", help="register the Intake agent with a Switch server")
    p.add_argument("--env-file", help="the server's .env (default: find Switch Console's local server)")
    p.add_argument("--api-url", help="Switch API URL (default: from the .env)")
    p.add_argument("--agent-name", default=DEFAULTS["agent_name"])
    p.add_argument("--overwrite", action="store_true", help="replace an existing agent of the same name")
    for key in ("intake_room", "triage_room", "reproducer", "skeptic"):
        p.add_argument("--" + key.replace("_", "-"), dest=key)
    p.add_argument("--create-rooms", action="store_true", help="create and link the two rooms (without the template)")
    p.add_argument("--with-agents", action="store_true", help="with --create-rooms, also add the reproducer and skeptic")
    p.add_argument("--users", help="with --create-rooms, comma-separated usernames to add")
    p.set_defaults(fn=cmd_setup)
    p = sub.add_parser("run", help="connect to the rooms and work")
    p.add_argument("--auto-check", action="store_true",
                   help="run the sandbox check itself (for setups without the Reproducer agent)")
    p.set_defaults(fn=cmd_run)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
