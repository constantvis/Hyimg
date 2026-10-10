"""Who made a change, on screen (owner 2026-10-07: two people share boards through a shared Dropbox folder, each on his own Mac).
Home asks for a name and a colour on the first launch, Settings › Profile renames and signs out, a board's menu moves it between the
shared and the private folder (greyed until both are chosen), a private board wears a lock; the board's history shows each change's
person with his colour and the name this Mac gives him. Chromium, dark theme, temporary folders. HY_SHOTS=<folder> keeps screenshots."""
import gzip
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
ME, OTHER = str(uuid.uuid4()), str(uuid.uuid4())
P = [{"id": "A", "name": "Atlas", "path": "/x/Shared/Atlas", "available": True, "updated": 1791100000, "covers": []},
     {"id": "B", "name": "Notes", "path": "/x/Private/Notes", "available": True, "updated": 1791000000, "covers": [],
      "news": {"n": 5, "rows": [{"p": "", "pid": "main", "k": "add", "w": "owner", "u": OTHER, "n": 2, "c": 3},
                                {"p": "", "pid": "main", "k": "note", "w": "Codex", "u": OTHER, "n": 3, "c": 0}]}}]
PEOPLE = {ME: {"name": "Ann", "own": "Ann", "color": "green", "me": True}, OTHER: {"name": "Partner", "own": "Bob", "color": "orange", "alias": "Partner"}}


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def browser_page(p, url=None):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    return browser, page, errors


