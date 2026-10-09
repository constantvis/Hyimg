"""A board open in the browser while an agent writes through hy.py and while a Dropbox conflicted copy appears (review/merge.py,
ui/merge.js; owner 2026-10-08: «Две правки одной доски с двух Маков могут перезаписать друг друга. Сделать слияние по объектам? — да»).
Changes to different things or different fields both stay; the same field: the newer change wins and a conflict record is kept;
the page keeps its selection, its camera and a drag under the mouse; a conflicted copy is merged and put away.
What the page shows (owner 2026-10-09 on r12/docs-merge.html: «6 версия отличная»): an agent's save merged gives no toast, the things it
changed glow in its colour with its name, its face is in the top row by History and History keeps a dot; a real clash gives one toast.
Chromium, dark theme, a temporary project. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


def note(x, text):
    return {"type": "note", "text": text, "x": x, "y": 600, "w": 300, "h": 0, "fs": 24, "size": 2, "color": "yellow", "reach": None, "to": []}


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"merge-{name}.png"))


def hy(port, script):
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}, "HYIMG_AGENT": "claude"}
    r = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "--port", str(port), "--quiet", "--label", "test", "do", script],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def get(port, path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10).read())


@pytest.fixture
def project(tmp_path):
    gen = run_server(tmp_path); port = next(gen)
    boards = tmp_path / "state" / "boards"
    b = json.loads((boards / "main.json").read_text())
    b["items"].update(n1=note(0, "One"), n2=note(500, "Two"))
    (boards / "main.json").write_text(json.dumps(b))
    yield port, boards
    next(gen, None)


def test_a_board_open_in_the_browser_merges_hy_py_and_a_dropbox_copy(project):
    port, boards = project
    disk = lambda: json.loads((boards / "main.json").read_text())
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.cam.main', JSON.stringify({x: -40, y: -40, z: .5})); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BASE && Object.keys(board.items).length === 8", timeout=20000)
        page.evaluate("() => { sel = new Set(['i3']); render(); }")
        cam = page.evaluate("() => ({ ...cam })")
        # an edit here not saved yet; the live board's poll held back (BASE), so the save itself meets the agent's version
        hold = "() => { BASE = null; dirty = true; lastEdit = Date.now(); }"
        # every toast of the page, with its kind
        page.evaluate("() => { window.__toasts = []; const o = window.hyToast; window.hyToast = (t, k, x) => { __toasts.push([t, k]); return o(t, k, x); }; }")

        # 1. the owner moves n1 here; the agent moves n2 and paints n1 red: different things and fields, all of it stays
        page.evaluate("() => { board.items.n1.x = 1500; board.items.n1.y = 700; }"); page.evaluate(hold)
        hy(port, "move n2 x=2000 y=600; set n1 color=red")
        assert page.evaluate("() => save()") is True
        b = disk()
        assert (b["items"]["n1"]["x"], b["items"]["n1"]["y"], b["items"]["n1"]["color"], b["items"]["n2"]["x"]) == (1500, 700, "red", 2000)
        assert page.evaluate("() => [board.items.n1.x, board.items.n1.color, board.items.n2.x, board.revision === %d]" % b["revision"]) == [1500, "red", 2000, True]
        assert page.evaluate("() => [...sel]") == ["i3"] and page.evaluate("() => ({ ...cam })") == cam
        assert not [e for e in get(port, "/api/events?name=main") if e["kind"] == "merge"]
        # quietly: no toast; n1 and n2 ringed in Claude's colour with «Claude» on them, Claude's face by History, History's dot
        glow = page.evaluate("""() => [...document.querySelectorAll('#hyMergeGlow .hy-mg')].map(g => ({ id: g.dataset.id, name: g.textContent,
          ring: getComputedStyle(g).outlineColor, warn: g.classList.contains('warn') }))""")
        assert sorted(g["id"] for g in glow) == ["n1", "n2"] and all(g["name"] == "Claude" and not g["warn"] for g in glow), glow
        claude = page.evaluate("() => { const d = document.createElement('i'); d.style.color = 'var(--hy-ag-claude)'; document.body.append(d); "
                               "const c = getComputedStyle(d).color; d.remove(); return c; }")
        assert {g["ring"] for g in glow} == {claude}
        page.wait_for_function("() => [...document.querySelectorAll('#hyMergeGlow .hy-mg')].every(g => getComputedStyle(g).opacity === '1')")
        face = page.evaluate("""() => { const f = document.getElementById('hyMergeFace'), r = f.getBoundingClientRect(), h = document.getElementById('bhist').getBoundingClientRect(),
          k = document.getElementById('bkeys').getBoundingClientRect(), a = f.querySelector('hy-avatar');
          return { on: document.documentElement.classList.contains('hy-mface-on'), agent: a && a.getAttribute('agent'), w: r.width, gap: h.left - r.right,
            keys: r.left - k.right, top: r.top - h.top }; }""")
        assert face["on"] and face["agent"] == "claude" and face["w"] == 38 and face["top"] == 0, face
        page.wait_for_function("() => { const f = document.getElementById('hyMergeFace').getBoundingClientRect(), k = document.getElementById('bkeys').getBoundingClientRect(); "
                               "return Math.abs(f.left - k.right - 8) < 1 && getComputedStyle(document.getElementById('hyMergeFace')).opacity === '1'; }")
        assert abs(face["gap"] - 8) < 1, face
        assert page.evaluate("() => document.getElementById('bhist').classList.contains('hy-mdot-on')")
        page.hover("#bhist")
        assert page.evaluate("() => document.querySelector('#bhist .hy-mhv').innerText") == "Claude merged 2 changes · just now"
        shot(page, "1-merged")
        assert page.evaluate("() => __toasts") == [], page.evaluate("() => __toasts")
        assert "Merged changes" not in page.evaluate("() => document.body.innerText")
        page.wait_for_function("() => !document.documentElement.classList.contains('hy-mface-on') && !document.querySelector('#hyMergeGlow .hy-mg')", timeout=6000)
        assert page.evaluate("() => document.getElementById('bhist').classList.contains('hy-mdot-on')")   # the dot stays until History opens
        page.click("#bhist"); page.click("#bhist")
        assert not page.evaluate("() => document.getElementById('bhist').classList.contains('hy-mdot-on')")

        # 2. the same field, the agent's change newer: it wins, the owner's position is in a conflict record and in History
        page.evaluate("() => { board.items.n2.x = 2600; }"); page.evaluate(hold)
        time.sleep(0.05); hy(port, "move n2 x=3000 y=600")
        assert page.evaluate("() => save()") is True
        assert disk()["items"]["n2"]["x"] == 3000 and page.evaluate("() => board.items.n2.x") == 3000
        ev = [e for e in get(port, "/api/events?name=main") if e["kind"] == "merge"]
        assert len(ev) == 1 and ev[0]["ids"] == ["n2"] and ev[0]["conflicts"][0]["lost"] == {"x": 2600, "y": 600}
        assert ev[0]["conflicts"][0]["kept_by"]["via"] == "claude"
        lost = next(h for h in get(port, "/api/history?name=main") if h.get("merge") == "ours")
        assert lost["label"] == "2 changes to the same thing merged; kept Claude's position"
        assert get(port, f"/api/history/board?name=main&id={lost['id']}")["items"]["n2"]["x"] == 2600
        # a real clash: one toast, amber, with Show; Show selects n2, brings it into view and rings it amber
        assert page.evaluate("() => __toasts") == [["You and Claude changed «Two»: theirs is kept", "warn"]]
        page.wait_for_selector("#hyToasts .ht.warn .ab")
        shot(page, "2-clash")
        page.click("#hyToasts .ht.warn .ab")
        assert page.evaluate("() => [...sel]") == ["n2"]
        assert page.evaluate("() => !!document.querySelector('#hyMergeGlow .hy-mg.warn[data-id=n2]')")
        page.evaluate("c => { cam = c; sel = new Set(); render(); }", cam)   # back where the steps below expect the board
        page.click("#bhist"); page.wait_for_function("() => /Changes merged/.test(document.querySelector('#evList').innerText)")
        shot(page, "2-conflict-in-history"); page.click("#bhist")

        # 3. the same field, the owner's change newer: his position wins
        hy(port, "move n1 x=100 y=600")
        page.evaluate("() => { board.items.n1.x = 4000; }"); page.evaluate(hold)
        assert page.evaluate("() => save()") is True
        assert disk()["items"]["n1"]["x"] == 4000 and disk()["items"]["n1"]["color"] == "red"
        assert page.evaluate("() => __toasts")[1:] == [["You and Claude changed «One»: yours is kept", "warn"]]   # a clash again: its one toast

        # 4. a merged save arrives while a picture is being dragged: the drag goes on and ends where the mouse lets go
        page.evaluate("() => { board.items.n1.text = 'One more'; }"); page.evaluate(hold)
        hy(port, "move n2 x=3300 y=600")
        r = page.evaluate("() => { const e = document.querySelector('.it[data-id=i0]').getBoundingClientRect(); return [e.x + e.width / 2, e.y + e.height / 2]; }")
        x0 = page.evaluate("() => board.items.i0.x")
        page.mouse.move(*r); page.mouse.down(); page.mouse.move(r[0] + 40, r[1] + 10, steps=4)
        assert page.evaluate("() => save()") is True   # the answer comes in the middle of the drag
        page.mouse.move(r[0] + 100, r[1] + 10, steps=6); page.mouse.up()
        page.wait_for_function("() => !dirty && !saveT && !saveFlight", timeout=10000)
        b = disk()
        assert round(b["items"]["i0"]["x"] - x0) == 200 and b["items"]["n2"]["x"] == 3300 and b["items"]["n1"]["text"] == "One more"
        assert page.evaluate("() => board.items.i0.x") == b["items"]["i0"]["x"]
        assert len(page.evaluate("() => __toasts")) == 2   # a merged save of the agent without a clash: no toast

        # 5. a Dropbox conflicted copy from the other Mac: merged into the page, the page shows it, the copy is put away
        b = disk(); copy = json.loads(json.dumps(b))
        copy.update(revision=b["revision"] + 1, vid="othermac1", parent=f"{b['vid']}~{b['revision']}", by={"via": "app"}, edited=time.time())
        copy["items"]["k1"] = note(5000, "from the other Mac"); copy["items"]["n2"]["color"] = "blue"
        name = "main (Partner's conflicted copy 2026-10-08).json"
        (boards / name).write_text(json.dumps(copy)); os.utime(boards / name, (time.time() - 10, time.time() - 10))
        page.wait_for_function("() => board.items.k1 && board.items.n2.color === 'blue'", timeout=20000)
        b = disk()
        assert b["items"]["k1"]["text"] == "from the other Mac" and b["items"]["n2"]["x"] == 3300 and b["items"]["i0"]["x"] == x0 + 200
        assert not (boards / name).exists() and (boards / "_history" / "main" / "dropbox" / name).exists()
        assert any(e["kind"] == "dropbox" and e["file"] == name for e in get(port, "/api/events?name=main"))
        shot(page, "3-dropbox-copy")
        assert errors == []
        browser.close()


def test_this_macs_agent_glows_in_the_persons_colour_with_its_own_name(project):
    """the board's person (profile.json beside the settings, people.py): the agent writes for him, so its ring is his colour and its
    name is the agent's alone (his own «Claude»), his face with Claude's badge comes by History; still no toast"""
    port, boards = project
    (boards.parents[1] / "profile.json").write_text(json.dumps({"id": "0a0a0a0a-1111-2222-3333-444444444444", "name": "Ann", "color": "orange", "created": "2026-10-09"}))
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900}, color_scheme="dark")
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{port}/canvas.html"
        page.goto(url); page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && BASE && Object.keys(board.items).length === 8", timeout=20000)
        page.wait_for_function("() => window.hyWhoOf && hyWhoOf({ person: '0a0a0a0a-1111-2222-3333-444444444444' }).me")
        page.evaluate("() => { window.__toasts = []; const o = window.hyToast; window.hyToast = (t, k, x) => { __toasts.push([t, k]); return o(t, k, x); }; }")
        page.evaluate("() => { board.items.n1.x = 1500; BASE = null; dirty = true; lastEdit = Date.now(); }")
        hy(port, "move n2 x=2000 y=600")
        assert page.evaluate("() => save()") is True
        g = page.evaluate("() => [...document.querySelectorAll('#hyMergeGlow .hy-mg')].map(g => [g.dataset.id, g.textContent, getComputedStyle(g).outlineColor])")
        assert g == [["n2", "Claude", "rgb(245, 154, 61)"]], g   # HY_COLORS.orange
        a = page.evaluate("() => { const a = document.querySelector('#hyMergeFace hy-avatar'); return [a.getAttribute('agent'), a.getAttribute('name')]; }")
        assert a == ["claude", "Ann"]
        assert page.evaluate("() => getComputedStyle(document.querySelector('#bhist .hy-mdot')).backgroundColor") == "rgb(245, 154, 61)"
        assert page.evaluate("() => __toasts") == [] and errors == []
        browser.close()
