"""Home's standard Archive (owner 2026-10-08: «Папку архив (или проект) Архив сделай, пожалуйста, стандартный, ее не удалить, она просто
есть. И туда будем пихать все, что не должно светиться нигде. Там просто будут лежать архивные какие-то старые файлы»). Home opened as a
file with a fake app bridge, Chromium, dark theme: the Archive is always there and can't be renamed or deleted, the owner's own archive
project is folded into it once, a board goes in and comes back to its project (homeSave), and an archived board shows only inside it:
not in Recent, All boards, Favorites, the news counts or the bell, never started from Home; a search lists it under «In Archive».
The app's side (⌃Tab, macOS notifications, starting servers) is tests/test_native_archive.swift. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
HOME = (Path(__file__).resolve().parents[1] / "review/home.html").as_uri()


def boards():
    """a in Brand Studio, b loose with news, c in the owner's own «_Archive» with news, d loose and open"""
    now = time.time()
    news = lambda n: {"n": n, "t": now - 120, "rows": [{"p": "Main", "pid": "main", "k": "add", "w": "codex", "n": 1, "c": n}]}
    return [{"id": "a", "name": "Brand Book", "path": "/tmp/boards/Brand Book", "available": True, "updated": now - 600, "covers": [], "onCanvas": 12},
            {"id": "b", "name": "Studio North", "path": "/tmp/boards/Studio North", "available": True, "updated": now - 3600, "covers": [], "news": news(4)},
            {"id": "c", "name": "Old Lookbook", "path": "/tmp/boards/Old Lookbook", "available": True, "updated": now - 86400 * 90, "covers": [],
             "onCanvas": 40, "news": news(7)},
            {"id": "d", "name": "Studio Test", "path": "/tmp/boards/Studio Test", "available": True, "updated": now - 7200, "covers": [], "open": True}]


FOLDERS = [{"id": "f1", "name": "Brand Studio", "projects": ["a"]}, {"id": "f9", "name": "_Archive", "icon": "🗂️", "projects": ["c"]}]


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def home(p, lang=None):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    errors, sent = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.expose_function("__post", lambda m: sent.append(m))
    page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
    if lang: page.add_init_script(f"window.HY_LANG = {json.dumps(lang)};")
    page.goto(HOME)
    return browser, page, errors, sent


def push(page, home, projects=None):
    page.evaluate(f"hyimgHome({json.dumps({'projects': projects or boards(), 'settings': {'cv.theme': 'dark'}, 'home': home})})")


def saved(sent):
    return [m["home"] for m in sent if m.get("action") == "homeSave"]


def box(home):
    return next(f for f in home["folders"] if f["id"] == "archive")


def ids(page, sel=".card"):
    return page.eval_on_selector_all(f"#body {sel}", "els => els.map(e => e.dataset.id)")


