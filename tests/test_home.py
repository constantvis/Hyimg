"""Home of the Mac app (review/home.html), opened as a file with a fake app bridge (the page talks to the app only through
webkit.messageHandlers.hyimg and window.hyimgHome)."""
import json
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()
P = [{"id": "a", "name": "Lookbook FW27", "path": "/x", "available": True, "updated": 1791100000, "covers": []},
     {"id": "b", "name": "Studio North · стенд", "path": "/y", "available": True, "updated": 1791000000, "covers": []},
     {"id": "c", "name": "Hyimg App", "path": "/z", "available": True, "updated": 0, "covers": []}]


def test_home_loads_folders_of_projects_and_its_menus():
    """Owner 2026-10-04: «on a reload it is empty and then something appears» (a loading state until the app sends the projects);
    «remove Добавить папку, keep the right click, Добавить проект; a folder gathers projects, Studio North, Lookbook FW27, apart
    from Finder folders»; later «folders become projects: projects, boards, pages». They live in home.json (folders) through the app (homeSave)."""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.add_init_script("window.HY_LANG = 'ru';")   # the app's language, Russian: this test checks Home's Russian words (owner 2026-10-06)
        page.goto(HOME)
        assert page.locator(".skel").count() > 0 and "Проектов пока нет" not in page.inner_text("body")
        page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {'cv.theme': 'light'}, 'home': {'folders': []}})})")
        assert page.evaluate("document.documentElement.dataset.theme") == "light"
        assert not page.get_by_text("Добавить папку").count()
        page.mouse.click(900, 700, button="right")
        assert page.locator("#menu.open button").all_inner_texts() == ["Новая доска", "Доска из папки Finder…", "Новый проект"]
        page.locator("#menu [data-local=newfolder]").click()
        page.locator("input[data-fname]").fill("Studio North"); page.keyboard.press("Enter")
        page.locator(".card[data-id=b]").drag_to(page.locator("[data-folder]").first)
        saves = [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"]
        assert saves[-1]["folders"][0]["name"] == "Studio North" and saves[-1]["folders"][0]["projects"] == ["b"]
        assert page.locator("#plist h4").first.text_content() == "Проекты" and not page.locator("#plist [data-tw]").count()
        # a project's icon: the picker under its icon, an icon in a colour or any emoji, kept in home.json
        page.locator("aside [data-ficon]").first.click(); page.locator("#pjpick [data-pjcolor='#3e63dd']").click(); page.locator("#pjpick [data-pjicon=camera]").click()
        page.locator("#pjpick [data-pjtab=emoji]").click(); page.locator("#pjpick [data-pjown]").fill("🦊"); page.keyboard.press("Enter")
        f0 = [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"][-1]["folders"][0]
        assert (f0["icon"], f0["color"]) == ("🦊", "#3e63dd") and page.locator("aside [data-ficon] .emo").inner_text() == "🦊"
        page.locator("[data-folder]").first.click()
        assert page.locator(".head h1").inner_text() == "Studio North" and page.locator(".card .n").all_inner_texts() == ["Studio North · стенд"]
        page.locator(".card[data-id=b]").click(button="right"); page.locator("#menu [data-local=unfile]").click()
        assert [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"][-1]["folders"][0]["projects"] == []
        # saving shows its steps on the board's own cover
        page.locator("[data-tab=all]").click()
        # favourites: none, no section; the heart on the cover puts a board on top of the sidebar, without opening it
        assert "Избранное" not in page.locator("#plist").text_content()
        page.locator(".card[data-id=c]").hover(); page.locator(".fav[data-fav=c]").click()
        assert page.locator("#plist h4").first.text_content() == "Избранное" and page.locator("#plist [data-open=c]").count() == 1
        assert [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"][-1]["favs"] == ["c"]
        assert not any(m["action"] == "open" for m in page.evaluate("window.__sent"))
        # cards or a list, as in Figma: the switch at the far right of the title, kept in home.json
        page.locator(".head [data-view=list]").click()
        assert page.locator(".list .card").count() == 3 and [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"][-1]["view"] == "list"
        page.locator(".head [data-view=grid]").click(); assert page.locator(".grid .card").count() == 3
        # the plus by «Проекты», shown on hover, makes a new project and names it in place
        n = page.locator("[data-folder]").count(); page.hover("#plist"); page.locator("#plist h4.ph [data-local=newfolder]").click()
        assert page.locator("[data-folder]").count() == n + 1 and page.locator("input[data-fname]").count() == 1
        page.keyboard.press("Escape")
        # «Без проекта»: the boards in no project, last in the list; a board dragged onto it leaves its project
        page.locator("[data-folder]").first.click(); page.locator("aside [data-tab=none]").click()
        assert page.locator(".head h1").inner_text() == "Без проекта" and page.locator(".card").count() == 3
        page.locator("[data-folder]").first.click(); page.locator("[data-tab=all]").click()
        page.locator(".card[data-id=a]").drag_to(page.locator("[data-folder]").first); page.locator(".card[data-id=a]").drag_to(page.locator("aside [data-tab=none]"))
        assert all("a" not in f["projects"] for f in [m["home"] for m in page.evaluate("window.__sent") if m["action"] == "homeSave"][-1]["folders"])
        page.evaluate(f"hyimgProgress({json.dumps({'id': 'b', 'text': 'Сохраняю'})})")
        page.wait_for_function("() => document.querySelectorAll('.prog[data-prog=b] li').length === 1")
        # opening a board: Home leaves at once, the plate and the steps stay in the middle until the canvas is drawn, then it hands over
        assert page.evaluate("hyimgOpen('a', 'Стенд')") is True
        assert page.locator("#load .nm").inner_text() == "Стенд" and "leave" in page.get_attribute("body", "class")
        for t in ("Сервер доски · порт 4181", "Сервер ответил · 40 мс"): page.evaluate(f"hyimgProgress({json.dumps({'id': 'a', 'text': t})})")
        page.wait_for_function("() => document.querySelectorAll('#load li').length === 2 && !document.querySelector('.prog[data-prog=a].on')")
        page.evaluate(f"hyimgProgress({json.dumps({'id': 'a', 'text': 'Доска нарисована', 'done': True})})")
        assert page.evaluate("hyimgHandoff('a')") is True
        page.wait_for_function("() => (window.__sent || []).some(m => m.action === 'handoff' && m.id === 'a')", timeout=4000)
        assert page.locator("#load li").count() == 3
        # back on Home it settles in at once, without waiting for fresh data
        assert page.evaluate("hyimgBack()") is True
        assert "leave" not in (page.get_attribute("body", "class") or "") and not page.locator("#load li").count()
        page.wait_for_function("() => getComputedStyle(document.querySelector('#load')).visibility === 'hidden'")
        assert page.evaluate("window.__tMiss") == [], "Russian words missing from ui/lang-home.js or ui/lang-common.js"
        assert not errors, errors
        browser.close()


# Two languages (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»): English by default, Russian by the
# app's setting cv.lang. In English nothing of the interface is Russian, only the owner's own data (and «Русский», the switch's own name).
PE = [{"id": "a", "name": "Lookbook FW27", "path": "/x", "available": True, "updated": 1791100000, "covers": [], "onCanvas": 1234, "open": True},
      {"id": "b", "name": "Studio North", "path": "/y", "available": False, "updated": 0, "covers": []}]
CYR = """() => { const out = [], add = s => { if (s && /[А-Яа-яЁё]/.test(s.replace(/Русский/g, ""))) out.push(s); };
  add(document.title); add(document.body.innerText);
  document.querySelectorAll("body *").forEach(el => ["title", "aria-label", "placeholder", "alt", "data-e"].forEach(a => add(el.getAttribute(a))));
  return out; }"""


def _home(p, lang=None):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    sent = []
    page.expose_function("__post", lambda m: sent.append(m))   # survives the page's reloads
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
    if lang: page.add_init_script(f"window.HY_LANG = {json.dumps(lang)};")
    page.goto(HOME)
    return browser, page, errors, sent


def _crawl(page, check):
    """every part of Home with words in it, each checked: the cards, the list, the menus, the settings, the icon picker, the loading"""
    page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {'cv.lang': page.evaluate('T.lang')}, 'home': {'folders': [{'id': 'f1', 'name': 'Studio', 'projects': ['a']}], 'favs': ['a']}})})")
    check("cards")
    page.locator(".card[data-id=a]").click(button="right"); check("a board's menu"); page.keyboard.press("Escape")
    page.locator("[data-folder=f1]").click(button="right"); check("a project's menu"); page.keyboard.press("Escape")
    page.mouse.click(900, 800, button="right"); check("the empty space's menu"); page.keyboard.press("Escape")
    page.locator("#bset").click(); check("the settings"); page.locator("#bset").click()
    page.locator("aside [data-ficon=f1]").click(); check("the icon picker, icon"); page.locator("#pjpick [data-pjtab=emoji]").click(); check("the icon picker, emoji"); page.keyboard.press("Escape")
    page.locator("[data-folder=f1]").click(); page.locator(".head [data-view=list]").click(); check("a project as a list")
    page.locator("aside [data-tab=none]").click(); check("no project"); page.locator(".head [data-view=grid]").click()
    page.fill("#q", "zzz"); check("nothing found"); page.fill("#q", "")
    page.evaluate("hyimgOpen('a', 'Lookbook FW27')"); check("a board loading"); page.evaluate("hyimgBack()")
    page.evaluate(f"hyimgHome({json.dumps({'projects': [], 'settings': {'cv.lang': page.evaluate('T.lang')}, 'home': {'folders': []}})})"); check("no boards")


def test_home_in_english_has_no_russian_words():
    with playwright.sync_playwright() as p:
        browser, page, errors, _ = _home(p)
        assert page.evaluate("T.lang") == "en" and page.evaluate("document.documentElement.lang") == "en"
        def check(where):
            left = page.evaluate(CYR); assert not left, (where, left)
        check("loading")
        _crawl(page, check)
        page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {}, 'home': {'folders': []}})})")
        assert "1,234 frames on the canvas" in page.inner_text(".card[data-id=a]") and "Never opened" in page.inner_text(".card[data-id=b]")
        assert page.locator("#plist h4").first.text_content() == "Projects" and page.locator(".head h1").inner_text() in ("Recent", "All boards", "No project")
        assert not errors, errors
        browser.close()


