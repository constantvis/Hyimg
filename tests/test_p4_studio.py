"""The Studios' П4 logic audit of 2026-10-10, the rules that live in Hyimg itself (docs/process.md §4, §5): one regression test each, every
one failing on the code before the fix. A fake Studio stands in for the plugins (they have their own tests); Chromium, dark theme, our own
temporary servers and folders, never the ports 4180–4184.

  S-03  «Close without saving?» (ui/confirm.js with save): the safe answer has the focus and ↵, ⌘↵ saves, Tab stays inside, the focus
        comes back after it; a plain question still takes ↵ as its action
  S-06  the board's keys wait while a Studio is open, also those the Studio does not take (L, 3, ⇧1, ⌘A, ⌘D, ⌘X)
  S-08  the board around an open Studio is inert: a press does not pick or move another card, a file dropped makes nothing and says why
  S-09  a page switch asks the open Studio to leave first, and stays when the Studio stays
  S-13  ⌘Z in a Studio is the Studio's, an annotation made there stays
  S-15  a checkbox or a slider touched with the mouse leaves the keys working"""
import pytest

import test_p4_board as B
from test_p4_board import board_page, box, browser_of, pic, playwright, serve, threads, wait

# a Studio that takes only its own keys, as hyimg-3d-studio and hyimg-dev-studio do: Esc leaves (asking first when __ask is set), ⌘Z is
# counted, every other key it leaves alone
FAKE = r"""
let open = null; window.__studioUndo = 0;
export function register(HY) {
  HY.register("fake", {
    render(el) { if (!el.firstChild) el.innerHTML = '<div style="position:absolute;inset:0;background:#2a6"></div>'; },
    dblclick(id) {
      open = id; HY.dock(Object.assign(document.createElement("span"), { innerHTML: '<button data-a="done">Done</button>', onclick: () => close() })); HY.modeChanged();
    },
    onKey(e) {
      if (!open) return false; if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); __studioUndo++; return true; }
      if (e.key === "Escape") { leave(); return true; } return false;
    },
  });
  const close = () => { open = null; HY.dock(null); HY.modeChanged(); };
  const leave = () => window.__ask ? import("/ui/confirm.js").then(m => m.hyConfirm({ title: "Leave?", ok: "Leave", cancel: "Stay", onOk: close })) : close();
  HY.mode("fake", { fit: false, label: "Fake", order: 5, icon: "<svg width=16 height=16></svg>", title: "Fake", hint: "Select a fake card", isOpen: () => !!open,
    target: ids => ids.length === 1 && HY.board.items[ids[0]] && HY.board.items[ids[0]].type === "fake" ? ids[0] : null, enter: id => PLG.fake.dblclick(id), leave });
}
"""
STATE = """() => JSON.stringify([Object.keys(board.items).sort(), Object.values(board.items).map(i => [Math.round(i.x), Math.round(i.y), i.opacity ?? 1]),
  [...sel].sort(), Object.keys(board.groups).length, [Math.round(cam.x), Math.round(cam.y), +cam.z.toFixed(3)], past.length])"""


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(B, "FAKE", FAKE)


def items():
    out = {f"i{n}": pic(n, n * 340) for n in range(3)}
    out["f1"] = {"type": "fake", "x": 0, "y": 600, "w": 480, "h": 300}
    return out


def studio(page):
    page.wait_for_function("() => window.MODES && document.querySelector('.plg[data-id=f1]')", timeout=10000)
    f = box(page, ".plg[data-id=f1]"); page.mouse.dblclick(f["cx"], f["cy"])
    page.wait_for_function("() => MODES.open === 'fake'")
    page.mouse.move(5, 5)


