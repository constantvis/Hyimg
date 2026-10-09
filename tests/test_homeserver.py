"""A board's server on its card on Home and the faces of who did the news. The owner asked for the key on the cover («когда я навожу на
тамбнейл, кнопки запустить либо остановить», in the list «по правую сторону от тайтла»), then set its look (2026-10-08): «Кнопки
остановить и плей должны находиться в правом нижнем углу. И они должны быть тоже прозрачные. И кнопка сама не должна быть зеленой или
красной, только сам символ ... остановить — красным, сам символ». The faces whole in the card's line («почему-то обрезаны иконки»).
Home opened as a file with a fake app bridge, Chromium, dark theme. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()
ME, OTHER = str(uuid.uuid4()), str(uuid.uuid4())
NEWS = {"n": 14, "rows": [{"p": "Main", "pid": "main", "k": "add", "w": "Codex", "u": OTHER, "n": 7, "c": 7},
                          {"p": "Main", "pid": "main", "k": "note", "w": "claude", "u": ME, "n": 7, "c": 0}]}
P = [{"id": "a", "name": "Brand Book", "path": "/tmp/boards/Brand Book", "available": True, "updated": 1791100000, "covers": [],
      "onCanvas": 7814, "open": True, "news": NEWS},
     {"id": "b", "name": "Studio North", "path": "/tmp/boards/Studio North", "available": True, "updated": 1791000000, "covers": [], "onCanvas": 12},
     {"id": "c", "name": "Lost board", "path": "/tmp/boards/Gone", "available": False, "updated": 0, "covers": []}]
PEOPLE = {ME: {"name": "Ann", "color": "blue", "me": True}, OTHER: {"name": "Kate", "color": "orange"}}
BOX = "s => { const r = document.querySelector(s).getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; }"
# each face and each agent's badge, with its ring (2 px), lies inside the box of the line that clips the words (owner: «обрезаны иконки»),
# and no face lies over a badge: the badge's middle is the badge's own face
FACES_IN = """line => { const L = document.querySelector(line), r = L.getBoundingClientRect(), out = [], hid = [];
  L.querySelectorAll('hy-avatar, .hya-b').forEach(e => { const q = e.getBoundingClientRect(), g = e.matches('.hya-b') ? 2 : 1.5;
    if (q.top - g < r.top - .01 || q.bottom + g > r.bottom + .01 || q.left - g < r.left - .01 || q.right + g > r.right + .01)
      out.push([e.className || e.tagName, q.top, q.bottom, r.top, r.bottom]); });
  L.querySelectorAll('.hya-b').forEach(e => { const q = e.getBoundingClientRect(), at = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
    if (!at || at.closest('hy-avatar') !== e.closest('hy-avatar')) hid.push(e.dataset.k || e.className); });
  return { n: L.querySelectorAll('.hya-b').length, out, hid, clip: getComputedStyle(L).overflow }; }"""
RED, INK = "rgb(255, 69, 58)", "rgb(250, 250, 250)"   # ui/tokens.css --hy-red and --ink, dark


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def home(p, view="grid", lang=None):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme="dark", device_scale_factor=2)
    errors, sent = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.expose_function("__post", lambda m: sent.append(m))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
    if lang: page.add_init_script(f"window.HY_LANG = {json.dumps(lang)};")
    page.goto(HOME)
    push(page, P, view)
    return browser, page, errors, sent


def push(page, projects, view="grid"):
    """the app's list, as native/main.swift pushHome sends it"""
    data = {"projects": projects, "settings": {"cv.theme": "dark"}, "home": {"folders": [], "view": view},
            "profile": {"id": ME, "name": "Ann", "color": "blue"}, "people": PEOPLE}
    page.evaluate(f"hyimgHome({json.dumps(data)})")


def with_open(**state):
    return [{**p, "open": state.get(p["id"], p.get("open", False))} for p in json.loads(json.dumps(P))]


