"""The primitives (review/ui/hy) in Chromium and WebKit, on their showcase (review/ui/hy/showcase.html) served as an HTML frame's page from a
temporary library, the way the board's cards show it: every element renders and is live, its sizes are the measured canonical ones of
docs/ui-inventory.md, its corners follow the shape and its colours the theme in each of the four looks side by side, the keyboard and the
pointer change its state, its events say so, no focus ring shows. Then the places migrated to them: the board's history tabs and the
library's filter count. HYIMG_TEST_SHOTS=<folder> keeps a picture of each family in both engines and both languages."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]
SHOTS = os.environ.get("HYIMG_TEST_SHOTS", "")
FAMILIES = ["buttons", "choices", "marks", "micro", "hints"]
TAGS = ["hy-switch", "hy-check", "hy-kbd", "hy-badge", "hy-chip", "hy-hint", "hy-info", "hy-swatch", "hy-swatches", "hy-button",
        "hy-icon-button", "hy-plate", "hy-segmented", "hy-keyhint", "hy-tip", "hy-studio-actions", "hy-open-in", "hy-minitoggle", "hy-scope", "hy-led",
        "hy-stepper", "hy-scrub"]
LOOK = '.sc-look[data-hy-theme="{}"][data-hy-shape="{}"]'
DR = LOOK.format("dark", "round")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(tmp_path, lang):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "html/hy").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    shell = (ROOT / "review/ui/hy/showcase.html").read_text(encoding="utf-8")
    for fam in ["all"] + FAMILIES:
        (lib / "html/hy" / f"{'index' if fam == 'all' else fam}.html").write_text(shell.replace('data-family="all"', f'data-family="{fam}"'), encoding="utf-8")
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": lang}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError:
            time.sleep(0.1)
    return proc, log, port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    proc, log, port = serve(tmp_path_factory.mktemp("hyprim"), "en")
    yield port
    proc.terminate(); proc.wait(5); log.close()


@pytest.fixture(scope="module", params=ENGINES)
def browser(request):
    with playwright.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as e:   # an engine that is not installed on this machine
            pytest.skip(f"{request.param}: {e}")
        b.engine = request.param
        yield b
        b.close()


def open_page(browser, port, family="index", lang_errors=True):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "fonts.g" not in m.text else None)
    page.goto(f"http://127.0.0.1:{port}/lib/html/hy/{family}.html")
    page.wait_for_selector("html.sc-ready", timeout=15000)
    page.wait_for_timeout(350)   # the thumbs' first placement and the fonts
    page.errors = errors
    return page


def shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=True)


def test_the_showcase_loads_every_primitive_live_from_the_core(browser, server):
    page = open_page(browser, server)
    assert page.evaluate("tags => tags.filter(t => !customElements.get(t))", TAGS) == []
    assert page.evaluate("() => document.documentElement.dataset.hyFrom") == "core"   # the live files of the core, not the snapshot
    assert page.evaluate("() => document.querySelectorAll('.sc-look').length") == 20   # 5 families × 4 looks
    assert "23 live · ui/hy" in page.inner_text(".sc-head")
    assert page.evaluate("() => window.__tMiss || []") == []
    assert page.errors == [], page.errors
    for fam in FAMILIES:
        p = open_page(browser, server, fam)
        assert p.errors == [], p.errors
        shot(p, f"primitives-{fam}-{browser.engine}-en")
        p.close()
    page.close()


HINTS = """look => {
  const L = document.querySelector(look), r = e => e.getBoundingClientRect(), kh = L.querySelector(".sc-fixed > hy-keyhint:not([bare])"), host = kh.parentElement;
  const bare = L.querySelector("hy-keyhint[bare]"), cap = bare.querySelector("hy-kbd"), cs = getComputedStyle(cap), off = L.querySelector("hy-tip[off]");
  return { inside: r(kh).left >= r(host).left - 1 && r(kh).top >= r(host).top - 1 && r(kh).bottom <= r(host).bottom + 1,
    shown: +getComputedStyle(kh).opacity > .5, bar: Math.round(r(L.querySelector("hy-keyhint[place=top]")).height),
    spec: [...L.querySelectorAll(".sc-sec.spec h4 code")].map(c => c.textContent), bulb: !!L.querySelector("hy-tip > svg path"),
    glass: Math.round(r(L.querySelector("hy-tip[glass]")).height),
    bareCap: [cap.textContent, cs.backgroundColor, cs.borderTopWidth, getComputedStyle(bare).backgroundColor],
    closed: [getComputedStyle(off.querySelector(".tip-t")).display, +getComputedStyle(off.querySelector("svg")).opacity] };
}"""


def test_the_hints_family_draws_all_three_built(browser, server):
    """owner 2026-10-09 on round 12: all three built. A key hint on a surface is the glyph alone in its ink, no cap plate («просто Enter
    символа достаточно, даже без подложки»); the capsule keeps its caps; the Hint bar is the key hint at place «top»; the tip (version 9)
    is <hy-tip>, its bulb, its glass over pictures, and closed: the bulb alone at half strength. Nothing is a static picture any more."""
    page = open_page(browser, server, "hints")
    for th, sh in (("dark", "round"), ("light", "pro")):
        m = page.evaluate(HINTS, LOOK.format(th, sh))
        assert m == {"inside": True, "shown": True, "bar": 26, "spec": [], "bulb": True, "glass": 23,
                     "bareCap": ["↵", "rgba(0, 0, 0, 0)", "0px", "rgba(0, 0, 0, 0)"], "closed": ["none", 0.5]}, (th, sh, m)
    assert page.errors == [], page.errors
    page.close()


SIZES = """look => {
  const L = document.querySelector(look), h = q => [...L.querySelectorAll(q)].map(e => Math.round(e.getBoundingClientRect().height * 10) / 10);
  const box = (q, pseudo) => { const e = L.querySelector(q), cs = getComputedStyle(e, pseudo); return [parseFloat(cs.width), parseFloat(cs.height)]; };
  const sq = q => [...L.querySelectorAll(q)].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; });
  return {
    button: Object.fromEntries(["s", "m", "l", "row", "dock", "plate"].map(s => [s, h(`hy-button[size=${s}]`)[0]])),
    buttonDefault: h("hy-button:not([size])")[0],
    iconButton: Object.fromEntries(["xs", "s", "m", "l", "dock", "plate"].map(s => [s, sq(`hy-icon-button[size=${s}]`)[0]])),
  };
}"""
SIZES2 = """look => {
  const L = document.querySelector(look), h = q => Math.round(L.querySelector(q).getBoundingClientRect().height * 10) / 10;
  const w = q => Math.round(L.querySelector(q).getBoundingClientRect().width * 10) / 10;
  const pseudo = (q, p) => { const cs = getComputedStyle(L.querySelector(q), p); return [parseFloat(cs.width), parseFloat(cs.height)]; };
  return { switch: [w("hy-switch"), h("hy-switch")], switchTarget: h("hy-switch > input"), check: pseudo("hy-check", "::before"),
    chip: h("hy-chip"), segS: [h("hy-segmented[size=s] > button"), h("hy-segmented[size=s]")], segM: [h("hy-segmented:not([size]) > button"), h("hy-segmented:not([size])")],
    segL: [h("hy-segmented[size=l] > button"), h("hy-segmented[size=l]")], swatch: [w("hy-swatch:not([size])"), w("hy-swatch[size=m]")] };
}"""
SIZES3 = """look => {
  const L = document.querySelector(look), h = q => Math.round(L.querySelector(q).getBoundingClientRect().height * 10) / 10;
  return { kbd: [h("hy-kbd:not([size])"), h("hy-kbd[size=m]"), h("hy-kbd[size=s]")], badge: h("hy-badge[count='3']"), dot: h("hy-badge[dot]"),
    plate: h("hy-plate"), hiddenZero: getComputedStyle(L.querySelector("hy-badge[count='0']")).display,
    hintFont: getComputedStyle(L.querySelector("hy-hint")).fontSize, info: h("hy-info") };
}"""


def test_sizes_are_the_inventorys_canonical_ones(browser, server):
    """docs/ui-inventory.md and design/contract.json heights: plate 38, its buttons 30, dock 34, panel row 32, .seg option 28, kbd 20"""
    page = open_page(browser, server, "buttons")
    m = page.evaluate(SIZES, DR)
    assert m["button"] == {"s": 24, "m": 28, "l": 30, "row": 32, "dock": 34, "plate": 38} and m["buttonDefault"] == 28
    assert m["iconButton"] == {"xs": [20, 20], "s": [24, 24], "m": [28, 28], "l": [30, 30], "dock": [34, 34], "plate": [38, 38]}
    page.close()
    page = open_page(browser, server, "choices")
    m = page.evaluate(SIZES2, DR)
    assert m["switch"] == [30, 18] and m["switchTarget"] == 24 and m["check"] == [16, 16] and m["chip"] == 28
    assert m["segS"] == [24, 30] and m["segM"] == [28, 34] and m["segL"] == [30, 36]   # a thumb 3 px in on every side
    assert m["swatch"] == [18, 22]
    page.close()
    page = open_page(browser, server, "marks")
    m = page.evaluate(SIZES3, DR)
    assert m["kbd"] == [20, 18, 15] and m["badge"] == 16 and m["dot"] == 8 and m["plate"] == 38 and m["hiddenZero"] == "none"
    assert m["hintFont"] == "11px" and m["info"] == 24
    page.close()


LOOKS = """([sel, q, prop, pseudo]) => { const e = document.querySelector(sel + " " + q); return getComputedStyle(e, pseudo || null)[prop]; }"""


@pytest.mark.parametrize("theme,shape", [("dark", "round"), ("dark", "pro"), ("light", "round"), ("light", "pro")])
def test_corners_follow_the_shape_and_colours_the_theme(browser, server, theme, shape):
    page = open_page(browser, server)
    look = LOOK.format(theme, shape)
    g = lambda q, prop, pseudo=None: page.evaluate(LOOKS, [look, q, prop, pseudo])
    pro = shape == "pro"
    assert g("hy-button:not([size])", "borderTopLeftRadius") == ("8px" if pro else "999px")
    assert g("hy-button[size=plate]", "borderTopLeftRadius") == ("11px" if pro else "999px")
    assert g("hy-plate", "borderTopLeftRadius") == ("11px" if pro else "999px")
    assert g("hy-segmented:not([size])", "borderTopLeftRadius") == ("8px" if pro else "999px")
    assert g("hy-segmented:not([size]) > .st", "borderTopLeftRadius") == ("5px" if pro else "996px")
    assert g("hy-chip", "borderTopLeftRadius") == ("6px" if pro else "999px")
    assert g("hy-switch", "borderTopLeftRadius") == ("6px" if pro else "999px")
    assert g("hy-icon-button[shape=round]", "borderTopLeftRadius") == "50%"
    dark = theme == "dark"
    ink, sel = ("rgb(250, 250, 250)", "rgb(59, 130, 246)") if dark else ("rgb(9, 9, 11)", "rgb(37, 99, 235)")
    assert g("hy-button[variant=solid]", "backgroundColor") == ink
    assert g("hy-switch[checked]:not([disabled])", "backgroundColor") == sel
    assert g("hy-check[checked]:not([disabled])", "backgroundColor", "::before") == sel
    assert g("hy-badge[count='3']", "backgroundColor") == sel
    assert g("hy-chip[state=include]", "backgroundColor") == ink
    assert g("hy-button[size=plate]", "boxShadow") != "none"
    page.close()


def last_event(page, look=DR):
    return page.inner_text(look + " .sc-ev output")


def test_switch_and_check_take_the_keyboard_and_the_pointer(browser, server):
    page = open_page(browser, server, "choices")
    sw = DR + " hy-switch:not([checked]):not([disabled])"
    page.focus(sw + " > input"); page.keyboard.press("Space")
    assert page.evaluate("q => document.querySelector(q.replace(':not([checked])', '')).hasAttribute('checked')", sw)
    assert last_event(page).startswith('hy-change · <hy-switch> {"checked":true}')
    page.keyboard.press("Enter")
    assert last_event(page).startswith('hy-change · <hy-switch> {"checked":false}')
    page.click(DR + " .sc-lbl span")   # the words of a <label> around a switch toggle it
    assert not page.evaluate("q => document.querySelector(q).hasAttribute('checked')", DR + " .sc-lbl hy-switch")
    page.click(DR + " hy-switch[disabled]:not([checked])", force=True)
    assert not page.evaluate("q => document.querySelector(q).hasAttribute('checked')", DR + " hy-switch[disabled]:not([checked])")
    assert page.evaluate("q => document.querySelector(q).getAttribute('role')", DR + " hy-switch > input") == "switch"
    ck = DR + " hy-check:not([checked]):not([indeterminate])"
    page.click(ck + " .hy-in")   # the checkbox lies over the words: a click on them ticks it
    assert page.evaluate("q => document.querySelector(q.replace(':not([checked])', '')).hasAttribute('checked')", ck)
    page.click(DR + " hy-check[indeterminate]")
    assert page.evaluate("q => { const e = document.querySelectorAll(q)[2]; return [e.hasAttribute('checked'), e.hasAttribute('indeterminate')]; }", DR + " hy-check") == [True, False]
    page.close()


def test_segmented_chooses_by_arrow_keys_and_moves_its_thumb(browser, server):
    page = open_page(browser, server, "choices")
    seg = DR + " hy-segmented:not([size]):not([variant]):not([full]):not([label])"
    page.focus(seg + " > button.on"); page.keyboard.press("ArrowRight")
    assert page.evaluate("q => document.querySelector(q).value", seg) == "auto"
    assert last_event(page) == 'hy-change · <hy-segmented> {"value":"auto"}'
    assert page.evaluate("q => [...document.querySelector(q).querySelectorAll('button')].map(b => b.tabIndex)", seg) == [-1, -1, 0]
    page.keyboard.press("ArrowRight")   # round the end
    assert page.evaluate("q => document.querySelector(q).value", seg) == "dark"
    page.wait_for_timeout(450)
    assert page.evaluate("q => { const s = document.querySelector(q), b = s.querySelector('button.on'), r = b.getBoundingClientRect(),"
                         " t = s.querySelector('.st').getBoundingClientRect(); return Math.abs(r.left - t.left) < 1.5 && Math.abs(r.width - t.width) < 1.5; }", seg)
    tabs = DR + " hy-segmented[variant=tabs]"
    assert page.evaluate("q => document.querySelector(q).getAttribute('role')", tabs) == "tablist"
    page.click(tabs + " button[value=ver]")
    assert page.evaluate("q => [...document.querySelector(q).children].filter(c => c.localName === 'button').map(b => b.getAttribute('aria-selected'))", tabs) == ["false", "true"]
    # variant=tint (owner 2026-10-07, the settings): no track, the chosen option a soft tint of the selection's blue, its words in that blue
    tint = DR + " hy-segmented[variant=tint]"
    page.click(tint + " button[value=light]"); page.wait_for_timeout(450)
    look = page.evaluate("""q => { const s = document.querySelector(q), on = s.querySelector('button.on'), off = s.querySelector('button:not(.on)'), t = s.querySelector('.st'),
      a = on.getBoundingClientRect(), b = t.getBoundingClientRect();
      return { role: s.getAttribute('role'), value: s.value, track: getComputedStyle(s).backgroundColor, thumb: getComputedStyle(t).backgroundColor, ink: getComputedStyle(on).color,
               other: getComputedStyle(off).color, under: Math.abs(a.left - b.left) < 1.5 && Math.abs(a.width - b.width) < 1.5 }; }""", tint)
    assert look["role"] == "radiogroup" and look["value"] == "light" and look["under"], look
    assert look["track"] == "rgba(0, 0, 0, 0)" and look["ink"] == "rgb(59, 130, 246)" and look["other"] != look["ink"], look   # the dark look's --sel
    assert "0.16" in look["thumb"] and look["thumb"] != look["track"], look   # a 16 % tint of it, not the panel's grey
    page.close()


def test_buttons_click_toggle_and_stay_quiet_when_disabled(browser, server):
    page = open_page(browser, server, "buttons")
    tog = DR + " hy-button[toggle]:not([pressed])"
    page.click(tog)
    assert last_event(page) == 'hy-toggle · <hy-button> {"pressed":true}'
    assert page.evaluate("q => document.querySelectorAll(q)[1].querySelector('button').getAttribute('aria-pressed')", DR + " hy-button[toggle]") == "true"
    page.click(DR + " hy-button[variant=solid]:not([size])")
    assert last_event(page) == "click · <hy-button>"
    page.click(DR + " hy-icon-button[variant=danger]")
    page.click(DR + " hy-button[disabled]:not([variant])", force=True)
    assert last_event(page) == "click · <hy-icon-button>", "a disabled button sends no click"
    assert page.evaluate("q => document.querySelector(q).querySelector('button > kbd').textContent", DR + " hy-button[kbd='⌘C']") == "⌘C"
    assert page.evaluate("q => !!document.querySelector(q).querySelector('button > svg.hy-i')", DR + " hy-button[icon=copy]")
    assert page.evaluate("q => document.querySelector(q).querySelector('button').getAttribute('aria-label')", DR + " hy-icon-button[icon=history][size=plate]") == "History"
    page.focus(DR + " hy-button[variant=ghost] > button"); page.keyboard.press("Enter")
    assert last_event(page) == "click · <hy-button>"
    page.close()


def test_chips_cycle_and_swatches_pick_one(browser, server):
    page = open_page(browser, server, "choices")
    chip = DR + " hy-chip[count='24']"
    states = []
    for _ in range(3):
        page.click(chip); states.append(page.evaluate("q => document.querySelector(q).getAttribute('state') || 'off'", chip))
    assert states == ["include", "exclude", "off"]
    page.focus(chip); page.keyboard.press("Enter")
    assert page.evaluate("q => document.querySelector(q).getAttribute('aria-pressed')", chip) == "true"
    row = DR + " hy-swatches"
    page.click(row + " hy-swatch[value=red]")
    assert page.evaluate("q => [...document.querySelectorAll(q + ' hy-swatch[selected]')].map(s => s.getAttribute('value'))", row) == ["red"]
    assert last_event(page).startswith('hy-change · <hy-swatches> {"value":"red"')
    page.keyboard.press("ArrowRight")
    assert page.evaluate("q => document.querySelector(q).value", row) == "pink"
    page.close()


def test_no_focus_ring_on_any_primitive(browser, server):
    page = open_page(browser, server, "choices")
    page.keyboard.press("Tab"); page.keyboard.press("Tab"); page.keyboard.press("Tab")
    ring = page.evaluate("() => { const e = document.activeElement, cs = getComputedStyle(e); return [e.localName, cs.outlineStyle === 'none' || parseFloat(cs.outlineWidth) === 0]; }")
    assert ring[1], ring
    page.close()


def test_the_showcase_speaks_russian(browser, tmp_path):
    proc, log, port = serve(tmp_path, "ru")
    try:
        page = open_page(browser, port)
        assert "Hyimg UI · примитивы" in page.inner_text(".sc-head") and "23 живых" in page.inner_text(".sc-head") and "Темная · Круглые" in page.text_content(".sc-look h3")
        assert page.evaluate("() => window.__tMiss") == []
        for fam in FAMILIES:
            p = open_page(browser, port, fam); shot(p, f"primitives-{fam}-{browser.engine}-ru"); p.close()
        page.close()
    finally:
        proc.terminate(); proc.wait(5); log.close()


def test_the_boards_history_tabs_are_the_apps_choice(browser, server):
    """migrated (step 3): Activity | Versions in the board's history were a tab strip of their own (canvas.html #hist .htabs)"""
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"http://127.0.0.1:{server}/canvas")
    page.wait_for_function("() => customElements.get('hy-segmented') && document.querySelector('#hist .htabs.seg')")
    page.click("#bhist")
    page.wait_for_selector("#hist.open")
    tabs = "#hist hy-segmented.htabs"
    assert page.evaluate("q => document.querySelector(q).getAttribute('role')", tabs) == "tablist"
    was = page.evaluate("q => document.querySelector(q).value", tabs)   # the last tab the board remembers
    assert page.evaluate("q => document.querySelector('#hist').classList.contains('ver')", tabs) == (was == "ver")
    other = "ev" if was == "ver" else "ver"
    page.click(f"{tabs} button[value={other}]")
    page.wait_for_function("v => document.querySelector('#hist').classList.contains('ver') === (v === 'ver')", arg=other)
    assert page.evaluate("q => document.querySelector(q + ' button.on').dataset.tab", tabs) == other
    page.keyboard.press("ArrowLeft")   # the focused tab moves with the arrows (two tabs: back to the other one)
    page.wait_for_function("v => document.querySelector('#hist').classList.contains('ver') === (v === 'ver')", arg=was)
    page.close()
