"""Round 18's bell and library (owner 2026-10-10, Concepts/html/editors-concepts/r18/r18-bell.html and r18-library.html). Chromium, dark,
the design audit's temporary library (tests/test_design_audit.py world).

- 9, the bell: filters as tabs in its header, «точно так же, как здесь»: All | Notifications | Comments with their counts, the same control
  as the «?» panel's «Tips | All keys 60» (<hy-segmented variant=pill>). Comments are what people wrote (annotations, replies, mentions, a
  reply to a note), the rest notifications. The rows stay as they are
- 11 b, arrows between collections: two small arrows in the library's path row, before its «…», ⌥↑ ⌥↓ in their tooltip; the keys work in
  the library and on the board
- 12 b, quieter headings in the narrow library: the folder in capitals like the path («A 3», one scale with «Folders 3»), the batch under
  it in 11 px; the wide library keeps the big names

  python3 -m pytest tests/test_r18_bell_library.py
"""
import json

from test_design_audit import board_doc, canvas_frame, new_page, reset_board, world  # noqa: F401
from test_design_r15 import GEO, open_lib, open_tips, settle, width

T0 = "2026-10-10 12:00:00"
ROWS = [{"id": "a1", "t": T0, "title": "Placed 6 pictures", "who": "Claude", "text": "Light from the left", "read": False, "type": "agent"},
        {"id": "c:1:1", "t": T0, "title": "New annotation", "who": "Ann", "text": "Softer shadow", "kind": "comment", "type": "comment", "read": True},
        {"id": "c:1:2", "t": T0, "title": "Reply in a thread", "who": "Ann", "text": "Lowered it", "kind": "comment", "type": "reply", "read": True},
        {"id": "n:main:n1:1", "t": T0, "title": "Reply to your note", "who": "Ann", "kind": "note", "type": "note", "read": True},
        {"id": "a2", "t": T0, "title": "Put 3 renderings", "who": "Codex", "read": True, "type": "agent"}]
TABS = """(q) => [...document.querySelectorAll(q + ' > button')].map(b => [b.querySelector('span') ? b.querySelector('span').textContent : b.textContent.trim(),
  (b.querySelector('em') || {}).textContent || '', b.getAttribute('aria-selected'), Math.round(b.getBoundingClientRect().height), getComputedStyle(b).fontSize])"""


def test_bell_tabs_filter_like_the_keys_panel(world):   # 9
    page, frame = open_tips(world)
    frame.click("#bkeys"); settle(frame, 300)
    # the bell: its rows from the server, as the app has them; the tabs count them
    page.route("**/api/notifications?limit=60", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"items": ROWS, "unread": 1})))
    frame.evaluate("() => { try { localStorage.removeItem('cv.bellTab'); } catch {} return pollNtf(); }")
    frame.click("#bntf"); frame.wait_for_selector("#ntf .ntabs > button")
    settle(frame, 300)
    bt = frame.evaluate(TABS, "#ntf .ntabs")
    assert [t[:3] for t in bt] == [["All", "5", "true"], ["Notifications", "2", "false"], ["Comments", "3", "false"]], bt
    assert all(t[3] == 30 and t[4] == "13.5px" for t in bt), "the same tabs as the ? panel's"
    assert frame.evaluate("() => [document.querySelector('#ntf .ntabs').localName, document.querySelector('#ntf .ntabs').getAttribute('variant')]") == ["hy-segmented", "pill"]
    titles = lambda: frame.evaluate("() => [...document.querySelectorAll('#ntf .nt b')].map(b => b.textContent)")
    assert len(titles()) == 5
    frame.click("#ntf .ntabs > button[value=com]"); settle(frame, 300)
    assert titles() == ["New annotation", "Reply in a thread", "Reply to your note"]
    frame.click("#ntf .ntabs > button[value=ntf]"); settle(frame, 300)
    assert titles() == ["Placed 6 pictures", "Put 3 renderings"]
    # the rows look as before: the title, who and when, the words
    assert frame.evaluate("() => !!document.querySelector('#ntf .nt .who') && document.querySelector('#ntf .nt p').textContent") == "Light from the left"
    # the choice stays for the next opening
    frame.click("#bntf"); settle(frame, 200); frame.click("#bntf"); frame.wait_for_selector("#ntf .ntabs > button")
    assert frame.evaluate("() => document.querySelector('#ntf .ntabs > button[value=ntf]').getAttribute('aria-selected')") == "true"
    frame.evaluate("() => { try { localStorage.removeItem('cv.bellTab'); } catch {} }")
    # the ? panel: the same control, the same tabs
    frame.click("#bkeys"); settle(frame, 400)
    keys = frame.evaluate("() => { const s = document.querySelector('#keys .kp-tabs'); return [s.localName, s.getAttribute('variant')]; }")
    assert keys == ["hy-segmented", "pill"], keys
    kt = frame.evaluate(TABS, "#keys .kp-tabs")
    assert [t[0] for t in kt] == ["Tips", "All keys"] and kt[0][2] == "true" and all(t[3] == 30 and t[4] == "13.5px" for t in kt), kt
    frame.click("#keys .kp-tab[data-kt=all]"); settle(frame, 300)
    assert frame.evaluate("() => document.querySelector('#keys .kp-tab[data-kt=all]').getAttribute('aria-selected')") == "true"
    assert not frame.evaluate("() => document.querySelector('#keys section[data-kt=all]').hidden")
    assert not page.errors, page.errors
    page.close()


