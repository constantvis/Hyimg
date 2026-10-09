"""Settings › Plugins on screen (owner 2026-10-07: «в настройках было видно, какие плагины подключены ... в процессе работы отключить какой-то
плагин, и он отключался. Естественно, если я работаю в этом плагине, выхожу, и он потом отключается»), and a double-click on an HTML frame
opening Dev mode while Dev studio is on (owner: «зашел в режим Dev вроде как, но по факту не зашел»).

A board with the three plugins linked from their working copies beside this repository into a temporary plugins folder (HYIMG_PLUGIN_DIR):
the section lists them with versions; Dev studio off takes its dock mode and its routes away («plugin off»), its card shows its still with
the «Plugin off» mark, the HTML frame's double-click opens the frame's live view; turned off from inside Dev mode it waits until the person
leaves; on again brings it all back; Remove takes only the link away. Home's section talks to the app (a stand-in for its bridge), in
English and Russian. Chromium, dark theme, temporary folders. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
REPOS = ROOT.parent
HOME = (ROOT / "review/home.html").as_uri()
PLUGS = (("3d", "hyimg-3d-studio"), ("frames", "hyimg-frames"), ("dev", "hyimg-dev-studio"))
PAGE = "<!doctype html><html><head><meta charset=utf-8><title>Demo</title></head><body style='margin:0;background:rgb(20,120,200)'><h1 id=t>Hello</h1></body></html>"


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"plugins-{name}.png"))


@pytest.fixture
def hy(tmp_path, request):
    if not all((REPOS / r / "manifest.json").is_file() for _n, r in PLUGS): pytest.skip("the plugins' repositories are not beside hyimg")
    lang = getattr(request, "param", "en")
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": lang, "cv.theme": "dark"}))
    lib, state, plugins = tmp_path / "lib", tmp_path / "state", tmp_path / "plugins"
    for d in (lib / "html/demo", lib / "a", state / "boards", plugins): d.mkdir(parents=True)
    (lib / "html/demo/index.html").write_text(PAGE)
    (lib / "a/0.png").write_bytes(png())
    for n, r in PLUGS: (plugins / n).symlink_to(REPOS / r)
    items = {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 260, "ar": 2 / 3, "crop": None},
             "f1": {"type": "htmlframe", "src": "html/demo/index.html", "vw": 1280, "x": 300, "y": 0, "w": 480, "h": 300},
             "h1": {"type": "html", "src": "html/demo/index.html", "vw": 1280, "x": 820, "y": 0, "w": 480, "h": 300, "pics": ["html/demo/index.html"]}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "home").mkdir()
    env.update(HOME=str(tmp_path / "home"), PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_PLUGIN_DIR=str(plugins),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield port, plugins, tmp_path
    finally:
        proc.terminate(); proc.wait(5); log.close()


def call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()


def ready(page, n):
    page.wait_for_function(f"() => typeof PLGST !== 'undefined' && PLGST.length === {n} && PLGST.every(x => x.ok) && EL.get('h1')", timeout=30000)


def board(p, port, n=3):
    try: br = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = br.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    ready(page, n)
    page.evaluate("() => { cam.x = -60; cam.y = -260; cam.z = 1; renderCam(); render(); }")
    return br, page, errors


def modes(page):
    return page.evaluate("[...document.querySelectorAll('#modes > button')].map(b => b.dataset.mode)")


def rows(page):
    return page.evaluate("[...document.querySelectorAll('#hyPlugSet .hpl-row')].map(r => [r.dataset.pl, r.querySelector('.hpl-name').textContent,"
                         " (r.querySelector('.hpl-ver') || {}).textContent || '', !!r.querySelector('hy-switch[checked]')])")


def switch(page, name, expect_reload=True):
    sw = page.locator(f"#hyPlugSet [data-pl=\"{name}\"] hy-switch")
    if expect_reload:
        with page.expect_navigation(timeout=20000): sw.click()
    else: sw.click()


def test_section_lists_turns_dev_off_and_on_and_html_frames_open_dev_mode(hy):
    port, plugins, _tmp = hy
    with playwright.sync_playwright() as p:
        br, page, errors = board(p, port)
        assert "dev" in modes(page)
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins")
        page.wait_for_selector("#hyPlugSet .hpl-row >> nth=2")
        assert rows(page) == [["3d", "3D objects", "0.1.0", True], ["dev", "Dev Studio", "0.2.0", True], ["frames", "Frames", "0.3.0", True]]
        assert "Dev Studio edits a page" in page.locator("#hyPlugSet [data-pl=\"dev\"] .hpl-desc").inner_text()
        assert page.locator("#hyPlugSet [data-pl-add]").get_attribute("title") == "Only in the Mac app"   # no app here: Add is grey
        page.locator("#hyPlugSet").scroll_into_view_if_needed(); shot(page, "1-board-section-en")
        # a double-click on an HTML frame opens Dev mode while Dev studio is on; the frame's live view is one click away, top right
        page.keyboard.press("Escape"); page.mouse.click(700, 820)
        page.dblclick(".plg[data-id=f1]")
        page.wait_for_function("() => window.__dev && __dev.D && __dev.D.id === 'f1'", timeout=10000)
        assert page.locator("hy-studio-actions [data-a=live]").count() == 1
        shot(page, "2-frame-in-dev-mode")
        page.click("hy-studio-actions [data-a=live]")
        page.wait_for_function("() => !__dev.D && document.querySelector('.plg[data-id=f1].plg-live') && document.querySelector('#dock .hfbar')", timeout=10000)
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('.plg.plg-live')")
        # the bar over a selected frame offers the live view too
        page.evaluate("() => { sel = new Set(['f1']); render(); }")
        assert page.locator(".tidy [data-plgbar]", has_text="Live view").count() == 1
        page.evaluate("() => { sel = new Set(); render(); }")
        # Dev studio off: the board reloads without it; its routes say so, its card is its still with «Plugin off»
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins")
        switch(page, "dev")
        ready(page, 2)
        assert "dev" not in modes(page) and json.loads(call(port, "/api/plugins/all")[1])["off"] == ["dev"]
        st, body = call(port, "/api/plugin/dev/source", {})
        assert st == 409 and json.loads(body)["error"] == "plugin off: dev"
        assert call(port, "/plugins/dev/canvas.js")[0] == 404 and "dev" not in [x["name"] for x in json.loads(call(port, "/api/plugins")[1])]
        page.wait_for_function("() => { const e = document.querySelector('.plg.plo[data-id=h1]'); return e && e.querySelector('img.plo').complete && e.querySelector('.mk-kind') }")
        assert page.locator(".plg[data-id=h1] .mk-kind .kt").inner_text() == "Plugin off"
        assert page.evaluate("document.querySelector('.plg[data-id=h1] img.plo').naturalWidth") > 0
        board_file = json.loads((_tmp / "state/boards/main.json").read_text())
        assert board_file["items"]["h1"]["type"] == "html"   # the board file keeps the card as it was
        page.wait_for_selector("#sets.open #hyPlugSet [data-pl=\"dev\"].hpl-off")   # the panel opens again where it was
        page.locator("#hyPlugSet").scroll_into_view_if_needed(); shot(page, "3a-dev-off-section")
        page.keyboard.press("Escape"); page.mouse.click(700, 820)
        page.evaluate("() => { cam.x = 600; cam.y = -260; cam.z = 1; renderCam(); render(); }")
        page.wait_for_timeout(400); shot(page, "3b-dev-off-card-still")
        page.evaluate("() => { cam.x = -60; cam.y = -260; cam.z = 1; renderCam(); render(); }")
        # without Dev studio a double-click on the HTML frame is its live view, as before
        page.dblclick(".plg[data-id=f1]")
        page.wait_for_function("() => document.querySelector('.plg[data-id=f1].plg-live') && document.querySelector('#dock .hfbar')", timeout=10000)
        assert page.locator(".tidy [data-plgbar]", has_text="Live view").count() == 0
        page.keyboard.press("Escape")
        # on again: the mode, the routes, the card
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins")
        switch(page, "dev")
        ready(page, 3)
        assert "dev" in modes(page) and call(port, "/api/plugin/dev/nothing", {})[0] == 404
        assert page.locator(".plg[data-id=h1].plo").count() == 0 and page.locator(".plg[data-id=h1] img.dvi").count() == 1
        assert not errors, errors
        br.close()


def test_off_while_in_dev_mode_applies_when_leaving(hy):
    port, plugins, _tmp = hy
    with playwright.sync_playwright() as p:
        br, page, errors = board(p, port)
        page.dblclick(".plg[data-id=h1]")
        page.wait_for_function("() => window.__dev && __dev.D && __dev.D.id === 'h1'", timeout=10000)
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins"); page.wait_for_selector("#hyPlugSet [data-pl=\"dev\"] hy-switch")
        switch(page, "dev", expect_reload=False)
        page.wait_for_selector("#hyPlugSet [data-pl=\"dev\"] .hpl-pend")
        assert page.locator("#hyPlugSet [data-pl=\"dev\"] .hpl-pend").inner_text() == "Turns off when you leave Dev Studio"
        all_ = json.loads(call(port, "/api/plugins/all")[1])
        assert all_["off"] == ["dev"] and all_["held"] == ["dev"]
        assert call(port, "/api/plugin/dev/nothing", {})[0] == 404   # still served while the person is inside: a route it has not, not «off»
        assert page.evaluate("!!(__dev.D && __dev.D.id === 'h1')")
        shot(page, "4-off-waits-in-dev-mode")
        page.click("#bset")   # the settings panel closes; Esc would leave Dev mode, as Done does
        with page.expect_navigation(timeout=20000):
            page.click("hy-studio-actions [data-a=done]")
        ready(page, 2)
        assert "dev" not in modes(page) and call(port, "/api/plugin/dev/nothing", {})[0] == 409
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins")
        switch(page, "dev")
        ready(page, 3)
        assert "dev" in modes(page)
        assert not errors, errors
        br.close()


def test_remove_takes_only_the_link_and_the_board_reloads_without_it(hy):
    port, plugins, _tmp = hy
    with playwright.sync_playwright() as p:
        br, page, errors = board(p, port)
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins"); page.wait_for_selector("#hyPlugSet [data-pl=\"3d\"] [data-pl-more]")
        page.locator("#hyPlugSet [data-pl=\"3d\"] [data-pl-more]").click()
        page.wait_for_selector(".hpl-menu.on")
        shot(page, "5-more-menu")
        page.locator(".hpl-menu [data-m=remove]").click()
        page.wait_for_selector("#hyConfirm.on")
        assert "Remove «3D objects»?" in page.locator("#hyConfirm").inner_text()
        with page.expect_navigation(timeout=20000):
            page.locator("#hyConfirm button.ok").click()
        ready(page, 2)
        assert not os.path.lexists(plugins / "3d") and (REPOS / "hyimg-3d-studio/manifest.json").is_file()
        assert "3d" not in modes(page) and sorted(os.listdir(plugins)) == ["dev", "frames"]
        assert not errors, errors
        br.close()


@pytest.mark.parametrize("hy", ["ru"], indirect=True)
def test_board_section_in_russian(hy):
    port, _plugins, _tmp = hy
    with playwright.sync_playwright() as p:
        br, page, errors = board(p, port)
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins"); page.wait_for_selector("#hyPlugSet .hpl-row >> nth=2")
        sec = page.locator("#hyPlugSet").text_content()
        assert "Плагины" in sec and "Добавить плагин…" in sec and "3D-объекты" in sec and "Dev Studio" in sec
        assert page.locator("#hyPlugSet [data-pl=\"dev\"] .hpl-desc").inner_text().startswith("HTML-файлы карточками")
        assert page.evaluate("window.__tMiss ? [...window.__tMiss] : []") == []
        page.locator("#hyPlugSet").scroll_into_view_if_needed(); shot(page, "6-board-section-ru")
        assert not errors, errors
        br.close()


LIST = {"root": "/x/plugins", "off": ["3d"], "plugins": [
    {"name": "3d", "title": "3D objects", "version": "0.1.0", "description": "A 3D scene as a card", "folder": "/x/repos/hyimg-3d-studio", "off": True,
     "own": True, "link": True, "removable": True, "canvas": True, "error": ""},
    {"name": "dev", "title": "Dev studio", "version": "0.2.0", "description": "HTML files as cards", "folder": "/x/repos/hyimg-dev-studio", "off": False,
     "own": True, "link": True, "removable": True, "canvas": True, "error": ""},
    {"name": "gone", "title": "gone", "version": "", "description": "", "folder": "/x/missing", "off": False, "own": True, "link": True, "removable": True,
     "canvas": False, "error": "no manifest.json"}]}


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_home_section_talks_to_the_app(lang):
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = br.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        sent = []
        page.expose_function("__post", lambda m: sent.append(m))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
        page.add_init_script(f"try {{ localStorage.setItem('cv.lang', '{lang}'); }} catch (e) {{}}")
        page.goto(HOME)
        page.evaluate("hyimgHome({projects: [], settings: {'cv.theme': 'dark', 'cv.lang': %s}, home: {folders: []}})" % json.dumps(lang))
        ops = lambda op: [m for m in sent if m.get("action") == "plugins" and m.get("op") == op]
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "plugins")
        page.wait_for_timeout(150)
        assert ops("list"), sent   # the panel opened: the app is asked for the list
        page.evaluate(f"hyimgPlugins({json.dumps(LIST)})")
        r = rows(page)
        assert [x[0] for x in r] == ["3d", "dev", "gone"] and r[0][3] is False and r[1][3] is True
        assert page.locator("#hyPlugSet [data-pl=\"gone\"] hy-switch").count() == 0
        page.locator("#hyPlugSet").scroll_into_view_if_needed(); shot(page, f"7-home-section-{lang}")
        if lang == "ru":
            sec = page.locator("#hyPlugSet").text_content()
            assert "Плагины" in sec and "нет manifest.json" in sec and "Добавить плагин…" in sec
        # on and off: the app's setting, as Home's other settings
        page.locator("#hyPlugSet [data-pl=\"dev\"] hy-switch input").click()
        assert [m for m in sent if m.get("action") == "settings"][-1] == {"action": "settings", "change": {"cv.plugoff": "3d,dev"}}
        page.locator("#hyPlugSet [data-pl=\"3d\"] hy-switch input").click()
        assert [m for m in sent if m.get("action") == "settings"][-1] == {"action": "settings", "change": {"cv.plugoff": "dev"}}
        # Add: the app's folder panel; the folder: Finder; Remove: the app asks first with the page's words
        page.locator("#hyPlugSet [data-pl-add] button").click()
        assert ops("add") == [{"action": "plugins", "op": "add"}]
        page.locator("#hyPlugSet [data-pl=\"dev\"] [data-pl-dir] button").click()
        assert ops("reveal") == [{"action": "plugins", "op": "reveal", "path": "/x/repos/hyimg-dev-studio"}]
        page.locator("#hyPlugSet [data-pl=\"dev\"] [data-pl-more] button").click()
        page.locator(".hpl-menu [data-m=remove]").click()
        m = ops("remove")[0]
        assert m["name"] == "dev" and m["confirm"] is True and ("Remove «Dev studio»?" if lang == "en" else "Убрать «Dev studio»?") == m["title"]
        assert not errors, errors
        br.close()
