DRAFT, needs maintainer review

# DRAFT: denial of service in sqlparse via parse

## Summary

A report to Prove It (R-004) claims denial of service when an application passes untrusted SQL to `sqlparse.parse(payload)`. The claimed severity is unrated. This draft says only what the sandbox recorded; a maintainer must review and complete it.

## Affected versions

- Reported affected version: 0.4.3 (as stated in the report, not tested as such)
- Tested vulnerable build, sqlparse 0.4.3: RESOURCE_EXHAUSTION, 3/3 clean runs
- Patched build, sqlparse 0.4.4: NOT_REPRODUCED, 3/3 clean runs

No fixed version is claimed. Only the two pinned builds were run.

## How it was reproduced

- Entry point: `parse`
- Payload: not included in this draft. SHA-256 `5bbd4e474a2414a50ec1ef79c6a82d1d0207ff1e1aa31a27bca6171c325097d0`, 44 bytes, known tags: none. The payload is in the private copy, private/R-004/payload.yaml (its folder is shown by `python -m proveit doctor`).
- Builds: sqlparse 0.4.3 (vulnerable) and 0.4.4 (patched), in a container with no network, a read-only file system, an unprivileged user, all capabilities dropped and fixed limits.
- Each check ran the payload several times in fresh containers; n/N above is how many agreed.

## Evidence

| file | SHA-256 |
| --- | --- |
| work/R-004/runs/01-vulnerable.json | e609327de22df0d9ebcf1fdb96b12b95a280280abe336acdf82a1fe7e9086988 |
| work/R-004/runs/02-patched.json | e88a8d6eab172a4bdfdd734a0403d31ea94a3d63028a938fc4e9edb32f1a7563 |

## Timeline

See [timeline.md](timeline.md) (every step with UTC timestamps).

Aliases: none