def test_home_language_switch():
    """the Language setting, first in Home's settings: English | Русский; the app's setting cv.lang is sent, and without the app
    (no HY_LANG, as here) Home reloads in it; the app's settings with another language bring Home to it as well"""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = _home(p)
        page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {}, 'home': {'folders': []}})})")
        page.locator("#bset").click()
        assert page.locator("#sets .sh").first.inner_text().lower() == "language"
        assert page.locator("#sets [data-set='cv.lang'] button").all_inner_texts() == ["English", "Русский"]
        assert page.get_attribute("#sets [data-set='cv.lang'] [data-v=en]", "aria-pressed") == "true"
        page.locator("#sets [data-set='cv.lang'] [data-v=ru]").click()
        page.wait_for_function("document.documentElement.lang === 'ru'", timeout=5000)
        assert {"action": "settings", "change": {"cv.lang": "ru"}} in sent
        page.wait_for_selector("aside [data-tab=recent]")
        assert page.locator("aside [data-tab=recent]").inner_text() == "Недавние" and page.get_attribute("#q", "placeholder") == "Найти доску"
        # Russian everywhere, every word from the dictionaries
        _crawl(page, lambda where: None)
        assert page.evaluate("window.__tMiss") == [], page.evaluate("window.__tMiss")
        page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {'cv.lang': 'ru'}, 'home': {'folders': []}})})")
        assert "1 234 кадра на холсте" in page.inner_text(".card[data-id=a]").replace("\u00a0", " ") and page.locator("#plist h4").first.text_content() == "Проекты"
        # the app's settings say English (none): Home goes back to it
        page.evaluate(f"setTimeout(() => hyimgHome({json.dumps({'projects': PE, 'settings': {}, 'home': {'folders': []}})}))")
        page.wait_for_function("document.documentElement.lang === 'en'", timeout=5000)
        page.wait_for_selector("aside [data-tab=recent]")
        assert page.locator("aside [data-tab=recent]").inner_text() == "Recent"
        assert not errors, errors
        browser.close()


