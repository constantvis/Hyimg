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
        assert not errors, errors
        browser.close()
