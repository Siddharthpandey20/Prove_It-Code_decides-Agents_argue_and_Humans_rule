# review4 live trial: room posts (exported from Mattermost)

Exported 2026-11-07 from the local Switch server's Mattermost, read-only, via the API. Times are IST. Post IDs let anyone with access find the original.
Reports are replays: R-001 replays public CVE-2020-14343; R-004, R-006, R-007 and R-008 are synthetic. Long posts are cut at 1,500 characters.

## PyYAML R-001 (review4-proveit-*)

### 20:10:14 · #review4-proveit-intake · @reporter_test · `byq9zrsf5bd8uemdiytunm3g7o`

> @review4-prove-it-intake 
> Title: Arbitrary code execution in yaml.full_load via python/object/new
> Reporter: replay of the public CVE-2020-14343 advisory
> Source: real. Public advisory https://nvd.nist.gov/vuln/detail/CVE-2020-14343 and https://github.com/yaml/pyyaml/issues/420 (rewritten into Prove It's data-only proof format)
> Severity: critical
> Affected version: before 5.4
> Entry point: yaml.full_load
> Claimed impact: arbitrary code execution when untrusted YAML is passed to yaml.full_load / FullLoader
> 
> `FullLoader` is meant to avoid arbitrary code execution, but it still
> resolves `!!python/object/new` and `!!python/name` tags. Combining them lets
> a document call any callable, including `eval`, while it is being loaded.
> This bypasses the fix for CVE-2020-1747.
> 
> Proof of concept (the document makes the loader create /tmp/proveit/marker):
> 
> ```yaml
> !!python/object/new:tuple
> - !!python/object/new:map
>   - !!python/name:eval
>   - ["__import__('pathlib').Path('/tmp/proveit/marker').write_text('owned by yaml.full_load')"]
> ```
> 
> Expected result: on PyYAML 5.3.1 the marker file is created during
> `yaml.full_load`. Fixed in PyYAML 5.4.
> 
> Expected: full_load builds plain data and runs no code
> Actual: full_load calls eval and the marker file is created
> 

### 20:10:21 · #review4-proveit-intake · @review4-prove-it-intake · thread reply · `eaoc3rm1xf8xpphfkkircstscw`

> **Received as R-001.** Your payload will run in an isolated sandbox against PyYAML 5.3.1 when a maintainer asks for it, and the maintainers' decision will be posted in this thread.
> 
> Scope: Prove It checks PyYAML only, comparing 5.3.1 (vulnerable) with 5.4 (patched), through `safe_load`, `full_load`, `load:SafeLoader`, `load:FullLoader`.

### 20:10:23 · #review4-proveit-triage · @review4-prove-it-intake · `jytpgktg4tf3zj3sodib7eizhe`

> **Ticket R-001** · claim `code_execution` · claimed severity `critical` · entry point `full_load` · payload sha256 `75ce42a97f62f51b` (171 bytes) · tags `!!python/object/new:tuple, !!python/object/new:map, !!python/name:eval` · reported: before 5.4, tested: 5.3.1
> The payload is data and only runs inside the sandbox. Nothing the reporter wrote is in this ticket.
> 
> Next: a maintainer asks the Reproducer to run `python -m proveit check R-001` (vulnerable build). The patched build runs only when someone asks: `check R-001 --build patched`.
> The Skeptic then reviews it. Maintainers decide with `escalate R-001` (needs a current concur, or an `override`), `close R-001 <reason>` or `override R-001`, addressed to Intake.

### 20:34:26 · #review4-proveit-triage · @user · `79pa9e1ipjfb5pgouusceqt4hr`

> @review4-prove-it-reproducer  check R-001 again.

### 20:34:49 · #review4-proveit-triage · @review4-prove-it-reproducer · `ob5uskmqnjf7unrf6nakjpx3ow`

