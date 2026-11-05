# Checkpoint 2026-11-05: assessment fixes

The read-only assessment of `7b42217` (main) found 31 issues. They are merged
here into groups that share code, then fixed one group at a time on branch
`fix/checkpoint-2026-11-05`. A box is ticked only with evidence: the test,
command or live observation that shows it. Items only a person can do are in
group M and say so; they are not ticked on anyone's behalf.

Finding numbers (F1 to F31) refer to the assessment.

## A. Only maintainers decide (F1)

- [x] A1 Triage room is private in the template (`channel_type: channel_private`); intake room stays public.
- [x] A2 Intake accepts `escalate` / `close` / `override` / `release` only from maintainers on an allowlist (`maintainers` in `.proveit/intake.json`, set by `setup --maintainers`, default the deployer); everyone else gets a refusal.
- [x] A3 Read-only commands (`status`, `tally`, `evidence`) stay open to anyone in triage.
- [x] A4 Tests: an outsider's `close` / `escalate` / `override` / `release` are refused and the ticket is unchanged; a listed maintainer still decides.

  Evidence: `tests/test_intake.py` (`test_outsider_in_triage_cannot_decide`, `test_outsider_can_still_read`, `test_no_maintainers_configured_refuses_everyone`); rehearsal step 4 shows `someone-else` refused; template with `channel_type: channel_private` accepted by Switch 0.31.0 `/templates/validate` (no errors, no warnings).

## B. Agent roles and lockdowns (F2, F3, F4)

- [ ] B1 Each agent's identity comes from its own config (`PROVEIT_AGENT=reproducer|skeptic`), not from `--by`. Agents' `--by` is ignored.
- [ ] B2 The CLI enforces roles: the Reproducer may `check`, never `concur`/`dispute`; the Skeptic may `concur`/`dispute`, never `check`.
- [ ] B3 Reproducer's Claude allow list no longer contains `concur`/`dispute`; deny list covers other Python forms (`python -I -c`, `python3.x`, ...).
- [ ] B4 Skeptic's Codex config is an allowlist: `approval_policy = "untrusted"` so anything unlisted needs a human's approval, `allow` rules for exactly its proveit commands, `forbidden` rules for the bypasses found (`python -I -c`, `python3.9 -c`, `Get-Content`, `type`, `dd`, `xargs`, `paste`, `tee`, `powershell`, `pwsh`, `cmd`, `osascript`, ...).
- [ ] B5 Reporter material moves out of the agents' writable ticket store: `private/` lives under `.proveit/private/<id>/` (git-ignored, denied to both agents), so the Skeptic's write access to `work/` cannot touch it.
- [ ] B6 `tests/test_agent_rules.py` covers every bypass from the assessment, and the Claude settings are checked for the role rules.
- [ ] B7 Console's `--permission-mode auto` is documented with what it means and how to check it (live result recorded in J).

## C. Evidence says only what it shows (F5, F6, F7, F8, F27, F28, F29)

- [ ] C1 The patched comparison uses only a patched run with the same entry point and payload hash as the vulnerable run; otherwise the checklist says `patched_comparable: False` and a note explains.
- [ ] C2 An inconclusive or invalid patched run does not count as "patched build checked"; a note says it was inconclusive.
- [ ] C3 Skeptic verdicts and overrides record the run they refer to; a new vulnerable run marks an earlier verdict stale.
- [ ] C4 Escalation needs a current Skeptic concur or a maintainer override (decision D-007); the refusal says which.
- [ ] C5 `INVALID_PROOF` never becomes `not_reproduced`.
- [ ] C6 Information-leak claims are never reported as "did not reproduce": the reporter is told the sandbox cannot decide them.
- [ ] C7 A timeout where the child used little CPU (a slow or overloaded host) is `INCONCLUSIVE`, not `RESOURCE_EXHAUSTION`.
- [ ] C8 Reporter messages state the patched result only when it is comparable, and never as proof of a fix when it is not.
- [ ] C9 Tests for each of the above.

## D. Only the reporter completes their report (F9)

- [ ] D1 In a reporter's thread, only the original reporter's replies change the ticket (decision D-008). Others get a notice and nothing changes.
- [ ] D2 Ignored contributions are recorded privately (who, when, a hash) and counted in the ticket as `foreign_replies`, so maintainers can see that someone else tried.
- [ ] D3 Tests: Bob's reply leaves Alice's ticket unchanged; Alice's reply still works.

## E. Intake does not lose or repeat work (F21, F22, F23, F24)

