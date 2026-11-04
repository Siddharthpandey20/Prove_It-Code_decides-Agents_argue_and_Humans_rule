# Setting up Prove It in Switch Console

About 15 minutes the first time. You need Docker, Python 3.9+, Switch Console, and at least one coding agent signed in (Claude Code; Codex optional). Everything runs on your machine.

## 1. Get the code and build the sandbox

```sh
git clone https://github.com/akhilll0305/team-pikachu-switch-ai
cd team-pikachu-switch-ai
python -m proveit build
python -m unittest discover -s tests      # optional: 17 tests, about 10 s
```

`build` creates two images, `proveit-target:vulnerable` (PyYAML 5.3.1) and `proveit-target:patched` (PyYAML 5.4). It needs network once; the sandbox never has network after that.

## 2. Start a Switch server

In Switch Console: **Add a server → Run a server on this computer → Start**, and wait until the sidebar shows **Running locally**. Then **Home → Messaging apps → Mattermost → Sign-in details… → Open in Mattermost** and sign in.

Check that your agents are signed in under **Settings → Agent providers** (`claude auth login`, `codex login`).

## 3. Register the Intake agent

Intake is our own Switch agent, written against the agent protocol. It is not a Claude or Codex session, so Console does not create it; this command does:

```sh
python -m proveit.intake setup
```

It finds Console's local server settings (`<app data>/<Switch Console>/local-switch-server/.env`), registers `prove-it-intake` with the server's registration token, and opens it to everyone in its rooms so reporters can reach it. Credentials go to `.proveit/intake.json`, which is git-ignored. Use `--env-file` and `--api-url` for a server elsewhere, and `--overwrite` to re-register.

## 4. Deploy the template

In Switch Console open **Templates**, add a template from YAML, and paste [`switch/prove-it.template.yaml`](../switch/prove-it.template.yaml). On the form:

- **Prove It checkout**: the folder you cloned in step 1. Both agents work there, because the `python -m proveit` commands and the `work/` tickets live there.
- **Reproducer runs on** / **Skeptic runs on** (under Advanced): Claude Code and Codex by default; each falls back to whatever you have installed.

Create it. You get `prove-it-reproducer`, `prove-it-skeptic`, and a **Prove It** room group with `#proveit-intake` and `#proveit-triage` linked, the triage roles and the `verdict-rules` document. The kickoff asks both agents to introduce themselves in triage.

If Console refuses the template because it cannot add `prove-it-intake` to a room, create the rooms from the template anyway with that name removed, then type `!invite-agent @prove-it-intake` in each room.

## 5. Turn on Switch Trust

Switch Trust checks every human message before it reaches a room. A blocked message never becomes a room message, so no agent sees it; the sender gets a notice instead. The free plan covers what Prove It needs.

1. Sign up for Switch Trust and open **Settings → Configurations → Guardrail policies → Add policy**.
2. Enable for the **User** role:
   - **Jailbreak** → Block
   - **Secrets** → Redact
   - **Regex** → Block, with patterns such as `(?i)ignore (all |your |previous )+(instructions|rules)` and `(?i)print (your )?env(ironment)?`
3. Copy the policy's **Policy ID** from the list, and create an API key (Editor role or higher).
4. In Switch Console, on the server's **Home** page, fill in the **Switch Trust** section (shown to server admins): endpoint `https://api.switchagents.ai`, the policy ID, and the API key.

Prove It works without this step. Intake's own screen and the sandbox still stop the injection; Trust adds a wall in front of both.

## 6. Run Intake

```sh
python -m proveit.intake run
```

It should print `Intake is listening in #proveit-intake and #proveit-triage`. Leave it running.

## 7. Try it

Post a report in `#proveit-intake` from Mattermost, or replay ours as your Mattermost user:

```sh
python scripts/replay.py report 01        # real CVE-2020-14343
python scripts/replay.py report 02        # slop, no PoC: Intake asks for one
python scripts/replay.py followup 02      # the "proof" that fakes the marker
python scripts/replay.py report 03        # billion laughs that isn't
python scripts/replay.py report 04        # injection hidden in an HTML comment
```

In `#proveit-triage`, the Reproducer and Skeptic pick up each ticket. Decide as a maintainer:

```
@prove-it-intake escalate R-001 confirmed, CVE-2020-14343
@prove-it-intake close R-002 the PoC wrote the marker itself
@prove-it-intake tally
```

`!interrupt @prove-it-reproducer` stops a run in progress.

## Without Switch Console

`scripts/switch-server.sh up` runs Switch's published server (0.31.0) and Mattermost on ports 18000/18065, and `python scripts/e2e.py --env-file .proveit/switch-server/.env` replays every report through it and checks the outcomes. Use `python -m proveit.intake run --auto-check` to have Intake run the sandbox itself when no Reproducer agent is in the room.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not find Switch Console's local server` | Start the server in Console first, or pass `--env-file` |
| `An agent named prove-it-intake already exists` | `python -m proveit.intake setup --overwrite` |
| Reporter gets "You're not permitted to direct messages to me" | Setup could not open the agent; in Console set prove-it-intake's **Who can talk to your agent** to everyone |
| `Rooms proveit-intake / proveit-triage not found` | Deploy the template, or run setup with `--create-rooms --users <your Mattermost username>` |
| Agents in triage do not answer | Console must stay open; mention them with `@` and the exact name |
| `check` builds images on first use | Run `python -m proveit build` beforehand |