> ✅ R-001 check ran (vulnerable build only). Quoting the tool:
> 
> ```
> R-001 vulnerable build: CODE_EXECUTION on PyYAML 5.3.1, 3/3 clean runs (image sha256:d8219ba0f788...)
>   - vulnerable on PyYAML 5.3.1 via full_load: CODE_EXECUTION, 3/3 clean runs
>     (image sha256:d8219ba0f788...); the marker file appeared, so the library ran
>     the payload as code; library frames: constructor.py:make_python_instance <
>     constructor.py:construct_python_object_apply <
>     constructor.py:construct_python_object_new; 0.066 s, 14.8 MB peak
> ticket status: reproduced
> note: the patched build has not been checked yet
> evidence: work/R-001/runs/01-vulnerable.json
> ```
> 
> - Outcome class: **CODE_EXECUTION**
> - Evidence line: vulnerable on PyYAML 5.3.1 via `full_load`, 3/3 clean runs, marker file appeared
> - Ticket status: **reproduced**
> - Evidence file: `work/R-001/runs/01-vulnerable.json`
> 
> What this shows: on the pinned vulnerable build (PyYAML 5.3.1) the `full_load` entry point executed the payload as code — the marker appeared in all 3 runs, through PyYAML's own constructor frames. What it does not show: whether the patched build still does this — the patched build has not been checked yet.

### 20:35:41 · #review4-proveit-triage · @review4-prove-it-skeptic · `w98wynhkhtgp5f1mnyomz7sxrh`

> R-001 review — status **reproduced**; review token `fc2284e2dd86d8bd`.
> 
> a. Entry point allowlisted: checklist says `entry_point_allowlisted            True`; the ticket declares `full_load`, matching `vulnerable_entry_point             full_load`.
> b. Outcome matches claim: `outcome_matches_claim              True`; both claim and recorded outcome are CODE_EXECUTION.
> c. Library evidence supports the result: `library_frames_recorded            True` and `code_execution_proven_by_marker    True`. The evidence records the marker appearing and PyYAML constructor frames; vulnerable runs agreed `3/3 clean runs`.
> d. Patched build: `patched_build_checked              False`. Please have Reproducer run `check R-001 --build patched` before relying on escalation.
> e. Severity: `severity_supported_by_outcome      True`; the recorded CODE_EXECUTION supports the claimed critical severity under the checklist.
> f. Scope: `full_load` is explicitly in scope under the room's scope-policy document, which lists it among the supported entry points.
> 
> @review4-prove-it-intake dispute R-001 patched_not_checked review=fc2284e2dd86d8bd

### 20:35:43 · #review4-proveit-triage · @review4-prove-it-intake · `ohj3seon1jrg5c9n6a3iooth4a`

> R-001: disputed by review4-prove-it-skeptic (patched_not_checked: the patched build has not been checked). Escalation is blocked until a maintainer overrides. Note for maintainers: ask the Reproducer to run `check R-001 --build patched`.

### 20:37:37 · #review4-proveit-triage · @user · `wys45gn8y7y7t8z1q7f3ys43go`

> @review4-prove-it-reproducer check R-001 --build patched

### 20:38:15 · #review4-proveit-triage · @review4-prove-it-reproducer · `cmfyqo364igczntrg1678demqy`

> ✅ R-001 patched-build check ran, same loader (`full_load`) as the vulnerable run. Quoting the tool:
> 
> ```
> R-001 patched build: NOT_REPRODUCED on PyYAML 5.4, 3/3 clean runs (image sha256:00125fc0958b...)
>   - patched on PyYAML 5.4 via full_load: NOT_REPRODUCED, 3/3 clean runs
>     (image sha256:00125fc0958b...); the library call finished without code
>     execution, crash or resource exhaustion; raised ConstructorError
>     (message sha256 5c5d1727eb22...); 0.067 s, 14.4 MB peak
> ticket status: disputed
> evidence: work/R-001/runs/02-patched.json
> ```
> 
> - Outcome class: **NOT_REPRODUCED**
> - Evidence line: patched on PyYAML 5.4 via `full_load`, 3/3 clean runs, raised `ConstructorError` instead of executing
> - Ticket status: **disputed**
> - Evidence file: `work/R-001/runs/02-patched.json`
> 
> What this shows: on PyYAML 5.4 the same `full_load` payload no longer runs as code — all 3 runs ended in a `ConstructorError` with no marker, so the fix holds against this payload via this entry point. What it does not show: nothing about other entry points or payload variants, and the ticket status still reads `disputed` — that's the Skeptic's standing verdict and the maintainers' call, not mine to change.

