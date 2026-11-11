# Live trial review4: results and numbers (2026-11-07)

Managed Claude Code (Reproducer) and Codex (Skeptic) agents in Switch Console, with Mattermost. This is the isolated trial `review4`:

| Item | Value |
| --- | --- |
| Code | branch `feat/second-library` at `7568a4e`, merged into `main` by PR #4 (`c63a832`) |
| Maintainer account | `user` |
| Reporter account | `reporter_test` |
| Room pairs | `review4-proveit-intake` / `review4-proveit-triage` (PyYAML); `review4-sqlparse-intake` / `review4-sqlparse-triage` (sqlparse) |

This folder holds the final managed-agent results: the advisory pack, the reporter limit and the sqlparse rooms, all live.

## What is here

| File | What it is |
| --- | --- |
| `room-posts.md` | Text of the 53 room posts behind each result: time (IST), room, sender, post ID. Exported read-only from Mattermost. |
| `tickets/R-001/` | PyYAML ticket: `ticket.json`, `runs/01-vulnerable.json`, `runs/02-patched.json`, `advisory/` (4 files) |
| `tickets/R-004/` | sqlparse ticket: the same set |
| `tickets/R-006/`, `tickets/R-007/` | Non-reproduction tickets: `ticket.json`, `runs/01-vulnerable.json` |
| `tickets/R-008/` | `ticket.json` only (accepted after the reset, not sandbox-tested) |
| `test-suite-7568a4e.log` | Full test suite output at `7568a4e` |

The ticket files were copied from `pikachu-lib2/.proveit-trials/review4/work/`, which git ignores. They hold no payload text, no absolute paths and no credentials (searched before copying). The payloads stay in the private folder; only their SHA-256 appears.

**Replays:**
- R-001 replays public CVE-2020-14343.
- R-004 is a synthetic replay based on CVE-2023-30608.
- R-006, R-007 and R-008 are synthetic.
- None of them is a new vulnerability.

## Results

### 1. PyYAML R-001: report to decision

1. Intake accepted the report and posted a fixed-field ticket.
2. Reproducer, `full_load` on PyYAML 5.3.1: **CODE_EXECUTION, 3/3** fresh-container runs. The marker file appeared, with PyYAML constructor frames recorded.
3. Skeptic: **dispute `patched_not_checked`**.
4. Reproducer, PyYAML 5.4: **NOT_REPRODUCED, 3/3**.
5. The Skeptic attempted to concur twice; **Intake refused both times** ("cannot concur a ticket that is disputed").
6. The maintainer **overrode** the dispute and **escalated**.
7. The reporter was told in their own thread, and Intake posted "Advisory pack for R-001 (DRAFT, needs maintainer review)".
8. The files are in `tickets/R-001/advisory/`: `osv-draft.json`, `ghsa-draft.md`, `timeline.md`, `timeline.json`.

### 2. sqlparse R-004: second target, same agents

1. Entry point `parse`, 44-byte payload.
2. **sqlparse 0.4.3: RESOURCE_EXHAUSTION, 3/3**, CPU-busy past the 10 s limit (10.005 s).
3. **sqlparse 0.4.4: NOT_REPRODUCED, 3/3**, 0.066 s.
4. The Skeptic disputed `patched_not_checked`; its concur was then refused twice while the dispute stood.
5. The maintainer overrode and escalated, and the reporter was told.
6. The advisory pack is in `tickets/R-004/advisory/`.

### 3. Claims closed on evidence

- R-006 (`SELECT 1;`) and R-007 (`SELECT 2;`) through `sqlparse.parse`: **NOT_REPRODUCED, 3/3** each.
- The Skeptic concurred, and the maintainer closed both.

### 4. Reporter limit and reset

1. After R-006 and R-007 were closed, the reporter had 2 failed proofs.
2. A new report was refused: "You already have an open report (R-002) that is waiting for a valid proof".
3. Intake posted "Reporter d89081282a9e is limited to one open report (2 proofs did not reproduce)".
4. The maintainer ran `clear-reporter d89081282a9e`, and Intake replied "invalid count reset to 0".
5. The next report was accepted as **R-008** (not sandbox-tested).

R-002, R-003 and R-005 were incomplete attempts (proofs never completed), not failed sandbox runs.

## Numbers

These are the numbers used in the demo video, with their sources.

| Number | Source |
| --- | --- |
| 3/3 clean runs per build check | R-001 and R-004 run files and room posts |
| 6 sandbox runs per vulnerable/patched comparison | 3 + 3: `tickets/R-001/runs/`, `tickets/R-004/runs/` |
| > 10 s (0.4.3) vs 0.066 s (0.4.4), same 44-byte payload | R-004 posts `e5py6na6…`, `8pothgw1…`; `tickets/R-004/runs/` |
| 4 draft files per escalation | `tickets/R-001/advisory/`, `tickets/R-004/advisory/` |
| 2 failed proofs → one open report | Post `4mhm6xh6…` |
| Tests passed, 0 failures | `test-suite-7568a4e.log` |
| 30–60 min per report, 1,390+ reports in H1 2026 | Elastic's figures for Elastic's system (Elastic Security Labs, 2026-08-04), not a Prove It measurement |

## Limits

**Not measured:**
- agent cost
- maintainer time saved (time to decision is elapsed time, not effort)

**Not demonstrated in review4:**
- every dispute reason
- stale-token rejection
- a refused escalation while disputed
- provider permission limits
- reporter attempts at maintainer commands
- cross-room throttling
- the exact fixed question received after a close
- a Trust red-team score
- schema validation of these specific advisory files
- hosted CI on `7568a4e`

Some of these have headless or offline evidence in `docs/evidence/live-checks-2026-11-07-headless.log` and the test suite.
