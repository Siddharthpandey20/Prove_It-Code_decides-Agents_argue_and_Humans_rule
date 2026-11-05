# Prove It — project context

> **Role:** Shared source of truth for Team Pikachu and AI agents during the Flip the Switch hackathon. Read this before changing the project; use the linked files for operational detail.

Last reviewed: 2026-11-05 (IST). Status combines the repository at `7b42217` with the team's answers on 2026-11-05. A recorded result is not a claim that it was rerun today.

## Project overview

**Goal:** Submit Prove It to the Flip the Switch hackathon's Track 01, Best Business Workflow. Prove It helps maintainers triage security reports: a reporter submits a claim in Switch, Intake requests a data-only proof, a sandbox records what happened, a Reproducer and Skeptic examine the evidence, and a human maintainer decides. The result returns to the reporter's thread. The intended users are open-source maintainers and teams handling public vulnerability reports.

**Why this project:** AI-generated, low-quality reports consume maintainer time. The team chose a workflow that asks the reporter for reproducible evidence, keeps Switch central to coordination, and keeps the final decision with a person. The [README](README.md) explains the product and limits; [SETUP](docs/SETUP.md) is the operational guide; [DEMO](docs/DEMO.md) is the current walkthrough.

**Hackathon scope:** A reproducible Switch workflow for the four supplied report replays, with an honest distinction between real, synthetic, and unverified results. This file tracks the hackathon through submission, not a post-hackathon product roadmap.

## Architecture and rules

- `proveit/intake.py` is a Python Switch agent, not an LLM. It handles the public intake room and routes fixed-field tickets to triage. `proveit/switch_client.py` implements its Switch connection.
- `#proveit-intake` holds reporter threads; `#proveit-triage` holds maintainers and the Reproducer (Claude Code) and Skeptic (Codex). The rooms are linked by the `triage` link in [the Switch template](switch/prove-it.template.yaml).
- `proveit/poc.py`, `proveit/sandbox.py`, and `target/` validate and run one allowlisted PyYAML entry point on a YAML payload in a restricted Docker container. The parent process observes the child and writes the outcome.
- `proveit/states.py`, `proveit/actions.py`, and `proveit/messages.py` enforce state changes and human decisions. `proveit/evidence.py` provides the evidence pack.
- Python 3.9+ and Docker are required to run the project. The demo targets Switch 0.31.0 and PyYAML 5.3.1 (vulnerable) versus 5.4 (patched). See the README for tested environments and exact commands.

The following rules govern all hackathon work:

1. A reporter's proof is data: an allowlisted entry point plus a UTF-8 YAML payload no larger than 64 KB. Do not accept reporter-supplied Python or unsafe loaders.
2. Agent-visible tickets, messages, output, and evidence contain fixed or sanitized fields. Reporter prose and raw payloads stay in private storage; agents must not read them.
3. Only a human maintainer may escalate, close, release, or override a report. A quarantined report cannot be escalated; a dispute requires a human override before escalation.
4. A result must say what was actually observed. A headless run with scripted agent choices does not verify live Claude Code or Codex behavior; planned Switch Trust protection must not be described as configured.
5. Keep **Bypass permissions** off for the two command-running agents in Switch Console. Their folders in `agents/` carry scoped permissions.

## Standing constraints