- [ ] E1 The event cursor per room is saved in `.proveit/` and resumed after a restart; reports posted while Intake was down are processed.
- [ ] E2 The cursor advances only after the handler succeeded.
- [ ] E3 The same message delivered twice creates one ticket (dedupe on message id).
- [ ] E4 If telling the reporter fails, the ticket records `notified: false`, triage gets a warning, and `@prove-it-intake notify R-001` resends.
- [ ] E5 Tests for each.

## F. Safe concurrent writes (F25)

- [ ] F1 Temporary files have unique names.
- [ ] F2 Every load-modify-save of a ticket holds a per-ticket lock (works on macOS, Linux and Windows).
- [ ] F3 Run files and ticket ids are created exclusively, so two writers never share a number.
- [ ] F4 Test: two simultaneous checks on one ticket both end up recorded; two simultaneous reports get different ids.

## G. Builds and tests everywhere (F10, F11, F12, F20)

- [ ] G1 `tests/test_harness.py` skips on non-POSIX systems instead of failing discovery.
- [ ] G2 CI runs the unit tests on `windows-latest` (Docker tests skip there) as well as the full suite on Ubuntu.
- [ ] G3 Dockerfile pins exact Cython and wheel versions.
- [ ] G4 Every Docker call has a timeout; build failures include Docker's output.
- [ ] G5 Fresh `python -m proveit build --force` on the demo machine, then the full suite with `PROVEIT_REQUIRE_DOCKER=1`, no unexpected skips.

## H. Demo tooling and preflight (F13, F14, F30, F31)

- [ ] H1 `scripts/replay.py` works against Console's native server: login from `.proveit/reporter.json` or env, port from Console's `ports.json`, channel found by display name with stale channels ignored.
- [ ] H2 `python -m proveit doctor` checks: Docker, both images current, Switch server reachable, Intake registered, rooms and `triage` link, triage private, agents present and in their own folders, maintainers set, reporter login for replays.
- [ ] H3 Tests for doctor's checks that do not need live services.
- [ ] H4 SETUP troubleshooting covers the Mattermost crash on room changes and the "admin" display name for Codex posts.

## I. Honest metrics and scope (F26, F27)

- [ ] I1 "Maintainer time" is renamed "time to decision" everywhere (tally, messages, docs).
- [ ] I2 The reporter's first reply states the scope (PyYAML 5.3.1 vs 5.4, the four entry points).
- [ ] I3 Tests updated.

## J. Live verification (F15, F16, F17, F18, F19)

- [ ] J1 Headless e2e (`scripts/e2e.py`) rerun on this branch; log saved to `docs/evidence/`.
- [ ] J2 Rehearsal twice on this branch.
- [ ] J3 Console redeployed from the updated template; Intake restarted on the new code.
- [ ] J4 Live run in Switch Console with the real Claude Reproducer and Codex Skeptic: check, patched check, Skeptic review, maintainer decision, reporter reply. Room log and ticket JSON saved to `docs/evidence/`.
- [ ] J5 Live permission checks: each agent asked to read `private/` and to run a forbidden command; results recorded.
- [ ] J6 Live outsider check: a non-maintainer's `close` is refused in the real room.

## K. Documentation (F30)

- [ ] K1 README: tested-with table filled from this machine, OS support, verification table, commands, limits.
- [ ] K2 SETUP, DEMO, agents/README, blog draft match the code.
- [ ] K3 `context.md` updated (status, decisions D-007 and D-008, history); `AGENTS.md` and `context.md` committed.

## L. Future work (F31 list)

- [ ] L1 `python -m proveit export R-001`: a folder of fixed-field evidence (ticket, runs, SHA-256 manifest), no reporter text. Tested.
- [ ] L2 README "After the hackathon" section: adapters, GitHub/HackerOne intake, separate OS user for agents, automatic fixing as a separate workflow.

## M. Only a person can do these

Tooling for each is in place; they are not ticked by the agent.

- [ ] M1 Configure Switch Trust and confirm replay 04 is blocked (SETUP section 5).
- [ ] M2 Run the Trust red-team evaluation and record the score.
- [ ] M3 Record agent cost from Switch ROI with `python -m proveit cost`.
- [ ] M4 A Windows teammate runs the suite on Windows.
- [ ] M5 Confirm decisions D-007 and D-008 as a team (defaults chosen here).
- [ ] M6 Record the demo video and submit by 2026-11-07 11:59 PM IST.

## N. Pull request

- [ ] N1 Branch pushed and a PR opened against `main` with this checklist's result.
