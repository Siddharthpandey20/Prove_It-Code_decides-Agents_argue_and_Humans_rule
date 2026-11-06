"""Post the replayed reports into the intake room as a real Mattermost user.

Used to record the demo and to test the whole flow end to end. Every report
it posts is a replay and says so in its Reporter line.

  python scripts/replay.py login                save a Mattermost login to post with (asks for it)
  python scripts/replay.py --as maintainer login   save a second login, e.g. the deployer, to steer agents
  python scripts/replay.py --as maintainer say triage "@prove-it-reproducer check R-001"
  python scripts/replay.py report 01            post reports/replays/01-*.md
  python scripts/replay.py followup 02          reply to report 02's thread with its follow-up
  python scripts/replay.py say triage "@prove-it-intake close R-002 fake proof"
  python scripts/replay.py thread 01            print the thread of report 01
  python scripts/replay.py read triage 20       print the last 20 posts in a room (with their senders)

The login comes from MM_URL / MM_USER / MM_PASSWORD, the one saved by
`login` (kept in ~/.proveit/<checkout>/, outside the checkout), or a server
.env given with --env-file (scripts/switch-server.sh writes one). With Switch
Console's own server the Mattermost port is read from Console's ports.json.

Rooms are found by their Mattermost display name (Switch names a template's
channel `proveit-intake-<id>` and displays it as `proveit-intake`). If several
channels match, the newest is used, so channels left over from an earlier
deployment are ignored. The public intake channel is joined if needed.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from proveit.config import PROVEIT_HOME  # noqa: E402
from proveit.intake import read_env  # noqa: E402
from proveit.replay_login import console_mattermost_port, find_login, save_login  # noqa: E402

POSTED = PROVEIT_HOME / "replay-posts.json"


class Mattermost:
    def __init__(self, url, user, password):
        self.url = url.rstrip("/") + "/api/v4"
        req = urllib.request.Request(self.url + "/users/login", method="POST",
                                     data=json.dumps({"login_id": user, "password": password}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            self.token = resp.headers["Token"]
            self.me = json.loads(resp.read())

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as exc:
            sys.exit("Mattermost %s %s: %s %s" % (method, path, exc.code, exc.read().decode()[:300]))

    def channel(self, name):
        """The newest channel named or displayed as `name`, among those joined and the public ones (joined if needed)."""
        mine, public = [], []
        for team in self.call("GET", "/users/me/teams"):
            mine += [ch for ch in self.call("GET", "/users/me/teams/%s/channels" % team["id"])
                     if name in (ch["name"], ch["display_name"]) and not ch.get("delete_at")]
            public += [ch for ch in self.call("GET", "/teams/%s/channels?per_page=200" % team["id"])
                       if name in (ch["name"], ch["display_name"]) and not ch.get("delete_at")]
        candidates = {ch["id"]: ch for ch in mine + public}
        if candidates:
            ch = max(candidates.values(), key=lambda c: c["create_at"])  # the newest deployment's channel
            if ch["id"] not in {c["id"] for c in mine}:
                self.call("POST", "/channels/%s/members" % ch["id"], {"user_id": self.me["id"]})
                print("joined #%s" % ch["display_name"])
            return ch["id"]
        sys.exit("No channel named %s that you are in or can join. A private room (like #proveit-triage) needs a "
                 "maintainer to add you." % name)

    def post(self, channel_id, message, root_id=None):
        body = {"channel_id": channel_id, "message": message}
        if root_id:
            body["root_id"] = root_id
        return self.call("POST", "/posts", body)


def settings(args):
    login = find_login(read_env(args.env_file) if args.env_file else None, profile=args.profile)
    if not login:
        sys.exit("No Mattermost login found for %r. Run `python scripts/replay.py --as %s login`, set MM_USER and "
                 "MM_PASSWORD, or pass --env-file." % (args.profile, args.profile))
    return login["url"], login["user"], login["password"]


def login(args):
    import getpass
    default_url = os.environ.get("MM_URL") or "http://127.0.0.1:%s" % (console_mattermost_port() or 8065)
    url = (input("Mattermost URL [%s]: " % default_url).strip() or default_url).rstrip("/")
    user = input("Mattermost username: ").strip()
    password = getpass.getpass("Password for %s: " % user)
    Mattermost(url, user, password)  # fails loudly if the login is wrong
    print("Logged in as %s. Saved to %s (outside the checkout)." % (user, save_login(user, password, url, args.profile)))


def replay_file(number, suffix=".md"):
    matches = [p for p in sorted((ROOT / "reports" / "replays").glob("%s-*" % number))
               if p.name.endswith(suffix) and (suffix != ".md" or not p.name.endswith(".followup.md"))]
    if not matches:
        sys.exit("No replay %s%s" % (number, suffix))
    return matches[0]


def load_posted():
    return json.loads(POSTED.read_text()) if POSTED.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file")
    parser.add_argument("--as", dest="profile", default="reporter",
                        help="which saved login to use (default: reporter); `--as maintainer login` saves another")
    parser.add_argument("--intake", default="proveit-intake")
    parser.add_argument("--triage", default="proveit-triage")
    parser.add_argument("action", choices=["login", "report", "followup", "say", "thread", "read"])
    parser.add_argument("target", nargs="?")
    parser.add_argument("text", nargs="?")
    args = parser.parse_args()
    if args.action == "login":
        return login(args)
    if not args.target:
        parser.error("%s needs a target" % args.action)
    mm = Mattermost(*settings(args))
    posted = load_posted()

    if args.action == "report":
        path = replay_file(args.target)
        post = mm.post(mm.channel(args.intake), path.read_text(encoding="utf-8"))
        posted[args.target] = post["id"]
        POSTED.parent.mkdir(parents=True, exist_ok=True)
        POSTED.write_text(json.dumps(posted, indent=2))
        print("posted %s as %s" % (path.name, post["id"]))
    elif args.action == "followup":
        root = posted.get(args.target) or sys.exit("Post report %s first" % args.target)
        path = replay_file(args.target, ".followup.md")
        mm.post(mm.channel(args.intake), path.read_text(encoding="utf-8"), root_id=root)
        print("posted %s in the thread" % path.name)
    elif args.action == "say":
        room = {"intake": args.intake, "triage": args.triage}.get(args.target, args.target)
        mm.post(mm.channel(room), args.text)
        print("said in %s" % room)
    elif args.action == "read":
        room = {"intake": args.intake, "triage": args.triage}.get(args.target, args.target)
        page = mm.call("GET", "/channels/%s/posts?per_page=%d" % (mm.channel(room), int(args.text or 20)))
        names = {}
        for pid in reversed(page["order"]):
            p = page["posts"][pid]
            if p["user_id"] not in names:
                names[p["user_id"]] = mm.call("GET", "/users/%s" % p["user_id"])["username"]
            print("--- %s %s%s\n%s" % (time.strftime("%H:%M:%S", time.localtime(p["create_at"] / 1000)), names[p["user_id"]],
                                     " (reply)" if p.get("root_id") else "", p["message"][:2000]))
    elif args.action == "thread":
        root = posted.get(args.target) or sys.exit("Post report %s first" % args.target)
        thread = mm.call("GET", "/posts/%s/thread" % root)
        for p in sorted(thread["posts"].values(), key=lambda post: post["create_at"]):
            print("--- %s\n%s" % (time.strftime("%H:%M:%S", time.localtime(p["create_at"] / 1000)), p["message"][:700]))


if __name__ == "__main__":
    main()
