"""The preflight (`python -m proveit doctor`) and the replay login (checkpoint group H), without live services."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from proveit import config, doctor, replay_login

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import replay  # noqa: E402


def report():
    return doctor.Report(io.StringIO())


class AgentFolders(unittest.TestCase):
    def session(self, provider, name, cwd, mode="auto"):
        return {"provider": provider, "name": name, "cwd": str(cwd), "mode": mode, "mtime": 1}

    def test_agents_in_their_own_folders_pass_and_auto_mode_is_flagged(self):
        r = report()
        doctor.check_agent_folders(r, [self.session("claude", "prove-it-reproducer", ROOT / "agents" / "reproducer"),
                                       self.session("codex", None, ROOT / "agents" / "skeptic")])
        statuses = [(s, w) for s, w, _ in r.results]
        self.assertIn(("PASS", "the reproducer starts in agents/reproducer"), statuses)
        self.assertIn(("PASS", "the skeptic starts in agents/skeptic"), statuses)
        self.assertIn(("WARN", "the reproducer's permission mode"), statuses)
        self.assertFalse(r.failed)

    def test_an_agent_in_the_repo_root_fails(self):
        # What the assessment found live: the old deployment started both agents in the checkout root.
        r = report()
        doctor.check_agent_folders(r, [self.session("claude", "prove-it-reproducer", ROOT)])
        self.assertTrue(r.failed)
        self.assertIn("its lockdown", r.out.getvalue())


class Emulation(unittest.TestCase):
    def check(self, text, machine="arm64"):
        path = Path(tempfile.mkdtemp()) / "colima.yaml"
        path.write_text(text)
        r = report()
        doctor.check_emulation(r, machine=machine, colima_yaml=path)
        return r

    def test_qemu_on_apple_silicon_is_flagged(self):
        r = self.check("arch: aarch64\nrosetta: false\n")
        self.assertIn("--vz-rosetta", r.out.getvalue())
        self.assertEqual(r.results[0][0], "WARN")

    def test_rosetta_passes_and_intel_is_not_checked(self):
        self.assertEqual(self.check("rosetta: true\n").results[0][0], "PASS")
        self.assertEqual(self.check("rosetta: false\n", machine="x86_64").results, [])


class Intake(unittest.TestCase):
    def test_no_maintainers_fails(self):
        r = report()
        with mock.patch.object(doctor, "load_intake_state", return_value=({"agent_name": "i", "api_url": "u"}, Path("x"))):
            doctor.check_intake(r)
        self.assertTrue(r.failed)
        self.assertIn("maintainers add", r.out.getvalue())

    def test_the_doctor_never_moves_files(self):
        tmp = Path(tempfile.mkdtemp())
        legacy, new = tmp / "legacy.json", tmp / "home" / "intake.json"
        legacy.write_text(json.dumps({"agent_name": "i", "api_url": "u", "maintainers": ["me"]}))
        with mock.patch("proveit.intake.LEGACY_STATE_FILE", legacy), mock.patch("proveit.intake.STATE_FILE", new):
            state, path = doctor.load_intake_state()
        self.assertEqual((state["maintainers"], path), (["me"], legacy))
        self.assertTrue(legacy.exists())
        self.assertFalse(new.exists())


class PrivateHome(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_world_readable_home_is_flagged(self):
        home = Path(tempfile.mkdtemp())
        os.chmod(home, 0o755)
        r = report()
        with mock.patch.object(config, "PROVEIT_HOME", home):
            doctor.check_private_home(r)
        self.assertIn("chmod 700", r.out.getvalue())

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_ensure_home_is_private(self):
        home = Path(tempfile.mkdtemp()) / "h"
        with mock.patch.object(config, "PROVEIT_HOME", home):
            config.ensure_home()
        self.assertEqual(home.stat().st_mode & 0o777, 0o700)


class ReplayLogin(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(replay_login, "LOGIN_FILE", self.tmp / "reporter.json"),
                        mock.patch.object(replay_login, "LEGACY_LOGIN_FILE", self.tmp / "legacy.json"),
                        mock.patch.object(config, "PROVEIT_HOME", self.tmp),
                        mock.patch.dict(os.environ, {"MM_URL": "", "MM_USER": "", "MM_PASSWORD": ""})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_saved_login_is_found_and_private(self):
        replay_login.save_login("rep", "pw", "http://127.0.0.1:52572")
        login = replay_login.find_login()
        self.assertEqual((login["user"], login["url"]), ("rep", "http://127.0.0.1:52572"))
        if os.name == "posix":
            self.assertEqual((self.tmp / "reporter.json").stat().st_mode & 0o777, 0o600)

    def test_console_port_is_used_without_a_saved_url(self):
        (self.tmp / "legacy.json").write_text(json.dumps({"username": "rep", "password": "pw"}))
        with mock.patch.object(replay_login, "console_mattermost_port", return_value=52572):
            self.assertEqual(replay_login.find_login()["url"], "http://127.0.0.1:52572")

    def test_env_file_and_environment_take_precedence(self):
        replay_login.save_login("saved", "pw", "http://saved")
        login = replay_login.find_login({"MATTERMOST_USER": "u", "MATTERMOST_USER_PASSWORD": "p", "MATTERMOST_HOST_PORT": "18065"})
        self.assertEqual((login["user"], login["url"]), ("u", "http://127.0.0.1:18065"))
        with mock.patch.dict(os.environ, {"MM_USER": "e", "MM_PASSWORD": "p", "MM_URL": "http://env"}):
            self.assertEqual((replay_login.find_login()["user"], replay_login.find_login()["url"]), ("e", "http://env"))

    def test_named_profiles_are_separate(self):
        replay_login.save_login("rep", "pw", "http://127.0.0.1:52572")
        replay_login.save_login("user", "pw2", "http://127.0.0.1:52572", profile="maintainer")
        self.assertEqual(replay_login.find_login()["user"], "rep")
        self.assertEqual(replay_login.find_login(profile="maintainer")["user"], "user")
        self.assertIsNone(replay_login.find_login(profile="other"))
        with self.assertRaises(ValueError):
            replay_login.login_file("../x")

    def test_nothing_found(self):
        self.assertIsNone(replay_login.find_login())

    def test_console_ports_file_is_read(self):
        app = self.tmp / "Library" / "Application Support" / "switchdash" / "local-switch-server"
        app.mkdir(parents=True)
        (app / "ports.json").write_text(json.dumps({"mattermost": 52572, "api": 52571}))
        with mock.patch.object(replay_login, "_console_roots", return_value=[self.tmp / "Library" / "Application Support"]):
            self.assertEqual(replay_login.console_mattermost_port(), 52572)


class ReplayChannels(unittest.TestCase):
    """The template's channel is `proveit-intake-<id>`, shown as `proveit-intake`; leftovers must be ignored."""

    def mattermost(self, mine, public):
        mm = replay.Mattermost.__new__(replay.Mattermost)
        mm.me = {"id": "me"}
        joined = []

        def call(method, path, body=None):
            if path == "/users/me/teams":
                return [{"id": "team"}]
            if path.startswith("/users/me/teams/"):
                return mine
            if path.startswith("/teams/"):
                return public
            if method == "POST":
                joined.append(path)
                return {}
            raise AssertionError(path)
        mm.call = call
        return mm, joined

    def test_newest_matching_channel_wins_over_a_leftover(self):
        old = {"id": "old", "name": "proveit-intake", "display_name": "proveit-intake", "create_at": 1, "delete_at": 0}
        new = {"id": "new", "name": "proveit-intake-ea26e181", "display_name": "proveit-intake", "create_at": 2, "delete_at": 0}
        mm, _ = self.mattermost([old, new], [old, new])
        self.assertEqual(mm.channel("proveit-intake"), "new")

    def test_public_intake_channel_is_joined(self):
        new = {"id": "new", "name": "proveit-intake-x", "display_name": "proveit-intake", "create_at": 2, "delete_at": 0}
        mm, joined = self.mattermost([], [new])
        with mock.patch("builtins.print"):
            self.assertEqual(mm.channel("proveit-intake"), "new")
        self.assertEqual(joined, ["/channels/new/members"])

    def test_a_newer_public_channel_beats_an_old_joined_one(self):
        # Seen live: the reporter was still in the previous deployment's channel.
        old = {"id": "old", "name": "proveit-intake-1", "display_name": "proveit-intake", "create_at": 1, "delete_at": 0}
        new = {"id": "new", "name": "proveit-intake-2", "display_name": "proveit-intake", "create_at": 2, "delete_at": 0}
        mm, joined = self.mattermost([old], [old, new])
        with mock.patch("builtins.print"):
            self.assertEqual(mm.channel("proveit-intake"), "new")
        self.assertEqual(joined, ["/channels/new/members"])

    def test_deleted_channels_are_ignored(self):
        gone = {"id": "gone", "name": "proveit-intake", "display_name": "proveit-intake", "create_at": 5, "delete_at": 9}
        live = {"id": "live", "name": "proveit-intake-x", "display_name": "proveit-intake", "create_at": 2, "delete_at": 0}
        mm, _ = self.mattermost([gone, live], [])
        self.assertEqual(mm.channel("proveit-intake"), "live")


class Cli(unittest.TestCase):
    def test_agents_cannot_run_the_doctor(self):
        from proveit import cli
        with mock.patch.dict(os.environ, {"PROVEIT_ACTOR": "agent", "PROVEIT_AGENT": "reproducer"}):
            self.assertIn("may not run doctor", cli.refuse_for_role("doctor"))


if __name__ == "__main__":
    unittest.main()
