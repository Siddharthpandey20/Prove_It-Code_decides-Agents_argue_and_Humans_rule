# Prove It: demo voiceover v2 (target 2:40 to 2:55)

About 430 words at roughly 165 words a minute. v1 is kept in `VOICEOVER-v1.md`.

**Footage:** live trial `review4`, 2026-11-07. Managed Claude Code and Codex agents in Switch Console, on Mattermost.

**Replays:**
- R-001 replays public CVE-2020-14343.
- R-004 is a synthetic replay fixture based on CVE-2023-30608.
- R-006 and R-007 are synthetic.

## 1. Hook

You maintain an open-source library. Your security inbox is full of reports marked critical. An AI wrote many of them in seconds. Each one can take you up to an hour to disprove.

## 2. Problem

This is already breaking real programs. curl ended its bug bounty in January, then stopped taking security reports for July. HackerOne paused its Internet Bug Bounty. And a chatbot won't save you. It reads the same convincing text you do, and it can be talked into agreeing.

## 3. Reveal

So we built Prove It: a triage room that makes every security report prove itself in a sandbox, before a maintainer spends time on it. Built on Switch. We don't detect AI. We require proof.

## 4. Demo

Here's a live run. A reporter posts a replay of a real CVE in the public intake room. Intake, our own Python agent, turns it into a fixed-field ticket in the private triage room. The maintainer asks Claude Code, the Reproducer. Three fresh sandbox runs on PyYAML 5.3.1: code execution, three out of three. Codex, the Skeptic, reads the evidence and pushes back: nobody checked the patched build. So the Reproducer runs 5.4. Not reproduced, three out of three. The Skeptic tries to concur, but Intake refuses: a dispute stands until a human decides. The maintainer overrides, and escalates. The reporter gets the answer in their own thread, and Prove It writes a draft advisory and timeline, marked for maintainer review.

## 5. Second room

Same agents, second room: sqlparse. A synthetic replay of a known bug keeps the CPU busy past ten seconds on version 0.4.3, three out of three, and finishes in milliseconds on 0.4.4. And Prove It says no, too. Two claims that didn't reproduce were closed on the evidence. After two failed proofs, that reporter can keep only one report open, until a maintainer lifts the limit with one command. No AI detector. No ban.

## 6. Why Switch

Switch is what turns this into a team workflow. It bridges Mattermost, links the public and private rooms, shares the scope policy and verdict rules as room documents, and runs Claude Code and Codex as managed agents, all from one template. And it tells Intake who sent every message, so only maintainers decide. Without Switch, the reporter, the agents and the maintainer have no shared room. Prove It enforces the rules. Docker runs the proof.

## 7. Impact

The numbers from this trial. Three fresh containers per build, six sandbox runs per verdict. The sqlparse hang ran past the ten-second limit; the patched build finished in sixty-six milliseconds. Every escalation writes four draft files. 314 tests pass, with zero failures. It fits any team that receives security reports: library maintainers, bug bounty desks, open-source security teams. Import the template to set up the rooms and agents.

## 8. Close

Prove It. Code decides, agents argue, humans rule. Built on Switch, for Flip the Switch.
