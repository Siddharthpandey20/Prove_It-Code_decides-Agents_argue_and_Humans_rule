"""v2: same visual system as compose.py, new idea-first story and review4 live-trial footage."""
from pathlib import Path
src = (Path(__file__).parent / "compose.py").read_text(encoding="utf-8-sig").rsplit("build()", 1)[0]
exec(src)

LEAD = 0.15
TAIL = {1: 0.3, 2: 0.3, 3: 1.2, 4: 0.3, 5: 0.3, 6: 0.3, 7: 0.3, 8: 1.8}
CHAPTERS = [("Problem", [1, 2]), ("Prove It", [3]), ("Live demo", [4]), ("Second room", [5]), ("Why Switch", [6]), ("Impact", [7, 8])]

def footage(room, imgs, chips=(), replay=None, layout="col", src="real post · live trial review4 · 2026-11-07 · managed agents in Switch Console"):
    rp = f'<span class="replay">{esc(replay)}</span>' if replay else ""
    ch = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)
    return (f'<div class="foot"><div class="roomhdr"><span class="room">{esc(room)}</span><span class="src">{esc(src)}</span>{rp}</div>'
            f'<div class="imgs {layout}">{"".join(imgs)}</div><div class="chips">{ch}</div></div>')

def flood(n):
    titles = ["CRITICAL Remote Code Execution in yaml.safe_load (CVSS 9.8)", "Denial of service via memory exhaustion (billion laughs) in yaml.safe_load",
              "Unsafe deserialization in yaml.full_load", "CRITICAL Remote Code Execution in yaml.safe_load (CVSS 9.8)",
              "Denial of service via memory exhaustion (billion laughs) in yaml.safe_load", "CRITICAL Remote Code Execution in yaml.safe_load (CVSS 9.8)"]
    cards = "".join(f'<div class="fl" style="transform:translate({(i%3-1)*90}px,{i*6}px) rotate({(i%2*2-1)*1.5}deg)"><span class="crit">CRITICAL</span> {esc(t)}<div class="flm">new security report · unverified</div></div>' for i, t in enumerate(titles[:n]))
    return f'<div class="flood">{cards}</div><div class="fine">Synthetic examples, modelled on curl\'s public AI slop reports</div>'

I4, T4, SI, ST = "#review4-proveit-intake", "#review4-proveit-triage", "#review4-sqlparse-intake", "#review4-sqlparse-triage"
RP = "Replayed report · public CVE-2020-14343"
RS = "Synthetic replay · based on CVE-2023-30608"
RN = "Synthetic test reports"
TPL = term("switch/prove-it.template.yaml (excerpt, real file)",
           ["rooms:", "  - name: proveit-intake     # channel_public: anyone may report", "  - name: proveit-triage     # channel_private", "    docs: [verdict-rules, scope-policy]",
            "agents: prove-it-reproducer / prove-it-skeptic", "    addressing: owner-agents   auto_approve: false", "links:", "  - from: proveit-intake  to: proveit-triage  label: triage"])
def sw(step):
    items = [("Mattermost bridge", "chat the team already uses"), ("Linked rooms", "public intake → private triage"), ("Room documents", "scope policy · verdict rules"),
             ("Managed agents", "Claude Code + Codex"), ("One template", "rooms, agents, docs, link"), ("Sender attribution", "only maintainers decide")]
    return '<div class="grid g6">' + "".join(f'<div class="{"on" if k <= step else "off"}">{a}<br><small>{b}</small></div>' for k, (a, b) in enumerate(items)) + '</div>'

