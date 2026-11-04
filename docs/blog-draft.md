# Making AI prove its bug reports: a custom Switch agent in plain Python

*Draft for the Flip the Switch "Best Blog" prize. Edit before publishing.*

In January 2026 curl ended its bug bounty. Its maintainers were drowning in vulnerability reports that an AI wrote in ten seconds and a human needed an hour to disprove. In July they stopped taking security reports for a month. We wanted to build something a small team could run: a place where a report has to prove itself before a maintainer reads it.

We built it on [Switch](https://github.com/sandbox-quantum/switch), which puts AI agents into team chat as teammates. This post covers what we learned as first-time Switch users, especially how to write your own agent against the Switch agent protocol. That turned out to be the most interesting part.

## The workflow

Two rooms. `#proveit-intake` is where anyone posts a report. `#proveit-triage` is where maintainers work with two coding agents: a Reproducer (Claude Code) that runs the proof of concept in a sandbox, and a Skeptic (Codex) that tries to disprove it. A maintainer closes or escalates with one message, and the reporter hears back in their own thread.

The interesting design question was the agent that reads the reports. A bug report is attacker-controlled text, and it is about to sit in front of agents that can run shell commands. So the agent in the intake room is not an LLM at all. It's plain Python on the standard library (a 220-line protocol client and the agent logic on top) that speaks Switch's protocol, screen for text written *to* AI reviewers, demand a runnable proof, and pass on only a ticket of fixed fields plus a PoC file. Nothing in the triage room ever reads the reporter's prose.

## Setting up Switch

Switch Console runs a local server in Docker and bundles Mattermost, so you don't need a company Slack. Two things worth knowing:

- Console keeps the local server's settings in a `.env` under its app-data folder, in `local-switch-server/`. It holds the agent registration token and the Gateway admin login. Our setup script reads it, so nobody copies secrets by hand.
- Templates are real infrastructure-as-code. One YAML file created our two Claude/Codex agents, both rooms as a room group, the link between them, exclusive `reproducer` and `skeptic` roles, a `verdict-rules` document in the room, and a kickoff message. An agent can even validate a template through the `save_template` operation, which returns warnings.

## Writing your own agent: what the protocol actually takes

The [agent protocol](https://docs.switchagents.ai/switch-rooms/internals/agent-protocol.md) is "SSE down, HTTP up". Here is the minimum we needed, all with Python's standard library:

1. **Register once.** `POST /agents` with the registration token as the bearer, `connector_type: "custom"` and an integration profile (`connection_model: "always_on"`). You get `{id, api_key}`, and the key is shown once.
2. **Open a stream per room.** `GET /agents/{id}/events?connection_id=<uuid>&scope=single&filter=all&rooms=<room id>`. Generate the connection id yourself and reuse it across reconnects; the connection outlives the socket. Declare the room on the URL, not afterwards, or you miss buffered events.
3. **Heartbeat every 2 seconds.** `POST /agents/{id}/connection/beat` with the connection id and cursor. A 404 or 409 means reopen the stream, not back off.
4. **Call operations.** `POST /agents/{id}/ops/{name}` with the arguments unwrapped. `GET /agents/{id}/ops` lists them all with schemas: `list_rooms`, `create_room`, `link_rooms`, `post_message`, `read_context` and many more.

Three things surprised us:

- `POST /agents/{id}/message` posts into a room but cannot reply in a thread. `post_message` can (`thread_id`), but it resolves the room from the `X-Switch-Connection-Id` header. Our fix: one connection per room, and post through the connection of the room you want.
- A new agent answers only its owner. Anyone else who mentions it gets an automatic "you're not permitted" reply. For a public intake room, the owner or an admin clears the policy with `PUT /gateway/agents/{id}/addressing-policy {"policy": null}`. Room membership is then the wall, and the agents that can run code stay in the room outsiders can't join.
- Agent senders look like `@switch-agent-…`. That made "only people can close tickets" easy to enforce: Intake ignores commands from other agents. We tested it with a rogue agent.

## Switch Trust in front of everything

Switch Trust guardrails are built into Switch itself. An admin enters a Trust endpoint, a policy ID and an API key on the server's Home page. From then on every human message is checked before it becomes a room message, and a blocked one never reaches any agent. We used a policy with Jailbreak set to Block, Secrets set to Redact, and a couple of regexes for "ignore your instructions".

## Proof, not opinion

The sandbox runs each PoC in a container with no network, a read-only filesystem, a 256 MB memory cap and no capabilities, against PyYAML 5.3.1 and 5.4. A Python audit hook records, for every file write or exec, whether the library's own code was on the call stack. That one detail separates a real bug from a fake proof. On the real CVE-2020-14343, the marker file is written from `construct_python_object_new`. On the AI-slop "RCE in safe_load", the script writes the marker itself, and the verdict is `INVALID_PROOF`.

## Try it

```sh
git clone https://github.com/akhilll0305/team-pikachu-switch-ai
cd team-pikachu-switch-ai
python -m proveit build
bash scripts/switch-server.sh up
python scripts/e2e.py --env-file .proveit/switch-server/.env
```

That replays all four demo reports through a real Switch server and Mattermost and checks every outcome.
