# Making AI prove its bug reports: what we built on Switch, and the hole an audit found

*Draft for the Flip the Switch "Best Blog" prize. Edit before publishing.*

In January 2026 curl ended its bug bounty. Its maintainers were drowning in vulnerability reports that an AI wrote in ten seconds and a human needed an hour to disprove. In July they stopped taking security reports for a month. We wanted to build something a small team could run: a place where a report has to prove itself before a maintainer reads it.

We built it on [Switch](https://github.com/sandbox-quantum/switch), which puts AI agents into team chat as teammates. Our rule ended up being: **code decides, agents argue, humans rule.**

## The workflow

Two rooms. `#proveit-intake` is where anyone posts a report. `#proveit-triage` is where maintainers work with two coding agents: a Reproducer (Claude Code) that runs the proof in a sandbox and explains the result, and a Skeptic (Codex) that reads the evidence and either concurs or disputes. A maintainer decides with one message, and the reporter hears back in their own thread.

The agent that reads the reports is not an LLM at all. A bug report is attacker-controlled text about to sit near agents that can run commands, so Intake is plain standard-library Python on Switch's agent protocol. It screens the text, demands a proof, and passes on only fixed fields.

## Writing your own Switch agent

The [agent protocol](https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md) is "SSE down, HTTP up". What we needed:

1. **Register once.** `POST /agents` with the registration token as the bearer, `connector_type: "custom"` and an integration profile (`connection_model: "always_on"`). You get `{id, api_key}`, and the key is shown once.
2. **Open a stream per room.** `GET /agents/{id}/events?connection_id=<uuid>&scope=single&filter=all&rooms=<room id>`. Generate the connection id yourself and reuse it across reconnects.
3. **Heartbeat every 2 seconds.** `POST /agents/{id}/connection/beat` with the connection id and cursor. A 404 or 409 means reopen the stream.
4. **Call operations.** `POST /agents/{id}/ops/{name}`. `GET /agents/{id}/ops` lists them with schemas.

Things that surprised us:

- `post_message` replies in a thread, but it resolves the room from the `X-Switch-Connection-Id` header. So Intake holds one connection per room and posts through the right one.
- A new agent answers only its owner. For a public intake room an admin clears the policy with `PUT /gateway/agents/{id}/addressing-policy {"policy": null}`.
- Room links are pointers, not pipes: `list_linked_rooms` tells an agent where the link goes, and "pointers grant no implicit access". We use that directly: Intake finds the triage room through the intake room's link labelled `triage`, and refuses to start without it.
- The template's `addressing` can be `owner`, `owner-agents`, `anyone` or `{anyone_in: [...]}`. We set the two command-running agents to `owner-agents`: only the deployer and the deployer's own agents can instruct them.
- The server will check your template for you. An agent can call `get_template_guide` (which returns a JSON schema) and `save_template` (which lists warnings). One caveat we hit: neither checks the agent fields, so `addressing: maintainers-only` saves without a warning.

## The hole: a proof that grades itself

Our first version let reporters send a Python script as their proof. The sandbox ran it under a Python audit hook and recorded whether PyYAML's own code was on the call stack when a marker file was written. It looked solid, and it caught the obvious fake: a script that writes the marker itself.

Then we had the project audited, and the audit broke it in ten lines. The PoC ran in the same process as the harness that wrote the result, so a PoC could walk the call stack, read the harness's one-time code, and print a perfect forged REPRODUCED record. Worse, the rules were easy to satisfy honestly: `time.sleep(60)` counted as a denial of service, `ctypes.string_at(0)` as a crash, and calling `yaml.unsafe_load` (unsafe by design, documented as such) as code execution on both the vulnerable and the patched release.

## The fix: proofs are data

We stopped accepting code. A proof is now one entry point from a short allowlist (`safe_load`, `full_load`, `load` with `SafeLoader` or `FullLoader`) plus a YAML payload of at most 64 KB. Python, and the loaders PyYAML documents as unsafe, are refused before anything runs.

Inside the container a parent process creates a fresh directory and starts a child that does one thing: import PyYAML and call the declared entry point on the payload. The parent watches from outside (exit status, signal, time, memory, and whether `/tmp/proveit/marker` appeared) and is the only process that writes the result. The one-time code never enters the child, and the parent makes itself non-dumpable so the child can't read it through `/proc`.

Now every cheat fails by construction. There's no script to sleep or call `ctypes`. The marker can only appear if the library itself ran the payload as code, which is exactly the bug. On the real CVE-2020-14343 payload, PyYAML 5.3.1 gives `CODE_EXECUTION` with `construct_python_object_new` on the stack, and 5.4 refuses the tag. Each of the audit's attacks is now a test.

## Agents get evidence, never prose

The second thing the audit found: reporter text still leaked to the agents, through the ticket's title, the screen's excerpts and exception messages. Now everything an agent can read holds fixed fields only: hashes, sizes, allowlisted names, outcome classes, numbers, exception type names plus a hash of the message, and YAML tags only if they're known PyYAML tags. A canary test puts one string in every field a reporter controls and checks it never shows up in anything an agent can read. A paraphrased injection that slips past our regex screen still reaches the agents as nothing but a SHA-256.

## Switch Trust: planned

Switch Trust guardrails are built into Switch: an admin enters a Trust endpoint, policy ID and API key on the server's Home page, and every human message is checked before it becomes a room message. We plan to use it as the first wall. At the time of writing we have not configured it, so we can't show it blocking anything yet.

## Try it

```sh
git clone https://github.com/akhilll0305/team-pikachu-switch-ai
cd team-pikachu-switch-ai
python -m proveit build
python scripts/rehearse.py --twice           # the whole demo offline
bash scripts/switch-server.sh up
python scripts/e2e.py --env-file .proveit/switch-server/.env
```

The rehearsal replays all four demo reports through the real code and sandbox. The end-to-end script does the same through a real Switch server and Mattermost.
