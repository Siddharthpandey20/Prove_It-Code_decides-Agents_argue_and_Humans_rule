# Setting up Prove It in Switch Console

About 15 minutes the first time. You need Docker, Python 3.9+, Switch Console, and Claude Code and Codex signed in. Everything runs on your machine.

## 1. Get the code and build the sandbox

```sh
git clone https://github.com/akhilll0305/team-pikachu-switch-ai
cd team-pikachu-switch-ai
python -m proveit build
python -m unittest discover -s tests       # 60 tests, about a minute, Docker running
python scripts/rehearse.py                 # the whole demo offline, no Switch
```

`build` creates `proveit-target:vulnerable` (PyYAML 5.3.1) and `proveit-target:patched` (PyYAML 5.4). It needs network once; the sandbox never has network. Images rebuild automatically when the harness changes.

## 2. Start a Switch server

In Switch Console: **Add a server → Run a server on this computer → Start**, and wait until the sidebar shows **Running locally**. Then **Home → Messaging apps → Mattermost → Sign-in details… → Open in Mattermost** and sign in.

Under **Settings → Agent providers**, confirm Claude Code and Codex both show **Signed in** (`claude auth login`, `codex login`).

## 3. Register the Intake agent

Intake is our own Switch agent, written against the agent protocol. It is not a Claude or Codex session, so Console does not create it; this command does:

```sh
python -m proveit.intake setup
```

It finds Console's local server settings (`<app data>/<Switch Console>/local-switch-server/.env`), registers `prove-it-intake` with the server's registration token, and opens it to everyone in its rooms so reporters can reach it. Credentials go to `.proveit/intake.json`, which is git-ignored. Use `--env-file` and `--api-url` for a server elsewhere, and `--overwrite` to re-register.

## 4. Deploy the template

In Switch Console open **Templates**, add a template from YAML, and paste [`switch/prove-it.template.yaml`](../switch/prove-it.template.yaml). On the form:

- **Prove It checkout**: the folder you cloned in step 1. The Reproducer starts in `agents/reproducer/` and the Skeptic in `agents/skeptic/` inside it; each folder holds that agent's permission lockdown ([agents/README.md](../agents/README.md)).
- **Reproducer runs on** / **Skeptic runs on** (under Advanced): Claude Code and Codex by default. Keep them on different vendors.

Create it. You get `prove-it-reproducer`, `prove-it-skeptic`, and a **Prove It** room group with `#proveit-intake` and `#proveit-triage`, linked as `triage`, plus the room instructions and the `verdict-rules` document. The kickoff asks both agents to introduce themselves in triage.

Then, for each agent:

- Confirm **Bypass permissions** is off. The template sets `auto_approve: false`; check that Console shows it that way.
- Trust its folder once, so its project settings apply: run `claude` in `agents/reproducer` and accept the trust prompt; run `codex` in `agents/skeptic` and trust the project. Deny rules in Claude Code apply even before trust; allow rules and the `env` block wait for it.
- Skeptic only: run `python -m proveit concur <a ticket id>` from Codex once. If it fails with a write error, Codex resolved `writable_roots = ["../../work"]` differently than expected; replace it in `agents/skeptic/.codex/config.toml` with the absolute path of your checkout's `work` folder.

The two agents use `addressing: owner-agents`: only you (the deployer) and your own agents can instruct them. Other maintainers you add to `#proveit-triage` can still decide through Intake (`escalate`, `close`, `override`, `release`), which checks that the sender is a person.

If Console refuses the template because it cannot add `prove-it-intake` to a room, create the rooms from the template anyway with that name removed, then type `!invite-agent @prove-it-intake` in each room. The link labelled `triage` from `#proveit-intake` to `#proveit-triage` must exist: Intake finds the triage room through it and refuses to start without it.

## 5. Turn on Switch Trust

Not configured by the team yet. Switch Trust checks every human message before it reaches a room; a blocked message never becomes a room message, so no agent sees it, and the sender gets a notice instead.

1. Sign up for Switch Trust and open **Settings → Configurations → Guardrail policies → Add policy**.
2. Enable for the **User** role:
   - **Jailbreak** → Block
   - **Secrets** → Redact
   - **Regex** → Block, with patterns such as `(?i)ignore (all |your |previous )+(instructions|rules)` and `(?i)print (your )?env(ironment)?`
3. Copy the policy's **Policy ID** from the list, and create an API key (Editor role or higher).
4. In Switch Console, on the server's **Home** page, fill in the **Switch Trust** section (shown to server admins): endpoint `https://api.switchagents.ai`, the policy ID, and the API key.
5. Post `python scripts/replay.py report 04` and confirm the message is blocked before it reaches `#proveit-intake`. Then update the README's verification table.

Prove It works without this step: Intake's screen quarantines replay 04, and even a paraphrased injection only ever reaches the agents as fixed fields.

## 6. Run Intake

```sh
python -m proveit.intake run
```

It should print `Intake is listening in #proveit-intake and the room it links to as 'triage'`. Leave it running.

## 7. Try it

Post a report in `#proveit-intake` from Mattermost, or replay ours as your Mattermost user:

```sh
python scripts/replay.py report 01        # real CVE-2020-14343
python scripts/replay.py report 02        # synthetic slop, no proof: Intake asks for one
python scripts/replay.py followup 02      # the "proof": a safe_load payload
python scripts/replay.py report 03        # synthetic slop: billion laughs
python scripts/replay.py report 04        # injection hidden in an HTML comment
```

In `#proveit-triage`, as a maintainer:

```
@prove-it-reproducer check R-001
@prove-it-reproducer run R-001 on the patched build
@prove-it-skeptic review R-001
@prove-it-intake override R-001 patched build checked
@prove-it-intake escalate R-001 confirmed, CVE-2020-14343
@prove-it-intake close R-002 safe_load refused the tag
@prove-it-intake tally
```

`!interrupt @prove-it-reproducer` is Switch's room command to stop an agent mid-run (not yet tried by us). It stops the agent, not a sandbox run already started; that one ends within 20 seconds anyway.

Record agent cost per report from Switch ROI or your provider's dashboard: `python -m proveit cost R-001 --usd <amount> --source "<where you read it>"`.

## Without Switch Console

`scripts/switch-server.sh up` runs Switch's published server (0.31.0) and Mattermost on ports 18000/18065, and `python scripts/e2e.py --env-file .proveit/switch-server/.env` replays every report through it and checks the outcomes. There, Intake runs the checks itself through a developer/test flag on `python -m proveit.intake run`, because those rooms have no LLM agents. `scripts/switch-server.sh down` stops it; `reset` also deletes its data.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not find Switch Console's local server` | Start the server in Console first, or pass `--env-file` |
| `An agent named prove-it-intake already exists` | `python -m proveit.intake setup --overwrite` |
| Reporter gets "You're not permitted to direct messages to me" | Setup could not open the agent; in Console set prove-it-intake's **Who can talk to your agent** to everyone |
| `Room proveit-intake not found` | Deploy the template, or run setup with `--create-rooms --users <your Mattermost username>` |
| `#proveit-intake has no Switch room link labelled 'triage'` | Deploy the template (it creates the link) or run setup with `--create-rooms` |
| Agents in triage do not answer | Console must stay open; mention them with `@` and the exact name, as the deployer |
| `refused: only humans may override` | You ran it from an agent's shell (`PROVEIT_ACTOR=agent`); run it in your own terminal |
