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
    "r_report": "byq9zrsf5bd8uemdiytunm3g7o", "r_received": "eaoc3rm1xf8xpphfkkircstscw", "r_ticket": "jytpgktg4tf3zj3sodib7eizhe",
    "r_vuln": "ob5uskmqnjf7unrf6nakjpx3ow", "r_skreview": "w98wynhkhtgp5f1mnyomz7sxrh", "r_dispute": "ohj3seon1jrg5c9n6a3iooth4a",
    "r_patchcmd": "wys45gn8y7y7t8z1q7f3ys43go", "r_patched": "cmfyqo364igczntrg1678demqy", "r_refused": "3ez5otmdc78y3dryz367ikidzy",
    "r_overridecmd": "d7unxiztibbquy6pir4xwcp41h", "r_overrode": "i359db6cmtnrignc3c1qmm78dy", "r_escalatecmd": "7se8pgho4igrzxudk4cjwgoxuh",
    "r_escalated": "7ut7hz5jhbgsxdqa3kqwra1zga", "r_advisory": "pa7wdaej5fn38mhq7adzaiiyia", "r_confirmed": "rkycri36ainwbjknyhp957ntow",
    "s_ticket": "tf4dgd4s57fzxpg8wtbhhc4gby", "s_vuln": "e5py6na6qj8z5kkhcx6wpj1k8c", "s_patched": "8pothgw1ktn6fexz4y3pigau3e",
    "s_overrode": "h4n68ij8ujb17c6i5ej13aw86c", "s_escalated": "oo8wz61cibgruew6rbmw8h8mwh", "s_advisory": "iwerxqa7itfw9yxh8ke7bu4s1e", "s_confirmed": "1s31h19b8td9xmyqqnirg8fyga",
    "n_r6": "3kcggic6dtru3qqaq44jexhnda", "n_r6concur": "mb7hc57433895qah1xrusbbtrr", "n_r6closed": "rrymbeunsibi8ct81t8ybd7qma",
    "n_r7": "8ccqc7icktnfdrc1yrz4bisr5o", "n_r7closed": "urbxbbhcqbnb7jetwq8nipgb7h",
    "l_refuse": "ufhc66t4wbgpi8se7auoib4yxy", "l_limit": "4mhm6xh6hpfkjgo856x5jksowo", "l_clearcmd": "cednhjcwgigq9xrhexutzqkq7o",
    "l_lifted": "8bkbfkw3kp8qdgxhxy3snwxgac", "l_r8": "nod5s37pttrqietzxcu9akag6h",
}
HIDE = """
.team-sidebar, #SidebarContainer, #sidebar-left, .app-bar, #global-header, .global-header,
#announcement-bar, .announcement-bar, #channel_view .post-create__container, #advancedTextEditorCell,
.channel-header__icons, #channelHeaderSearchWrapper, .AnnouncementBar, .toast, .toast__visible, .toast__jump, .scroll-to-bottom-toast, [class*="toast"], [id*="toast"] { display: none !important; }
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