def key_state(page, sel):
    return page.evaluate("""s => { const k = document.querySelector(s); if (!k) return null; const c = getComputedStyle(k), b = k.querySelector('button');
      return { open: k.dataset.open, wait: k.hasAttribute('data-wait'), op: +c.opacity, vis: c.visibility, bg: c.backgroundColor, fg: c.color,
               w: b.offsetWidth, h: b.offsetHeight, kbg: getComputedStyle(b).backgroundColor, title: b.title, label: b.getAttribute('aria-label'), spin: !!b.querySelector('.hs-spin'),
               icon: (b.querySelector('svg') || {}).innerHTML || '', glyph: b.querySelector('svg') ? getComputedStyle(b.querySelector('svg')).fill : '' }; }""", sel)


def actions(sent):
    return [m for m in sent if m.get("action") in ("startServer", "stopServer", "open")]


def test_cover_key_starts_and_stops_without_opening():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        # no key on a board whose folder is missing; none shown on a card the pointer is not over
        assert page.locator(".card[data-id=c] .hs-key").count() == 0
        page.mouse.move(5, 790); page.wait_for_timeout(300)
        assert key_state(page, ".card[data-id=b] .hs-key")["op"] == 0
        # a stopped board: «Start server», the play glyph in ink on the cover's glass, at the cover's bottom right
        page.hover(".card[data-id=b] .cover"); page.wait_for_timeout(350)
        k = key_state(page, ".card[data-id=b] .hs-key")
        assert (k["open"], k["op"], k["title"], k["label"], k["w"], k["h"]) == ("0", 1, "Start server", "Start server", 30, 30), k
        assert "M8 5.6" in k["icon"] and k["glyph"] == INK, k
        assert k["bg"] == "rgba(9, 9, 11, 0.55)", k   # glass: the heart's and the «Open» chip's, not a coloured key
        key, cov, fav = (page.evaluate(BOX, f".card[data-id=b] {s}") for s in (".hs-key", ".cover", ".fav"))
        assert abs(cov["r"] - 8 - key["r"]) < .5 and abs(cov["b"] - 8 - key["b"]) < .5, (key, cov)
        assert key["t"] > fav["b"] and key["l"] > cov["l"], (key, fav)
        shot(page, "grid-stopped-hover")
        # an open board: the same neutral glass, the stop glyph red
        page.hover(".card[data-id=a] .cover"); page.wait_for_timeout(350)
        k = key_state(page, ".card[data-id=a] .hs-key")
        assert (k["open"], k["op"], k["title"], k["bg"], k["glyph"]) == ("1", 1, "Stop server", "rgba(9, 9, 11, 0.55)", RED), k
        page.hover(".card[data-id=a] .hs-key"); page.wait_for_timeout(250)
        k = key_state(page, ".card[data-id=a] .hs-key")
        assert k["glyph"] == RED and k["bg"] == "rgba(9, 9, 11, 0.75)", k   # the pointer darkens the glass, the glyph stays red
        shot(page, "grid-running-hover")
        # a click sends the menu's own message and does not open the board; the key waits for the app, shown without the pointer
        page.click(".card[data-id=a] .hs-key")
        assert actions(sent) == [{"action": "stopServer", "id": "a"}], sent
        page.mouse.move(5, 790); page.wait_for_timeout(300)
        k = key_state(page, ".card[data-id=a] .hs-key")
        assert (k["wait"], k["spin"], k["op"], k["title"]) == (True, True, 1, "Stopping the server"), k
        page.click(".card[data-id=a] .hs-key"); assert len(actions(sent)) == 1, "one message per press until the app answers"
        # the app's list without it open: the chip goes, the key is «Start server» again
        push(page, with_open(a=False))
        assert page.locator(".card[data-id=a] .chip").count() == 0
        k = key_state(page, ".card[data-id=a] .hs-key"); assert (k["open"], k["wait"], k["title"], k["glyph"]) == ("0", False, "Start server", INK), k
        # start: the board loads behind (its steps on the cover), the key stands aside until they end, then it is «Stop server»
        page.hover(".card[data-id=b] .cover"); page.click(".card[data-id=b] .hs-key")
        assert actions(sent)[-1] == {"action": "startServer", "id": "b"}
        page.evaluate("hyimgProgress({id: 'b', text: 'Starting “Studio North”'})")
        push(page, with_open(a=False, b=True))
        page.wait_for_function("() => getComputedStyle(document.querySelector('.card[data-id=b] .hs-key')).visibility === 'hidden'")
        assert page.locator(".card[data-id=b] .chip").count() == 1
        page.evaluate("hyimgProgress({id: 'b', text: 'Board drawn', done: true})")
        page.wait_for_function("() => getComputedStyle(document.querySelector('.card[data-id=b] .hs-key')).visibility === 'visible'")
        k = key_state(page, ".card[data-id=b] .hs-key"); assert (k["open"], k["wait"], k["title"]) == ("1", False, "Stop server"), k
        assert not any(m["action"] == "open" for m in sent)
        # the app never answering: the wait ends on its own after 8 s
        page.evaluate("() => { document.querySelector('.card[data-id=a] .hs-key button').click(); }")
        assert page.evaluate("hyHomeServer.waiting('a')") is True
        page.wait_for_function("() => !hyHomeServer.waiting('a')", timeout=10000)
        assert key_state(page, ".card[data-id=a] .hs-key")["spin"] is False
        assert not errors, errors
        browser.close()


