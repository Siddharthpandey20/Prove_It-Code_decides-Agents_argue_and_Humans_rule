"""The Intake agent: Prove It's own Switch agent, built on the agent protocol.

It sits in two linked rooms:

  #proveit-intake   anyone can post a report here. Intake is the only agent
                    in the room, and it runs no code and has no shell.
  #proveit-triage   maintainers, the Reproducer (Claude Code) and the Skeptic
                    (Codex). Intake finds this room through the intake room's
                    Switch link labelled "triage", posts tickets of fixed
                    fields here, and relays maintainers' decisions back to
                    the reporter's thread.

It deliberately has no language model. The one component that reads
attacker-controlled prose is plain code: it screens the text, demands a
proof in the data-only format (entry point + YAML payload), and hands
triage a ticket with no reporter text in it.

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

from . import actions, evidence, messages, reports, screen, states, store
from .config import LEGACY_STATE_DIR, PROVEIT_HOME, ensure_home
from .switch_client import Agent, CursorStore, SwitchError, open_to_everyone, register_agent

log = logging.getLogger("proveit.intake")
STATE_FILE = Path(os.environ.get("PROVEIT_STATE") or PROVEIT_HOME / "intake.json")
LEGACY_STATE_FILE = LEGACY_STATE_DIR / "intake.json"
TRIAGE_LINK_LABEL = "triage"
# Decisions only the maintainers listed in the state file may make.
HUMAN_ONLY = ("escalate", "close", "release", "override", "notify")
# Verdicts only the Skeptic agent (or a maintainer) may record.
VERDICTS = ("concur", "dispute")

DEFAULTS = {
    "agent_name": "prove-it-intake",
    "intake_room": "proveit-intake",
    "triage_room": "proveit-triage",
    "reproducer": "prove-it-reproducer",
    "skeptic": "prove-it-skeptic",
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


def split_names(text):
    """'alice, @bob' -> ['alice', 'bob']"""
    return [n.strip().lstrip("@") for n in (text or "").split(",") if n.strip().lstrip("@")]


def move_legacy_state():
    """Older versions kept Intake's credentials in the checkout's .proveit/; move them out of the agents' reach."""
    if not os.environ.get("PROVEIT_STATE") and not STATE_FILE.exists() and LEGACY_STATE_FILE.exists():
        ensure_home()
        LEGACY_STATE_FILE.replace(STATE_FILE)
        _private_file(STATE_FILE)
        log.info("moved %s to %s", LEGACY_STATE_FILE, STATE_FILE)


def _private_file(path):
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_state():
    move_legacy_state()
    if not STATE_FILE.exists():
        sys.exit("No agent registered yet. Run: python -m proveit.intake setup")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    if STATE_FILE.parent == PROVEIT_HOME:
        ensure_home()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _private_file(STATE_FILE)


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
    state["maintainers"] = split_names(args.maintainers)
    save_state(state)
    print("Saved credentials to %s (outside the checkout, never committed)" % STATE_FILE)
    if state["maintainers"]:
        print("Maintainers who may decide: %s" % ", ".join(state["maintainers"]))
    else:
        print("WARNING: no maintainers set, so Intake will refuse every escalate/close/override/release. "
              "Add yours: python -m proveit.intake maintainers add <your Mattermost username>")

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
            agent.link_rooms(intake, triage, TRIAGE_LINK_LABEL)
        except SwitchError as exc:
            print("note: could not link rooms (%s)" % exc)
        print("Rooms ready: %s, %s (linked as %r)" % (state["intake_room"], state["triage_room"], TRIAGE_LINK_LABEL))
    print("\nNext: python -m proveit.intake run")


# --------------------------------------------------------------------------
# The agent
# --------------------------------------------------------------------------
def ticket_from_record(record):
    """Rebuild the parse result for a stored ticket (its payload lives in private/)."""
    return reports.Ticket(claim=record.get("claim", ""), severity=record.get("severity", "unrated"),
                          entry_point=record.get("entry_point", ""), payload=store.payload(record["id"]),
                          poc_problem=record.get("poc_problem", ""), missing=list(record.get("missing", [])))


