DRAFT, needs maintainer review

# DRAFT: code execution in PyYAML via full_load

## Summary

A report to Prove It (R-001) claims code execution when an application passes untrusted YAML to `yaml.full_load(payload)`. The claimed severity is critical. This draft says only what the sandbox recorded; a maintainer must review and complete it.

## Affected versions

- Reported affected version: before 5.4 (as stated in the report, not tested as such)
- Tested vulnerable build, PyYAML 5.3.1: CODE_EXECUTION, 3/3 clean runs
- Patched build, PyYAML 5.4: NOT_REPRODUCED, 3/3 clean runs

No fixed version is claimed. Only the two pinned builds were run.

## How it was reproduced

- Entry point: `full_load`
- Payload: not included in this draft. SHA-256 `75ce42a97f62f51b906ca79b2e94f7affd0eb6816850b3bfc5132ec65bfbda06`, 171 bytes, known tags: `!!python/object/new:tuple`, `!!python/object/new:map`, `!!python/name:eval`. The payload is in the private copy, private/R-001/payload.yaml (its folder is shown by `python -m proveit doctor`).
- Builds: PyYAML 5.3.1 (vulnerable) and 5.4 (patched), in a container with no network, a read-only file system, an unprivileged user, all capabilities dropped and fixed limits.
- Each check ran the payload several times in fresh containers; n/N above is how many agreed.

## Evidence

| file | SHA-256 |
| --- | --- |
| work/R-001/runs/01-vulnerable.json | 7a7f47c5a0dc4c11fe6a67c80dc80619ae8f42b92a51e344f12dc9d332aa7c49 |
| work/R-001/runs/02-patched.json | e9e7c52e4b0f74799d090eec0ef3acebf8b598b5f290de910a021d2c65655fb5 |

## Timeline

See [timeline.md](timeline.md) (every step with UTC timestamps).

Aliases: none
