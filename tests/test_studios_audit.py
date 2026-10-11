"""Studios audit 2026-10-11, the rules that live in Hyimg for all three Studios (the real plugins beside this repository). Chromium, dark,
the Russian interface, our own temporary server.

  S-01  in a Studio the switch shows only Board and the open Studio; Actions is the dock's icon button 36 × 34, its name and ⌘K in the
        tooltip (ui/dock.js hyDock.acts)
  S-04  the Hint bar: «Select» in Russian is «Выбрать» in every Studio, a key held with its modifier is one cap (⌥R), the slash only
        between alternatives (Esc / ⌘↵), at most five items
  S-19  the board's Info card is gone from the first moment a Studio opens (Image Studio's took 2–3 s, its frame still being made)

  nice -n 10 python3 -m pytest -q tests/test_studios_audit.py
"""
import json

import pytest

from test_p4_studio_keys import Dev, Studio3D, board, serve

playwright = pytest.importorskip("playwright.sync_api")

BAR = """() => { const h = document.querySelector('hy-keyhint[place=top]'); if (!h) return null;
  return [...h.querySelectorAll('.kh-i')].map(i => ({ id: i.dataset.id, caps: [...i.querySelectorAll('hy-kbd')].map(k => k.textContent),
    or: i.querySelectorAll('.kh-or').length, t: (i.querySelector('.kh-t') || {}).textContent || '' })); }"""
DOCK = """() => { const vis = b => b.getClientRects().length && getComputedStyle(b).display !== 'none';
  const a = document.querySelector('#dock .dkacts'), r = a && a.getBoundingClientRect();
  return { modes: [...document.querySelectorAll('#modes > button')].filter(vis).map(b => b.dataset.mode),
    acts: a && [Math.round(r.width), Math.round(r.height), a.title, a.textContent.trim(), a.getAttribute('aria-label')] }; }"""


def test_the_studios_switch_actions_and_hint_bar(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as pw:
        (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru", "cv.theme": "dark"}))
        browser = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page, errors = board(browser, port)
        assert page.evaluate("T('Board')") == "Доска"
        bad = []
        for key, s in (("3d", Studio3D(page, lib)), ("dev", Dev(page, lib))):
            s.open(); page.wait_for_function("() => !!document.querySelector('hy-keyhint[place=top] .kh-i')", timeout=5000)
            bar, dock = page.evaluate(BAR), page.evaluate(DOCK)
            words = [i["t"] for i in bar]
            if "Выбрать" not in words or any("Select" in w for w in words): bad.append(f"{key}: the Hint bar's words {words}")
            if len(bar) > 5: bad.append(f"{key}: {len(bar)} items in the Hint bar")
            for i in bar:   # a combination is one cap; a slash only between alternatives
                if i["or"] and i["or"] != len(i["caps"]) - 1: bad.append(f"{key}: {i}")
                if any(c in ("⌥", "⇧", "⌘", "⌃") for c in i["caps"]) and i["or"]: bad.append(f"{key}: a modifier alone as an alternative: {i}")
            if key == "dev":
                reload = next((i for i in bar if i["id"] == "reload"), None)
                if not reload or reload["caps"] != ["⌥R"] or reload["or"]: bad.append(f"dev: ⌥R is not one cap: {reload}")
            if dock["modes"] != ["board", key]: bad.append(f"{key}: the switch shows {dock['modes']}")
            a = dock["acts"]
            if not a or a[:2] != [36, 34] or "⌘K" not in a[2] or a[3] or a[4] != "Действия": bad.append(f"{key}: Actions {a}")
            s.close()
        # back on the board the switch shows every Studio again
        page.wait_for_function("() => MODES.open === 'board'")
        if page.evaluate(DOCK)["modes"] != ["board", "image", "dev", "3d"]: bad.append(f"board: {page.evaluate(DOCK)['modes']}")
        assert not bad, "\n".join(bad)
        assert not errors, errors
        browser.close()


def test_the_info_card_goes_as_a_studio_opens(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page, errors = board(browser, port)
        INFO = "() => { const i = document.getElementById('info'); return !!i && getComputedStyle(i).display !== 'none' && +getComputedStyle(i).opacity > 0; }"
        b = page.locator(".it[data-id=a1]").bounding_box()
        page.mouse.click(b["x"] + 40, b["y"] + 40)
        page.wait_for_function(INFO, timeout=5000)   # the picture's Info card on the board
        page.keyboard.press("Enter")
        page.wait_for_function("() => MODES.open === 'image'", timeout=5000)
        opening = page.evaluate("() => !(window.__frames && __frames.ED && __frames.ED.win)")
        seen = page.evaluate(INFO)
        assert opening, "the studio had opened already: the test proves nothing"
        assert not seen, "the board's Info card shows while Image Studio opens"
        page.wait_for_function("() => window.__frames && __frames.ED && __frames.ED.win && __frames.ED.win.__ed && __frames.ED.win.__ed.ready", timeout=30000)
        assert not page.evaluate(INFO)
        page.evaluate("() => __frames.closeNow()"); page.wait_for_function("() => !__frames.ED", timeout=20000)
        page.mouse.click(b["x"] + 40, b["y"] + 40); page.wait_for_function(INFO, timeout=5000)   # back on the board it is there again
        assert not errors, errors
        browser.close()