def fill(record, ticket):
    """Copy only fixed fields from a parsed ticket into the agent-readable record."""
    from . import poc
    record.update({
        "claim": ticket.claim, "severity": ticket.severity, "entry_point": ticket.entry_point,
        "poc_problem": ticket.poc_problem, "missing": ticket.missing,
        "payload_sha256": poc.sha256(ticket.payload) if ticket.payload else None,
        "payload_bytes": len(ticket.payload.encode("utf-8", "surrogatepass")) if ticket.payload else 0,
        "tags": poc.tags(ticket.payload),
    })
    if ticket.payload:
        store.set_payload(record["id"], ticket.payload)


def target_for(ticket):
    if ticket.poc_problem:
        return "invalid_proof"
    if ticket.missing:
        return "awaiting_poc"
    return "in_triage"


class Handled:
    """Message ids Intake has already handled, so a message delivered twice is acted on once."""

    KEEP = 5000

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.ids = []
        if self.path and self.path.exists():
            try:
                self.ids = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                log.warning("ignoring unreadable %s", self.path)
        self.set = set(self.ids)

    def __contains__(self, message_id):
        return message_id in self.set

    def add(self, message_id):
        if not message_id or message_id in self.set:
            return
        with self.lock:
            self.ids.append(message_id)
            self.set.add(message_id)
            if len(self.ids) > self.KEEP:
                dropped = self.ids[:-self.KEEP]
                self.ids = self.ids[-self.KEEP:]
                self.set.difference_update(dropped)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text(json.dumps(self.ids), encoding="utf-8")
                os.replace(str(tmp), str(self.path))


