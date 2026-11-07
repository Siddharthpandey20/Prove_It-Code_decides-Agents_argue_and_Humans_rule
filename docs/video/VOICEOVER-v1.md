# Prove It: demo voiceover (target 2:45 to 3:00)

Read at a calm pace, about 140 words a minute. About 350 words.

**Audio file:** save it as `docs/video/voiceover.wav` (or `voiceover.m4a`). One take, no music. Leave a short pause between sections.

**Footage:** all footage is from the live run on 2026-11-06, 15:35–15:46 IST: Switch Console 0.40.1 on Windows 11, Reproducer Claude Code 2.1.318, Skeptic Codex 0.166.0. Source: `docs/evidence/live-trust-2026-11-06-windows.log`.

**Replays:** every report shown is a replay.
- 01 is the public CVE advisory.
- 02 is synthetic.
- 04 is an attack we wrote.

---

## 1. Hook (0:00)

Writing a fake bug report takes an AI ten seconds. Checking it takes a maintainer an hour. In 2026, curl ended its bug bounty, then stopped taking security reports for July. HackerOne paused its Internet Bug Bounty.

## 2. Title

This is Prove It, built on Switch. AI spam is drowning open source. Prove It makes the AI prove its bug report before a human reads it.

## 3. How it works

Reporters post in a public intake room. Our own Intake agent, plain Python on Switch's agent protocol, links it to a private triage room. There, Claude Code reproduces, Codex plays the skeptic, and a maintainer decides. Code decides. Agents argue. Humans rule.

## 4. Case one: a slop report

Case one, a replayed slop report: critical code execution in PyYAML's safe load, with no proof. Intake asks for one, as data: an entry point and a YAML payload, never code. The proof becomes a ticket of fixed fields. The Reproducer runs it in a locked-down sandbox: not reproduced. The Skeptic concurs, and the maintainer closes it. The reporter hears exactly what the sandbox recorded.

## 5. Case two: a real CVE

Case two, a replayed real CVE: code execution through full load. On PyYAML 5.3.1: code execution. The Skeptic disputes: nobody checked the patched build, so escalation is blocked. The maintainer asks for PyYAML 5.4: not reproduced. The fix holds. The maintainer overrides and escalates, and the reporter is told, with both results.

## 6. Case three: an attack

Case three, an attack we wrote: hidden instructions telling AI reviewers to print their environment. Switch Trust blocked it before it entered the room. Even if it got through: a sandbox with no network and no secrets, and agents never see reporter text.

## 7. Why it matters

In our live run, both decided reports reached a maintainer's decision in under ten minutes, with the agents doing the checking. Elastic says a senior engineer spends thirty to sixty minutes on a typical report. We don't detect AI. We require proof.

## 8. Close

Rooms, linked rooms, a custom agent, Claude Code and Codex in one room, Switch Trust, a room document, and one template. Prove It: make the AI prove it. Built on Switch.