def test_home_first_launch_profile_and_visibility():
    with playwright.sync_playwright() as p:
        browser, page, errors = browser_page(p)
        sent = []
        page.expose_function("__post", lambda m: sent.append(m))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
        page.goto(HOME)
        data = lambda **k: json.dumps({"projects": json.loads(json.dumps(P)), "settings": {"cv.theme": "dark"}, "home": {"folders": []}, **k})
        ops = lambda op: [m for m in sent if m.get("action") == "profile" and m.get("op") == op]
        # Home without the app's word on the profile (older app, tests): no question
        page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {'cv.theme': 'dark'}, 'home': {'folders': []}})})")
        assert page.locator("#hyWelcome").count() == 0
        # the first launch: no profile on this Mac; a name and a colour, nothing else
        page.evaluate(f"hyimgHome({data(profile=None, people={}, places={'shared': '', 'private': ''}, vis={})})")
        page.wait_for_selector("#hyWelcome.in")
        assert page.locator("#hyWelcome h2").inner_text() == "What's your name?" and page.locator("#hyWelcome hy-swatch").count() == 8
        page.wait_for_timeout(450); shot(page, "1-first-launch")
        page.locator("#hyWelcome [data-hw-ok] button").click()   # no name yet: it stays and asks for one
        assert page.locator("#hyWelcome").count() == 1 and not ops("save")
        page.fill("#hwName", "Ann"); page.locator('#hyWelcome hy-swatch[value="green"]').click()
        page.locator("#hyWelcome [data-hw-ok] button").click()
        page.wait_for_function("() => (window.__sent, !document.querySelector('#hyWelcome'))")
        assert ops("save") == [{"action": "profile", "op": "save", "name": "Ann", "color": "green"}]
        # the app writes it and sends Home again: Settings › Profile, the folders not chosen yet
        page.evaluate(f"hyimgHome({data(profile={'id': ME, 'name': 'Ann', 'color': 'green'}, people=PEOPLE, places={'shared': '', 'private': ''}, vis={'A': '', 'B': ''})})")
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "profile")   # its section of the settings window
        sec = page.locator("#hyPeopleSet")
        assert sec.locator(".hp-prof").is_visible() and sec.locator("[data-hp-name]").input_value() == "Ann"
        assert sec.locator(".hp-place .hp-path").all_inner_texts() == ["not chosen", "not chosen"]
        assert sec.locator("[data-hp-alias]").get_attribute("placeholder") == "Bob" and sec.locator("[data-hp-alias]").input_value() == "Partner"
        shot(page, "2-settings-profile")
        sec.locator("[data-hp-name]").fill("Ann Lee"); sec.locator("[data-hp-name]").press("Enter")
        assert ops("save")[-1] == {"action": "profile", "op": "save", "name": "Ann Lee", "color": "green"}
        sec.locator('hy-swatch[value="purple"]').click()
        assert ops("save")[-1]["color"] == "purple"
        sec.locator('[data-hp-pick="shared"] button').click()
        assert ops("pick") == [{"action": "profile", "op": "pick", "which": "shared"}]
        page.keyboard.press("Escape"); page.mouse.click(700, 600)
        # a board's menu: «Shared» and «Only for me», grey with the reason until both folders are chosen
        page.locator(".card[data-id=A]").click(button="right")
        items = page.locator("#menu.open [data-hpto]")
        assert items.count() == 2 and all(items.nth(i).get_attribute("aria-disabled") == "true" for i in range(2))
        assert "Settings › Profile" in items.first.get_attribute("title")
        items.nth(1).click(force=True)
        assert not ops("visibility")
        # both chosen: Notes is private (a lock, the filter), Atlas is shared and can be made private
        page.keyboard.press("Escape")
        both = {"shared": "/x/Shared", "private": "/x/Private"}
        page.evaluate(f"hyimgHome({data(profile={'id': ME, 'name': 'Ann', 'color': 'green'}, people=PEOPLE, places=both, vis={'A': 'shared', 'B': 'private'})})")
        assert page.locator(".card[data-id=B] .hp-lock").count() == 1 and page.locator(".card[data-id=A] .hp-lock").count() == 0
        page.locator(".hp-vis [data-hpvis=private]").click()
        assert page.locator(".grid .card").evaluate_all("cs => cs.map(c => c.dataset.id)") == ["B"]
        assert [m["home"].get("vis") for m in sent if m.get("action") == "homeSave"][-1] == "private"
        shot(page, "3-home-private-filter")
        page.locator(".hp-vis [data-hpvis='']").click()
        page.locator(".card[data-id=A]").click(button="right")
        assert page.locator('#menu.open [data-hpto="shared"]').get_attribute("aria-disabled") == "true"
        page.locator('#menu.open [data-hpto="private"]').click()
        assert ops("visibility") == [{"action": "profile", "op": "visibility", "id": "A", "to": "private"}]
        # the news of another person: his name as this Mac shows him, his agent «Codex (Partner)»
        assert page.locator(".card[data-id=B] .nb").get_attribute("title").endswith("· Partner, Codex (Partner)")
        # sign out: the profile goes, Home does not ask again until the next start
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "profile"); page.locator("#hyPeopleSet [data-hp=signout] button").click()
        assert ops("signout") == [{"action": "profile", "op": "signout"}]
        page.evaluate(f"hyimgHome({data(profile=None, people=PEOPLE, places={'shared': '', 'private': ''}, vis={})})")
        page.wait_for_timeout(100)
        assert page.locator("#hyWelcome").count() == 0 and page.locator("#hyPeopleSet [data-hp=signin]").count() == 1
        assert not errors, errors
        browser.close()


def write_history(state, who, by):
    d = state / "boards/_history/main"; d.mkdir(parents=True, exist_ok=True)
    sid = time.strftime("%y%m%d-%H%M%S") + "-" + who
    with gzip.open(d / f"{sid}.json.gz", "wt", encoding="utf-8") as f: json.dump(json.loads((state / "boards/main.json").read_text()), f)
    e = {"id": sid, "t": time.strftime("%Y-%m-%d %H:%M:%S"), "who": who, "label": "v", "revision": 1, "pictures": 6, "notes": 0, "titles": 0, "groups": 0, "by": by}
    with open(d / "index.jsonl", "a", encoding="utf-8") as f: f.write(json.dumps(e) + "\n")