VIS = {
 1: [card('<div class="big">You maintain an open-source library.</div>'), card(flood(3)), card(flood(6)),
     card(flood(6) + '<div class="big" style="margin-top:20px">Up to <b>an hour</b> each to disprove.</div><div class="fine">30–60 min per report: Elastic Security Labs, 2026-08-04</div>')],
 2: [card('<div class="big">This is already breaking real programs.</div>'), card(heads(2)), card(heads(3)),
     card('<div class="big">A chatbot won\'t save you.</div>'), card('<div class="big">A chatbot won\'t save you.</div><div class="list"><div>It reads the same convincing text you do.</div><div>It can be <b>talked into agreeing</b>.</div></div>')],
 3: [card('<div class="title">Prove It</div><div class="sub">A triage room that makes every security report <b style="color:#f5b942">prove itself in a sandbox</b> before a maintainer spends time on it.</div>'),
     card('<div class="title">Prove It</div><div class="sub">A triage room that makes every security report <b style="color:#f5b942">prove itself in a sandbox</b> before a maintainer spends time on it.</div><div class="built big2">Built on <b>Switch</b></div>'),
     card('<div class="title2">We don\'t detect AI.</div>'), card('<div class="title2">We don\'t detect AI.<br><b>We require proof.</b></div>')],
 4: [card(diagram(2)),
     footage(I4, [img("r_report", 1500, crop=520, hl=True, label="Reporter posts in the public room")], ["Room: public intake"], RP),
     footage(T4, [img("r_received", 820, crop=150, label="Intake replies in the reporter's thread"), img("r_ticket", 1650, hl=True, label="Intake · fixed-field ticket in private triage")], ["Linked rooms", "Reporter prose never reaches the agents"], RP),
     footage(T4, [img("r_vuln", 1450, crop=430, hl=True, label="REPRODUCER · Claude Code · asked by the maintainer")], ["Managed agent in the room"], RP),
     footage(T4, [img("r_vuln", 1450, crop=430, hl=True, label="REPRODUCER · Claude Code · PyYAML 5.3.1")], ["CODE_EXECUTION · 3/3 fresh containers"], RP),
     footage(T4, [img("r_dispute", 1650, hl=True, label="SKEPTIC · Codex · disputes")], ["patched_not_checked"], RP),
     footage(T4, [img("r_patchcmd", 1500, label="Maintainer"), img("r_patched", 1450, crop=300, hl=True, label="REPRODUCER · Claude Code · PyYAML 5.4")], ["Same payload, same loader"], RP),
     footage(T4, [img("r_patched", 1450, crop=300, hl=True, label="NOT_REPRODUCED · 3/3")], ["The fix holds"], RP),
     footage(T4, [img("r_refused", 1650, hl=True, label="INTAKE refuses the Skeptic's concur")], ["A dispute stands until a human decides"], RP),
     footage(T4, [img("r_overridecmd", 1650, hl=True, label="THE MAINTAINER STEPS IN"), img("r_overrode", 1650), img("r_escalatecmd", 1650), img("r_escalated", 1650)], ["Humans rule"], RP),
     footage(I4, [img("r_confirmed", 820, crop=360, hl=True, label="Reporter told, in their own thread"),
                  term(".proveit-trials/review4/work/R-001/advisory/ghsa-draft.md (real file, excerpt)", ["DRAFT, needs maintainer review", "# DRAFT: code execution in PyYAML via full_load", "- Tested vulnerable build, PyYAML 5.3.1: CODE_EXECUTION, 3/3 clean runs", "- Patched build, PyYAML 5.4: NOT_REPRODUCED, 3/3 clean runs", "No fixed version is claimed.", "+ osv-draft.json · timeline.md · timeline.json   (local drafts, not published)"])], ["Draft advisory + timeline"], RP, "row")],
 5: [footage(ST, [img("s_ticket", 1650, hl=True, label="Same Intake, second room pair")], ["Same Reproducer and Skeptic"], RS),
     footage(ST, [img("s_vuln", 1450, crop=230, hl=True, label="sqlparse 0.4.3 · RESOURCE_EXHAUSTION · 3/3"), img("s_patched", 1450, crop=230, hl=True, label="sqlparse 0.4.4 · NOT_REPRODUCED · 3/3")], ["Override + escalate + advisory, as for R-001"], RS),
     footage(ST, [img("n_r6", 1450, crop=200, hl=True, label="R-006 · NOT_REPRODUCED · 3/3")], ["It can say no"], RN),
     footage(ST, [img("n_r6concur", 1650, label="Skeptic concurs"), img("n_r6closed", 1650, hl=True, label="Maintainer closes R-006"), img("n_r7closed", 1650, hl=True, label="Maintainer closes R-007")], ["Closed on evidence"], RN),
     footage(ST, [img("l_limit", 1650, hl=True, label="INTAKE · reporter limit after 2 failed proofs"), img("l_lifted", 1650, hl=True, label="Limit lifted"), img("l_r8", 820, label="Next report accepted as R-008")], ["Reversible, one command"], RN),
     card('<div class="title2">No AI detector.</div>'), card('<div class="title2">No AI detector.<br><b>No ban.</b></div>')],
 6: [card(sw(-1)), card(sw(4) + TPL), card(sw(5)),
     card('<div class="big">Without Switch:</div><div class="list"><div>no shared room for reporter, agents and maintainer</div><div>no linked rooms, no managed agents, no sender identity</div></div><div class="fine">The CLI and the offline rehearsal still run without Switch; the team workflow does not.</div>'),
     card('<div class="grid g3"><div class="on">Switch<br><small>chat, agents, shared room context</small></div><div class="on">Prove It<br><small>ticket states, reporter limits, maintainer decisions</small></div><div class="off">Docker + harness<br><small>runs and classifies the proof</small></div></div>'),
     card('<div class="grid g3"><div class="on">Switch<br><small>chat, agents, shared room context</small></div><div class="on">Prove It<br><small>ticket states, reporter limits, maintainer decisions</small></div><div class="on">Docker + harness<br><small>runs and classifies the proof</small></div></div>')],
 7: [card('<div class="num"><b>3</b> fresh containers per build</div><div class="numl">6 sandbox runs per vulnerable/patched comparison · an evidence pack · a human decision<br><small>Sandbox time is not workflow time. Agent cost was not recorded. No time-saved figure is claimed.</small></div>'),
     card('<div class="num"><b>326</b> tests</div><div class="numl">314 passed · 12 skipped · 0 failures<br><small>full suite at commit 7568a4e (team run, 2026-11-07)</small></div>'),
     card('<div class="sub">Any maintainer team can deploy the template.</div><div class="built">github.com/akhilll0305/team-pikachu-switch-ai</div>')],
 8: [card('<div class="title">Prove It</div>'), card('<div class="title">Prove It</div><div class="sub">Code decides. Agents argue. <b style="color:#f5b942">Humans rule.</b></div>'),
     card('<div class="title">Prove It</div><div class="sub">Code decides. Agents argue. <b style="color:#f5b942">Humans rule.</b></div><div class="built big2">Built on <b>Switch</b>, for Flip the Switch</div><div class="built">github.com/akhilll0305/team-pikachu-switch-ai</div>')],
}
CSS += """
.flood{position:relative;height:520px;width:1300px;margin:0 auto}
.fl{position:absolute;left:150px;width:1000px;background:#151d2c;border:2px solid #3a2530;border-left:8px solid #ff6b5a;border-radius:12px;padding:18px 24px;font-size:30px;text-align:left;box-shadow:0 10px 30px rgba(0,0,0,.5)}
.fl:nth-child(1){top:0}.fl:nth-child(2){top:80px}.fl:nth-child(3){top:160px}.fl:nth-child(4){top:240px}.fl:nth-child(5){top:320px}.fl:nth-child(6){top:400px}
.crit{background:#ff6b5a;color:#111;font-weight:800;font-size:22px;padding:3px 10px;border-radius:6px;margin-right:10px}.flm{font-size:20px;color:#8b96a8;margin-top:6px}
.g6{grid-template-columns:repeat(3,480px)} .g3{grid-template-columns:repeat(3,520px)} .grid div.off{opacity:.25} .grid div.on{opacity:1}
"""
build()
