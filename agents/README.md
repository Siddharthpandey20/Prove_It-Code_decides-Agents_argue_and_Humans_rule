# Agent working folders

The Switch template starts each triage agent in its own folder here, not in
the repository root, so the lockdowns below apply only to the agents and
never to people developing Prove It.

| Folder | Agent | Config | What it enforces |
| --- | --- | --- | --- |
| `reproducer/` | Reproducer (Claude Code) | `.claude/settings.json` | `defaultMode: dontAsk` (anything not allowed is denied, no prompt), `disableBypassPermissionsMode: disable`, allow only `python -m proveit check / evidence / show / list / tally / concur / dispute`, deny network tools, shells, `docker`, `rm`, `git`, `python -c`, the Edit/Write tools, web tools and reads of `work/*/private/`. `PROVEIT_ACTOR=agent` makes the CLI refuse `override` and `cost`. |
| `skeptic/` | Skeptic (Codex) | `.codex/config.toml`, `.codex/rules/proveit.rules` | `workspace-write` sandbox with no network, writes only to `../../work`. `forbidden` rules (for `python` and `python3`) for `proveit check / override / cost / submit / build`, `-c` / `-` / other `-m` modules, every general file reader (`cat`, `head`, `grep`, `sed`, `jq`, ...), nested shells, network tools, `docker`, and file changes. Codex's sandbox does not limit reads, and rules match a command's leading words rather than paths, so file readers are forbidden outright: the Skeptic reads tickets only through `python -m proveit`. Same `PROVEIT_ACTOR=agent`. `tests/test_agent_rules.py` checks the rules with `codex execpolicy` when Codex is installed. |

`PYTHONPATH=../..` lets `python -m proveit` run from these folders; tickets
still live in the checkout's `work/`.

Both tools apply project allow rules and environment settings only after you
trust the folder (Claude Code: workspace trust; Codex: project trust). Deny
rules in Claude Code apply right away. Bash permission rules match the
command the agent writes, not every way a program can be started, so they
are a guard rail on top of the real boundary: the payload only ever runs in
the no-network sandbox, and agents only ever see fixed fields.