class Intake:
    VERBS = "escalate|close|release|override|notify|concur|dispute|evidence|status|tally"
    # A command is the text right after the @mention: "@prove-it-intake dispute R-001 patched build not checked".
    COMMAND = re.compile(r"[\s:,]*(%s)\b\s*(R-\d{3,})?\s*(.*)" % VERBS, re.I | re.S)

    def __init__(self, state, auto_check=False, source="switch", state_dir=None):
        self.state = state
        # Saved next to the state file when running for real; in memory for tests and the rehearsal.
        self.state_dir = Path(state_dir) if state_dir else None
        key = state.get("agent_id", "local")
        self.handled = Handled(self.state_dir / ("handled-%s.json" % key) if self.state_dir else None)
        self.cursors = CursorStore(self.state_dir / ("cursors-%s.json" % key) if self.state_dir else None)
        self.failed_log = self.state_dir / "failed-events.jsonl" if self.state_dir else None
        self.agent = Agent(state["api_url"], state["agent_id"], state["api_key"]) if state.get("api_url") else None
        self.auto_check = auto_check
        self.source = source
        self.names = {state["agent_name"]}
        self.maintainers = {n.lower() for n in state.get("maintainers") or []}
        skeptic = state.get("skeptic", DEFAULTS["skeptic"])
        self.skeptic_names = {n.lower() for n in [skeptic, "Prove It Skeptic"] + list(state.get("skeptic_names") or [])}
        self.lock = threading.RLock()
        self.intake = None   # anything with .post(body, thread_id=None)
        self.triage = None

    # -- helpers -------------------------------------------------------------
    def mention(self):
        return "@" + self.state["agent_name"]

    def is_maintainer(self, name):
        return bool(name) and name.lstrip("@").lower() in self.maintainers

    def is_self(self, payload):
        return payload.get("sender_name") in self.names

    @staticmethod
    def is_system(payload):
        return payload.get("sender_kind") == "platform" and not payload.get("on_behalf_of")

    @staticmethod
    def is_agent(payload):
        return payload.get("sender_kind") == "agent" or str(payload.get("sender", "")).startswith("@switch-agent")

    def linked_room(self, conn, label):
        for link in self.agent.op("list_linked_rooms", {}, connection_id=conn.id) or []:
            if link.get("label") == label:
                return link.get("target_room_id")
        return None

    def start(self):
        detail = self.agent.op("get_agent_detail", {"agent_id": self.agent.id}) or {}
        for key in ("name", "display_name"):
            if detail.get(key):
                self.names.add(detail[key])
        intake_id = self.agent.room_id(self.state["intake_room"])
        if not intake_id:
            sys.exit("Room %s not found or %s is not in it. Deploy switch/prove-it.template.yaml in Switch Console, "
                     "or run setup with --create-rooms." % (self.state["intake_room"], self.state["agent_name"]))
        self.intake = self.agent.connect(intake_id, self.on_intake_event, cursors=self.cursors, failed_log=self.failed_log)
        if not self.intake.ready.wait(20):
            sys.exit("Could not open the event stream for room %s" % intake_id)
        # The triage room is wherever the intake room's Switch link labelled "triage" points.
        triage_id = self.linked_room(self.intake, TRIAGE_LINK_LABEL)
        if not triage_id:
            sys.exit("#%s has no Switch room link labelled %r, so Intake does not know where to send tickets. "
                     "Deploy switch/prove-it.template.yaml (it creates the link) or run setup with --create-rooms."
                     % (self.state["intake_room"], TRIAGE_LINK_LABEL))
        self.triage = self.agent.connect(triage_id, self.on_triage_event, cursors=self.cursors, failed_log=self.failed_log)
        if not self.triage.ready.wait(20):
            sys.exit("Could not open the event stream for room %s" % triage_id)
        log.info("Intake is listening in #%s and the room it links to as %r", self.state["intake_room"], TRIAGE_LINK_LABEL)

    # -- #proveit-intake -----------------------------------------------------
    def on_intake_event(self, conn, kind, frame):
        if kind != "message":
            return
        payload = frame["payload"]
        if self.is_self(payload) or self.is_system(payload) or not payload.get("body", "").strip():
            return
        with self.lock:
            if payload.get("message_id") in self.handled:
                log.info("message %s already handled; ignoring the repeat", payload.get("message_id"))
                return
            thread = payload.get("thread_id")
            if thread and thread != payload["message_id"]:
                record = store.find_by_thread(thread)
                if record:
                    self.followup(record, payload)
                self.handled.add(payload.get("message_id"))
                return  # a reply in a thread that is not a report is ignored
            self.new_report(payload)
            self.handled.add(payload.get("message_id"))

    def new_report(self, payload):
        text, thread = payload["body"], payload["message_id"]
        if store.find_by_thread(thread):
            # A retry after a failure part-way through: the ticket exists already.
            log.info("report %s already has a ticket; not creating another", thread)
            return
        result = screen.screen(text)
        ticket = reports.parse(text)
        record = store.create({}, text, source=self.source)
        with store.ticket_lock(record["id"]):
            store.save_private_json(record["id"], "contact.json",
                                    {"intake_thread": thread, "reporter": payload.get("sender_name", "unknown"),
                                     "message_id": payload.get("message_id")})
            fill(record, ticket)
            if result.blocked:
                self.quarantine(record, result, thread, "receive")
                return
            self.route(record, ticket, thread, "receive")

    def quarantine(self, record, result, thread, command):
        record["screen_rules"] = sorted({f["rule"] for f in result.findings})
        store.save_private_json(record["id"], "screen.json", result.findings)
        store.apply(record, command, "intake", "intake", target="quarantined")
        self.intake.post(messages.quarantined(record["id"]), thread)
        self.triage.post(messages.quarantine_notice(record, self.mention()))

    def route(self, record, ticket, thread, command, actor="intake", by="intake"):
        target = target_for(ticket)
        store.apply(record, command, actor, by, target=target)
        if target == "invalid_proof":
            self.intake.post(messages.invalid_proof(record["id"], ticket.poc_problem), thread)
        elif target == "awaiting_poc":
            self.intake.post(messages.ask_for_proof(record["id"], ticket), thread)
        else:
            self.intake.post(messages.accepted(record["id"], ticket.claim), thread)
            self.triage.post(messages.ticket_posted(record))
            if self.auto_check:
                threading.Thread(target=self.run_auto_check, args=(record["id"],), daemon=True).start()

    def followup(self, record, payload):
        with store.ticket_lock(record["id"]):
            self._followup(store.load(record["id"]), payload)

    def _followup(self, record, payload):
        contact = store.load_private_json(record["id"], "contact.json")
        thread = contact.get("intake_thread")
        sender = payload.get("sender_name", "")
        if sender.lower() != str(contact.get("reporter", "")).lower():
            self.foreign_reply(record, payload, thread)
            return
        if record["status"] not in ("awaiting_poc", "invalid_proof"):
            self.intake.post("%s is %s. A maintainer will reply in this thread." % (
                record["id"], record["status"].replace("_", " ")), thread)
            return
        text = payload["body"]
        store.append_report(record["id"], text)
        result = screen.screen(text)
        merged = reports.merge(ticket_from_record(record), text)
        fill(record, merged)
        if result.blocked:
            self.quarantine(record, result, thread, "followup")
            return
        self.route(record, merged, thread, "followup")

    def foreign_reply(self, record, payload, thread):
        """Decision D-008: only the original reporter completes a report. Someone else's reply in the
        thread changes nothing; it is kept privately for maintainers and counted in the ticket."""
        import hashlib
        text = payload.get("body", "")
        foreign = store.load_private_json(record["id"], "foreign.json") or {"replies": []}
        foreign["replies"].append({"sender": payload.get("sender_name", "unknown"), "message_id": payload.get("message_id"),
                                   "at": store.now(), "sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
                                   "text": text})
        store.save_private_json(record["id"], "foreign.json", foreign)
        with store.ticket_lock(record["id"]):
            fresh = store.load(record["id"])
            fresh["foreign_replies"] = len(foreign["replies"])
            store.event(fresh, "foreign_reply_ignored", "intake")
            store.save(fresh)
        self.intake.post(messages.foreign_reply(record["id"]), thread)
        self.triage.post(messages.foreign_reply_notice(record["id"], len(foreign["replies"])))

    def run_auto_check(self, ticket_id):
        """Developer/test mode only: Intake runs the vulnerable-build check itself, labelled as such."""
        try:
            record, run, _ = actions.check(ticket_id, "vulnerable", actor="intake", by="intake (auto-check)")
            self.triage.post(messages.auto_check(record, run))
        except Exception as exc:
            log.exception("auto-check failed")
            self.triage.post("Automatic check for %s failed: %s" % (ticket_id, type(exc).__name__))

    # -- #proveit-triage -----------------------------------------------------
    def on_triage_event(self, conn, kind, frame):
        if kind != "message":
            return
        payload = frame["payload"]
        if self.is_self(payload) or self.is_system(payload):
            return
        body = payload.get("body", "")
        if not any(("@" + n) in body for n in self.names):
            return
        if payload.get("message_id") in self.handled:
            log.info("message %s already handled; ignoring the repeat", payload.get("message_id"))
            return
        self.handle_command(payload)
        self.handled.add(payload.get("message_id"))

    def parse_command(self, body):
        """The command after any line's @mention of Intake, or None."""
        for name in sorted(self.names, key=len, reverse=True):
            for part in re.split(r"@%s\b" % re.escape(name), body, flags=re.I)[1:]:
                match = self.COMMAND.match(part)
                if match:
                    return match
        return None

    def is_skeptic(self, payload):
        return self.is_agent(payload) and payload.get("sender_name", "").lstrip("@").lower() in self.skeptic_names

    def handle_command(self, payload):
        body, thread = payload.get("body", ""), payload.get("thread_id")
        match = self.parse_command(body)
        log.info("triage command from %r (kind %s): %s", payload.get("sender_name"), payload.get("sender_kind"),
                 match.group(1).lower() if match else "none")
        with self.lock:
            if not match and self.is_agent(payload):
                return  # never answer an agent's chatter with help text: two agents could loop
            if not match:
                self.triage.post("Commands: `escalate R-001 [note]`, `close R-001 <reason>`, `override R-001 [note]`, "
                                 "`release R-001`, `notify R-001`, `evidence R-001`, `status`, `tally`; "
                                 "from the Skeptic: `concur R-001`, `dispute R-001 <reason>`.", thread)
                return
            verb, ticket_id, rest = match.group(1).lower(), match.group(2), match.group(3).strip()
            human_only = verb in HUMAN_ONLY
            who = payload.get("sender_name", "")
            if verb in VERDICTS and not (self.is_skeptic(payload) or (not self.is_agent(payload) and self.is_maintainer(who))):
                # Switch tells Intake who sent a message, so only the real Skeptic (or a maintainer) records a verdict.
                self.triage.post("Refused: only @%s or a maintainer records a verdict (%s), and @%s is neither."
                                 % (self.state.get("skeptic", "prove-it-skeptic"), verb, who or "?"), thread)
                return
            if human_only and self.is_agent(payload):
                # Only people decide; agents' opinions stay opinions.
                self.triage.post("Refused: only maintainers can %s a ticket, and that request came from an agent." % verb, thread)
                return
            if human_only and not self.is_maintainer(who):
                # Being in the room is not enough: only the maintainers listed in Intake's settings decide.
                if self.maintainers:
                    self.triage.post("Refused: only Prove It's maintainers can %s a ticket, and @%s is not one of them. "
                                     "A maintainer can add you on the host: `python -m proveit.intake maintainers add %s`."
                                     % (verb, who or "?", who or "<name>"), thread)
                else:
                    self.triage.post("Refused: no maintainers are configured, so nobody can %s yet. On the host run "
                                     "`python -m proveit.intake maintainers add <your Mattermost username>`." % verb, thread)
                return
            if verb == "status":
                self.triage.post(self.status_text(), thread)
                return
            if verb == "tally":
                self.triage.post(actions.tally_text(), thread)
                return
            if not ticket_id:
                self.triage.post("Which ticket? For example `%s %s R-001`." % (self.mention(), verb), thread)
                return
            try:
                record = store.load(ticket_id)
            except FileNotFoundError:
                self.triage.post("There is no ticket %s." % ticket_id, thread)
                return
            try:
                if verb in VERDICTS:
                    getattr(self, "do_" + verb)(record, who, rest, thread,
                                                actor="agent" if self.is_agent(payload) else "human")
                else:
                    getattr(self, "do_" + verb)(record, who, rest, thread)
            except states.IllegalTransition as exc:
                self.triage.post("Refused %s for %s: %s." % (verb, ticket_id, exc), thread)

    def reporter_thread(self, record):
        return store.load_private_json(record["id"], "contact.json").get("intake_thread")

    def do_concur(self, record, who, note, thread, actor="agent"):
        record = actions.concur(record["id"], actor, who)
        self.triage.post("%s: %s concurs with the evidence; status %s." % (
            record["id"], who, record["status"].replace("_", " ")), thread)

    def do_dispute(self, record, who, note, thread, actor="agent"):
        record = actions.dispute(record["id"], note, actor, who)
        self.triage.post("%s: disputed by %s (%s). Escalation is blocked until a maintainer overrides." % (
            record["id"], who, record["skeptic"]["reason"]), thread)

    def do_evidence(self, record, who, note, thread):
        self.triage.post("```\n%s\n```" % evidence.text(evidence.pack(record)), thread)

    def do_release(self, record, who, note, thread):
        with store.ticket_lock(record["id"]):
            record = store.load(record["id"])
            ticket = ticket_from_record(record)
            self.route(record, ticket, self.reporter_thread(record), "release", actor="human", by=who)
        self.triage.post("%s released by %s; it is now %s." % (record["id"], who, store.load(record["id"])["status"].replace("_", " ")), thread)

    def do_override(self, record, who, note, thread):
        record = actions.override(record["id"], "human", who, note)
        self.triage.post(actions.override_text(record), thread)

    def do_escalate(self, record, who, note, thread):
        record = actions.decide(record["id"], "escalate", "human", who, note)
        self.triage.post("%s escalated by %s. Telling the reporter." % (record["id"], who), thread)
        self.tell_reporter(record["id"], actions.clean_reason(note), thread)

    def do_close(self, record, who, note, thread):
        record = actions.decide(record["id"], "close", "human", who, note)
        self.triage.post("%s closed by %s. Telling the reporter." % (record["id"], who), thread)
        self.tell_reporter(record["id"], actions.clean_reason(note), thread)

    def tell_reporter(self, ticket_id, note, thread):
        """Post the decision in the reporter's thread and record whether it arrived.

        The decision is saved first; if the post fails, the ticket says so and a
        maintainer can resend it with `notify`, instead of the reporter never hearing.
        """
        with store.ticket_lock(ticket_id):
            record = store.load(ticket_id)
            if note:
                record["decision_note"] = note
            try:
                self.intake.post(messages.decision(record, record.get("decision_note", "")), self.reporter_thread(record))
            except Exception as exc:
                record["notified"] = False
                store.event(record, "notify_failed", "intake", error=type(exc).__name__)
                store.save(record)
                log.exception("could not tell the reporter about %s", ticket_id)
                self.triage.post("%s: the decision is recorded, but telling the reporter failed (%s). Resend it with "
                                 "`%s notify %s`." % (ticket_id, type(exc).__name__, self.mention(), ticket_id), thread)
                return False
            record["notified"] = True
            store.event(record, "notified", "intake")
            store.save(record)
            return True

    def do_notify(self, record, who, note, thread):
        if record["status"] not in states.TERMINAL:
            raise states.IllegalTransition("%s has no decision to send yet; it is %s" % (
                record["id"], record["status"].replace("_", " ")))
        again = record.get("notified") is True
        if self.tell_reporter(record["id"], "", thread):
            self.triage.post("%s: the decision was sent to the reporter%s." % (record["id"], " again" if again else ""), thread)

    @staticmethod
    def status_text():
        tickets = store.all_tickets()
        if not tickets:
            return "No tickets yet."
        return "\n".join("- **%s** %s · %s · `%s`" % (r["id"], r["status"].replace("_", " "), r.get("claim") or "?",
                                                      r.get("entry_point") or "-") for r in tickets)


