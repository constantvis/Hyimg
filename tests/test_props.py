"""«Copy properties ⌥⌘C ›» and «Paste properties ⌥⌘V ›» on the board (owner 2026-10-06, after Lightroom's Copy Settings).

- the item copies every property the object has, its submenu one kind (only the kinds the object has), «Custom… ⇧⌥⌘C» a window of
  checkboxes (the last choice kept), «Save as preset…» names a set
- «Paste properties» pastes the clipboard onto every selected object a kind applies to (one undo step); its submenu: a quiet line of what
  the clipboard holds, the kinds (one that applies to none of the selection greyed, its reason in the tooltip), «Presets ›»
- hovering «Paste properties», a kind or a preset shows the result on the selected cards; leaving puts them back; a click keeps it
- crop is a share of the frame, time in seconds up to a shorter video's end, size the width, opacity a value; never rating, ♥ or tags
- a plugin's kind: the frames plugin's colour grade (its own copy/paste items are gone from the right click)
- the clipboard goes from project to project (a file beside the app's settings); presets in the project's presets.json
- hy.py do 'props from=REF to=REF... only=...' and 'props preset=NAME to=...'
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only (the frames plugin from its repository's last commit)."""
import re
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import free_port, png
from test_move_to_page import frames_plugin, screen

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium"]   # the board's tests run in Chromium, dark (owner 2026-10-07)
FFMPEG = shutil.which("ffmpeg")
GRADE = {"basic": {"exposure": 0.6}}


