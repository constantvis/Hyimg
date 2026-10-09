"""Two Macs signed into one Dropbox account (owner 2026-10-08): every board folder syncs to both, each Mac has its own catalog.
- Home on a Mac: «Boards in Dropbox not on this Mac» from the background scan (review/boardid.py scan) of a temporary Dropbox-like root
  with two board folders, «Add» per board; a hyimg:// link's board offered as «Add this board from Dropbox» (window.hyimgOffer).
- People across the two Macs: one board folder, two profiles; the second Mac names the first Mac's person from the board's card and
  his changes carry his id; the server's health gives the board's folder id and its folder relative to Dropbox.
Chromium, dark theme, temporary folders only, only these tests (nice -n 10)."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_shortcuts import free_port, png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
sys.path.insert(0, str(ROOT / "review"))
import people  # noqa: E402


def dropbox(tmp):
    """a Dropbox-like root: a board made on the other Mac (board.json), an old board (saved pages, no board.json), a plain folder"""
    root = tmp / "Dropbox"
    a = root / "Studio/Brand/Atlas"; (a / "_review").mkdir(parents=True)
    (a / "_review/board.json").write_text(json.dumps({"id": str(uuid.uuid4()), "name": "Studio Atlas", "created": "2026-10-08T09:00:00Z"}))
    b = root / "Projects/Old board"; (b / "_review/boards").mkdir(parents=True)
    (root / "Projects/Photos").mkdir(parents=True)
    return root


def scan(root, catalog=None):
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}, "HYIMG_DROPBOX_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, str(ROOT / "review/boardid.py"), "scan"] + (["--catalog", str(catalog)] if catalog else []),
                         env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_home_lists_boards_in_dropbox_and_offers_a_links_board(tmp_path):
    root = dropbox(tmp_path)
    found = scan(root)
    assert [b["name"] for b in found["boards"]] == ["Old board", "Studio Atlas"] and found["complete"]
    projects = [{"id": "p1", "name": "Concepts", "path": str(tmp_path / "Concepts"), "available": True, "updated": 1791100000, "covers": []}]
    with playwright.sync_playwright() as p:
        try: browser = p.chromium.launch()
        except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark"); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => { (window.__sent = window.__sent || []).push(m); } } } };")
        page.goto(HOME)
        data = lambda boards, ps=projects: json.dumps({"projects": ps, "settings": {"cv.theme": "dark"}, "home": {"folders": []}, "dropbox": {"t": found["t"], "boards": boards}})
        page.evaluate(f"hyimgHome({data(found['boards'])})")
        assert page.evaluate("document.documentElement.dataset.theme") == "dark"
        sec = page.locator("section.dbx")
        assert sec.locator("h2").inner_text().startswith("Boards in Dropbox not on this Mac")
        assert sec.locator(".dbx-row .dbx-n").all_inner_texts() == ["Old board", "Studio Atlas"]
        assert sec.locator(".dbx-row .dbx-p").all_inner_texts() == ["Dropbox/Projects/Old board", "Dropbox/Studio/Brand/Atlas"]
        page.fill("#q", "shell"); page.locator("#q").dispatch_event("input")
        page.wait_for_function("() => document.querySelectorAll('.dbx-row').length === 1")
        page.fill("#q", ""); page.locator("#q").dispatch_event("input")
        page.wait_for_function("() => document.querySelectorAll('.dbx-row').length === 2")
        # «Add» sends the folder; the app's next list no longer has it
        shell = next(b for b in found["boards"] if b["name"] == "Studio Atlas")
        sec.locator(f'.dbx-row[data-dbx-path="{shell["path"]}"] [data-dbx=add] button').click()
        assert [m for m in page.evaluate("window.__sent") if m["action"] == "dropboxAdd"] == [{"action": "dropboxAdd", "path": shell["path"]}]
        page.evaluate(f"hyimgHome({data([b for b in found['boards'] if b is not shell])})")
        assert page.locator(".dbx-row").count() == 1
        # a project's own list shows none of it
        page.locator("aside [data-tab=none]").click()
        assert page.locator("section.dbx").count() == 0
        page.locator("aside [data-tab=all]").click()
        # a link to a board this Mac has not added: the offer on top, «Add» sends it, «Not now» puts it away
        page.evaluate(f"hyimgOffer({json.dumps(shell)})")
        offer = page.locator(".dbx-offer")
        assert offer.locator(".dbx-t b").inner_text() == "Add this board from Dropbox" and "Studio Atlas · Dropbox/Studio/Brand/Atlas" in offer.inner_text()
        if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / "dropbox-home.png"))
        offer.locator("[data-dbx=later] button").click()
        assert page.locator(".dbx-offer").count() == 0
        page.evaluate(f"hyimgOffer({json.dumps(shell)})")
        page.locator(".dbx-offer [data-dbx=add] button").click()
        assert [m["path"] for m in page.evaluate("window.__sent") if m["action"] == "dropboxAdd"] == [shell["path"], shell["path"]]
        assert page.locator(".dbx-offer").count() == 0
        # a second Mac with no boards yet: the empty Home still lists them; Russian words
        page.evaluate(f"hyimgHome({data(found['boards'], [])})")
        assert page.locator(".empty").count() == 1 and page.locator("section.dbx .dbx-row").count() == 2
        assert not errors, errors
        page2 = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        page2.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => {} } } }; window.HY_LANG = 'ru';")
        page2.goto(HOME); page2.evaluate(f"hyimgHome({data(found['boards'])})"); page2.evaluate(f"hyimgOffer({json.dumps(shell)})")
        assert page2.locator("section.dbx h2").inner_text().startswith("Доски в Dropbox, которых нет на этом Mac")
        assert page2.locator(".dbx-offer .dbx-t b").inner_text() == "Добавить эту доску из Dropbox"
        assert page2.locator(".dbx-offer [data-dbx=add]").inner_text() == "Добавить" and page2.locator(".dbx-offer [data-dbx=later]").inner_text() == "Не сейчас"
        browser.close()
    # the scan leaves out what the catalog has, by folder or by folder id
    cat = tmp_path / "projects.json"
    cat.write_text(json.dumps([{"id": str(uuid.uuid4()), "folderId": shell["id"], "libraryRoot": "/elsewhere", "stateRoot": "/elsewhere/_review", "port": 4180}]))
    assert [b["name"] for b in scan(root, cat)["boards"]] == ["Old board"]


def start(lib, state, support, dropbox_root):
    """a board server as one Mac's app starts it: the settings and the profile beside that Mac's catalog"""
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(support / "settings.json"),
               HYIMG_PROFILE_DIR=str(support), HYIMG_DROPBOX_ROOT=str(dropbox_root), PYTHONDONTWRITEBYTECODE="1")
    (support / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    log = open(support / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)
    return port, proc, log


def api(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)


def test_two_macs_name_each_other_through_the_board(tmp_path):
    root = tmp_path / "Dropbox"; lib = root / "Projects/Board"; state = lib / "_review"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    (lib / "a/0.png").write_bytes(png())
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {"i0": {"path": "a/0.png", "x": 0, "y": 0, "w": 320, "ar": 1, "crop": None}},
                                                       "groups": {}, "removed": {}}))
    bid = str(uuid.uuid4()); (state / "board.json").write_text(json.dumps({"id": bid, "name": "Board"}))
    mac_a, mac_b = tmp_path / "A", tmp_path / "B"; mac_a.mkdir(); mac_b.mkdir()
    ann, bob = people.save_me(mac_a, "Ann", "green"), people.save_me(mac_b, "Bob", "orange")
    port, proc, log = start(lib, state, mac_a, root)
    try:
        h = api(port, "/api/health")
        assert h["boardId"] == bid and h["dir"] == "Projects/Board"   # the app's link: hyimg://board/<bid>?…&dir=Projects/Board
        b = api(port, "/api/board?name=main")
        b["items"]["n1"] = {"type": "note", "text": "from Mac A", "x": 0, "y": 900, "w": 320, "fs": 18, "color": "yellow"}
        api(port, "/api/board?name=main&who=owner", b)
    finally:
        proc.terminate(); proc.wait(5); log.close()
    assert (state / "people" / f"{ann['id']}.json").exists() and not list(state.glob("profile.json")) and not list(state.glob("people.json"))
    port, proc, log = start(lib, state, mac_b, root)   # Dropbox brought the same folder to Mac B
    try:
        v = api(port, "/api/profile")
        assert v["me"]["id"] == bob["id"] and v["people"][ann["id"]]["name"] == "Ann" and not v["people"][ann["id"]].get("me")
        ev = api(port, "/api/events?name=main")[0]
        assert ev["by"] == {"person": ann["id"], "via": "app"}
        nid = next(i for i, it in api(port, "/api/board?name=main")["items"].items() if it.get("text") == "from Mac A")
        assert api(port, f"/api/edited?name=main&id={nid}")["by"]["person"] == ann["id"]
    finally:
        proc.terminate(); proc.wait(5); log.close()
    assert json.loads((mac_a / "profile.json").read_text())["id"] == ann["id"] and json.loads((mac_b / "profile.json").read_text())["id"] == bob["id"]
