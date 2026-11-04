"""Post the replayed reports into the intake room as a real Mattermost user.

Used to record the demo and to test the whole flow end to end. Every report
it posts is a replay and says so in its Reporter line.

  python scripts/replay.py report 01            post reports/replays/01-*.md
  python scripts/replay.py followup 02          reply to report 02's thread with its follow-up
  python scripts/replay.py say triage "@prove-it-intake close R-002 fake proof"
  python scripts/replay.py thread 01            print the thread of report 01

Settings come from Switch Console's local server (.env) unless overridden
with --env-file, or MM_URL / MM_USER / MM_PASSWORD.
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
from proveit.intake import console_env_candidates, read_env  # noqa: E402

POSTED = ROOT / ".proveit" / "replay-posts.json"


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
        for team in self.call("GET", "/users/me/teams"):
            for ch in self.call("GET", "/users/me/teams/%s/channels" % team["id"]):
                if name in (ch["name"], ch["display_name"]):
                    return ch["id"]
        sys.exit("You are not a member of a channel named %s" % name)

    def post(self, channel_id, message, root_id=None):
        body = {"channel_id": channel_id, "message": message}
        if root_id:
            body["root_id"] = root_id
        return self.call("POST", "/posts", body)


def settings(args):
    env = {}
    path = args.env_file or next(iter(console_env_candidates()), None)
    if path:
        env = read_env(path)
    url = os.environ.get("MM_URL") or "http://127.0.0.1:%s" % env.get("MATTERMOST_HOST_PORT", "8065")
    user = os.environ.get("MM_USER") or env.get("MATTERMOST_USER")
    password = os.environ.get("MM_PASSWORD") or env.get("MATTERMOST_USER_PASSWORD")
    if not (user and password):
        sys.exit("No Mattermost login found. Set MM_USER and MM_PASSWORD, or pass --env-file.")
    return url, user, password


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
    parser.add_argument("--intake", default="proveit-intake")
    parser.add_argument("--triage", default="proveit-triage")
    parser.add_argument("action", choices=["report", "followup", "say", "thread"])
    parser.add_argument("target")
    parser.add_argument("text", nargs="?")
    args = parser.parse_args()
    mm = Mattermost(*settings(args))
    posted = load_posted()

    if args.action == "report":
        path = replay_file(args.target)
        post = mm.post(mm.channel(args.intake), path.read_text(encoding="utf-8"))
        posted[args.target] = post["id"]
        POSTED.parent.mkdir(exist_ok=True)
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
    elif args.action == "thread":
        root = posted.get(args.target) or sys.exit("Post report %s first" % args.target)
        thread = mm.call("GET", "/posts/%s/thread" % root)
        for p in sorted(thread["posts"].values(), key=lambda post: post["create_at"]):
            print("--- %s\n%s" % (time.strftime("%H:%M:%S", time.localtime(p["create_at"] / 1000)), p["message"][:700]))


if __name__ == "__main__":
    main()