def test_cover_key_respects_reduced_motion():
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme="dark", reduced_motion="reduce")
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } };")
        page.goto(HOME); push(page, P)
        page.hover(".card[data-id=b] .cover")
        got = page.evaluate("() => { const s = getComputedStyle(document.querySelector('.card[data-id=b] .hs-key')); return [s.transitionDuration, s.transform]; }")
        assert got == ["0s", "none"], got
        browser.close()


def test_card_faces_are_whole_and_the_words_keep_their_ellipsis():
    """the agent's badge on a face stood 3 px past the 17 px line and was cut by its overflow, and the next face lay over it
    (owner: «[K][K] 14», cut)"""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)   # 1280 px: three cards in a row
        page.set_viewport_size({"width": 1000, "height": 800})   # two cards in a row: the line's words do not fit
        got = page.evaluate(FACES_IN, ".card[data-id=a] .meta .s")
        assert got["n"] == 2 and got["out"] == [] and got["hid"] == [] and got["clip"] == "hidden", got
        words = page.evaluate("() => { const s = document.querySelector('.card[data-id=a] .meta .s > span'); return [s.scrollWidth, s.clientWidth, getComputedStyle(s).textOverflow]; }")
        assert words[2] == "ellipsis", words
        # laid out where it was: a card's name and line stand as on a card without news
        h = page.evaluate("() => ['a', 'b'].map(i => document.querySelector(`.card[data-id=${i}] .meta`).getBoundingClientRect().height)")
        assert abs(h[0] - h[1]) < .5, h
        if os.environ.get("HY_SHOTS"): page.locator(".card[data-id=a] .meta").screenshot(path=str(Path(os.environ["HY_SHOTS"]) / "grid-faces.png"))
        assert not errors, errors
        browser.close()


def test_list_key_right_of_the_title():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p, view="list")
        assert page.locator(".list .card").count() == 3 and page.locator(".list .card[data-id=c] .hs-key").count() == 0
        page.set_viewport_size({"width": 1440, "height": 800})   # a name column where «Studio North» is whole
        page.mouse.move(5, 790); page.wait_for_timeout(250)
        k = key_state(page, ".list .card[data-id=b] .hs-key")
        assert k["op"] == 0, k
        page.hover(".list .card[data-id=b] .n"); page.wait_for_timeout(250)
        k = key_state(page, ".list .card[data-id=b] .hs-key")
        assert (k["open"], k["op"], k["title"], k["w"], k["h"], k["kbg"], k["glyph"]) == ("0", 1, "Start server", 28, 28, "rgba(0, 0, 0, 0)", INK), k
        n, key, col = (page.evaluate(BOX, f".list .card[data-id=b] {s}") for s in (".n", ".hs-key button", ".nmc"))
        assert abs(key["l"] - n["r"] - 10) < .5 and key["r"] <= col["r"], (n, key, col)   # a short name: the key 10 px after it
        assert abs((key["t"] + key["b"]) / 2 - (n["t"] + n["b"]) / 2) < 1.5, (n, key)
        shot(page, "list-hover")
        page.click(".list .card[data-id=b] .hs-key")
        assert actions(sent) == [{"action": "startServer", "id": "b"}], sent
        # the keyboard: the key shows on focus without the pointer, Enter stops the open board, and it keeps the focus through Home's redraw
        page.mouse.move(5, 790)
        page.focus(".list .card[data-id=a]"); page.keyboard.press("Tab"); page.wait_for_timeout(250)
        assert page.evaluate("document.activeElement.closest('.hs-key').dataset.hsKey") == "a"
        k = key_state(page, ".list .card[data-id=a] .hs-key"); assert (k["op"], k["title"], k["bg"], k["glyph"]) == (1, "Stop server", "rgba(0, 0, 0, 0)", RED), k
        assert k["kbg"] == "rgb(32, 32, 36)", k   # the key the keyboard is on: the pointer's ground (Home's --raise2, dark)
        page.keyboard.press("Enter")
        assert actions(sent)[-1] == {"action": "stopServer", "id": "a"} and not any(m["action"] == "open" for m in sent), sent
        push(page, with_open(a=False, b=True), view="list")
        assert page.evaluate("document.activeElement.closest('.hs-key') && document.activeElement.closest('.hs-key').dataset.hsKey") == "a"
        # the faces of the news in the time's column whole as well
        got = page.evaluate(FACES_IN, ".list .card[data-id=a] .c3")
        assert got["n"] == 2 and got["out"] == [] and got["hid"] == [], got
        assert not errors, errors
        browser.close()


