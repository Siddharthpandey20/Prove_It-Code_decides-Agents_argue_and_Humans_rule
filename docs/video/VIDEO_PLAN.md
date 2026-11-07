# Demo video: audit, edit plan and evidence notes (2026-11-07)

## Files

| File | What it is |
| --- | --- |
| `docs/video/out/prove-it-demo-v2.mp4` | **Final.** 2:51.7, 1920×1080, 30 fps, H.264, AAC stereo, −16.8 LUFS |
| `docs/video/out/prove-it-demo-v1.mp4` | Backup of v1: 2:50, footage from main's live run on 2026-11-06 |
| `docs/video/out/thumbnail.png` | Thumbnail, 1280×720 |
| `docs/video/VOICEOVER.md` | v2 script; v1 is kept in `VOICEOVER-v1.md` |
| `docs/video/src/` | Build scripts |

The build scripts in `docs/video/src/`:
- `capture.py` / `capture4.py`: screenshots of real Mattermost posts
- `tts.py`: narration
- `compose.py` / `compose2.py`: the stills
- `sfx.py`: synthesized music and sound effects
- `render.py` / `render2.py`: the final render

## 1. Audit of v1

| v1 time | Shows / says | Verdict |
| --- | --- | --- |
| 0:00–0:18 | Hook text, then the curl / HackerOne cards | Keep the cards; replace the hook with the maintainer's inbox |
| 0:18–0:29 | Title card | Too early, before the problem lands; move to 0:29 as the reveal |
| 0:29–0:51 | Room diagram, vendors log line | Tighten into one diagram beat at the start of the demo |
| 0:51–1:22 | R-002 slop flow (main, 2026-11-06) | Replace with the review4 rejections (R-006/R-007) and the reporter limit |
| 1:22–1:53 | R-001 flow (main, 2026-11-06) | Replace with review4 R-001: 3/3 runs, refused concur, override, advisory |
| 1:53–2:13 | Attack blocked by Switch Trust | Cut. Trust results apply only to the historical regex-only policy; no review4 evidence |
| 2:13–2:32 | 532 s / 582 s, Elastic figures | Replace. Elapsed time is not effort, and there's no measured baseline |
| 2:32–2:50 | Feature grid, close | Rework into the "Why Switch" section and a close with a hit |

**Silences in v1:** `silencedetect=noise=-35dB:d=0.4` found **42 gaps** over 0.4 s. v1 had no music bed, and each scene ended with a 1.5–4.5 s silent tail.

## 2. v2 structure

Stills and the timeline come from `compose2.py`; the times below are scene starts.

| Time | Section | Content |
| --- | --- | --- |
| 0:00 | Hook | A maintainer's inbox filling with "CRITICAL" reports (titles from our synthetic fixtures, labelled synthetic), then "up to an hour each" (Elastic, cited) |
| 0:11.6 | Problem | curl and HackerOne cards (cited); why a chatbot fails: it reads the same text and can be talked into agreeing |
| 0:29.1 | Reveal | The "Prove It" title and the one-liner, a riser and a hit, "Built on Switch", then "We don't detect AI. We require proof." The one deliberate beat comes after this section. |
| 0:43.2 | Live demo, PyYAML R-001 (review4) | Diagram → report → ticket → Reproducer 3/3 CODE_EXECUTION → Skeptic dispute → patched 5.4 3/3 NOT_REPRODUCED → Intake refuses the concur → maintainer overrides and escalates → reporter told, plus a `ghsa-draft.md` excerpt |
| 1:31.7 | Second room, sqlparse R-004 | Same agents; 0.4.3 RESOURCE_EXHAUSTION 3/3, 0.4.4 NOT_REPRODUCED 3/3; R-006/R-007 NOT_REPRODUCED 3/3 and closed; reporter limit; clear-reporter; R-008 accepted |
| 2:01.6 | Why Switch | Feature grid building one item at a time, plus the real template excerpt; "Without Switch…"; who does what: Switch / Prove It / Docker |
| 2:29.1 | Impact | 3 fresh containers per build, 6 runs per comparison; 326 tests: 314 passed, 12 skipped |
| 2:43.1 | Close | Prove It, the motto, "Built on Switch, for Flip the Switch", the repo URL, a final hit |

**Audio:**
- Narration: edge-tts `en-US-AndrewMultilingualNeural` at +8% rate, about 160 words a minute. It is generated, not a person.
- Music and sound effects: synthesized in `sfx.py` (a chord pad, a pulse from the reveal on, whooshes, pops, two risers and three hits), so there are no licensing issues. Swap in a licensed track if you have one.
- Ducking: sidechain-compressed under the voice.

## 3. Timestamped technical corrections and added coverage

