"""Home's news (owner 2026-10-08): «Я хочу на главной странице по левую сторону видеть не только сколько у меня досок, но и сколько
обновлений. И еще, может, стоит добавить вверху справа, где настройки, тоже нотификации, чтобы я мог видеть: так, у меня тут что-то
новенькое появилось», and the card's line as data only: «Зачем мне эта писанина? On canvas туда-сюда. Мне главное данные: сколько
гигабайт, сколько чего, frames достаточно». Home opened as a file with a fake app bridge (ui/homebell.js asks it {action: "homeBell"},
the test answers as the app would with hyimgHomeBell), Chromium, dark theme. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import time
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()
ME, KATE = str(uuid.uuid4()), str(uuid.uuid4())
PEOPLE = {ME: {"name": "Ann", "color": "blue", "me": True}, KATE: {"name": "Kate", "color": "orange"}}
GB = 10 ** 9
FOLDERS = [{"id": "f1", "name": "Brand Studio", "projects": ["a", "b"]}, {"id": "f2", "name": "Hyimg", "projects": ["c"]}]
RED = "rgb(255, 69, 58)"
BOX = "s => { const r = document.querySelector(s).getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; }"


def boards():
    """four boards: two with news in project f1 (a open, b stopped), one quiet in f2, one with news in no project; times from now"""
    now = time.time()
    na = {"n": 14, "t": now - 300, "rows": [{"p": "Renderings", "pid": "p2", "k": "add", "w": "Codex", "u": KATE, "n": 7, "c": 24},
                                           {"p": "Renderings", "pid": "p2", "k": "note", "w": "claude", "u": ME, "n": 2, "c": 0},
                                           {"p": "Main", "pid": "main", "k": "move", "w": "owner", "u": KATE, "n": 5, "c": 9}]}
    nb = {"n": 3, "t": now - 5 * 3600, "rows": [{"p": "Main", "pid": "main", "k": "comment", "w": "owner", "u": KATE, "n": 3, "c": 0}]}
    nd = {"n": 2, "t": now - 60, "rows": [{"p": "", "pid": "main", "k": "add", "w": "gemini", "u": ME, "n": 2, "c": 2}]}
    return [{"id": "a", "name": "Brand Book", "path": "/tmp/boards/Brand Book", "available": True, "updated": now - 16 * 60 - 20, "covers": [],
             "onCanvas": 7814, "open": True, "news": na},
            {"id": "b", "name": "Studio North", "path": "/tmp/boards/Studio North", "available": True, "updated": now - 86400 * 3, "covers": [],
             "onCanvas": 12, "news": nb},
            {"id": "c", "name": "Hyimg App", "path": "/tmp/boards/Hyimg App", "available": True, "updated": now - 60, "covers": [], "onCanvas": 1},
            {"id": "d", "name": "Loose board", "path": "/tmp/boards/Loose", "available": True, "updated": now - 30, "covers": [], "open": True, "news": nd}]


def bell_rows(now):
    t = lambda s: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - s))
    a = [{"id": "n1", "t": t(30), "ts": now - 30, "read": False, "title": "Put 24 renderings on Renderings", "text": "Batch G7", "who": "Codex",
          "by": {"person": KATE, "via": "codex"}, "page": "p2", "ids": ["x1", "x2"], "type": "agent",
          "pv": [{"src": "/thumb?p=r%2Fa.png&s=320", "k": "pic"}], "pvn": 1},
         {"id": "c:7", "t": t(1800), "ts": now - 1800, "read": True, "title": "Kate commented", "text": "Too dark", "who": "Kate",
          "by": {"person": KATE, "via": "app"}, "page": "main", "ids": [], "type": "comment", "area": {"x": 10, "y": 20, "w": 300, "h": 200}}]
    d = [{"id": "n9", "t": t(90), "ts": now - 90, "read": True, "title": "Gemini put 2 images", "text": "", "who": "Gemini",
          "by": {"person": ME, "via": "gemini"}, "page": "main", "ids": ["y1"], "type": "agent"}]
    return {"boards": [{"id": "a", "base": "http://127.0.0.1:4999", "items": a, "unread": 1}, {"id": "d", "base": "http://127.0.0.1:4998", "items": d, "unread": 0}]}


def shot(page, name, sel=None):
    if not os.environ.get("HY_SHOTS"): return
    out = str(Path(os.environ["HY_SHOTS"]) / f"{name}.png")
    page.locator(sel).screenshot(path=out) if sel else page.screenshot(path=out)


def home(p, lang=None, view="grid", width=1280):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": width, "height": 800}, color_scheme="dark", device_scale_factor=2)
    errors, sent = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.expose_function("__post", lambda m: sent.append(m))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
    if lang: page.add_init_script(f"window.HY_LANG = {json.dumps(lang)};")
    page.goto(HOME)
    push(page, boards(), view)
    summary = {"t": 0, "boards": [{"id": "a", "name": "Brand Book", "total": {"bytes": 3.5 * GB, "disk": 3.5 * GB}}], "global": {"backups": []},
               "totals": {"boards": {"disk": 3.5 * GB}, "made": {"disk": 0}, "cache": {"disk": 0}, "clearable": {"disk": 0}, "backups": {"disk": 0}, "dups": 0}}
    page.evaluate(f"hyimgStorage({json.dumps({'op': 'summary', 'summary': summary})})")
    return browser, page, errors, sent


def push(page, projects, view="grid", favs=("b",)):
    data = {"projects": projects, "settings": {"cv.theme": "dark"}, "home": {"folders": FOLDERS, "favs": list(favs), "view": view},
            "profile": {"id": ME, "name": "Ann", "color": "blue"}, "people": PEOPLE}
    page.evaluate(f"hyimgHome({json.dumps(data)})")


def text(page, sel):
    return page.inner_text(sel).replace(" ", " ").replace(" ", " ")


def test_sidebar_counts_the_news_of_each_project():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        count = lambda s: page.locator(f"aside {s} .hb-n").all_inner_texts()
        # a project: its boards' news beside its count of boards; none at 0; «No project», a favourite, «All boards»
        assert count("[data-folder=f1]") == ["17"] and count("[data-folder=f2]") == [], (count("[data-folder=f1]"), count("[data-folder=f2]"))
        assert count("[data-tab=none]") == ["2"] and count("[data-tab=all]") == ["19"] and count("[data-open=b]") == ["3"]
        assert page.locator("aside [data-folder=f1] .ct").inner_text() == "2"
        # the card's red badge, small, left of the count of boards
        look = page.evaluate("""() => { const b = document.querySelector('aside [data-folder=f1] .hb-n'), s = getComputedStyle(b), r = b.getBoundingClientRect(),
          c = document.querySelector('aside [data-folder=f1] .ct').getBoundingClientRect(); return { bg: s.backgroundColor, fg: s.color, h: r.height, gap: c.left - r.right }; }""")
        assert look["bg"] == RED and look["fg"] == "rgb(255, 255, 255)" and look["h"] == 16 and 4 <= look["gap"] <= 8, look
        assert page.locator("aside [data-folder=f1] .hb-n").get_attribute("title") == "17 new"
        shot(page, "sidebar-counts", "aside")
        # a board seen: its news leaves the project's count at once
        page.evaluate("hyimgSeen('a')")
        assert count("[data-folder=f1]") == ["3"] and count("[data-tab=all]") == ["5"]
        assert not errors, errors
        browser.close()


def test_bell_lists_every_boards_news_and_opens_the_place():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        # the bell: a plate of the top row, the row's gap from «New board» and from the settings
        bell, sets, new = (page.evaluate(BOX, s) for s in ("#hbell", "#bset", ".top .btn.primary"))
        assert (bell["t"], bell["w"], bell["h"]) == (12, 38, 38) and abs(sets["l"] - bell["r"] - 8) < .5 and abs(bell["l"] - new["r"] - 8) < .5, (bell, sets, new)
        # its own dot red: something came since the list was last opened
        assert page.locator("#hbell.dot").count() == 1
        assert page.evaluate("getComputedStyle(document.querySelector('#hbell svg circle')).fill") == RED
        assert {"action": "homeBell"} in sent
        page.click("#hbell"); page.wait_for_selector("#ntf.open")
        assert page.get_attribute("#hbell button", "aria-expanded") == "true"
        # every board with news, the newest first, under its name; the app has not brought any bell rows yet: the news by page and who
        assert page.locator("#ntf .hb-b").evaluate_all("bs => bs.map(b => b.dataset.hbBoard)") == ["d", "a", "b"]
        a = "#ntf .hb-b[data-hb-board=a]"
        assert page.locator(f"{a} .hb-h .hb-bn").inner_text() == "Brand Book" and page.locator(f"{a} .hb-h .hb-n").inner_text() == "14"
        assert page.locator(f"{a} .nt b").all_inner_texts() == ["+24 images on Renderings", "2 notes on Renderings", "5 moves on Main"], page.locator(f"{a} .nt b").all_inner_texts()
        assert page.locator(f"{a} .nt").first.locator(".who hy-avatar .hya-b").count() == 1   # the agent's badge on Kate's face
        assert page.locator(f"{a} .nt .who").first.inner_text().startswith("Codex · Kate · ")
        assert page.locator("#ntf .nt.new").count() == 5   # new since the last look
        shot(page, "bell-news")
        # opened, it is read: the dot goes; opened again, nothing is tinted
        assert page.locator("#hbell.dot").count() == 0
        page.keyboard.press("Escape"); assert page.locator("#ntf.open").count() == 0
        page.click("#hbell"); assert page.locator("#ntf .nt.new").count() == 0
        page.keyboard.press("Escape")
        # the app brings the bell rows of the two running boards: a new row lights the dot
        page.evaluate(f"hyimgHomeBell({json.dumps(bell_rows(time.time()))})")
        assert page.locator("#hbell.dot").count() == 1
        page.click("#hbell"); page.wait_for_selector("#ntf.open")
        # a running board: its bell rows and the news its bell does not tell, the newest first, under the card's count. Codex's row on
        # Renderings tells Codex's +24 images there; Claude's notes and Kate's moves stay news rows (Kate's comment row is about comments)
        assert page.locator(f"{a} .nt b").all_inner_texts() == ["Put 24 renderings on Renderings", "2 notes on Renderings", "5 moves on Main", "Kate commented"]
        assert page.locator(f"{a} .hb-h .hb-n").inner_text() == "14"
        assert page.locator(f"{a} .nt.new").count() == 1 and page.locator(f"{a} .nt.new b").inner_text() == "Put 24 renderings on Renderings"
        assert page.get_attribute(f"{a} .nt .pv img", "src") == "http://127.0.0.1:4999/thumb?p=r%2Fa.png&s=320"   # from its board's server
        assert page.locator("#ntf .hb-b[data-hb-board=d] .nt b").all_inner_texts() == ["Gemini put 2 images"]
        assert page.locator("#ntf .hb-b[data-hb-board=b] .nt b").all_inner_texts() == ["3 comments on Main"]   # stopped: its news
        assert {"action": "bellRead", "read": {"a": ["n1"]}} in sent
        shot(page, "bell-rows")
        shot(page, "bell-panel", "#ntf")
        # news after the last look on a running board: its rows are new, and so is the bell row that tells some of it
        page.keyboard.press("Escape")
        later = boards(); later[0]["news"]["t"] = time.time() + 60; push(page, later)
        assert page.locator("#hbell.dot").count() == 1
        page.click("#hbell"); page.wait_for_selector("#ntf.open")
        assert page.locator(f"{a} .nt.new b").all_inner_texts() == ["2 notes on Renderings", "5 moves on Main", "Put 24 renderings on Renderings"]
        # the app's since (the last look) bounds what a bell row tells: a row from before it tells nothing
        page.keyboard.press("Escape")
        later[0]["news"]["since"] = time.time() - 10; push(page, later)
        page.click("#hbell"); page.wait_for_selector("#ntf.open")
        assert page.locator(f"{a} .nt b").all_inner_texts() == ["+24 images on Renderings", "2 notes on Renderings", "5 moves on Main",
                                                                  "Put 24 renderings on Renderings", "Kate commented"]
        page.keyboard.press("Escape"); push(page, boards()); page.click("#hbell")
        # a row opens its board at the place: page and objects, or the area; never a server key
        page.click(f"{a} .nt[data-n=n1]")
        assert sent[-1] == {"action": "open", "id": "a", "page": "p2", "obj": ["x1", "x2"]}, sent[-1]
        assert page.locator("#ntf.open").count() == 0
        page.click("#hbell"); page.click(f"{a} .nt[data-n='c:7']")
        assert sent[-1] == {"action": "open", "id": "a", "page": "main", "area": [10, 20, 300, 200]}, sent[-1]
        page.click("#hbell"); page.click("#ntf .hb-b[data-hb-board=b] .nt")
        assert sent[-1] == {"action": "open", "id": "b", "page": "main"}, sent[-1]
        page.click("#hbell"); page.click("#ntf .hb-b[data-hb-board=d] .hb-h")
        assert sent[-1] == {"action": "open", "id": "d"}, sent[-1]
        # a press outside closes it
        page.click("#hbell"); page.mouse.click(1200, 780); assert page.locator("#ntf.open").count() == 0
        assert not any(m["action"] in ("startServer", "stopServer") for m in sent)
        assert not errors, errors
        browser.close()


def test_bell_and_counts_in_russian():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p, lang="ru")
        assert page.get_attribute("#hbell button", "title") == "Уведомления"
        page.click("#hbell")
        assert page.inner_text("#ntf .nh0") == "Уведомления"
        # the page first, its name as written: «Renderings: +24 картинки», the unnamed first page «Страница 1: +2 картинки»
        assert page.locator("#ntf .hb-b[data-hb-board=a] .nt b").first.inner_text() == "Renderings: +24 картинки"
        assert page.locator("#ntf .hb-b[data-hb-board=d] .nt b").inner_text() == "Страница 1: +2 картинки"
        shot(page, "bell-panel-ru", "#ntf")
        assert page.locator("aside [data-folder=f1] .hb-n").get_attribute("title") == "17 новых"
        page.keyboard.press("Escape"); push(page, [])
        assert page.locator("aside .hb-n").count() == 0 and page.locator("#hbell.dot").count() == 0
        page.click("#hbell"); assert page.inner_text("#ntf .none") == "На досках ничего нового"
        assert page.evaluate("window.__tMiss") == [], page.evaluate("window.__tMiss")
        assert not errors, errors
        browser.close()


def test_card_line_is_data_only():
    """«16 min ago · 7,814 frames · 3.5 GB», no «Edited», no «on the canvas»; the faces and the news badge stay"""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        assert text(page, ".card[data-id=a] .meta .s > span") == "16 min ago · 7,814 frames · 3.5 GB"
        assert text(page, ".card[data-id=b] .meta .s > span").endswith(" · 12 frames") and "Edited" not in page.inner_text(".grid")
        assert page.locator(".card[data-id=a] .meta .s .nb-who hy-avatar").count() == 3 and page.inner_text(".card[data-id=a] .meta .s .nb") == "14"
        shot(page, "meta-line", ".card[data-id=a]")
        push(page, boards(), view="list")
        assert text(page, ".list .card[data-id=a] .c3 > span") == "16 min ago" and page.locator(".list .lh").inner_text().count("Edited") == 1
        browser.close()
        browser, page, errors, sent = home(p, lang="ru")
        assert text(page, ".card[data-id=a] .meta .s > span") == "16 мин назад · 7 814 кадров · 3,5 ГБ"
        # the data comes first: at 1280 px the line keeps it whole and shows the faces that still fit, one at least
        page.wait_for_timeout(100)
        fit = page.evaluate("""() => { const s = document.querySelector('.card[data-id=a] .meta .s > span');
          return [s.scrollWidth <= s.clientWidth, document.querySelectorAll('.card[data-id=a] .nb-who > hy-avatar:not([hidden])').length]; }""")
        assert fit[0] and 1 <= fit[1] < 3, fit
        page.set_viewport_size({"width": 1440, "height": 800}); page.wait_for_timeout(200)
        assert page.locator(".card[data-id=a] .nb-who > hy-avatar:not([hidden])").count() == 3   # room again: all three
        shot(page, "meta-line-ru", ".card[data-id=a] .meta")
        assert text(page, ".card[data-id=c] .meta .s > span") == "1 мин назад · 1 кадр"
        assert page.evaluate("window.__tMiss") == [], page.evaluate("window.__tMiss")
        assert not errors, errors
        browser.close()