### 20:38:57 · #review4-proveit-triage · @review4-prove-it-skeptic · `gcziynoe4jgg7nh6yzxc1z9qje`

> R-001 re-review — the previous verdict is stale. Current review token: `f8c01730c4153559`.
> 
> a. Entry point allowlisted: `entry_point_allowlisted            True`; `vulnerable_entry_point             full_load` matches the ticket.
> b. Outcome matches claim: `outcome_matches_claim              True`; the vulnerable outcome is CODE_EXECUTION, matching the claim.
> c. Library evidence supports CODE_EXECUTION: `library_frames_recorded            True` and `code_execution_proven_by_marker    True`; the vulnerable run records the marker and PyYAML constructor frames, with `vulnerable_clean_runs              3/3 clean runs`.
> d. Patched build: `patched_build_checked              True`; `patched_comparable                 True`; `patched_entry_point                full_load`; `patched_outcome                    NOT_REPRODUCED`; `patched_clean_runs                 3/3 clean runs`; `reproduces_on_patched_too          False`.
> e. Severity: `severity_supported_by_outcome      True`; critical is supported by the recorded CODE_EXECUTION outcome.
> f. Scope: `full_load` is in scope under the room's scope-policy document, which explicitly lists it as an entry point that avoids code execution.
> 
> @review4-prove-it-intake concur R-001 review=f8c01730c4153559

### 20:38:59 · #review4-proveit-triage · @review4-prove-it-intake · `3ez5otmdc78y3dryz367ikidzy`

> Refused concur for R-001: cannot concur a ticket that is disputed.

### 20:40:20 · #review4-proveit-triage · @review4-prove-it-skeptic · `z55rjo7xptgepf1z3n7oyko13w`

> R-001 re-review — I re-read the evidence pack; its review token remains `f8c01730c4153559`.
> 
> a. `entry_point_allowlisted            True`; declared `full_load` matches `vulnerable_entry_point             full_load`.
> b. `outcome_matches_claim              True`; vulnerable outcome is CODE_EXECUTION, matching the claim.
> c. `library_frames_recorded            True`; `code_execution_proven_by_marker    True`; vulnerable result is CODE_EXECUTION with `vulnerable_clean_runs              3/3 clean runs`.
> d. `patched_build_checked              True`; `patched_comparable                 True`; patched entry point is `full_load`, outcome is `NOT_REPRODUCED` on `3/3 clean runs`, and `reproduces_on_patched_too          False`.
> e. `severity_supported_by_outcome      True`.
> f. Scope-policy includes `full_load` as in scope.
> 
> I concur with the recorded vulnerable-build result. The evidence pack still reports status disputed and marks the skeptic verdict stale; Intake previously refused concurrence because of that status. The existing dispute must be cleared by a maintainer before escalation can proceed.
> 
> @review4-prove-it-intake concur R-001 review=f8c01730c4153559

### 20:40:22 · #review4-proveit-triage · @review4-prove-it-intake · `xapr7p3uy3dguy48khzyhg7hna`

> Refused concur for R-001: cannot concur a ticket that is disputed.

### 20:43:59 · #review4-proveit-triage · @user · `d7unxiztibbquy6pir4xwcp41h`

> @review4-prove-it-intake override R-001 The patched build was checked with the same full_load payload and did not reproduce in 3/3 runs. I reviewed the updated evidence and Skeptic review.

### 20:44:05 · #review4-proveit-triage · @review4-prove-it-intake · `i359db6cmtnrignc3c1qmm78dy`

> R-001: user overrode the dispute (patched_not_checked); it can now be escalated or closed.

### 20:45:01 · #review4-proveit-triage · @user · `7se8pgho4igrzxudk4cjwgoxuh`

> @review4-prove-it-intake escalate R-001

