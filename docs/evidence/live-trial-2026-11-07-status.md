# Isolated live trial status — 2026-11-07

This is a short, sanitized account of the local `review` trial as inspected in
Switch on 2026-11-07. It is not a complete end-to-end sign-off.

## Observed

- `R-001` ran through `full_load` on pinned PyYAML 5.3.1 and 5.4 builds.
- PyYAML 5.3.1 recorded `CODE_EXECUTION`, 3/3 clean runs, image prefix
  `d8219ba0f788`.
- PyYAML 5.4 recorded `NOT_REPRODUCED`, 3/3 clean runs, image prefix
  `00125fc0958b`.
- The Switch-managed Skeptic's first evidence command failed with
  `No module named proveit`. A later read-only room-history inspection showed
  a visible Skeptic concurrence after a maintainer supplied the sanitized
  evidence pack. That confirms the reply arrived, but not an independent read
  by the Skeptic.
- The isolated Reproducer and Skeptic are running in the primary PyYAML rooms.
  The sqlparse rooms have not been deployed.

## Still unverified

- A fresh managed Skeptic evidence command and review from its own session.
- Live reason-coded dispute behavior, fixed reporter question, advisory pack,
  reporter limit and reset, permission probes, and cross-room behavior.
- The sqlparse rooms, sqlparse images on the demo machine, and a live sqlparse
  check/review.
- Reporter and maintainer identity separation for human decisions.

No ticket escalation or close was observed. The Windows computer-use layer
declined access to Switch Console during this work, so no Console settings,
agent definitions, or rooms were changed.
