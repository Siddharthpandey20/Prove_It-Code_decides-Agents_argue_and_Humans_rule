"""Screenshot real run-2 posts from the local Mattermost (login never printed)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, r"D:\PROJECTS\Switch-the-flip\team-pikachu-switch-ai")
from proveit import replay_login
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SHOTS = HERE / "shots"; SHOTS.mkdir(exist_ok=True)
login = replay_login.find_login()
base = login["url"]

POSTS = {
    # intake
    "i_02_report": "tbhx1j67i3n8dj9formhinmf4o",
    "i_02_askproof": "mchfg7e4qprxzftarrn59qc1na",
    "i_02_proof": "6pgaj9zod3rejphimwgoh9dbhr",
    "i_02_received": "hrzc1nofw3y8urytpfyy9rhn3e",
    "i_02_closed": "9sj1rwj8minx7puicgy35esmse",
    "i_01_report": "g7636bj19fdcd8wq9po596ds6c",
    "i_01_confirmed": "5gs8993hp7gd5k8re3k84nu1wc",
    "i_04_report": "cbhbe3hdnp8h3jk679p84d7mre",
    "i_04_blocked": "cmxed6aoktyyikqesyoi8fb9dw",
    # triage
    "t_02_ticket": "xj6hg6uk1i8rpekq98rkp8dnoe",
    "t_02_check": "mjdk3gpa8fb3jehxofpdc6pzrr",
    "t_02_result": "wfr3nt6r17ro7ke8txxpr3hw8y",
    "t_02_concur": "musya344gifzbgs4fxzf9guodo",
    "t_02_concur_intake": "4ea893ghtifw8cezg93j1mi9jh",
    "t_02_close": "3cbk8mjnktge5pg16nqbsp6i3w",
    "t_01_ticket": "pa87jirrq3dk58gafuxjbxthfc",
    "t_01_dispute": "qqsqdjik9fb1d8pd49fa1iqp4o",
    "t_01_patchedcmd": "swtw4ycdrpremjomf674pdiebc",
    "t_01_patched": "333w9kcyxpg6tkzk18br5hm9ic",
    "t_01_override": "rcszjbucuidymf1okeag7encya",
    "t_01_escalate": "yfifmt8ni7yr8ckwfnqfh6mm3o",
    "t_tally": "se91p6gmqtyhmnqx37pt4zh4gh",
}
HIDE = """
.team-sidebar, #SidebarContainer, #sidebar-left, .app-bar, #global-header, .global-header,
#announcement-bar, .announcement-bar, #channel_view .post-create__container, #advancedTextEditorCell,
.channel-header__icons, #channelHeaderSearchWrapper, .AnnouncementBar { display: none !important; }
.app__body .channel-view, .main-wrapper, #channel_view { margin-left: 0 !important; }
"""
only = set(sys.argv[1:])
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1.5, color_scheme="dark")
    import urllib.request
    req = urllib.request.Request(base + "/api/v4/users/login", data=json.dumps({"login_id": login["user"], "password": login["password"]}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        token = r.headers["Token"]; uid = json.loads(r.read())["id"]
    host = base.split("//")[1].split(":")[0]
    ctx.add_cookies([{"name": "MMAUTHTOKEN", "value": token, "domain": host, "path": "/", "httpOnly": True},
                     {"name": "MMUSERID", "value": uid, "domain": host, "path": "/"},
                     {"name": "MMCSRF", "value": "x", "domain": host, "path": "/"}])
    pg = ctx.new_page()
    pg.goto(base + "/switch/channels/proveit-triage"); time.sleep(6)
    pg.screenshot(path=str(SHOTS / "_home.png"))
    for name, pid in POSTS.items():
        if only and name not in only:
            continue
        pg.goto(f"{base}/switch/pl/{pid}"); time.sleep(4)
        pg.add_style_tag(content=HIDE); time.sleep(1.2)
        pg.screenshot(path=str(SHOTS / f"{name}_view.png"))
        for sel in (f"#rhsPost_{pid}", f"#post_{pid}"):
            el = pg.query_selector(sel)
            if el and el.is_visible():
                el.scroll_into_view_if_needed(); time.sleep(0.5)
                el.screenshot(path=str(SHOTS / f"{name}_post.png"))
                print(name, "ok", sel); break
        else:
            print(name, "NO ELEMENT")
    b.close()