def test_the_archive_is_always_there_takes_the_owners_archive_once_and_cant_be_renamed_or_deleted():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        push(page, {"folders": FOLDERS, "favs": ["c"]})
        h = saved(sent)[-1]
        # made at once, last of the projects; the owner's «_Archive» folded in, its board remembered as from no project, the fold kept
        assert [f["id"] for f in h["folders"]] == ["f1", "archive"], h["folders"]
        a = box(h)
        assert (a["name"], a["icon"], a["projects"], a["from"]) == ("Archive", "archive", ["c"], {"c": ""})
        assert a["merged"] == [{"id": "f9", "name": "_Archive", "icon": "🗂️", "color": "", "projects": ["c"]}]
        # its row is the very last of the sidebar, after «No project»
        rows = page.eval_on_selector_all("#plist .nav", "els => els.map(e => e.dataset.folder || e.dataset.tab || e.dataset.open)")
        assert rows[-2:] == ["none", "archive"], rows
        assert page.locator("aside [data-folder=archive] .nm").inner_text() == "Archive" and page.locator("aside [data-folder=archive] .ct").inner_text() == "1"
        # the saved home comes back from the app: nothing changes, nothing is saved again
        n = len(saved(sent)); push(page, h); assert len(saved(sent)) == n
        # no rename: a double click opens no field, its right click is the empty space's menu (no Rename, Icon or Delete)
        page.locator("aside [data-folder=archive]").dblclick()
        assert page.locator("input[data-fname]").count() == 0 and page.locator(".head h1").inner_text() == "Archive"
        page.locator("aside [data-folder=archive]").click(button="right")
        items = page.locator("#menu.open button").all_inner_texts()
        assert items == ["New board", "Board from a Finder folder…", "New project"], items
        page.keyboard.press("Escape")
        page.locator(".head .hic[data-ficon=archive]").click()
        assert "open" not in (page.get_attribute("#pjpick", "class") or "")
        # no delete: a home.json read without it (edited by hand) gets it back, empty; one written without it by something else keeps the
        # file's Archive and its boards in the app (native/HomeArchive.swift kept, tests/test_native_archive.swift)
        stale = {"folders": [{"id": "f1", "name": "Brand Studio", "projects": ["a"]}], "favs": []}
        push(page, stale)
        assert [f["id"] for f in saved(sent)[-1]["folders"]] == ["f1", "archive"] and page.locator("aside [data-folder=archive]").count() == 1
        # a new project goes before it
        page.hover("#plist"); page.locator("#plist h4.ph [data-local=newfolder]").click(); page.keyboard.press("Enter")
        assert [f["id"] for f in saved(sent)[-1]["folders"]][-1] == "archive" and len(saved(sent)[-1]["folders"]) == 3
        assert not errors, errors
        browser.close()


def test_an_unreadable_home_json_is_not_written_over_by_the_archive_alone():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        # the app could not read home.json (none, or broken): home {}. Home shows the Archive but writes nothing on its own
        push(page, {})
        assert page.locator("aside [data-folder=archive]").count() == 1 and saved(sent) == []
        page.locator("aside [data-folder=archive]").click()
        assert "Nothing in the Archive" in page.locator("#body .none").inner_text() and saved(sent) == []
        # the owner's first change writes it, with the Archive
        page.locator("aside [data-tab=all]").click()
        page.locator(".card[data-id=a]").click(button="right"); page.locator("#menu [data-local=move][data-f=archive]").click()
        assert [f["id"] for f in saved(sent)[-1]["folders"]] == ["archive"] and box(saved(sent)[-1])["projects"] == ["a"]
        assert not errors, errors
        browser.close()


def test_a_board_made_while_the_archive_is_open_goes_into_no_project():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        push(page, {"folders": FOLDERS, "favs": []})
        page.locator("aside [data-folder=f1]").click(); page.mouse.click(900, 700, button="right")
        page.locator("#menu [data-act=create]").click()
        assert [m for m in sent if m.get("action") == "create"][-1].get("folder") == "f1"   # in a project: into it
        page.locator("aside [data-folder=archive]").click()
        for act in ("create", "add"):
            page.mouse.click(900, 700, button="right"); page.locator(f"#menu [data-act={act}]").click()
            m = [m for m in sent if m.get("action") == act][-1]
            assert "folder" not in m, m   # a new board is in use: not put away into the Archive
        assert not errors, errors
        browser.close()