def cmd_maintainers(args):
    state = load_state()
    current = list(state.get("maintainers") or [])
    names = split_names(",".join(args.names))
    if args.action in ("add", "remove") and not names:
        sys.exit("Give one or more Mattermost usernames.")
    if args.action == "add":
        current += [n for n in names if n.lower() not in {c.lower() for c in current}]
    elif args.action == "remove":
        current = [c for c in current if c.lower() not in {n.lower() for n in names}]
    if args.action != "list":
        state["maintainers"] = current
        save_state(state)
        print("Saved. Restart `python -m proveit.intake run` for the change to apply.")
    print("Maintainers: %s" % (", ".join(current) or "none (every decision is refused)"))


def cmd_run(args):
    from . import sandbox
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    state = load_state()
    if args.auto_check:
        if not sandbox.docker_available():
            sys.exit("--auto-check needs Docker running")
        sandbox.build()
    intake = Intake(state, auto_check=args.auto_check, state_dir=STATE_FILE.parent)
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
    p.add_argument("--maintainers", help="comma-separated Mattermost usernames allowed to escalate, close, override "
                                         "and release (you, the deployer, at least)")
    p.set_defaults(fn=cmd_setup)
    p = sub.add_parser("maintainers", help="list, add or remove the people allowed to decide")
    p.add_argument("action", choices=["list", "add", "remove"], nargs="?", default="list")
    p.add_argument("names", nargs="*", help="Mattermost usernames")
    p.set_defaults(fn=cmd_maintainers)
    p = sub.add_parser("run", help="connect to the rooms and work")
    p.add_argument("--auto-check", action="store_true",
                   help="DEVELOPER/TEST ONLY: Intake runs the vulnerable-build check itself (used by scripts/e2e.py "
                        "when no Reproducer agent is in the room). Not part of the demo flow.")
    p.set_defaults(fn=cmd_run)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
