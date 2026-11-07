"""Build stills (HTML -> PNG via Playwright/Edge) and the timeline for the Prove It demo video."""
import json, html
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SH = (HERE / "shots").as_uri() + "/"
FR = HERE / "frames"; FR.mkdir(exist_ok=True)
SEG = json.loads((HERE / "audio" / "segments.json").read_text(encoding="utf-8"))
LEAD = 0.5
TAIL = {1: 2.5, 2: 1.5, 3: 2.5, 4: 3.5, 5: 3.5, 6: 3.0, 7: 3.0, 8: 4.5}
CHAPTERS = [("Problem", [1, 2]), ("How", [3]), ("Slop", [4]), ("Real bug", [5]), ("Attack", [6]), ("Impact", [7, 8])]
ACC = "#f5b942"

def esc(s): return html.escape(s)

def img(name, w, crop=None, label=None, hl=False):
    style = f"width:{w}px;" + (f"height:{crop}px;overflow:hidden;" if crop else "")
    lab = f'<div class="lab">{esc(label)}</div>' if label else ""
    return f'<div class="shot{" hl" if hl else ""}" style="{style}">{lab}<img src="{SH}{name}_post.png" style="width:{w}px"></div>'

def footage(room, imgs, chips=(), replay=None, layout="col"):
    rp = f'<span class="replay">{esc(replay)}</span>' if replay else ""
    ch = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)
    return (f'<div class="foot"><div class="roomhdr"><span class="room">{esc(room)}</span>'
            f'<span class="src">real post · live run 2026-11-06 IST · Switch Console 0.40.1</span>{rp}</div>'
            f'<div class="imgs {layout}">{"".join(imgs)}</div><div class="chips">{ch}</div></div>')

def card(inner): return f'<div class="card">{inner}</div>'

def term(title, lines):
    body = "".join(f"<div>{esc(l)}</div>" for l in lines)
    return f'<div class="term"><div class="thdr">{esc(title)}</div><div class="tbody">{body}</div></div>'

HOOK1 = '<div class="big">Writing a fake bug report takes AI <b>10 seconds</b>.</div>'
HOOK2 = HOOK1 + '<div class="big">Checking it takes a maintainer <b>an hour</b>.</div><div class="fine">Measured elsewhere: a senior engineer spends 30–60 minutes on a typical report (Elastic Security Labs, 2026-08-04)</div>'
def heads(n):
    hs = [("curl ends its bug bounty", "January 2026", "theregister.com/2026/01/21/curl_ends_bug_bounty"),
          ("curl stops accepting security reports for July", "2026", "curl.se/dev/security.html"),
          ("HackerOne pauses its Internet Bug Bounty payouts", "2026", "csoonline.com/article/4154216")]
    return '<div class="heads">' + "".join(f'<div class="head"><div class="ht">{esc(a)}</div><div class="hd">{esc(b)}</div><div class="hs">Source: {esc(c)}</div></div>' for a, b, c in hs[:n]) + "</div>"

TITLE = ('<div class="title">Prove It</div><div class="sub">AI spam is drowning open source. Prove It makes the AI prove its bug report before a human reads it.</div>'
         '<div class="built">Built on <b>Switch</b> · Team Pikachu · Flip the Switch hackathon</div>')

def diagram(step):
    on = lambda k: " on" if k <= step else ""
    return f'''<div class="diag">
 <div class="rm{on(0)}"><div class="rt">#proveit-intake</div><div class="rd">public · outsiders post reports</div><div class="who">Reporter</div></div>
 <div class="link{on(1)}"><div class="ag">Intake<br><small>our Python agent · Switch agent protocol · no LLM</small></div><div class="arr">linked rooms ⟷</div></div>
 <div class="rm{on(2)}"><div class="rt">#proveit-triage</div><div class="rd">private · maintainers + agents</div>
   <div class="who">Reproducer <small>Claude Code</small></div><div class="who">Skeptic <small>Codex</small></div><div class="who">Maintainer <small>decides</small></div></div>
</div>
<div class="motto">{"".join(f'<span class="m{on(k)}">{t}</span>' for k, t in [(3, "Code decides."), (4, "Agents argue."), (5, "Humans rule.")])}</div>'''