def test_a_board_goes_into_the_archive_and_back_to_its_project():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        push(page, {"folders": FOLDERS, "favs": []})
        page.locator("aside [data-tab=all]").click()
        # the card's menu: «Move to Archive», remembered from Brand Studio
        page.locator(".card[data-id=a]").click(button="right"); page.locator("#menu [data-local=move][data-f=archive]").click()
        h = saved(sent)[-1]
        assert box(h)["projects"] == ["c", "a"] and box(h)["from"] == {"c": "", "a": "f1"} and h["folders"][0]["projects"] == []
        assert "a" not in ids(page)
        # dragged onto the Archive's row: from no project
        page.locator(".card[data-id=b]").drag_to(page.locator("aside [data-folder=archive]"))
        assert box(saved(sent)[-1])["from"]["b"] == "" and "b" not in ids(page)
        # an open board going in is stopped by the app (which saves it first)
        page.locator(".card[data-id=d]").click(button="right"); page.locator("#menu [data-local=move][data-f=archive]").click()
        assert {"action": "stopServer", "id": "d"} in sent
        # inside the Archive: dimmed, labelled, no heart, no server key
        page.locator("aside [data-folder=archive]").click()
        assert sorted(ids(page)) == ["a", "b", "c", "d"] and page.locator(".card.archived").count() == 4
        assert page.locator(".card[data-id=a] .ar-chip").inner_text() == "Archived"
        page.locator(".card[data-id=a]").hover()
        assert not page.locator(".card[data-id=a] .fav").is_visible() and not any(k.is_visible() for k in page.locator(".card[data-id=a] .hs-key").all())
        op = page.evaluate("getComputedStyle(document.querySelector('.card[data-id=a] .cover .dots')).opacity")
        assert float(op) < 1, op
        shot(page, "archive-open")
        # its menu: «Restore» first, to where it came from; no favourites, no «Start server», no «Remove from “Archive”»
        page.locator(".card[data-id=a]").click(button="right")
        items = page.locator("#menu.open button").all_inner_texts()
        assert items[2].replace(" ", " ").split("\n")[0].startswith("Restore") and "to “Brand Studio”" in items[2], items
        assert not any(t in " ".join(items) for t in ("Start server", "Add to favorites", "Remove from", "Move to Archive")), items
        shot(page, "archive-menu")
        page.locator("#menu [data-local=move][data-id=a]").first.click()
        h = saved(sent)[-1]
        assert h["folders"][0]["projects"] == ["a"] and "a" not in box(h)["projects"] and "a" not in box(h)["from"]
        # «Restore» of a board that came from no project, or from a project deleted since: no project
        page.locator(".card[data-id=b]").click(button="right")
        assert "to No project" in page.locator("#menu [data-local=move][data-id=b]").first.inner_text()
        page.locator("#menu [data-local=move][data-id=b]").first.click()
        assert all("b" not in f["projects"] for f in saved(sent)[-1]["folders"])
        # dragged out onto a project: forgotten in from
        page.locator(".card[data-id=d]").drag_to(page.locator("aside [data-folder=f1]"))
        h = saved(sent)[-1]
        assert "d" in h["folders"][0]["projects"] and "d" not in box(h)["from"] and box(h)["projects"] == ["c"]
        # «Start server» of a board in the Archive: not on its card, not in its menu
        page.locator(".card[data-id=c]").click(button="right")
        assert "Start server" not in page.locator("#menu.open").inner_text()
        page.keyboard.press("Escape")
        assert not any(m.get("action") == "startServer" for m in sent)
        assert not errors, errors
        browser.close()