def board():
    items = {
        "src": {"path": "a/0.png", "x": 0, "y": 0, "w": 300, "ar": 2 / 3, "crop": [0.1, 0.2, 0.9, 0.8], "opacity": 0.5, "grade": GRADE},
        "t1": {"path": "a/1.png", "x": 400, "y": 0, "w": 200, "ar": 2 / 3, "crop": None},
        "t2": {"path": "a/2.png", "x": 700, "y": 0, "w": 250, "ar": 1.5, "crop": None},
        "nt": {"type": "note", "text": "a note", "x": 1000, "y": 300, "w": 200, "fs": 12, "color": "yellow"},
        "plain": {"path": "a/3.png", "x": 0, "y": 700, "w": 300, "ar": 2 / 3, "crop": None},
    }
    if FFMPEG:
        items["v7"] = {"path": "a/v7.mp4", "x": 0, "y": 1300, "w": 300, "ar": 16 / 9, "crop": None, "trim": [1, 6]}
        items["v3"] = {"path": "a/v3.mp4", "x": 400, "y": 1300, "w": 300, "ar": 16 / 9, "crop": None}
    return {"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}


def start(tmp, settings_dir, items=None):
    lib, state, plugins = tmp / "lib", tmp / "state", tmp / "plugins"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True); plugins.mkdir()
    for n in range(4):
        (lib / "a" / f"{n}.png").write_bytes(png())
    if FFMPEG and items is None:
        for name, sec in (("v7", 7), ("v3", 3)):
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=15", "-t", str(sec), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(lib / f"a/{name}.mp4")], check=True, timeout=120)
    frames = frames_plugin(plugins / "frames")
    (state / "boards/main.json").write_text(json.dumps(items or board()))
    settings = settings_dir / "settings.json"
    if not settings.exists(): settings.write_text(json.dumps({"cv.lang": "en"}))
    (tmp / "home").mkdir()
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HOME=str(tmp / "home"), HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(settings),
               HYIMG_PLUGINS=str(plugins), HYIMG_VIDEO_CACHE=str(tmp / "vcache"), PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(Path.home() / "Library/Caches/ms-playwright"))
    log = open(tmp / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    return {"port": port, "proc": proc, "log": log, "state": state, "frames": frames}


@pytest.fixture
def server(tmp_path):
    s = start(tmp_path / "one", tmp_path)
    yield dict(s, tmp=tmp_path)
    s["proc"].terminate(); s["proc"].wait(5); s["log"].close()


def api(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r:
        return json.load(r)


def open_board(p, engine, port):
    try:
        browser = getattr(p, engine).launch()
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
    page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.src && EL.get('src') && byPath.size >= 4", timeout=20000)
    errors.clear()   # WebKit reports the first load's requests, cancelled by the reload, as errors («… due to access control checks»)
    page.evaluate("() => { cam.x = -100; cam.y = -100; cam.z = .5; renderCam(); render(); }")
    page.wait_for_timeout(300)
    return browser, page, errors


def ctx(page, id):
    it = page.evaluate(f"() => board.items['{id}']")
    at = screen(page, it["x"] + it["w"] / 3, it["y"] + 40)
    page.mouse.click(at[0], at[1], button="right")
    page.wait_for_selector("#ctx.open [data-sub=props-copy]")


def item(page, sel):
    return page.locator(f"#ctx {sel}").bounding_box()


SUBITEMS = "() => [...document.querySelectorAll('#ctx .hy-sub > [role=menuitem], #ctx .hy-sub > .mhint')].map(b => (b.classList.contains('mhint') ? 'hint: ' : '') + (b.querySelector('.ml') || b).textContent.trim() + (b.getAttribute('aria-disabled') ? ' [off: ' + b.title + ']' : ''))"


def wait_saved(page):
    page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)


@pytest.mark.parametrize("engine", ENGINES)
def test_copy_menu_paste_with_live_preview_and_one_undo(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        if server["frames"]: page.wait_for_function("() => HY.props.list().some(d => d.id === 'grade')", timeout=15000)
        ctx(page, "src")
        assert not page.locator("#ctx [role=menuitem]", has_text="colour grade").count()   # the grade's own items are folded into this
        op = item(page, "[data-sub=props-copy]")
        page.mouse.move(op["x"] + 30, op["y"] + op["height"] / 2)
        page.wait_for_function("() => document.querySelector('#ctx .hy-sub')")
        kinds = (["Raw Editor"] if server["frames"] else []) + ["Crop", "Size", "Opacity"]
        # every kind is listed (owner 2026-10-06: «I want users to know what functions exist»), what this picture has not, grey with why
        every = (["Raw Editor", "Mask [off: This picture has no mask]"] if server["frames"] else []) + [
            "Crop", "Size", "Opacity"]   # the kinds a picture can have (the menu by kind, owner 2026-10-07): no time, no PDF page
        assert page.evaluate(SUBITEMS) == ["Custom…"] + every + ["Save as preset…"]
        page.mouse.click(op["x"] + 30, op["y"] + op["height"] / 2)   # the item itself: everything it has
        clip = page.evaluate("() => JSON.parse(localStorage.getItem('cv.propsClip'))")
        assert clip["from"] == "0" and clip["kinds"]["crop"] == [0.1, 0.2, 0.9, 0.8] and clip["kinds"]["opacity"] == 0.5 and clip["kinds"]["size"]["w"] == 300
        assert ("grade" in clip["kinds"]) == bool(server["frames"])
        assert not page.evaluate("() => $('#ctx').classList.contains('open')")
        assert api(port, "/api/propsclip")["kinds"]["crop"] == [0.1, 0.2, 0.9, 0.8]
        # paste onto two pictures and a note: hovering shows it, leaving puts it back
        page.evaluate("() => { sel = new Set(['t1', 't2', 'nt']); render(); }")
        ctx(page, "t1")
        before = page.evaluate("() => JSON.stringify([board.items.t1, board.items.t2, board.items.nt])")
        pp = item(page, "[data-sub=props-paste]")
        page.mouse.move(pp["x"] + 30, pp["y"] + pp["height"] / 2)
        page.wait_for_function("() => board.items.t1.opacity === 0.5 && board.items.t2.crop && board.items.t2.w === 300 && board.items.nt.w === 300")
        assert page.evaluate("() => EL.get('t1').style.opacity") == "0.5" and page.evaluate("() => board.items.nt.opacity") is None   # a note takes no opacity
        page.wait_for_function("() => document.querySelector('#ctx .hy-sub .mhint')")
        sub = page.evaluate(SUBITEMS)
        low = lambda k: k if k[1:2].isupper() or re.search(r"[\s-][A-ZА-ЯЁ][a-zа-яё]", k) else k[0].lower() + k[1:]   # a name («Raw Editor», «PDF page») keeps its case
        assert sub[0] == "hint: from 0: " + ", ".join(low(k) for k in kinds), sub
        assert [k for k in sub[1:] if "[off" not in k] == kinds, sub
        assert ("Mask [off: Not in the clipboard]" in sub) == bool(server["frames"]) and sub[-1].startswith("Presets [off: No presets yet"), sub
        # one kind: only the crop shows
        page.mouse.move(pp["x"] + 30, pp["y"] + pp["height"] / 2 + 2)
        crop = page.locator("#ctx .hy-sub [role=menuitem]", has_text="Crop").bounding_box()
        page.mouse.move(crop["x"] + 20, crop["y"] + crop["height"] / 2, steps=6)
        page.wait_for_function("() => board.items.t1.crop && board.items.t1.opacity === undefined && board.items.t1.w === 200")
        # out of the menu: everything back, nothing saved meanwhile
        page.mouse.move(1350, 850); page.wait_for_timeout(400)
        assert page.evaluate("() => JSON.stringify([board.items.t1, board.items.t2, board.items.nt])") == before
        assert api(port, "/api/board?name=main")["items"]["t1"]["crop"] is None
        # a click keeps it: one undo step for all of them
        page.mouse.move(pp["x"] + 30, pp["y"] + pp["height"] / 2)
        page.mouse.click(pp["x"] + 30, pp["y"] + pp["height"] / 2)
        wait_saved(page)
        b = api(port, "/api/board?name=main")["items"]
        assert b["t1"]["crop"] == [0.1, 0.2, 0.9, 0.8] and b["t1"]["opacity"] == 0.5 and b["t1"]["w"] == 300 and b["t2"]["w"] == 300 and b["nt"]["w"] == 300
        assert ("grade" in b["t1"]) == bool(server["frames"]) and "grade" not in b["nt"] and "opacity" not in b["nt"]
        page.mouse.click(1350, 300); page.keyboard.press("Control+z"); wait_saved(page)
        assert page.evaluate("() => JSON.stringify([board.items.t1, board.items.t2, board.items.nt])") == before
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_greyed_kinds_keys_custom_window_and_presets(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        # ⇧⌥⌘C: the window, every kind the object has checked; untick Size, Copy; the choice is kept
        page.evaluate("() => { sel = new Set(['src']); render(); }")
        page.mouse.move(1350, 850)
        page.keyboard.press("Control+Alt+Shift+KeyC")
        page.wait_for_selector("#propsDlg")
        boxes = page.evaluate("() => [...document.querySelectorAll('#propsDlg [data-k]:not(:disabled)')].map(b => [b.dataset.k, b.checked])")
        assert [k for k, _ in boxes] == (["grade"] if server["frames"] else []) + ["crop", "size", "opacity"] and all(c for _, c in boxes)
        page.locator("#propsDlg label", has_text="Size").click()
        page.locator("#propsDlg [data-a=ok]").click()
        clip = page.evaluate("() => JSON.parse(localStorage.getItem('cv.propsClip'))")
        assert "size" not in clip["kinds"] and "crop" in clip["kinds"]
        page.keyboard.press("Control+Alt+Shift+KeyC"); page.wait_for_selector("#propsDlg")
        assert not page.evaluate("() => document.querySelector('#propsDlg [data-k=size]').checked")
        page.keyboard.press("Escape"); assert not page.evaluate("() => !!document.querySelector('#propsDlg')")
        # ⌥⌘V onto a note only: nothing it holds applies; the submenu lists only what a note can have (its size, not in the clipboard)
        page.evaluate("() => { sel = new Set(['nt']); render(); }")
        ctx(page, "nt")
        pp = item(page, "[data-sub=props-paste]")
        page.mouse.click(pp["x"] + 30, pp["y"] + pp["height"] / 2)   # with a clipboard the item pastes: on a note nothing applies
        wait_saved(page)
        ctx(page, "nt")
        page.mouse.move(pp["x"] + 30, pp["y"] + pp["height"] / 2)
        page.wait_for_function("() => document.querySelector('#ctx .hy-sub')")
        sub = page.evaluate(SUBITEMS)
        assert not any(k.startswith(("Crop", "Opacity", "Raw Editor", "Mask")) for k in sub) and "Size [off: Not in the clipboard]" in sub, sub
        page.keyboard.press("Escape"); page.keyboard.press("Escape")
        # ⌥⌘C / ⌥⌘V by keys: everything from src onto plain
        page.evaluate("() => { sel = new Set(['src']); render(); }")
        page.keyboard.press("Control+Alt+KeyC")
        page.evaluate("() => { sel = new Set(['plain']); render(); }")
        page.keyboard.press("Control+Alt+KeyV"); wait_saved(page)
        b = api(port, "/api/board?name=main")["items"]
        assert b["plain"]["crop"] == [0.1, 0.2, 0.9, 0.8] and b["plain"]["opacity"] == 0.5
        assert b["plain"]["x"] == 0 and b["plain"]["y"] == 700   # the place is not a property
        # a preset: saved from the copy submenu's window with a name, put on from «Presets ›», previewed on hover
        page.evaluate("() => { sel = new Set(['src']); render(); }")
        ctx(page, "src")
        op = item(page, "[data-sub=props-copy]")
        page.mouse.move(op["x"] + 30, op["y"] + op["height"] / 2)
        page.locator("#ctx .hy-sub [role=menuitem]", has_text="Save as preset…").click()
        page.wait_for_selector("#propsDlg .pdn")
        page.locator("#propsDlg label", has_text="Size").click()   # the last choice had Size off: now on again
        page.fill("#propsDlg .pdn", "Warm look")
        page.keyboard.press("Enter")
        page.wait_for_function("() => !document.querySelector('#propsDlg')")
        for _ in range(30):
            pr = api(port, "/api/presets")["presets"]
            if pr: break
            time.sleep(0.1)
        assert pr[0]["name"] == "Warm look" and set(pr[0]["kinds"]) >= {"crop", "size", "opacity"}
        page.evaluate("() => { sel = new Set(['t2']); render(); }")
        ctx(page, "t2")
        pp = item(page, "[data-sub=props-paste]")
        page.mouse.move(pp["x"] + 30, pp["y"] + pp["height"] / 2)
        page.wait_for_function("() => document.querySelector('#ctx .hy-sub [data-sub=presets]')")
        pr = page.locator("#ctx .hy-sub [data-sub=presets]").bounding_box()
        page.mouse.move(pr["x"] + 20, pr["y"] + pr["height"] / 2, steps=8)
        page.wait_for_function("() => [...document.querySelectorAll('#ctx .hy-sub .hy-sub [role=menuitem]')].some(b => b.textContent.trim() === 'Warm look')")
        wl = page.locator("#ctx .hy-sub .hy-sub [role=menuitem]", has_text="Warm look").bounding_box()
        page.mouse.move(pr["x"] + pr["width"] - 10, pr["y"] + pr["height"] / 2, steps=3)
        page.mouse.move(wl["x"] + 20, wl["y"] + wl["height"] / 2, steps=4)
        page.wait_for_function("() => board.items.t2.w === 300 && board.items.t2.opacity === 0.5")   # its look on hover
        page.mouse.click(wl["x"] + 20, wl["y"] + wl["height"] / 2); wait_saved(page)
        assert api(port, "/api/board?name=main")["items"]["t2"]["opacity"] == 0.5
        assert not errors, errors
        browser.close()


@pytest.mark.skipif(not FFMPEG, reason="no ffmpeg for the test videos")
@pytest.mark.parametrize("engine", ENGINES)
def test_time_goes_to_a_shorter_video_up_to_its_end(server, engine):
    port = server["port"]
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, port)
        page.wait_for_function("() => (byPath.get('a/v3.mp4') || {}).duration > 0", timeout=20000)
        page.evaluate("() => { sel = new Set(['v7']); render(); }")
        page.keyboard.press("Control+Alt+KeyC")
        assert page.evaluate("() => JSON.parse(localStorage.getItem('cv.propsClip')).kinds.trim") == [1, 6]
        page.evaluate("() => { sel = new Set(['v3', 'plain']); render(); }")
        page.keyboard.press("Control+Alt+KeyV"); wait_saved(page)
        b = api(port, "/api/board?name=main")["items"]
        assert b["v3"]["trim"][0] == 1 and abs(b["v3"]["trim"][1] - 3) < 0.15, b["v3"]   # up to its end
        assert "trim" not in b["plain"]
        assert not errors, errors
        browser.close()


def test_the_clipboard_goes_to_another_project(server, tmp_path):
    two = start(tmp_path / "two", tmp_path, items={"schema": 1, "revision": 1, "items": {"x": {"path": "a/0.png", "x": 0, "y": 0, "w": 100, "ar": 1, "crop": None}}, "groups": {}, "removed": {}})
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, "chromium", server["port"])
            page.evaluate("() => { sel = new Set(['src']); render(); }")
            page.keyboard.press("Control+Alt+KeyC")
            page.wait_for_timeout(300)
            other = browser.new_page()
            other.goto(f"http://127.0.0.1:{two['port']}/canvas.html")
            other.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.x")
            other.wait_for_function("() => { const c = JSON.parse(localStorage.getItem('cv.propsClip') || 'null'); return c && c.from === '0' && c.kinds.opacity === 0.5; }", timeout=5000)
            other.evaluate("() => { sel = new Set(['x']); render(); }")
            other.keyboard.press("Control+Alt+KeyV")
            other.wait_for_function("() => board.items.x.opacity === 0.5")
            browser.close()
    finally:
        two["proc"].terminate(); two["proc"].wait(5); two["log"].close()


def hy(port, *args):
    r = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--port", str(port), *args], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_hy_props(server):
    port = server["port"]
    out = hy(port, "--page", "main", "do", "props from=src to=t1,nt only=crop,opacity,grade", "--quiet")
    b = api(port, "/api/board?name=main")["items"]
    assert b["t1"]["crop"] == [0.1, 0.2, 0.9, 0.8] and b["t1"]["opacity"] == 0.5 and b["t1"]["grade"] == GRADE and b["t1"]["w"] == 200
    assert "opacity" not in b["nt"] and "grade" not in b["nt"] and "crop" not in b["nt"]
    assert "не подошло" in out, out
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/presets", data=json.dumps({"name": "Half", "kinds": {"opacity": 0.3, "size": {"w": 120, "h": 1}}}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req).read()
    assert json.loads((server["state"] / "presets.json").read_text())["presets"][0]["name"] == "Half"
    hy(port, "--page", "main", "do", "props preset=half to=t2", "--quiet")
    b = api(port, "/api/board?name=main")["items"]
    assert b["t2"]["opacity"] == 0.3 and b["t2"]["w"] == 120


def test_a_mask_goes_to_another_project_with_its_file(tmp_path):
    """a value that refers to a library file (the frames plugin's mask, its png) brings the file along: the copy keeps its bytes beside
    the clipboard, a paste in another project writes it into that library (at the same path when free, else under a name of its own) and
    the pasted value refers to the copy there"""
    mask = "frames/board-masks/masks/mA.png"
    one = start(tmp_path / "one", tmp_path, items={"schema": 1, "revision": 1, "removed": {}, "groups": {},
                "items": {"src": {"path": "a/0.png", "x": 0, "y": 0, "w": 200, "ar": 1, "crop": None, "mask": {"file": mask}}}})
    two = start(tmp_path / "two", tmp_path, items={"schema": 1, "revision": 1, "removed": {}, "groups": {},
                "items": {"x": {"path": "a/0.png", "x": 0, "y": 0, "w": 100, "ar": 1, "crop": None}}})
    try:
        if not one["frames"]: pytest.skip("no hyimg-frames repository beside this one")
        src_png, other_png = png(30, 30), png(31, 30)
        for d, data in ((tmp_path / "one/lib", src_png), (tmp_path / "two/lib", other_png)):   # project two has another file at that path
            (d / mask).parent.mkdir(parents=True); (d / mask).write_bytes(data)
        with playwright.sync_playwright() as p:
            try: browser = p.chromium.launch()
            except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{one['port']}/canvas.html")
            page.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.src && HY.props.list().some(d => d.id === 'mask')", timeout=20000)
            page.evaluate("() => { sel = new Set(['src']); render(); }")
            page.keyboard.press("Control+Alt+KeyC")
            page.wait_for_timeout(500)
            other = browser.new_page()
            other.goto(f"http://127.0.0.1:{two['port']}/canvas.html")
            other.wait_for_function("() => typeof BOARD !== 'undefined' && board.items.x && HY.props.list().some(d => d.id === 'mask')", timeout=20000)
            other.wait_for_function("() => { const c = JSON.parse(localStorage.getItem('cv.propsClip') || 'null'); return c && c.kinds.mask; }", timeout=5000)
            other.evaluate("() => { sel = new Set(['x']); render(); }")
            other.keyboard.press("Control+Alt+KeyV")
            other.wait_for_function("() => board.items.x.mask && board.items.x.mask.file", timeout=5000)
            got = other.evaluate("() => board.items.x.mask.file")
            assert got != mask and got.startswith("frames/board-masks/masks/mA-"), got   # the path there was taken by another file
            assert (tmp_path / "two/lib" / got).read_bytes() == src_png and (tmp_path / "two/lib" / mask).read_bytes() == other_png
            # pasted again in the same project: the file it already brought is used, nothing new is written
            other.evaluate("() => { board.items.x.mask = null; delete board.items.x.mask; }")
            other.keyboard.press("Control+Alt+KeyV")
            other.wait_for_function("() => board.items.x.mask && board.items.x.mask.file", timeout=5000)
            assert other.evaluate("() => board.items.x.mask.file") == got
            assert len(list((tmp_path / "two/lib/frames/board-masks/masks").iterdir())) == 2
            # and in the project it came from, the path stays as it was
            page.evaluate("() => { board.items.src.mask = null; delete board.items.src.mask; sel = new Set(['src']); render(); }")
            page.keyboard.press("Control+Alt+KeyV")
            page.wait_for_function("() => board.items.src.mask && board.items.src.mask.file", timeout=5000)
            assert page.evaluate("() => board.items.src.mask.file") == mask
            browser.close()
    finally:
        for s in (one, two): s["proc"].terminate(); s["proc"].wait(5); s["log"].close()