### 20:45:06 · #review4-proveit-triage · @review4-prove-it-intake · `7ut7hz5jhbgsxdqa3kqwra1zga`

> R-001 escalated by user. Telling the reporter.

### 20:45:08 · #review4-proveit-triage · @review4-prove-it-intake · `pa7wdaej5fn38mhq7adzaiiyia`

> Advisory pack for R-001 (DRAFT, needs maintainer review): work/R-001/advisory/ osv-draft.json, ghsa-draft.md, timeline.md

### 20:45:11 · #review4-proveit-intake · @review4-prove-it-intake · thread reply · `rkycri36ainwbjknyhp957ntow`

> **R-001 confirmed by a maintainer.** It reproduced in the sandbox: CODE_EXECUTION on PyYAML 5.3.1 via `full_load`, 3/3 clean runs.
> 
> On the patched PyYAML 5.4, through the same entry point on the same payload, the outcome was NOT_REPRODUCED (3/3 clean runs).
> 
> _Cost so far: 6 sandbox runs (0.40 s of sandbox time); 2086 s from triage to decision (elapsed time, not effort); agent cost not recorded._

## sqlparse R-004 (review4-sqlparse-*)

### 21:02:33 · #review4-sqlparse-intake · @reporter_test · thread reply · `9rao7xekspr38d557qi4t9c8be`

> @review4-prove-it-intake affected_version: 0.4.3
> entry_point: parse
> payload:
> ```sql
> '\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
> ```
> expected: parse returns quickly
> actual: parse hangs, pinning a CPU

### 21:02:39 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `pumi1y8fufg5um5p6qur8qmcja`

> **Received as R-004.** Your payload will run in an isolated sandbox against sqlparse 0.4.3 when a maintainer asks for it, and the maintainers' decision will be posted in this thread.
> 
> Scope: Prove It checks sqlparse only, comparing 0.4.3 (vulnerable) with 0.4.4 (patched), through `parse`, `format`, `split`.

### 21:02:41 · #review4-sqlparse-triage · @review4-prove-it-intake · `tf4dgd4s57fzxpg8wtbhhc4gby`

> **Ticket R-004** · claim `denial_of_service` · claimed severity `unrated` · entry point `parse` · payload sha256 `5bbd4e474a2414a5` (44 bytes) · tags `none` · reported version 0.4.3, tested 0.4.3
> The payload is data and only runs inside the sandbox. Nothing the reporter wrote is in this ticket.
> 
> Next: a maintainer asks the Reproducer to run `python -m proveit check R-004` (vulnerable build). The patched build runs only when someone asks: `check R-004 --build patched`.
> The Skeptic then reviews it. Maintainers decide with `escalate R-004` (needs a current concur, or an `override`), `close R-004 <reason>` or `override R-004`, addressed to Intake.

### 21:03:52 · #review4-sqlparse-triage · @user · `htkiinqqm7bi3cpxecphmygnta`

> @review4-prove-it-reproducer  check R-004

### 21:04:44 · #review4-sqlparse-triage · @review4-prove-it-reproducer · `e5py6na6qj8z5kkhcx6wpj1k8c`