def test_board_history_names_people_and_a_save_says_who(tmp_path):
    """the partner's changes came with the shared folder: Activity and Versions show «Partner» and «Codex · Partner» in his colour,
    the name this Mac gave him; a save made on this canvas is this Mac's person's, by the app"""
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann", "color": "green", "created": ""}))
    (tmp_path / "people.json").write_text(json.dumps({OTHER: {"name": "Bob", "color": "orange", "alias": "Partner"}}))
    state = tmp_path / "state"
    servers = run_server(tmp_path); port = next(servers)   # the partner's changes arrive with the shared folder
    (state / "boards/_events").mkdir(parents=True)
    now = time.time()
    lines = [{"kind": "add", "ids": ["i0"], "count": 1, "paths": ["a/0.png"], "who": "owner", "t": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": now - 60,
              "by": {"person": OTHER, "via": "app"}},
             {"kind": "add", "ids": ["i1"], "count": 1, "paths": ["a/1.png"], "who": "ai", "agent": "Codex", "t": time.strftime("%Y-%m-%d %H:%M:%S"),
              "ts": now - 30, "by": {"person": OTHER, "via": "Codex"}}]
    (state / "boards/_events/main.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    try:
        write_history(state, "owner", {"person": OTHER, "via": "app"})
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps({"cv.theme": "dark"}).encode(), method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=10).read()
        with playwright.sync_playwright() as p:
            browser, page, errors = browser_page(p)
            url = f"http://127.0.0.1:{port}/canvas.html"
            page.goto(url)
            page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
            page.goto(url)
            page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && EL.get('i0')", timeout=20000)
            page.wait_for_function("() => window.hyPeople && hyPeople.me() && hyPeople.me().name === 'Ann'")
            page.click("#bhist"); page.click('#hist [data-tab="ev"]')
            page.wait_for_selector("#evList .ev .hy-by")
            who = page.locator("#evList .ev .hy-by").all_inner_texts()
            assert who[:2] == ["Codex · Partner", "Partner"], who
            assert page.locator("#evList .ev .hy-by hy-avatar .hya-p").nth(1).evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(245, 154, 61)"
            assert page.locator("#evList .ev .hy-by hy-avatar").first.get_attribute("agent") == "codex"   # «Codex» of an older event, folded
            shot(page, "4-board-activity")
            page.click('#hist [data-tab="ver"]')
            page.wait_for_selector("#histList .hv .hy-by")
            assert page.locator("#histList .hv .hy-by").first.inner_text() == "Partner"
            shot(page, "5-board-versions")
            page.keyboard.press("Escape")
            # a save made here, on the canvas: this Mac's person, by the app; the info panel says who changed the card last
            page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = 1; renderCam(); render(); sel = new Set(['i2']); render(); }")
            page.mouse.click(1350, 860); page.evaluate("() => { sel = new Set(['i2']); render(); }")
            page.keyboard.press("ArrowRight")
            for _ in range(100):   # the canvas saves a moment after the press
                ev = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/events?name=main", timeout=10))[0]
                if ev["kind"] == "move": break
                time.sleep(0.1)
            assert ev["by"] == {"person": ME, "via": "app"}, ev
            box = page.evaluate("() => { const r = EL.get('i1').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }")
            page.mouse.click(box["x"], box["y"])
            page.wait_for_selector("#info .hy-edited", timeout=5000)   # in the File section since the header became the facts (2026-10-10)
            assert "Codex · Partner" in page.locator("#info .hy-edited").inner_text()
            shot(page, "6-info-edited-by")
            # Settings › Profile on the board: the partner renamed for this Mac only
            page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "team")   # the people this Mac knows: Team & agents
            alias = page.locator("#hyPeopleSet [data-hp-alias]")
            assert alias.input_value() == "Partner"
            alias.fill("Bobby"); alias.press("Enter")
            page.wait_for_function("() => hyWhoText({by: {person: %s, via: 'app'}}) === 'Bobby'" % json.dumps(OTHER))
            assert json.loads((tmp_path / "people.json").read_text())[OTHER]["alias"] == "Bobby"
            shot(page, "7-board-settings")
            assert not errors, errors
            browser.close()
    finally:
        servers.close()