def test_list_key_never_cuts_the_name_again():
    """a long name ended «Hyimg Site with a ra…» and on the row's hover «Hyimg Site wi…» (the key took 28 px as it showed); now its …
    stays where it was and the key lies over the name's end on the row's ground"""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p, view="list")
        long = {**P[1], "id": "d", "name": "Hyimg Site with a rather long board name", "path": "/tmp/boards/Hyimg Site"}
        push(page, P + [long], view="list")
        name = """() => { const n = document.querySelector('.list .card[data-id=d] .n'), r = n.getBoundingClientRect();
          return { w: n.clientWidth, cut: n.scrollWidth > n.clientWidth, r: r.right, t: r.top, b: r.bottom }; }"""
        page.mouse.move(5, 790); page.wait_for_timeout(250)
        rest = page.evaluate(name)
        page.hover(".list .card[data-id=d] .c3"); page.wait_for_timeout(250)
        hover = page.evaluate(name)
        assert rest["cut"] and hover == rest, (rest, hover)   # the same width, the same …
        k = key_state(page, ".list .card[data-id=d] .hs-key")
        key, col = (page.evaluate(BOX, f".list .card[data-id=d] {s}") for s in (".hs-key button", ".nmc"))
        assert k["op"] == 1 and (k["w"], k["h"]) == (28, 28) and abs(key["r"] - col["r"]) < .5 and abs(key["r"] - rest["r"]) < .5, (k, key, col, rest)
        # under the key and 10 px before it the row's own ground (the row's hover colour), so the name's end does not show through
        ground = page.evaluate("""() => { const k = document.querySelector('.list .card[data-id=d] .hs-key'), s = getComputedStyle(k, '::before'),
          b = k.querySelector('button').getBoundingClientRect(), r = k.getBoundingClientRect();
          return [s.backgroundImage, getComputedStyle(k.closest('.card')).backgroundColor, b.left - r.right + parseFloat(s.width)]; }""")
        assert ground[0].startswith("linear-gradient") and ground[1] in ground[0] and ground[2] == 10, ground
        page.hover(".list .card[data-id=d] .hs-key button"); page.wait_for_timeout(250)
        assert page.evaluate(name) == rest
        shot(page, "list-hover-long")
        page.click(".list .card[data-id=d] .hs-key button")
        assert actions(sent) == [{"action": "startServer", "id": "d"}], sent
        assert not errors, errors
        browser.close()


def test_key_words_in_russian():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p, lang="ru")
        page.hover(".card[data-id=b] .cover"); page.wait_for_timeout(300)
        assert key_state(page, ".card[data-id=b] .hs-key")["title"] == "Запустить сервер"
        page.click(".card[data-id=b] .hs-key")
        assert key_state(page, ".card[data-id=b] .hs-key")["title"] == "Запускаю сервер"
        page.hover(".card[data-id=a] .cover"); page.click(".card[data-id=a] .hs-key")
        assert key_state(page, ".card[data-id=a] .hs-key")["title"] == "Останавливаю сервер"
        assert page.evaluate("window.__tMiss") == [], "Russian words missing from ui/lang-home.js"
        assert not errors, errors
        browser.close()