> **R-004** — vulnerable build, sqlparse 0.4.3 via `parse`
> - **Outcome:** `RESOURCE_EXHAUSTION`, 3/3 clean runs (image sha256:223e1f6d9580...)
> - **Evidence:** "the library call ran past the 10 s limit, busy on the CPU; 10.005 s, 14.1 MB peak"
> - **Status:** `reproduced`
> - **Evidence file:** `work/R-004/runs/01-vulnerable.json`
> 
> The 44-byte payload kept sqlparse 0.4.3's `parse` busy on the CPU past the 10 s limit in all three sandbox runs, with low memory use. That fits the `denial_of_service` claim. It does not show the patched build is fixed, since that hasn't been run yet, and it doesn't show whether the parse would ever finish or how cost grows with input size.
> 
> (Side note: the earlier "check R-001" was addressed to "Prove It Reproducer", which didn't reach me. Ask again if you want it run.)

### 21:05:59 · #review4-sqlparse-triage · @review4-prove-it-skeptic · `foqyhgc7hjbuxyebnr6mhs8p9c`

> @review4-prove-it-intake R-004 review (recorded status: reproduced)
> 
> a. Entry point allowlist: `entry_point_allowlisted True`; `vulnerable_entry_point parse`. The declared `parse` entry point is allowlisted.
> b. Claim match: `outcome_matches_claim True`. The recorded `RESOURCE_EXHAUSTION` is consistent with the `denial_of_service` claim.
> c. Library/outcome evidence: `vulnerable_outcome RESOURCE_EXHAUSTION`; `vulnerable_clean_runs 3/3 clean runs`; `vulnerable_runs_agree True`. The recorded call exceeded the 10 s limit while CPU-busy (10.005 s, 14.1 MB peak), supporting the resource-exhaustion result.
> d. Patched build: `patched_build_checked False`; `patched_run_present False`. Please have the Reproducer run `check R-004 --build patched`.
> e. Severity: `claimed_severity unrated`; `severity_supported_by_outcome unknown`. No severity is claimed, so support cannot be affirmed or called overclaimed.
> f. Scope: in scope. The scope-policy says “In scope: parse, format, split (the documented top-level API)”; this report uses `parse`.
> 
> @review4-prove-it-intake dispute R-004 patched_not_checked review=e933b82cf46b0783 patched build not checked; request Reproducer check it.

### 21:06:01 · #review4-sqlparse-triage · @review4-prove-it-intake · `gx5tjxetx7nxfybg3qz3paxp9h`

> R-004: disputed by review4-prove-it-skeptic (patched_not_checked: the patched build has not been checked). Escalation is blocked until a maintainer overrides. Note for maintainers: ask the Reproducer to run `check R-004 --build patched`.
> Skeptic's note (triage only, never sent to the reporter): patched build not checked; request Reproducer check it.

### 21:06:10 · #review4-sqlparse-triage · @user · `61wahhjou7n7b8w3edf6bpw94r`

> @review4-prove-it-reproducer  check R-004 --build patched

### 21:06:33 · #review4-sqlparse-triage · @review4-prove-it-reproducer · `8pothgw1ktn6fexz4y3pigau3e`

> **R-004**: patched build, sqlparse 0.4.4 via `parse` (same entry point as the vulnerable run)
> - **Outcome:** `NOT_REPRODUCED`, 3/3 clean runs (image sha256:e597bc2dcbc4...)
> - **Evidence:** "the library call finished without code execution, crash or resource exhaustion; 0.066 s, 14.0 MB peak"
> - **Status:** `disputed`
> - **Evidence file:** `work/R-004/runs/02-patched.json`
> 
> The same payload that ran past 10 s on 0.4.3 finishes in 0.066 s on 0.4.4, so the hang is specific to the vulnerable build and the patch removes it for this input. The status still says `disputed` because the Skeptic's earlier `patched_not_checked` dispute stands until it re-reviews; this run alone doesn't change the status.

### 21:07:11 · #review4-sqlparse-triage · @review4-prove-it-intake · `wgaw1w1s6bn6tkdomonqm6yhqh`

> Refused concur for R-004: cannot concur a ticket that is disputed.

### 21:08:08 · #review4-sqlparse-triage · @review4-prove-it-intake · `a8j1tkb9ubdh5f6bzzjodrsmpe`

> Refused concur for R-004: cannot concur a ticket that is disputed.

### 21:09:57 · #review4-sqlparse-triage · @user · `udxx899517dfffbaahs8jow18w`

> @review4-prove-it-intake override R-004 The patched build was checked through the same parse entry point and did not reproduce in 3/3 runs. I reviewed the updated evidence and Skeptic review.

### 21:10:02 · #review4-sqlparse-triage · @review4-prove-it-intake · `h4n68ij8ujb17c6i5ej13aw86c`

> R-004: user overrode the dispute (patched_not_checked); it can now be escalated or closed.

### 21:10:16 · #review4-sqlparse-triage · @user · `48azc48jxbfipmq5ygkxugy99a`

> @review4-prove-it-intake escalate R-004

### 21:10:21 · #review4-sqlparse-triage · @review4-prove-it-intake · `oo8wz61cibgruew6rbmw8h8mwh`

> R-004 escalated by user. Telling the reporter.

### 21:10:26 · #review4-sqlparse-triage · @review4-prove-it-intake · `iwerxqa7itfw9yxh8ke7bu4s1e`

> Advisory pack for R-004 (DRAFT, needs maintainer review): work/R-004/advisory/ osv-draft.json, ghsa-draft.md, timeline.md

### 21:10:23 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `1s31h19b8td9xmyqqnirg8fyga`

> **R-004 confirmed by a maintainer.** It reproduced in the sandbox: RESOURCE_EXHAUSTION on sqlparse 0.4.3 via `parse`, 3/3 clean runs.
> 
> On the patched sqlparse 0.4.4, through the same entry point on the same payload, the outcome was NOT_REPRODUCED (3/3 clean runs).
> 
> _Cost so far: 6 sandbox runs (30.18 s of sandbox time); 463 s from triage to decision (elapsed time, not effort); agent cost not recorded._

## Non-reproduction R-006 / R-007

### 21:23:47 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `j55kk3byr7f9dm8sszsm3g1d7c`

> **Received as R-006.** Your payload will run in an isolated sandbox against sqlparse 0.4.3 when a maintainer asks for it, and the maintainers' decision will be posted in this thread.
> 
> Scope: Prove It checks sqlparse only, comparing 0.4.3 (vulnerable) with 0.4.4 (patched), through `parse`, `format`, `split`.

### 21:25:28 · #review4-sqlparse-triage · @review4-prove-it-reproducer · `3kcggic6dtru3qqaq44jexhnda`

> **R-006**: vulnerable build, sqlparse 0.4.3 via `parse`
> - **Outcome:** `NOT_REPRODUCED`, 3/3 clean runs (image sha256:223e1f6d9580...)
> - **Evidence:** "the library call finished without code execution, crash or resource exhaustion; 0.067 s, 14.0 MB peak"
> - **Status:** `not_reproduced`
> - **Evidence file:** `work/R-006/runs/01-vulnerable.json`
> 
> On the build the reporter named, the 10-byte payload made `parse` finish normally in 0.067 s in all three runs, so the sandbox found no evidence of the claimed denial of service. This covers only the `parse` entry point on 0.4.3 under the 10 s limit. No other entry point has been tried, and the patched build hasn't been run, though it matters little when the vulnerable build doesn't reproduce.

### 21:25:59 · #review4-sqlparse-triage · @review4-prove-it-intake · `mb7hc57433895qah1xrusbbtrr`

> R-006: review4-prove-it-skeptic concurs with the evidence; status not reproduced.

### 21:26:28 · #review4-sqlparse-triage · @user · `kx743gohop8kmrcoim8obh3y7o`

> @review4-prove-it-intake close R-006 Synthetic reporter-limit test; it did not reproduce.

### 21:26:34 · #review4-sqlparse-triage · @review4-prove-it-intake · `rrymbeunsibi8ct81t8ybd7qma`

> R-006 closed by user. Telling the reporter with the question for not_reproduced.

### 21:26:36 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `ceughw5n1irjpbhixhq6sakpbc`

> **R-006 closed by a maintainer.**
> 
> It did not reproduce in the sandbox: NOT_REPRODUCED on sqlparse 0.4.3, 3/3 clean runs (the library call finished without code execution, crash or resource exhaustion).
> 
> Question from the maintainers: The sandbox did not reproduce this on sqlparse 0.4.3. Which exact input and entry point trigger it?
> 
> Maintainer's note: Synthetic reporter-limit test; it did not reproduce.
> 
> _Cost so far: 3 sandbox runs (0.20 s of sandbox time); 167 s from triage to decision (elapsed time, not effort); agent cost not recorded._

### 21:27:39 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `yhuuc87ci38bmrkjoc8od1eydo`

> **Received as R-007.** Your payload will run in an isolated sandbox against sqlparse 0.4.3 when a maintainer asks for it, and the maintainers' decision will be posted in this thread.
> 
> Scope: Prove It checks sqlparse only, comparing 0.4.3 (vulnerable) with 0.4.4 (patched), through `parse`, `format`, `split`.

### 21:28:45 · #review4-sqlparse-triage · @review4-prove-it-reproducer · `8ccqc7icktnfdrc1yrz4bisr5o`

> **R-007**: vulnerable build, sqlparse 0.4.3 via `parse`
> - **Outcome:** `NOT_REPRODUCED`, 3/3 clean runs (image sha256:223e1f6d9580...)
> - **Evidence:** "the library call finished without code execution, crash or resource exhaustion; 0.066 s, 14.1 MB peak"
> - **Status:** `not_reproduced`
> - **Evidence file:** `work/R-007/runs/01-vulnerable.json`
> 
> On the build the reporter named, the 10-byte payload made `parse` finish normally in 0.066 s in all three runs, so the sandbox found no evidence of the claimed low-severity denial of service. This covers only the `parse` entry point on 0.4.3 under the 10 s limit. No other entry point has been tried, and the patched build hasn't been run.

### 21:29:14 · #review4-sqlparse-triage · @review4-prove-it-intake · `nwb59eyhep8z5f5mxknjzha7ze`

> R-007: review4-prove-it-skeptic concurs with the evidence; status not reproduced.

### 21:29:28 · #review4-sqlparse-triage · @user · `kd9k6yzffpf6udrgaskd4jyy1a`

> @review4-prove-it-intake close R-007 Synthetic reporter-limit test; it did not reproduce.

### 21:29:34 · #review4-sqlparse-triage · @review4-prove-it-intake · `urbxbbhcqbnb7jetwq8nipgb7h`

> R-007 closed by user. Telling the reporter with the question for not_reproduced.

### 21:29:36 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `g5ahgwszqtyd5kx7su18pw9pmw`

> **R-007 closed by a maintainer.**
> 
> It did not reproduce in the sandbox: NOT_REPRODUCED on sqlparse 0.4.3, 3/3 clean runs (the library call finished without code execution, crash or resource exhaustion).
> 
> Question from the maintainers: The sandbox did not reproduce this on sqlparse 0.4.3. Which exact input and entry point trigger it?
> 
> Maintainer's note: Synthetic reporter-limit test; it did not reproduce.
> 
> _Cost so far: 3 sandbox runs (0.20 s of sandbox time); 114 s from triage to decision (elapsed time, not effort); agent cost not recorded._

## Reporter limit, reset, R-008

### 21:31:18 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `ufhc66t4wbgpi8se7auoib4yxy`

> You already have an open report (R-002) that is waiting for a valid proof. You can fix it by replying in its thread, or post this again once it is closed. A maintainer can lift this limit.

### 21:31:20 · #review4-sqlparse-triage · @review4-prove-it-intake · `4mhm6xh6hpfkjgo856x5jksowo`

> Reporter d89081282a9e is limited to one open report (2 proofs did not reproduce). A maintainer can lift it with: python -m proveit clear-reporter d89081282a9e

### 21:34:27 · #review4-sqlparse-triage · @user · `cednhjcwgigq9xrhexutzqkq7o`

> @review4-prove-it-intake clear-reporter d89081282a9e
> 

### 21:34:33 · #review4-sqlparse-triage · @review4-prove-it-intake · `8bkbfkw3kp8qdgxhxy3snwxgac`

> Reporter d89081282a9e: limit lifted by user (invalid count reset to 0).

### 21:39:28 · #review4-sqlparse-intake · @review4-prove-it-intake · thread reply · `nod5s37pttrqietzxcu9akag6h`

> **Received as R-008.** Your payload will run in an isolated sandbox against sqlparse 0.4.3 when a maintainer asks for it, and the maintainers' decision will be posted in this thread.
> 
> Scope: Prove It checks sqlparse only, comparing 0.4.3 (vulnerable) with 0.4.4 (patched), through `parse`, `format`, `split`.