| v2 time | Correction or addition |
| --- | --- |
| 0:00–0:43 | The idea, the user and the need come first. No jargon before the demo. |
| 0:29 | One-liner on screen and spoken: "a triage room that makes every security report prove itself in a sandbox before a maintainer spends time on it. Built on Switch." |
| 0:43+ | Footage moved from main's 2026-11-06 run to the **review4 managed-agent trial, 2026-11-07**, and labelled that way on every frame |
| ~0:58 | Intake, our Python agent, posts a fixed-field ticket; "reporter prose never reaches the agents" chip |
| ~1:00 | **3/3 fresh-container runs** shown (the v1 footage predated repeats) |
| ~1:10 | Skeptic dispute `patched_not_checked`, shown as Intake's real post |
| ~1:17 | Patched 5.4: NOT_REPRODUCED 3/3. Not presented as clearing the dispute. |
| ~1:21 | **Added:** Intake **refusing** the Skeptic's concur while the dispute stands |
| ~1:27 | **Added:** the maintainer override and escalate (real commands), labelled "THE MAINTAINER STEPS IN" |
| ~1:30 | **Added:** reporter notification plus an excerpt of the real `ghsa-draft.md` showing "DRAFT, needs maintainer review"; labelled local drafts, not published |
| 1:32–1:46 | **Added:** sqlparse second room, same agents, synthetic replay label |
| 1:46–2:01 | **Added:** non-reproduction closes (R-006/R-007) and the reversible reporter limit with clear-reporter; R-008 accepted |
| 2:01–2:29 | **Corrected:** what Switch contributes vs what Prove It and Docker do; "Without Switch" scoped to the team workflow (the CLI and rehearsal still run alone) |
| 2:29–2:43 | **Corrected:** v1's 532 s / 582 s and the Elastic comparison are removed from the impact claim. The test figure is stated as 314 passed, 12 skipped. |
| removed | The Switch Trust attack scene (no review4 evidence; the historical Trust result covers only the regex-only policy) |

## 4. Evidence for each significant claim

| Claim | Evidence |
| --- | --- |
| R-001: 3/3 CODE_EXECUTION on 5.3.1, marker, constructor frames | review4-proveit-triage post `ob5uskmq…` (20:34:49 IST); `timeline.md` row 2026-11-07T15:04:39Z |
| Skeptic dispute `patched_not_checked` | Post `ohj3seon…` (20:35:43) |
| 5.4: 3/3 NOT_REPRODUCED | Post `cmfyqo36…` (20:38:15); timeline row 15:08:04Z |
| Concur refused while disputed | Posts `3ez5otmd…` (20:38:59) and `xapr7p3u…` (20:40:22) |
| Override, escalate | Posts `d7unxizt…`, `i359db6c…`, `7se8pgho…`, `7ut7hz5j…`; timeline rows 15:14:02Z and 15:15:04Z |
| Reporter told | review4-proveit-intake reply `rkycri36…` (20:45:11) |
| Advisory pack | Post `pa7wdaej…`; files `.proveit-trials/review4/work/R-001/advisory/{osv-draft.json, ghsa-draft.md, timeline.md, timeline.json}` (20:45) |
| R-004 sqlparse 0.4.3 RESOURCE_EXHAUSTION 3/3, 0.4.4 NOT_REPRODUCED 3/3 | Posts `e5py6na6…` (21:04:44) and `8pothgw1…` (21:06:33) |
| R-004 override, escalate, advisory, reporter told | Posts `h4n68ij8…`, `oo8wz61c…`, `iwerxqa7…`, `1s31h19b…` |
| R-006/R-007 NOT_REPRODUCED 3/3, concur, closed | Posts `3kcggic6…`, `mb7hc574…`, `rrymbeun…`, `8ccqc7ic…`, `urbxbbhc…` |
| Reporter limit, clear-reporter, R-008 | Posts `ufhc66t4…` (refusal to reporter), `4mhm6xh6…` (limit), `cednhjcw…` (clear), `8bkbfkw3…` (lifted), `nod5s37p…` (R-008 received) |
| Template features | `switch/prove-it.template.yaml` lines 191–207 (rooms), 233/252 (docs), 59–60 and 105–106 (addressing, auto_approve), 272–275 (link) |
| 326 / 314 / 12 | Your statement of the full suite at `7568a4e`. **I did not re-run it.** |
| curl, HackerOne, Elastic | README sources (theregister.com, curl.se, csoonline.com, elastic.co), cited on screen |

## 5. Missing recordings and unverified claims

- **No screen recording of Switch Console.** The setup shot is the template file excerpt; no Console screenshot exists in the evidence.
- **No Wispr Flow** use is documented in the README, so there is no Wispr shot.
- **The maintainer's first `check R-001` command** in review4 was not captured; the Reproducer's result post is shown instead.
- **Not claimed:** every dispute reason, stale-token rejection, a refused escalation while disputed, provider permission limits, reporter attempts at maintainer commands, cross-room throttling, the exact fixed question text received after the close, a Trust red-team score, schema validation of these specific advisory files, and hosted CI on `7568a4e`.
- **No time-saved figure** is shown: there's no measured baseline, and agent cost wasn't recorded.

## 6. Stale documentation statements for the team (README not edited)

These were found by searching `pikachu-lib2` at `7568a4e`. Check each against the review4 evidence above:

| Location | Statement |
| --- | --- |
| `README.md:219` | "its live agent behavior still needs verification" |
| `README.md:292-293` | Scope policy and four-field request are "Verified offline, not yet live" |
| `README.md:312` | "Two targets, but only PyYAML is live" (sqlparse R-004 ran live in review4) |
| `README.md:331-333` | sqlparse "not yet in Switch Console" |
| `context.md:86, 95, 111, 129` | Branch features "verified offline, not yet live" |
| `docs/CHECKPOINT.md:143, 156` | O8/P5 live coverage partial / "not yet live" |
| `docs/DEMO.md:7, 37` | "Needs a live run before recording"; sqlparse "verified offline" |

## 7. Final checks run on v2

| Check | Result |
| --- | --- |
| Duration | 2:51.67 (ffmpeg), under 3:00 |
| Silences | `silencedetect=noise=-35dB:d=0.4` on the full mix: **0 gaps** (v1: 42) |
| Loudness | −16.8 LUFS integrated |
| Captions | Each still and its caption switch at the sentence boundary reported by the TTS engine |
| Frames | Contact sheet of all 43 stills checked; I fixed one overflowing frame (the reporter-limit frame) |
| Tested | Not watched end to end with sound by me. Please do one full watch before uploading. |