def test_home_in_the_app_waits_for_the_app():
    """with the app (HY_LANG given) Home only sends the choice: the app writes it and reloads Home in it"""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = _home(p, "ru")
        page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {}, 'home': {'folders': []}})})")
        assert page.evaluate("T.lang") == "ru" and page.locator("aside [data-tab=recent]").inner_text() == "Недавние"
        page.locator("#bset").click()
        assert page.get_attribute("#sets [data-set='cv.lang'] [data-v=ru]", "aria-pressed") == "true"
        page.locator("#sets [data-set='cv.lang'] [data-v=en]").click(); page.wait_for_timeout(600)
        assert {"action": "settings", "change": {"cv.lang": "en"}} in sent and page.evaluate("T.lang") == "ru"
        assert not errors, errors
        browser.close()


def test_home_choices_are_the_one_segmented_control():
    """Owner 2026-10-06: «why isn't this a switch like ours»: Home's cards/list switch and the settings' choices are the app's .seg, one
    capsule with a thumb that slides, eased, under the chosen option."""
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = _home(p)
        page.evaluate(f"hyimgHome({json.dumps({'projects': PE, 'settings': {}, 'home': {'folders': []}})})")
        vt = page.locator(".head .seg.vt")
        assert vt.count() == 1 and vt.locator("> .st").count() == 1 and vt.locator("button").count() == 2
        thumb = lambda root: root.evaluate("seg => { const t = seg.querySelector(':scope > .st'), b = seg.querySelector(':scope > [aria-pressed=true]'); return { x: t.offsetLeft + new DOMMatrix(getComputedStyle(t).transform).m41, bx: b.offsetLeft, w: parseFloat(t.style.width), bw: b.offsetWidth }; }")
        page.wait_for_timeout(400)
        a = thumb(vt); assert abs(a["x"] - a["bx"]) < 1.5 and abs(a["w"] - a["bw"]) < 1.5, a   # under the chosen card view
        assert page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.head .seg.vt > .st')).transitionDuration) > 0")   # eased
        page.locator(".head [data-view=list]").click()
        page.wait_for_timeout(500)
        b = thumb(page.locator(".head .seg.vt")); assert b["bx"] > a["bx"] and abs(b["x"] - b["bx"]) < 1.5, (a, b)   # it slid to the list
        assert page.locator(".list .card").count() == len(PE)
        # a moment after the click it is on its way, not there yet
        page.locator(".head [data-view=grid]").click()
        mid = page.evaluate("() => { const t = document.querySelector('.head .seg.vt > .st'); return new DOMMatrix(getComputedStyle(t).transform).m41; }")
        page.wait_for_timeout(500)
        end = page.evaluate("() => { const t = document.querySelector('.head .seg.vt > .st'); return new DOMMatrix(getComputedStyle(t).transform).m41; }")
        assert abs(end - a["bx"]) < 1.5 and mid > end, (mid, end, a)
        # the settings: every choice is a .seg with a thumb under its chosen option
        page.locator("#bset").click(); page.wait_for_timeout(400)
        segs = page.locator("#sets .seg"); n = segs.count()
        assert n >= 7 and page.locator("#sets .opts").count() == 0
        for i in range(n):
            if not segs.nth(i).is_visible(): continue
            assert segs.nth(i).locator("> .st").count() == 1, i
        theme = page.locator("#sets .seg[data-set='cv.theme']"); x0 = thumb(theme)
        theme.locator("[data-v=dark]").click(); page.wait_for_timeout(500)
        x1 = thumb(theme); assert x1["bx"] != x0["bx"] and abs(x1["x"] - x1["bx"]) < 1.5, (x0, x1)
        assert not errors, errors
        browser.close()


