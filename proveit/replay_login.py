"""The Mattermost login scripts/replay.py posts the demo reports with.

Found, in order: MM_URL / MM_USER / MM_PASSWORD; the login saved by
`python scripts/replay.py login` (~/.proveit/<checkout>/reporter.json); an
older `.proveit/reporter.json` in the checkout; a server .env given with
--env-file (MATTERMOST_USER, MATTERMOST_USER_PASSWORD, MATTERMOST_HOST_PORT,
as scripts/switch-server.sh writes). The URL falls back to the Mattermost
port Switch Console reports in its ports.json, then to 8065.
"""

import json
import os
from pathlib import Path

from . import config

LOGIN_FILE = config.PROVEIT_HOME / "reporter.json"
LEGACY_LOGIN_FILE = config.LEGACY_STATE_DIR / "reporter.json"
DEFAULT_PROFILE = "reporter"


def login_file(profile=DEFAULT_PROFILE):
    """reporter.json for the default profile (the account replays are posted as), <profile>.json otherwise
    (for example a maintainer account to steer the agents with)."""
    if profile in (None, "", DEFAULT_PROFILE):
        return LOGIN_FILE
    if not profile.replace("-", "").isalnum():
        raise ValueError("a profile name is letters, digits and dashes")
    return LOGIN_FILE.with_name("%s.json" % profile)


def _console_roots():
    home = Path.home()
    return [Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")), home / "Library" / "Application Support",
            Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))]


def console_mattermost_port():
    """The Mattermost port of Switch Console's local server, from its ports.json, or None."""
    for root in _console_roots():
        if not root.exists():
            continue
        for path in root.glob("*/local-switch-server/ports.json"):
            try:
                port = json.loads(path.read_text(encoding="utf-8")).get("mattermost")
            except (OSError, ValueError):
                continue
            if port:
                return int(port)
    return None


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def find_login(env_file_values=None, profile=DEFAULT_PROFILE):
    """{"url", "user", "password", "source"} or None."""
    env_file_values = env_file_values or {}
    named = login_file(profile)
    if named != LOGIN_FILE:  # a named profile is only ever its own saved file
        saved = _read_json(named)
        if not (saved.get("username") and saved.get("password")):
            return None
        url = saved.get("url") or "http://127.0.0.1:%s" % (console_mattermost_port() or 8065)
        return {"url": url.rstrip("/"), "user": saved["username"], "password": saved["password"], "source": str(named)}
    saved_path = LOGIN_FILE if _read_json(LOGIN_FILE) else LEGACY_LOGIN_FILE
    saved = _read_json(saved_path)
    if os.environ.get("MM_USER") and os.environ.get("MM_PASSWORD"):
        user, password, source = os.environ["MM_USER"], os.environ["MM_PASSWORD"], "environment"
    elif env_file_values.get("MATTERMOST_USER") and env_file_values.get("MATTERMOST_USER_PASSWORD"):
        user, password, source = env_file_values["MATTERMOST_USER"], env_file_values["MATTERMOST_USER_PASSWORD"], "--env-file"
    elif saved.get("username") and saved.get("password"):
        user, password, source = saved["username"], saved["password"], str(saved_path)
    else:
        return None
    if os.environ.get("MM_URL"):
        url = os.environ["MM_URL"]
    elif source == "--env-file":
        url = "http://127.0.0.1:%s" % env_file_values.get("MATTERMOST_HOST_PORT", "8065")
    elif saved.get("url") and source != "environment":
        url = saved["url"]
    else:
        url = "http://127.0.0.1:%s" % (console_mattermost_port() or 8065)
    return {"url": url.rstrip("/"), "user": user, "password": password, "source": source}


def save_login(user, password, url, profile=DEFAULT_PROFILE):
    config.ensure_home()
    path = login_file(profile)
    path.write_text(json.dumps({"username": user, "password": password, "url": url}, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path