def test_s06_s08_s15_the_board_around_a_studio_stays_still(tmp_path, fake):
    with serve(tmp_path, items(), plugin=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        studio(page); s0 = ev(STATE)
        # S-06: keys the Studio does not take wait too
        for k in ("l", "3", "Shift+Digit1", "Meta+a", "Meta+d", "Meta+x", "n", "g"):
            page.keyboard.press(k); page.wait_for_timeout(150)
            assert ev(STATE) == s0, f"{k} changed the board behind the Studio"
        # S-08: a press on another card neither picks nor moves it; a double click on the board makes nothing; a dropped file neither
        r = box(page, '.it[data-id="i1"]'); page.mouse.click(r["cx"], r["cy"]); page.wait_for_timeout(150)
        page.mouse.move(r["cx"], r["cy"]); page.mouse.down(); page.mouse.move(r["cx"] + 120, r["cy"] + 60, steps=6); page.mouse.up(); page.wait_for_timeout(200)
        page.mouse.dblclick(1200, 300); page.wait_for_timeout(300)
        assert ev(STATE) == s0, "the board around the Studio answered a press"
        ev("""() => { const dt = new DataTransfer(); dt.items.add(new File([new Uint8Array([137, 80, 78, 71])], 'x.png', { type: 'image/png' }));
          for (const t of ['dragenter', 'dragover', 'drop']) stage.dispatchEvent(new DragEvent(t, { dataTransfer: dt, bubbles: true, cancelable: true, clientX: 1100, clientY: 300 })); }""")
        page.wait_for_timeout(800)
        assert ev(STATE) == s0 and any("is open" in t for t in ev("() => TL")), ev("() => TL")
        assert ev("() => MODES.open") == "fake"
        # back on the board the keys and presses are the board's again
        page.keyboard.press("Escape"); page.wait_for_function("() => MODES.open === 'board'")
        page.mouse.click(r["cx"], r["cy"]); page.wait_for_function("() => sel.has('i1')")
        # S-15: a checkbox touched with the mouse leaves the keys working
        ev("() => { const c = document.createElement('input'); c.type = 'checkbox'; c.id = 'tcb'; c.style.cssText = 'position:fixed;left:300px;top:20px;z-index:999'; document.body.appendChild(c); }")
        page.click("#tcb"); page.wait_for_timeout(100)
        n0 = ev("() => Object.keys(board.items).length"); page.keyboard.press("l"); page.wait_for_timeout(300)
        assert ev("() => Object.keys(board.items).length") == n0 + 1, "a key after a checkbox did nothing"
        assert not errors, errors
        browser.close()


def test_s09_a_page_switch_asks_the_studio_first(tmp_path, fake):
    with serve(tmp_path, items(), plugin=True, pages=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        page.wait_for_function("() => typeof pages !== 'undefined' && pages.length === 2", timeout=10000)
        # the Studio asks, the person stays: the page stays, the Studio open
        studio(page); ev("() => { window.__ask = true; }")
        ev("() => { window.__sw = switchPage('p2'); }")
        page.wait_for_selector("#hyConfirm.on"); page.keyboard.press("Escape")
        ev("() => window.__sw"); page.wait_for_timeout(200)
        assert ev("() => [BOARD, MODES.open]") == ["main", "fake"]
        # it asks, the person leaves: then the page changes
        ev("() => { window.__sw = switchPage('p2'); }")
        page.wait_for_selector("#hyConfirm.on"); page.click("#hyConfirm [data-a=ok]")
        ev("() => window.__sw"); page.wait_for_function("() => BOARD === 'p2'")
        assert ev("() => MODES.open") == "board"
        assert not errors, errors
        browser.close()


def test_s03_the_question_and_s13_an_annotation_in_a_studio(tmp_path, fake):
    with serve(tmp_path, items(), plugin=True) as (port, _), playwright.sync_playwright() as p:
        browser = browser_of(p); page, errors = board_page(browser, port); ev = page.evaluate
        ev("() => import('/ui/confirm.js')")
        ev("() => { window.__A = []; window.__q = () => hyConfirm({ title: 'Close without saving?', ok: 'Discard', cancel: 'Keep editing', onOk: () => __A.push('discard'),"
           " onCancel: () => __A.push('keep'), save: { label: 'Save', run: () => __A.push('save') } }); }")
        ev("() => __q()"); page.wait_for_selector("#hyConfirm.on"); page.wait_for_timeout(120)
        assert ev("() => document.activeElement.dataset.a") == "no"
        for _ in range(5):
            page.keyboard.press("Tab"); assert ev("() => !!document.activeElement.closest('#hyConfirm')"), "Tab left the question"
        ev("() => document.querySelector('#hyConfirm [data-a=no]').focus()"); page.keyboard.press("Enter"); page.wait_for_timeout(300)
        ev("() => __q()"); page.wait_for_selector("#hyConfirm.on"); page.wait_for_timeout(120); page.keyboard.press("Meta+Enter"); page.wait_for_timeout(300)
        ev("() => __q()"); page.wait_for_selector("#hyConfirm.on"); page.wait_for_timeout(120); page.keyboard.press("Escape"); page.wait_for_timeout(300)
        assert ev("() => __A") == ["keep", "save", "keep"], ev("() => __A")
        # a plain question keeps ↵ as its action
        ev("() => hyConfirm({ title: 'Clear?', ok: 'Clear', onOk: () => __A.push('ok') })"); page.wait_for_selector("#hyConfirm.on"); page.wait_for_timeout(120)
        page.keyboard.press("Enter"); page.wait_for_timeout(300)
        assert ev("() => __A")[-1] == "ok"
        # S-13: an annotation made in the Studio, then ⌘Z there: the Studio's step, the annotation stays
        studio(page)
        page.keyboard.press("c"); r = box(page, '.it[data-id="i1"]'); page.mouse.click(r["x"] + 80, r["y"] + 90)
        if ev("() => !!document.querySelector('#cmthread.open textarea')"):
            page.keyboard.type("in the studio"); page.keyboard.press("Enter"); wait(lambda: len(threads(port)) == 1, "the annotation was sent")
        else:   # the board around is inert: the annotation made through the board's own way, as a Studio's annotations are
            ev("() => hyComments.newAt({ x: 400, y: 100 }, { anchor: null, at: [400, 100] })"); page.wait_for_selector("#cmthread.open textarea")
            page.keyboard.type("in the studio"); page.keyboard.press("Enter"); wait(lambda: len(threads(port)) == 1, "the annotation was sent")
        page.keyboard.press("Escape"); page.wait_for_timeout(200)
        ev("() => document.activeElement && document.activeElement.blur()")
        u0 = ev("() => __studioUndo"); page.keyboard.press("Meta+z"); page.wait_for_timeout(600)
        assert len(threads(port)) == 1, "⌘Z in the Studio deleted its annotation"
        assert ev("() => __studioUndo") == u0 + 1
        assert not errors, errors
        browser.close()
