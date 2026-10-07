"""The menus' keys (ui/menu.js) belong to a menu only while it is open (image studio agent, 2026-10-06: any .menu with items was taken for
open after it closed and only faded out, so ↑ ↓ Enter never reached the page under it: the studio's arrows stopped moving layers after any
menu had been opened, and Enter after Esc ran an invisible item).

- a closed menu that stays laid out (faded, as the image studio's .menu) takes no key: ↑ ↓ Enter reach the page, its items are not run
- the same menu with its «open» class takes them (↓ goes to its first item)
- the board's right-click menu opened and closed with Esc: Enter does nothing, the arrows reach the board
Runs in Chromium and WebKit where Playwright has them, on temporary libraries only."""
import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ENGINES = ["chromium", "webkit"]


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


FADED = """() => {
  const m = document.createElement('div'); m.className = 'menu'; m.id = 'faded'; m.setAttribute('role', 'menu');
  m.style.cssText = 'position:fixed;left:20px;top:300px;opacity:0;pointer-events:none';
  m.innerHTML = '<button role="menuitem" id="fadedItem">One</button><button role="menuitem">Two</button>';
  m.querySelector('#fadedItem').addEventListener('click', () => { window.__ran = (window.__ran || 0) + 1; });
  document.body.appendChild(m);
  window.__keys = []; addEventListener('keydown', e => window.__keys.push(e.key));   // after menu.js's: what got through to the page
}"""


@pytest.mark.parametrize("engine", ENGINES)
def test_a_closed_menu_takes_no_keys(server, engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        url = f"http://127.0.0.1:{server}/canvas.html"
        page.goto(url)
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }")
        page.goto(url)
        page.wait_for_function("() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === 6 && EL.get('i0')", timeout=20000)
        errors.clear()
        page.evaluate(FADED)
        page.mouse.click(1300, 850)
        for k in ("ArrowDown", "ArrowUp", "Enter"): page.keyboard.press(k)
        assert page.evaluate("() => window.__keys") == ["ArrowDown", "ArrowUp", "Enter"]
        assert page.evaluate("() => window.__ran || 0") == 0 and page.evaluate("() => document.activeElement.id") != "fadedItem"
        # open, the same list takes the arrows
        page.evaluate("() => { window.__keys = []; document.getElementById('faded').classList.add('open'); document.getElementById('faded').style.opacity = 1; }")
        page.keyboard.press("ArrowDown")
        assert page.evaluate("() => document.activeElement.id") == "fadedItem" and page.evaluate("() => window.__keys") == []
        page.evaluate("() => { const m = document.getElementById('faded'); m.classList.remove('open'); m.style.opacity = 0; document.activeElement.blur(); window.__keys = []; }")
        # the board's own menu: opened, closed with Esc; Enter then does nothing, the arrows reach the board
        r = page.evaluate("() => { const it = board.items.i1, s = stage.getBoundingClientRect(); return [(it.x + 60 - cam.x) * cam.z + s.left, (it.y + 60 - cam.y) * cam.z + s.top]; }")
        page.mouse.click(*r, button="right")
        page.wait_for_selector("#ctx.open")
        page.keyboard.press("ArrowDown"); page.keyboard.press("Escape")
        assert not page.evaluate("() => $('#ctx').classList.contains('open')")
        page.evaluate("() => { window.__keys = []; window.__copied = 0; const w = navigator.clipboard && navigator.clipboard.writeText; if (w) navigator.clipboard.writeText = t => { window.__copied++; return Promise.resolve(); }; }")
        for k in ("Enter", "ArrowDown", "ArrowRight"): page.keyboard.press(k)
        assert page.evaluate("() => window.__keys") == ["Enter", "ArrowDown", "ArrowRight"]
        assert page.evaluate("() => window.__copied") == 0 and not page.evaluate("() => $('#ctx').classList.contains('open')")
        assert not errors, errors
        browser.close()
