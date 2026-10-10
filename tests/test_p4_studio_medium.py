"""The Studios' П4 medium findings that live in Hyimg itself (2026-10-10, docs/process.md §4, §5) and the owner's decisions of that day,
with two fake Studios in place of the plugins (they have their own tests and tests/test_p4_studio_keys.py runs them all). Chromium, dark
theme, our own temporary servers and folders, never the ports 4180–4184. Each fails on the code before.

  S-31  a Studio whose leave writes for a while (a slow Save) is waited for: the other Studio opens after it, not never
  S-61  a Studio's card is flown into the board's free part between the Studio's panels as it opens, and back as it closes
  S-29  the Hint bar as a Studio opens: V Select, C Annotation, its own keys, Esc / ⌘↵ with its primary action's word
  pins  the board's annotation pin is Hyimg's one pin (ui/hy/apin.css): its bottom left corner is sharp and stands on the spot"""
import pytest

import test_p4_board as B
from test_p4_board import board_page, box, browser_of, playwright, serve

# two Studios: «slow» leaves after a 4.5 s write, «fast» at once; both put two side panels (data-hyui) beside the board
FAKE = r"""
let open = null;
const panels = () => { for (const side of ["left", "right"]) { const p = document.createElement("div"); p.className = "fkp"; p.dataset.hyui = "";
  p.style.cssText = `position:fixed;${side}:12px;top:70px;bottom:80px;width:260px;background:#222;z-index:60`; document.body.appendChild(p); } };
const shut = () => { document.querySelectorAll(".fkp").forEach(p => p.remove()); open = null; HY.modeChanged(); };
let HY;
export function register(hy) {
  HY = hy;
  HY.register("fake", { render(el) { if (!el.firstChild) el.innerHTML = '<div style="position:absolute;inset:0;background:#2a6"></div>'; }, dblclick(id) { go("slow", id); } });
  const go = (k, id) => { open = { k, id }; panels(); HY.modeChanged(); };
  const def = (k, order, wait) => ({ label: k, order, icon: "<svg width=16 height=16></svg>", title: k, hint: "Select a fake card", isOpen: () => !!open && open.k === k,
    card: () => open && open.id, target: ids => ids.length === 1 && HY.board.items[ids[0]] && HY.board.items[ids[0]].type === "fake" ? ids[0] : null,
    enter: id => go(k, id), leave: () => new Promise(ok => setTimeout(() => { shut(); ok(); }, wait)), primary: k === "slow" ? "Save" : "Done",
    hints: [{ id: "own", keys: ["b"], t: "Brush" }] });
  HY.mode("slow", def("slow", 5, 4500)); HY.mode("fast", def("fast", 6, 0));
}
"""


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(B, "FAKE", FAKE)


def items():
    return {"f1": {"type": "fake", "x": 400, "y": 300, "w": 300, "h": 200}, "i0": B.pic(0, 0)}


def test_leaving_waits_camera_flies_and_the_hint_bar(tmp_path, fake):
    with serve(tmp_path, items(), plugin=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        page.wait_for_function("() => window.MODES && document.querySelector('.plg[data-id=f1]')", timeout=10000)
        ev("() => { localStorage.setItem('cv.keyhint', 'always'); sel = new Set(['f1']); render(); }"); page.wait_for_timeout(200)
        cam0 = ev("() => [cam.x, cam.y, cam.z]")
        ev("() => MODES.enter('slow', ['f1'])"); page.wait_for_function("() => MODES.open === 'slow'"); page.wait_for_timeout(1500)
        # S-29: the Hint bar
        h = ev("() => [...document.querySelectorAll('hy-keyhint')].map(x => x.textContent).join(' ')")
        for w in ("Select", "Annotation", "Brush", "Esc", "Save"): assert w in h, (w, h)
        # S-61: the card between the panels
        c, panes = box(page, ".plg[data-id=f1]"), ev("() => [...document.querySelectorAll('.fkp')].map(p => { const r = p.getBoundingClientRect(); return [r.left, r.right]; })")
        l, r = min(panes), max(panes)
        assert c["x"] >= l[1] - 1 and c["x"] + c["w"] <= r[0] + 1 and c["w"] > 300, (c, panes)
        # S-31: to the other Studio through a 4.5 s leave: it opens once the first is gone
        ev("() => MODES.enter('fast', ['f1'])"); page.wait_for_timeout(5500)
        assert ev("() => MODES.open") == "fast", "the second Studio gave up on a slow leave"
        # leaving: the board's camera back as it was
        ev("() => MODES.enter('board')"); page.wait_for_function("() => MODES.open === 'board'"); page.wait_for_timeout(900)
        cam1 = ev("() => [cam.x, cam.y, cam.z]")
        assert abs(cam1[2] - cam0[2]) < 1e-3, (cam0, cam1)
        assert not errors, errors
        browser.close()


def test_the_board_pin_stands_on_its_spot(tmp_path, fake):
    with serve(tmp_path, items(), plugin=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        page.wait_for_function("() => window.hyComments && window.hyAnnot")
        ev("() => hyAnnot.api('/api/comments', { op: 'new', name: BOARD, anchor: null, at: [900, 120], text: 'Here' }).then(() => hyComments.load())")
        page.wait_for_selector("#cmpins .cmpin", timeout=8000); page.wait_for_timeout(300)
        pin = ev("""() => { const b = document.querySelector('#cmpins .cmpin'), r = b.getBoundingClientRect(), s = document.getElementById('stage').getBoundingClientRect(),
          c = getComputedStyle(b); return { cls: b.className, x: r.left, y: r.bottom, sx: s.left + (900 - cam.x) * cam.z, sy: s.top + (120 - cam.y) * cam.z,
            bl: c.borderBottomLeftRadius, tl: c.borderTopLeftRadius }; }""")
        assert "hy-apin" in pin["cls"], pin
        assert abs(pin["x"] - pin["sx"]) <= 1 and abs(pin["y"] - pin["sy"]) <= 1, pin
        assert float(pin["bl"].replace("px", "")) <= 3 < float(pin["tl"].replace("px", "")), pin
        assert not errors, errors
        browser.close()
