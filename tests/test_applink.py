"""hyimg:// links that open the app, and the browser's as before (owner 2026-10-07: «Можно ли сделать ссылку, которую нажимаешь, и
открывается приложение? ... При этом чтобы оставалась возможность классической ссылки»).

- «Copy as ›» on the board: the app's link first, the browser's as before, the same for the view; the empty board has both of its own
- a board opened in a normal browser shows «Open in Hyimg» · «Stay in browser» at the top centre; «Open in Hyimg» asks for the hyimg://
  equivalent of the address, «Stay in browser» puts the plate away for this tab; never inside the app, never after ?stay=1
- the setting «Open board links in the app» sends the page to the app by itself as it opens
- window.hyimgGo (the app handing a link to a drawn board): the page switches, the object is selected
- hy.py link: the app's link first, the browser's second
Chromium, dark (owner 2026-10-07), a temporary library; the browser's own going to hyimg:// is caught (window.hyAppOpenHook)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_move_to_page import screen

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
PID = str(uuid.uuid4())
SHOTS = Path(os.environ.get("HY_SHOTS") or Path(tempfile.gettempdir()) / "hyimg-shots")   # screenshots never go into the repository
BRIDGE = "window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };"
HOOK = "window.hyAppOpenHook = u => { window.__opened = u; };"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("applink")
    lib, state = tmp / "lib", tmp / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(2): (lib / "a" / f"{n}.png").write_bytes(png(40 + n, 60))
    item = lambda path, x: {"path": path, "x": x, "y": 0, "w": 300, "ar": 2 / 3, "crop": None}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {"p": item("a/0.png", 0)}, "groups": {}, "removed": {}}))
    (state / "boards/p2.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {"q": item("a/1.png", 4000)}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Main"}, {"id": "p2", "title": "Second"}]}))
    settings = tmp / "settings.json"; settings.write_text(json.dumps({"cv.lang": "en", "cv.theme": "dark"}))
    (tmp / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=PID, HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(tmp / "noplugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    try:
        yield {"port": port, "settings": settings}
    finally:
        proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try: br = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        yield br
        br.close()


def new_page(browser, *scripts):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    for s in scripts: ctx.add_init_script(s)
    page = ctx.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, errors


def shot(page, name, clip=None):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"applink-{name}.png"), clip=clip)


SUB = "() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem]')].map(b => [b.dataset.act, (b.querySelector('.ml') || b).textContent.trim()])"


def test_copy_as_gives_the_app_link_first(server, browser):
    port = server["port"]
    page, errors = new_page(browser)
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(f"http://127.0.0.1:{port}/canvas.html")
    page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p') && hyLink.project", timeout=20000)
    page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = .5; renderCam(); render(); }"); page.wait_for_timeout(300)
    clip = lambda: page.evaluate("() => navigator.clipboard.readText()")
    at = screen(page, 150, 150)   # on the picture

    def copy_as(act):
        page.mouse.click(at[0], at[1], button="right"); page.wait_for_selector("#ctx.open [role=menuitem]")
        page.locator("#ctx [data-sub=copyas]").hover()
        page.wait_for_function("() => document.querySelectorAll('#ctx .hy-sub [role=menuitem]').length === 6")
        rows = page.evaluate(SUB)
        if act == "applink": page.wait_for_timeout(400); shot(page, "copy-as")
        page.locator(f"#ctx .hy-sub [data-act={act}]").click(); page.wait_for_timeout(250)
        return rows

    rows = copy_as("applink")
    assert rows == [["applink", "App link"], ["link", "Browser link"], ["appview", "App link to this view"], ["view", "Browser link to this view"],
                    ["image", "Image"], ["path", "File path"]], rows
    assert clip() == f"hyimg://board/{PID}?page=main&obj=p"
    copy_as("link")
    assert clip() == f"http://127.0.0.1:{port}/?view=canvas&page=main&obj=p"   # the browser's link, as before
    copy_as("appview")
    app_view = clip()
    assert app_view.startswith(f"hyimg://board/{PID}?page=main&at=") and app_view.endswith(",0.5"), app_view
    # the empty board: its own two, the app's first
    page.keyboard.press("Escape"); page.mouse.click(1300, 800, button="right"); page.wait_for_selector("#ctx.open [role=menuitem]")
    acts = page.evaluate("() => [...document.querySelectorAll('#ctx > [role=menuitem]')].map(b => b.dataset.act)")
    assert acts[-2:] == ["appview", "view"], acts
    page.locator("#ctx > [data-act=view]").click(); page.wait_for_timeout(250)
    assert clip().startswith(f"http://127.0.0.1:{port}/?view=canvas&page=main&at="), clip()
    assert not errors, errors
    page.context.close()


def test_the_plate_in_a_browser_and_not_in_the_app(server, browser):
    port = server["port"]
    url = f"http://127.0.0.1:{port}/?view=canvas&page=p2&obj=q&applink=1"   # applink=1: an automated browser is shown it too
    page, errors = new_page(browser, HOOK)
    page.goto(url)
    page.wait_for_selector("#hyAppPlate hy-button >> nth=1", timeout=20000); page.wait_for_timeout(600)
    box = page.evaluate("() => { const r = document.getElementById('hyAppPlate').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    assert abs(box[0] + box[2] / 2 - 700) <= 1 and box[1] == 12 and box[3] == 38, box   # the top row's middle, a plate of the row
    assert page.evaluate("() => [...document.querySelectorAll('#hyAppPlate hy-button')].map(b => b.textContent.trim())") == ["Open in Hyimg", "Stay in browser"]
    logo = page.evaluate("() => { const b = document.querySelector('#hyAppPlate [data-applink=open]'), s = b.querySelector('svg.hy-applink-logo'), r = s && s.getBoundingClientRect();"
                         " return [!!s, !!b.querySelector('rect[fill=\"#e92001\"]'), r && Math.round(r.width)]; }")
    assert logo == [True, True, 20], logo   # the app's mark on «Open in Hyimg», not a link arrow (owner 2026-10-08)
    shot(page, "plate", clip={"x": 350, "y": 0, "width": 700, "height": 90})
    shot(page, "plate-window")
    page.locator("#hyAppPlate [data-applink=open]").click()
    assert page.evaluate("window.__opened") == f"hyimg://board/{PID}?page=p2&obj=q"   # the hyimg:// equivalent of the address
    page.locator("#hyAppPlate [data-applink=stay]").click()
    assert page.evaluate("() => !document.getElementById('hyAppPlate')")
    page.reload(); page.wait_for_function("() => window.hyLink && hyLink.project", timeout=20000); page.wait_for_timeout(500)
    assert page.evaluate("() => !document.getElementById('hyAppPlate')")   # this tab stays in the browser
    page.context.close()
    # the app's View › Open in Browser (?stay=1), an automated browser without applink=1, the app's own page: no plate
    for scripts, u in [((HOOK,), url + "&stay=1"), ((HOOK,), url.replace("&applink=1", "")), ((HOOK, BRIDGE), url)]:
        p2, err2 = new_page(browser, *scripts)
        p2.goto(u); p2.wait_for_function("() => window.hyLink && hyLink.project", timeout=20000); p2.wait_for_timeout(600)
        assert p2.evaluate("() => !document.getElementById('hyAppPlate') && !window.__opened"), u
        assert not err2, err2
        p2.context.close()
    assert not errors, errors


def test_the_setting_goes_to_the_app_by_itself(server, browser):
    port = server["port"]
    page, errors = new_page(browser, HOOK)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps({"cv.applinks": "1"}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=5).read()
    try:
        page.goto(f"http://127.0.0.1:{port}/?view=canvas&page=main&obj=p&at=10,20,0.5&applink=1")
        page.wait_for_function("() => window.__opened", timeout=20000)
        assert page.evaluate("window.__opened") == f"hyimg://board/{PID}?page=main&obj=p&at=10,20,0.5"
        assert page.evaluate("() => !!document.getElementById('hyAppPlate')")   # the plate stays for a second try
        page.goto(f"http://127.0.0.1:{port}/?view=canvas&page=main&applink=1&stay=1"); page.wait_for_timeout(800)
        assert page.evaluate("() => !window.__opened")   # sent from the app: it stays
    finally:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps({"cv.applinks": None}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5).read()
    assert not errors, errors
    page.context.close()


def test_the_app_hands_a_link_to_a_drawn_board(server, browser):
    page, errors = new_page(browser, BRIDGE)
    page.goto(f"http://127.0.0.1:{server['port']}/?view=canvas&page=main")
    frame = lambda: page.frame_locator("#cvFrame")
    page.wait_for_function("() => { const w = document.getElementById('cvFrame').contentWindow; return !!(w && w.hyimgGo && w.eval(`typeof EL !== 'undefined' && !!EL.get('p')`)); }", timeout=20000)
    page.evaluate("() => hyimgGo({ page: 'p2', obj: ['q'] })")   # as LinkRouting.swift deliver() calls it on the window's page
    page.wait_for_function("() => { const w = document.getElementById('cvFrame').contentWindow; return w.eval('BOARD') === 'p2' && w.eval('[...sel].join()') === 'q'; }", timeout=10000)
    page.evaluate("() => hyimgGo({ page: '../x', obj: ['a/b'] })")   # nothing outside the patterns gets through
    page.wait_for_timeout(300)
    assert page.evaluate("() => document.getElementById('cvFrame').contentWindow.eval('BOARD')") == "p2"
    assert not page.evaluate("() => !!document.getElementById('hyAppPlate')")   # inside the app: no plate
    assert frame() is not None and not errors, errors
    page.context.close()


def test_hy_py_link(server):
    env = dict(os.environ, HYIMG_PORT=str(server["port"]))
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "link", *a], env=env, capture_output=True, text=True, timeout=60)
    r = run("p", "--page", "main")
    assert r.returncode == 0 and r.stdout.splitlines() == [f"hyimg://board/{PID}?page=main&obj=p", f"http://127.0.0.1:{server['port']}/?view=canvas&page=main&obj=p"], r
    r = run("at=1,2,0.5", "--page", "p2")
    assert r.stdout.splitlines()[0] == f"hyimg://board/{PID}?page=p2&at=1,2,0.5", r
    assert run("nothing-here", "--page", "main").returncode != 0
