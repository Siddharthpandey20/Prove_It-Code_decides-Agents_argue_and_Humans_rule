# Agent instructions

> **Role:** Entry point for AI agents working on Team Pikachu's Prove It repository during the Flip the Switch hackathon. Read [context.md](context.md) before taking project action.

## Information locations

| Subject | Home |
| --- | --- |
| Product, scope, users | [context.md — Project overview](context.md#project-overview) |
| Architecture and invariants | [context.md — Architecture and rules](context.md#architecture-and-rules) |
| Standing constraints | [context.md — Standing constraints](context.md#standing-constraints) |
| Code and documentation conventions | [context.md — Working conventions](context.md#working-conventions) |
| Current status and progress | [context.md — Current status](context.md#current-status) and [Progress and deadlines](context.md#progress-and-deadlines) |
| Work items and completion evidence | [context.md — Progress and deadlines](context.md#progress-and-deadlines) |
| Authoritative decisions and their reasons | [context.md — Key decisions](context.md#key-decisions) |
| Historical trials and corrections | [context.md — Important history and trials](context.md#important-history-and-trials) |
| Open questions | [context.md — Open questions and risks](context.md#open-questions-and-risks) |
| Operational setup | [docs/SETUP.md](docs/SETUP.md) |
| Demo flow | [docs/DEMO.md](docs/DEMO.md) |
| Product explanation and verification claims | [README.md](README.md) |

This compact layout was chosen for a short hackathon: one shared context file keeps current status, decisions, and selective history together; this file makes it discoverable to agents. Open the setup or demo guide only when the task needs those steps.

## Working rule

When a task changes status, decisions, deadlines, or a meaningful failure, update `context.md` in the same change. Include date, result, evidence, and next action. Do not turn an unverified plan into a verified claim. Keep secrets out of documentation.

For documentation changes, manually check that links and headings resolve, decisions have unique IDs and reasons, status agrees with the README and demo guide, and no secrets or unfinished placeholders were added. There is no automated documentation guard.