def test_library_arrows_and_keys_between_collections(world):   # 11 b
    page, frame = open_lib(world, 320)
    coll = lambda: page.evaluate("() => document.getElementById('coll').value")
    page.evaluate("() => chooseFolder('')"); settle(page)
    arrows = page.evaluate("""() => [...document.querySelectorAll('#fbar .fstep button')].map(b => { const r = b.getBoundingClientRect();
      return [b.title, Math.round(r.width), Math.round(r.height)]; })""")
    assert arrows == [["Previous collection · ⌥↑", 22, 22], ["Next collection · ⌥↓", 22, 22]], arrows
    more = page.evaluate(GEO, "#fbar .fsMore"); nxt = page.evaluate(GEO, "#fbar .fstep button[data-fstep='1']")
    assert nxt[0] + nxt[2] <= more[0] and abs((nxt[1] + nxt[3] / 2) - (more[1] + more[3] / 2)) <= 2, (nxt, more)   # in the path row, before «…»
    page.click("#fbar .fstep button[data-fstep='1']"); settle(page)
    first = coll(); assert first, "the next collection after All folders"
    page.click("#fbar .fstep button[data-fstep='-1']"); settle(page)
    assert coll() == ""
    # ⌥↓ on the board: the library beside it steps
    frame.click("#stage", position={"x": 700, "y": 500}); settle(frame, 200)
    page.keyboard.press("Alt+ArrowDown"); page.wait_for_function("c => document.getElementById('coll').value === c", arg=first, timeout=5000)
    page.keyboard.press("Alt+ArrowUp"); page.wait_for_function("() => document.getElementById('coll').value === ''", timeout=5000)
    # ⌥↓ in the library itself
    page.click("header.hy-dock .lph"); page.keyboard.press("Alt+ArrowDown")
    page.wait_for_function("c => document.getElementById('coll').value === c", arg=first, timeout=5000)
    page.evaluate("() => chooseFolder('')")
    assert not page.errors, page.errors
    page.close()


def test_narrow_library_headings_are_quiet(world):   # 12 b
    page, _ = open_lib(world, 320)
    page.evaluate("() => chooseFolder('')"); settle(page)
    HEAD = """() => { const h = document.querySelector('#list section h2'), b = h.querySelector('.lqh b'), bt = document.querySelector('#list h3.batch'),
      s = e => e && e.getClientRects().length ? getComputedStyle(e) : null;
      return { h: Math.round(h.getBoundingClientRect().height), title: s(h).fontSize, caps: s(b) && [s(b).fontSize, s(b).textTransform, b.textContent],
        batch: s(bt).fontSize, count: (h.querySelector('.lqh em') || {}).textContent, path: (s(document.querySelector('.lfh')) || {}).fontSize }; }"""
    q = page.evaluate(HEAD)
    assert q["caps"] and q["caps"][0] == "10.5px" and q["caps"][1] == "uppercase" and q["caps"][0] == q["path"], q   # one scale with «Folders 3»
    assert q["title"] == "0px" and q["h"] <= 16 and q["batch"] == "11px" and q["count"], q
    width(page, 248)   # compact: quiet too
    assert page.evaluate(HEAD)["caps"][0] == "10.5px"
    width(page, 560)   # wide: the big names as before
    w = page.evaluate("() => { const h = document.querySelector('#list section h2'); return [getComputedStyle(h).fontSize, h.querySelector('.lqh').getClientRects().length]; }")
    assert w == ["22px", 0], w
    assert not page.errors, page.errors
    page.close()