def test_an_archived_board_shows_nowhere_else_and_a_search_finds_it_in_the_archive():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p)
        push(page, {"folders": FOLDERS, "favs": ["c"]})   # c: archived, a favourite, 7 news
        # Recent and All boards without it; no Favorites (its only favourite is archived); the news counts only b's 4
        assert "c" not in ids(page)
        page.locator("aside [data-tab=all]").click()
        assert sorted(ids(page)) == ["a", "b", "d"] and page.locator(".head .hn").inner_text() == "3"
        assert "Favorites" not in page.locator("#plist").inner_text()
        assert page.locator("aside [data-tab=all] .hb-n").inner_text() == "4"
        page.locator(".head [data-onlynew]").click(); assert ids(page) == ["b"]; page.locator(".head [data-onlynew]").click()
        # inside the Archive: no red number on its card either
        page.locator("aside [data-folder=archive]").click()
        assert ids(page) == ["c"] and page.locator(".card[data-id=c] .nb").count() == 0
        # the bell: its rows from the app are left out, no dot for them, its list says nothing new
        push(page, {"folders": FOLDERS, "favs": ["c"]}, [x for x in boards() if x["id"] != "b"])
        now = time.time()
        rows = [{"id": "r1", "ts": now - 30, "read": False, "title": "Put 7 images", "text": "", "who": "Codex", "by": {"via": "codex"}, "page": "main",
                 "ids": [], "type": "agent"}]
        page.evaluate(f"hyimgHomeBell({json.dumps({'boards': [{'id': 'c', 'base': 'http://127.0.0.1:4999', 'items': rows, 'unread': 1}]})})")
        assert "dot" not in (page.get_attribute("#hbell", "class") or "")
        page.locator("#hbell button").click()
        assert page.locator("#ntf [data-hb-board]").count() == 0 and "Nothing new on the boards" in page.locator("#ntf").inner_text()
        assert not any(m.get("action") == "bellRead" for m in sent)
        page.keyboard.press("Escape")
        # a search of All boards: not among the results, under them «In Archive», dimmed and labelled
        push(page, {"folders": FOLDERS, "favs": ["c"]})
        page.locator("aside [data-tab=all]").click(); page.fill("#q", "look")
        assert page.locator("#body > .grid .card").count() == 0 and "Nothing found" in page.locator("#body .none").inner_text()
        assert page.locator(".ar-found h2").inner_text().startswith("In Archive") and page.locator(".ar-found h2 > span:last-child").inner_text() == "1"
        assert ids(page, ".ar-found .card.archived") == ["c"]
        shot(page, "archive-search")
        # Home's filters hold there too: with «Only new» on, an archived board (no news on Home) is not listed, the new one is
        page.fill("#q", "o"); assert ids(page, ".ar-found .card") == ["c"]
        page.locator(".head [data-onlynew]").click()
        assert ids(page, ".grid .card") == ["b"] and page.locator(".ar-found").count() == 0
        shot(page, "archive-search-onlynew")
        page.locator(".head [data-onlynew]").click()
        # and «Only mine»: a shared board in the Archive is not listed under it, a private one is
        vis = [{**x, "vis": "shared" if x["id"] == "c" else "private"} for x in boards()]
        push(page, {"folders": FOLDERS, "favs": [], "vis": "private"}, vis); page.fill("#q", "o")
        assert page.locator(".ar-found").count() == 0
        push(page, {"folders": FOLDERS, "favs": [], "vis": "shared"}, vis); page.fill("#q", "o")
        assert ids(page, ".ar-found .card") == ["c"]
        push(page, {"folders": FOLDERS, "favs": ["c"]})
        page.fill("#q", "studio")
        assert sorted(ids(page, ".grid .card")) == ["b", "d"] and page.locator(".ar-found").count() == 0
        # inside a project or the Archive the search stays there
        page.locator("aside [data-folder=archive]").click(); page.fill("#q", "look")
        assert ids(page) == ["c"] and page.locator(".ar-found").count() == 0
        # the list view says Archive in its project column
        page.fill("#q", ""); page.locator(".head [data-view=list]").click()
        assert page.locator(".list .card[data-id=c] .c2").inner_text().strip() == "Archive"
        assert not errors, errors
        browser.close()


def test_the_archive_in_russian():
    with playwright.sync_playwright() as p:
        browser, page, errors, sent = home(p, "ru")
        push(page, {"folders": FOLDERS, "favs": []})
        assert box(saved(sent)[-1])["name"] == "Архив"   # the board's crumb reads the name from home.json, in the app's language
        assert page.locator("aside [data-folder=archive] .nm").inner_text() == "Архив"
        page.locator("aside [data-tab=all]").click()
        page.locator(".card[data-id=a]").click(button="right")
        assert page.locator("#menu [data-local=move][data-f=archive]").inner_text().strip() == "В архив"
        page.locator("#menu [data-local=move][data-f=archive]").click()
        page.locator("aside [data-folder=archive]").click()
        assert page.locator(".card[data-id=a] .ar-chip").inner_text() == "В архиве"
        page.locator(".card[data-id=a]").click(button="right")
        t = page.locator("#menu [data-local=move][data-id=a]").first.inner_text().replace("\n", " ")
        assert t.startswith("Вернуть") and "в «Brand Studio»" in t, t
        page.keyboard.press("Escape")
        push(page, {"folders": [{"id": "archive", "name": "Archive", "icon": "archive", "projects": []}]})
        page.locator("aside [data-folder=archive]").click()
        assert "В архиве пусто" in page.locator("#body .none").inner_text()
        assert page.evaluate("window.__tMiss") == [], "Russian words missing from ui/lang-common.js"
        assert not errors, errors
        browser.close()