def test_a_board_menu_ends_with_a_red_remove():
    """(owner 2026-10-06: «why can't I remove it completely? write it in red»): a board's menu on Home ends with «Remove board…» in
    red, which asks the app to remove it (the app asks first and keeps the folder on disk)"""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.goto(HOME)
        page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {'cv.theme': 'dark'}, 'home': {'folders': []}})})")
        page.locator(".card[data-id=b]").click(button="right")
        last = page.locator("#menu.open button").last
        assert last.inner_text() == "Remove board…"
        r, g, b = page.evaluate("el => getComputedStyle(el).color.match(/\\d+/g).slice(0, 3).map(Number)", last.element_handle())
        assert r > 200 and g < 100 and b < 100, (r, g, b)   # red
        last.click()
        assert [m for m in page.evaluate("window.__sent") if m.get("action") == "removeBoard"] == [{"action": "removeBoard", "id": "b"}] or \
            any(m.get("action") == "removeBoard" for m in page.evaluate("window.__sent"))
        assert not errors, errors
        browser.close()


def test_a_new_board_goes_into_the_picked_project():
    """(owner 2026-10-06: «in Studio North, add board: it is added to this project and appears there, not outside of it»): New board
    and Board from a Finder folder carry the picked project to the app; with Recent or All boards picked they carry none"""
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.goto(HOME)
        page.evaluate(f"hyimgHome({json.dumps({'projects': P, 'settings': {}, 'home': {'folders': [{'id': 'f1', 'name': 'Studio', 'projects': ['a']}]}})})")
        sent = lambda a: [m for m in page.evaluate("window.__sent || []") if m.get("action") == a]
        page.locator("[data-folder=f1]").click()
        page.locator(".head [data-act=create], [data-act=create]").first.click()
        assert sent("create")[-1].get("folder") == "f1", sent("create")
        page.mouse.click(900, 700, button="right"); page.locator("#menu.open [data-act=add]").click()
        assert sent("add")[-1].get("folder") == "f1", sent("add")
        page.locator("[data-tab=all]").click()
        page.locator("[data-act=create]").first.click()
        assert "folder" not in sent("create")[-1], sent("create")
        assert not errors, errors
        browser.close()