VENDORS = term("live run log, 2026-11-06 15:20–15:46 IST (docs/evidence/live-trust-2026-11-06-windows.log)",
               ["# Reproducer: Claude Code 2.1.318; Skeptic: Codex 0.166.0;", "# managed agents on this computer, Bypass permissions off."])

I, T = "#proveit-intake", "#proveit-triage"
R02, R01, R04 = "Replayed report · synthetic slop", "Replayed report · public CVE-2020-14343", "Replayed report · attack written by our team"
VIS = {
 1: [card(HOOK1), card(HOOK2), card(heads(2)), card(heads(3))],
 2: [card(TITLE)] * 3,
 3: [card(diagram(0)), card(diagram(1)), card(diagram(2) + VENDORS), card(diagram(3)), card(diagram(4)), card(diagram(5))],
 4: [footage(I, [img("i_02_report", 1500, crop=600, hl=True, label="The report: no proof")], ["Room: #proveit-intake"], R02),
     footage(I, [img("i_02_askproof", 900, crop=640, hl=True, label="Intake asks for a data-only proof")], ["Custom agent over Switch's agent protocol", "Thread reply"], R02),
     footage(T, [img("i_02_proof", 760, crop=250, label="Reporter's proof, in the #proveit-intake thread"), img("t_02_ticket", 1720, hl=True, label="Fixed-field ticket, posted by Intake in #proveit-triage")], ["Linked rooms: intake → triage"], R02),
     footage(T, [img("t_02_check", 1500, label="Maintainer"), img("t_02_result", 1500, hl=True, label="Reproducer · Claude Code")], ["Claude Code in the room"], R02),
     footage(T, [img("t_02_concur", 1500, crop=300, hl=True, label="Skeptic · Codex"), img("t_02_concur_intake", 1500), img("t_02_close", 1500, label="Maintainer closes")], ["Codex in the room", "Room document: verdict-rules"], R02),
     footage(I, [img("i_02_closed", 960, hl=True, label="What the reporter is told")], ["Reply in the reporter's thread"], R02)],
 5: [footage(I, [img("i_01_report", 1500, crop=560, hl=True, label="The report")], ["Room: #proveit-intake"], R01),
     footage(I, [img("i_01_confirmed", 960, crop=250, hl=True, label="Recorded result, PyYAML 5.3.1 (same run)")], ["Sandbox: no network"], R01),
     footage(T, [img("t_01_ticket", 1500), img("t_01_dispute", 1500, hl=True, label="Skeptic disputes · escalation blocked")], ["Codex in the room"], R01),
     footage(T, [img("t_01_patchedcmd", 1500, label="Maintainer steers"), img("t_01_patched", 1500, hl=True, label="Reproducer · patched PyYAML 5.4")], ["Claude Code in the room"], R01),
     footage(T, [img("t_01_patched", 1500, crop=150, hl=True, label="NOT_REPRODUCED on 5.4")], ["Same payload, same loader"], R01),
     footage(T, [img("t_01_override", 1500, label="Maintainer overrides"), img("t_01_escalate", 1500, label="Maintainer escalates"), img("i_01_confirmed", 900, crop=330, hl=True, label="Reporter told, with both results")], ["Humans rule"], R01)],
 6: [footage(I, [img("i_04_report", 1500, hl=True, label="Hidden instructions for AI reviewers")], ["Room: #proveit-intake"], R04),
     footage(I, [img("i_04_blocked", 1000, hl=True, label="Switch's reply in the thread"),
                 term("live run log, Switch server, 2026-11-06 (policy id redacted)", ["2026-11-06T15:36:30 [BRIDGE-IN] message from user not relayed —", "Switch Trust outcome=blocked (policy=<redacted>)"])], ["Switch Trust"], R04),
     card('<div class="big">Even if it got through:</div><div class="list"><div>Sandbox with <b>no network</b> and <b>no secrets</b></div><div>Agents never see reporter text, only fixed fields</div></div>')],
 7: [card('<div class="num"><b>532 s</b> and <b>582 s</b></div><div class="numl">from triage to a maintainer\'s decision, per report<br><small>live tally, 2026-11-06 (elapsed time, not effort; agent cost not recorded)</small></div>' + img("t_tally", 1500)),
     card('<div class="num"><b>30–60 min</b></div><div class="numl">a senior engineer on a typical report · 1,390+ reports in H1 2026<br><small>Elastic Security Labs, 2026-08-04 · elastic.co/security-labs/ai-vulnerability-triage-bug-bounty-hackerone</small></div>'),
     card('<div class="title2">We don\'t detect AI.</div>'), card('<div class="title2">We don\'t detect AI.<br><b>We require proof.</b></div>')],
 8: [card('<div class="grid">' + "".join(f'<div>{t}</div>' for t in ["Rooms", "Linked rooms", "Custom agent<br><small>agent protocol</small>", "Claude Code + Codex<br><small>in one room</small>", "Switch Trust", "Room document", "Template YAML", "Private triage room"]) + '</div><div class="fine">Switch features used in this live run</div>'),
     card('<div class="title">Prove It</div><div class="sub">Make the AI prove its bug report before a human reads it.</div><div class="built">github.com/akhilll0305/team-pikachu-switch-ai</div>'),
     card('<div class="title">Prove It</div><div class="built big2">Built on <b>Switch</b></div><div class="built">github.com/akhilll0305/team-pikachu-switch-ai</div>')],
}

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}} body{{width:1920px;height:1080px;background:#0b0f17;color:#e8edf5;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden;position:relative}}
.prog{{position:absolute;top:0;left:0;right:0;height:54px;display:flex;background:#070a10}}
.prog div{{flex:1;text-align:center;font-size:20px;line-height:46px;color:#6b7686;border-right:1px solid #1a2230;letter-spacing:.5px}}
.prog div.cur{{color:{ACC};font-weight:600}} .bar{{position:absolute;top:50px;left:0;height:4px;background:{ACC}}}
.main{{position:absolute;top:70px;left:0;right:0;height:790px;display:flex;align-items:center;justify-content:center}}
.cap{{position:absolute;bottom:0;left:0;right:0;height:200px;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center;padding:0 140px;text-align:center;font-size:38px;line-height:1.3;color:#fff;font-weight:500}}
.card{{text-align:center;max-width:1700px}} .big{{font-size:72px;font-weight:600;margin:18px 0}} .big b{{color:{ACC}}}
.fine{{font-size:24px;color:#8b96a8;margin-top:30px}}
.heads{{display:flex;gap:36px;justify-content:center}} .head{{width:520px;background:#121a28;border:1px solid #27324a;border-top:6px solid {ACC};border-radius:14px;padding:34px;text-align:left}}
.ht{{font-size:40px;font-weight:700;line-height:1.2}} .hd{{font-size:32px;color:{ACC};margin-top:16px}} .hs{{font-size:20px;color:#7d889a;margin-top:22px}}
.title{{font-size:150px;font-weight:800;color:{ACC};letter-spacing:-2px}} .title2{{font-size:96px;font-weight:700}} .title2 b{{color:{ACC}}}
.sub{{font-size:46px;max-width:1400px;margin:20px auto;line-height:1.3}} .built{{font-size:34px;color:#a9b4c6;margin-top:30px}} .built b{{color:#fff}} .big2{{font-size:56px}}
.diag{{display:flex;align-items:center;gap:30px;justify-content:center}} .rm{{width:560px;min-height:420px;border:3px solid #2a3550;border-radius:18px;padding:30px;opacity:.35;transition:none}}
.rm.on,.link.on{{opacity:1}} .rm.on{{border-color:{ACC}}} .rt{{font-size:44px;font-weight:700;font-family:Consolas,monospace}} .rd{{font-size:28px;color:#9aa5b8;margin:10px 0 24px}}
.who{{font-size:34px;background:#162033;border-radius:10px;padding:12px 18px;margin:12px 0;text-align:left}} .who small{{color:{ACC};font-size:26px;margin-left:10px}}
.link{{opacity:.35;text-align:center;width:420px}} .ag{{font-size:40px;font-weight:700;background:#1d2a42;border:3px solid {ACC};border-radius:16px;padding:22px}} .ag small{{font-size:24px;font-weight:400;color:#c5cfdf}}
.arr{{font-size:32px;color:{ACC};margin-top:18px}} .motto{{margin-top:40px;font-size:64px;font-weight:700;text-align:center}} .motto span{{margin:0 22px;opacity:0}} .motto span.on{{opacity:1}}
.term{{margin:36px auto 0;max-width:1500px;background:#05070b;border:1px solid #2a3550;border-radius:12px;text-align:left;font-family:Consolas,monospace}}
.thdr{{font-size:20px;color:#8b96a8;padding:10px 18px;border-bottom:1px solid #1d2638}} .tbody{{font-size:30px;color:#9fe3a8;padding:18px 22px;line-height:1.45}}
.foot{{width:1760px;display:flex;flex-direction:column;align-items:center}} .roomhdr{{width:100%;display:flex;align-items:center;gap:22px;margin-bottom:18px}}
.room{{font-family:Consolas,monospace;font-size:36px;font-weight:700}} .src{{font-size:22px;color:#7d889a}} .replay{{margin-left:auto;background:#3a1d1d;color:#ffb4a8;border:2px solid #ff7a66;border-radius:30px;padding:6px 20px;font-size:26px;font-weight:600}}
.imgs{{display:flex;flex-direction:column;gap:14px;align-items:center}} .imgs.row{{flex-direction:row;align-items:flex-start;gap:30px}}
.shot{{position:relative;margin-top:30px;border:2px solid #222b3c;border-radius:10px;background:#1e1e1e}} .shot img{{display:block}} .shot.hl{{border:4px solid {ACC};box-shadow:0 0 40px rgba(245,185,66,.25)}}
.lab{{position:absolute;top:-38px;left:18px;background:{ACC};color:#111;font-size:22px;font-weight:700;padding:4px 14px;border-radius:8px;z-index:2}}
.chips{{margin-top:22px;display:flex;gap:16px}} .chip{{background:#11253a;border:2px solid #3a8fd6;color:#cfe6ff;font-size:26px;padding:8px 20px;border-radius:30px}}
.num{{font-size:110px;font-weight:800}} .num b{{color:{ACC}}} .numl{{font-size:36px;margin:10px 0 30px;line-height:1.35}} .numl small{{font-size:22px;color:#8b96a8}}
.list{{font-size:46px;line-height:1.7;margin-top:20px}} .list b{{color:{ACC}}}
.grid{{display:grid;grid-template-columns:repeat(4,380px);gap:26px;justify-content:center}} .grid div{{background:#121a28;border:2px solid {ACC};border-radius:16px;padding:34px 10px;font-size:36px;font-weight:700}} .grid small{{font-size:22px;color:#9aa5b8;font-weight:400}}
"""

def build():
    # timeline
    t, stills, scenes, audio = 0.0, [], [], []
    for n in range(1, 9):
        s = SEG[str(n)]; L = LEAD + s["dur"] + TAIL[n]
        audio.append({"n": n, "at": t + LEAD})
        starts = [0.0] + [LEAD + x["start"] for x in s["sents"][1:]]
        vis = VIS[n]; assert len(vis) == len(s["sents"]), (n, len(vis), len(s["sents"]))
        for i, st in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else L
            stills.append({"scene": n, "i": i, "t0": t + st, "dur": end - st, "cap": s["sents"][i]["text"], "html": vis[i]})
        scenes.append({"n": n, "t0": t, "dur": L}); t += L
    total = t
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for k, s in enumerate(stills):
            cur = next(ci for ci, (_, ns) in enumerate(CHAPTERS) if s["scene"] in ns)
            prog = "".join(f'<div class="{"cur" if ci == cur else ""}">{c}</div>' for ci, (c, _) in enumerate(CHAPTERS))
            pct = 100 * (s["t0"] + s["dur"] / 2) / total
            doc = f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="prog">{prog}</div><div class="bar" style="width:{pct:.1f}%"></div><div class="main">{s["html"]}</div><div class="cap">{esc(s["cap"])}</div></body></html>'
            f = FR / f"f{k:03d}.html"; f.write_text(doc, encoding="utf-8")
            pg.goto(f.as_uri()); pg.wait_for_timeout(150)
            pg.screenshot(path=str(FR / f"f{k:03d}.png"))
            s["png"] = str(FR / f"f{k:03d}.png"); s.pop("html")
        b.close()
    (HERE / "timeline.json").write_text(json.dumps({"total": total, "stills": stills, "scenes": scenes, "audio": audio}, indent=1), encoding="utf-8")
    print("stills", len(stills), "total", round(total, 1))
    for sc in scenes: print("scene", sc["n"], round(sc["t0"], 1), round(sc["dur"], 1))

build()