- The current demo is limited to PyYAML, four supported entry points, and four supplied replays. Information-leak claims are not automatically decided. See [README: Limits](README.md#limits).
- Secrets and registration tokens belong in ignored local configuration, never in this file or Git. Record configuration names or setup steps only.
- The final hackathon submission closes **2026-11-07 at 11:59 PM IST**, per the [official rules](https://www.devtoolsacademy.com/hackathons/flip-the-switch). No earlier team deadline has been set.
- Task owners remain **unassigned** until the team agrees on them.

## Working conventions

- Use [SETUP](docs/SETUP.md) for console steps, [DEMO](docs/DEMO.md) for the walkthrough, and the README for reproducibility claims. Update those files when a new verified result changes their instructions or claims.
- For a completed task, record the date, result, evidence (commit, file, or command output), and next step in this file in the same change. Record failed attempts only when they explain a decision or a remaining problem.
- Before marking code work complete, run the relevant checks. The full documented checks are `python -m unittest discover -s tests -v`, `python scripts/rehearse.py --twice`, and, when a Switch server is available, `python scripts/e2e.py --env-file .proveit/switch-server/.env`. Report skips and environment limits accurately.

## Current status

**As of 2026-11-05:** Core code, test suite, repeatable rehearsal, and a headless Switch 0.31.0 end-to-end run are recorded. [The run log](docs/evidence/e2e-2026-11-05.log) ends in `E2E PASSED`; CI is configured to build both images, run tests, and rehearse twice. The team confirms that no additional demo, Trust, blog, or submission work has been completed since the last repository update. The live two-agent workflow in Switch Console remains the main unverified gap.

**Next action:** Set up Switch Console on the demo machine, sign in Claude Code and Codex, deploy the template, and verify both agents work in a real triage room. Check the demo machine's Claude sign-in before the deadline; the former team brief warned that its session might expire around November 7–10, but its current state has not been checked.

## Progress and deadlines

| Item | Status | Owner | Done when / evidence |
| --- | --- | --- | --- |
| Data-only proof sandbox, evidence-only routing, state machine | Done | Historical team work | Implementation and tests in Git; see decisions and history below. |
| Offline tests and four-report rehearsal | Recorded as passing | Unassigned | Latest README reports 74 tests and a two-run rehearsal; rerun on the final demo machine and record the actual result. |
| Headless Switch/Mattermost end-to-end | Done | Historical team work | [2026-11-05 log](docs/evidence/e2e-2026-11-05.log) records `E2E PASSED`. This uses scripted agent choices. |
| Live Claude Code + Codex in Switch Console | Pending | Unassigned | Both agents receive the intended room instructions, run their allowed commands, and post evidence-based results in the real room. Record machine, versions, and observations. |
| Agent permissions on the demo machine | Pending verification | Unassigned | Confirm both folder settings apply, Bypass permissions is off, and the Skeptic can write only its intended result. |
| Switch Trust guardrail and replay 04 | Pending setup | Unassigned | Configure Trust, post replay 04, and record whether it is blocked before reaching intake. Intake's existing quarantine is the fallback. |
| Public repo and accurate README | Repo exists; final review pending | Unassigned | Confirm public access and update verification claims after the live run. |
| Short demo video | Deferred from immediate priorities; required for submission | Unassigned | Record the running workflow and include its link in the submission by **Nov 7, 11:59 PM IST**. |
| Submit Track 01 entry | Pending | Unassigned | Submit the public repo, README, and video by **Nov 7, 11:59 PM IST**; record confirmation. |

**Possible later work, outside the active checklist:** Edit and publish [the blog draft](docs/blog-draft.md) for Best Blog; make a `#HowISwitch` clip/post; pursue a Track 03 Switch contribution if an eligible issue is available and assigned. These are optional side activities, not completed commitments.

## Key decisions

These records are authoritative. Keep their IDs and reasons when updating them; refer to an ID elsewhere instead of copying its record.

- **D-001 — Build Prove It for Track 01.** Reason: the team judged it a more distinctive, Switch-centered, and achievable hackathon workflow than Shipyard or API Change Gate. Source: former `docs/team-brief.md` at commit `de6b7a6`.
- **D-002 — Accept data-only YAML proofs.** Reason: the original reporter-supplied Python could forge a result and manufacture crash or resource-exhaustion outcomes. A limited entry point and payload remove those arbitrary actions. Source: audit redesign in commits `302ea3f` and [blog draft](docs/blog-draft.md#the-hole-a-proof-that-grades-itself).
- **D-003 — Have a separate parent observe the proof process.** Reason: the first harness shared a process with untrusted code, allowing the code to read or forge the result; the parent now makes the classification from its own observations. Source: `302ea3f`, with a forged-MemoryError correction in `c1b36bb`.
- **D-004 — Show agents fixed-field evidence, never reporter prose.** Reason: the audit found reporter text in titles, excerpts, and exceptions, creating a prompt-injection path. Source: `9370c8e` and [blog draft](docs/blog-draft.md#agents-get-evidence-never-prose).
- **D-005 — Keep final report decisions with maintainers.** Reason: agents should test and challenge evidence while a person decides whether to escalate or close. Source: `9370c8e`, [README: Ticket states](README.md#ticket-states).
- **D-006 — Use one root context file plus a short agent entry point during the hackathon.** Reason: people and agents need the same current status and selective history, with one obvious place to update it. Source: team answers on 2026-11-05.

## Important history and trials

All dated entries below are **2026-11-05 IST** unless noted. Commit links are given as hashes so the history stays available in Git even if the hosted repo changes.

| Date / commit | Trial, problem, or milestone | Result and lesson |
| --- | --- | --- |
| Before first commit; former team brief | Questionnaire, support, onboarding, Shipyard, and API Change Gate ideas were considered. | Prove It was selected for Track 01 (D-001). Shipyard faced direct competition; API Change Gate did not use Switch strongly enough. |
| Nov 5, `50ce08c`–`4a3e62e` | Initial Intake, sandbox, Switch template, tests, demo materials, and a headless Reproducer dry run. | Established the end-to-end concept. The early report claiming 17 tests and an audit-hook Python proof is historical, not the current design. |
| Nov 5, audit and `302ea3f` | The first proof ran reporter Python in the harness process. An audit demonstrated forged results and artificial sleep/crash/unsafe-loader outcomes. | Replaced executable proofs with data-only YAML and an out-of-process observer (D-002, D-003). Tests cover the former attacks. |
| Nov 5, `9370c8e`–`de6b7a6` | Audit also found reporter-controlled text reaching agents. Access roles, state transitions, and messages needed tightening. | Added fixed-field evidence, a canary test, human-only decisions, scoped agent folders, and repeatable rehearsal (D-004, D-005). |
| Nov 5, `61e2d84`, `cff4e10` | PyYAML 5.4's ARM64 build and Docker mount behavior caused Apple silicon problems. | Changed the Docker build and temporary mount location; later fixed the build/run path again. Verify on the final demo machine. |
| Nov 5, `c1c54e4` | Ran Intake against Switch 0.31.0 and Mattermost. | Headless end-to-end replay passed and was logged. It did not exercise live LLM agents. |
| Nov 5, `c1b36bb`, merged by `7b42217` | Review found a child-forged `MemoryError`, overly broad Skeptic file reads, and a follow-up that erased a saved payload. | Fixed classification, permission rules, and follow-up merging; added tests. The latest README reports 74 tests. |

## Open questions and risks

- **Live agent behavior:** Will both vendors' agents follow the intended workflow and permissions in the final Switch Console environment? This is the next test, not a known success.
- **Trust configuration:** Can the team configure and demonstrate the guardrail before submission? If not, describe the actual Intake quarantine only.
- **Submission logistics:** The exact form, video link, and submitting teammate have not been recorded. Assign these before Nov 7.
- **Demo machine readiness:** Check Claude/Codex sign-in, Docker, and Switch Console before recording; do not assume the earlier dry run covers this machine.

## How this file is maintained

- **Current status and progress:** Replace stale status as work changes; mark completion only with a date and evidence. Keep the next action and deadline visible. Assign owners only after the team agrees.
- **Decisions and constraints:** Add a `D-NNN` record for a consequential confirmed choice, with its reason and source. Never reuse an ID or silently change the reason. If a decision is replaced, keep the old record marked superseded and point to the new ID. Keep active rules in the architecture or constraints sections.
- **History:** Append only milestones, failed trials that changed direction, or corrections to an important claim. Preserve the result and source. Do not turn this into a daily journal or copy long explanations already in Git or linked docs.
- **Open questions and optional work:** Resolve or update them when evidence or a team decision arrives. Keep unverified results visibly distinct from verified ones.
- **Before sharing or submitting:** Check links and headings, compare status with the README and demo guide, confirm every decision has one record and a reason, and scan for secrets or unfinished placeholders. These documentation checks are manual; no guard script is installed.