# News on a board without the owner (owner 2026-10-06: «on Home show how many new events happened on each board without him»): the
# app sends news {n, rows} with a board (native BoardNews, tests/test_native_news.swift); Home shows the number in a red capsule after
# «Edited …» (the list) or beside the edited line (cards), its words as the plain tooltip, boards with news first in Recent, «Only new»
# filters and is kept in home.json, and the number goes when the board is opened.
NEWS = {"n": 12, "t": 1791100000, "rows": [
    {"p": "Renderings", "pid": "p2", "k": "add", "w": "Codex", "n": 3, "c": 24},
    {"p": "Renderings", "pid": "p2", "k": "note", "w": "Codex", "n": 2, "c": 0},
    {"p": "", "pid": "main", "k": "move", "w": "ai", "n": 7, "c": 30}]}
PN = [{"id": "a", "name": "Lookbook FW27", "path": "/x", "available": True, "updated": 1791100000, "opened": 1791100000, "covers": []},
      {"id": "b", "name": "Studio North", "path": "/y", "available": True, "updated": 1791000000, "opened": 1791000000, "covers": [], "news": NEWS},
      {"id": "c", "name": "Hyimg App", "path": "/z", "available": True, "updated": 1790000000, "opened": 1790000000, "covers": [],
       "news": {"n": 150, "rows": [{"p": "Main", "pid": "main", "k": "add", "w": "claude", "n": 150, "c": 151}]}}]


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_home_shows_news_on_boards(engine):
    with playwright.sync_playwright() as p:
        try: browser = getattr(p, engine).launch()
        except Exception as error: pytest.skip(f"no {engine} for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.add_init_script("window.HY_LANG = 'ru';")
        page.goto(HOME)
        data = lambda home, projects=PN: json.dumps({"projects": projects, "settings": {"cv.theme": "light"}, "home": home})
        saves = lambda: [m["home"] for m in page.evaluate("window.__sent || []") if m["action"] == "homeSave"]
        page.evaluate(f"hyimgHome({data({'folders': [], 'view': 'list'})})")
        # Recent: the boards with news first, in their own order, then the rest
        assert page.locator(".list .card").evaluate_all("cs => cs.map(c => c.dataset.id)") == ["b", "c", "a"]
        # the red capsule after «изменена …», 99+ above 99, none at 0
        nb = page.locator(".card[data-id=b] .c3 .nb")
        assert nb.inner_text() == "12" and page.locator(".card[data-id=c] .c3 .nb").inner_text() == "99+" and page.locator(".card[data-id=a] .nb").count() == 0
        assert page.locator(".card[data-id=b] .c3 > span").first.inner_text().startswith("изменена")
        look = nb.evaluate("el => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return { bg: s.backgroundColor, fg: s.color, rad: parseFloat(s.borderRadius), h: r.height, w: r.width }; }")
        assert look["bg"] == "rgb(255, 59, 48)" and look["fg"] == "rgb(255, 255, 255)" and look["rad"] >= look["h"] / 2 and look["w"] >= look["h"], look
        # its words: the usual tooltip (title), one line by page and kind, then who
        assert nb.get_attribute("title") == "12 новых: +24 картинки, 2 заметки на Renderings; 7 перемещений на Страница 1 · Codex, ИИ"
        assert page.locator(".card[data-id=c] .nb").get_attribute("title") == "150 новых: +151 картинка на Main · claude"
        # the cards: the same capsule beside the edited line
        page.locator(".head [data-view=grid]").click()
        g = page.locator(".grid .card[data-id=b] .meta .s .nb")
        assert g.inner_text() == "12" and g.get_attribute("title").startswith("12 новых: +24 картинки")
        line, cap = page.locator(".grid .card[data-id=b] .meta .s > span").first.bounding_box(), g.bounding_box()
        assert abs((line["y"] + line["height"] / 2) - (cap["y"] + cap["height"] / 2)) < 2 and cap["x"] >= line["x"] + line["width"]
        # dark: the iPhone's dark red
        page.evaluate(f"hyimgHome({json.dumps({'projects': PN, 'settings': {'cv.theme': 'dark'}, 'home': {'folders': [], 'view': 'grid'}})})")
        assert page.locator(".card[data-id=b] .nb").evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(255, 69, 58)"
        # «Только с новым»: only the boards with news, kept in home.json, and it comes back so
        tg = page.locator(".head .nf [data-onlynew]")
        assert tg.inner_text() == "Только с новым" and tg.get_attribute("aria-pressed") == "false" and tg.get_attribute("data-has") is not None
        tg.click()
        assert page.locator(".grid .card").evaluate_all("cs => cs.map(c => c.dataset.id)") == ["b", "c"] and saves()[-1].get("onlyNew") is True
        page.wait_for_timeout(350)
        assert page.evaluate("() => getComputedStyle(document.querySelector('.head .nf > .st')).opacity") == "1"   # its thumb, the app's one selected look
        page.reload(); page.evaluate(f"hyimgHome({data({'folders': [], 'view': 'grid', 'onlyNew': True})})")
        assert page.locator(".head .nf [data-onlynew]").get_attribute("aria-pressed") == "true" and page.locator(".grid .card").count() == 2
        page.locator("aside [data-tab=all]").click(); assert page.locator(".grid .card").count() == 2   # in every list
        page.locator(".head .nf [data-onlynew]").click()
        assert page.locator(".grid .card").count() == 3 and "onlyNew" not in saves()[-1]
        page.locator("aside [data-tab=recent]").click()
        # opened from Home: the number goes, but the card stays where it was pressed until Home comes back
        page.locator(".grid .card[data-id=b] .cover").click()
        assert {"action": "open", "id": "b"} in page.evaluate("window.__sent")
        assert page.evaluate("hyimgSeen('b')") is True
        assert page.locator(".grid .card").first.get_attribute("data-id") == "b"
        page.evaluate("hyimgOpen('b', 'Studio North')"); page.evaluate("hyimgBack()")
        assert page.locator(".card[data-id=b] .nb").count() == 0 and page.locator(".grid .card").evaluate_all("cs => cs.map(c => c.dataset.id)") == ["c", "a", "b"]
        # seen while Home is on screen (a board left from its tab): at once
        page.evaluate("hyimgSeen('c')")
        assert page.locator(".nb").count() == 0 and page.locator(".head .nf [data-onlynew]").get_attribute("data-has") is None
        page.locator(".head .nf [data-onlynew]").click()
        assert page.locator(".body .none").inner_text() == "На досках ничего нового"
        assert page.evaluate("window.__tMiss") == [], page.evaluate("window.__tMiss")
        assert not errors, errors
        browser.close()


def test_home_news_in_english():
    with playwright.sync_playwright() as p:
        browser, page, errors, _ = _home(p)
        page.evaluate(f"hyimgHome({json.dumps({'projects': PN, 'settings': {}, 'home': {'folders': [], 'view': 'list'}})})")
        assert page.locator(".card[data-id=b] .nb").get_attribute("title") == "12 new: +24 images, 2 notes on Renderings; 7 moves on Page 1 · Codex, AI"
        assert page.locator(".card[data-id=c] .nb").get_attribute("title") == "150 new: +151 images on Main · claude"
        assert page.locator(".head .nf [data-onlynew]").inner_text() == "Only new"
        assert not page.evaluate(CYR), page.evaluate(CYR)
        assert not errors, errors
        browser.close()
