"""Folders as on the board (owner 2026-10-05, review/foldersync.py): plan, apply, aliases, undo, the auto mode, the library's dialog.

Only ever on a temporary project: two pages, a group inside a group by its frame and one by membership, notes with rows and a note
inside a note's zone, a picture on two pages, name collisions, an ungrouped picture, sidecar jsons with relative links, an image
frame, a pasted picture and an external mount that must not move.
"""
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOTS = os.environ.get("LAYOUT_SHOTS")


def png(w=40, h=60, shade=255):
    raw = b"".join(b"\x00" + bytes([shade, shade, shade]) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pic(path, x, y, w=100, ar=1.0):
    return {"path": path, "x": x, "y": y, "w": w, "ar": ar, "crop": None}


SHADE = (10 + n * 7 % 238 for n in __import__("itertools").count())   # a new grey for every picture


def put(lib, rel, meta=None, raw=None):
    f = lib / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(png(shade=next(SHADE)))   # every picture its own bytes: no library copies
    if meta is not None:
        (f.parent / (f.stem + ".json")).write_text(raw if raw is not None else json.dumps(meta, ensure_ascii=False, indent=2))


def build(tmp):
    lib, state, refs = tmp / "lib", tmp / "state", tmp / "style-refs"
    put(lib, "r30-studio-light/b1.png", {"prompt": "b1 studio", "inputs": ["../inputs/x.png"], "feedback": {"fav": True}})
    put(lib, "r30-studio-light/b2.png", {"prompt": "b2"}, raw='{"prompt":"b2","feedback":{"verdict":"take"}}')   # compact json
    put(lib, "r31-dark/b1.png", {"prompt": "b1 dark"})
    put(lib, "zz/r31-dark/b1.png", {"prompt": "b1 deep"})
    put(lib, "r32/a3.png", {"prompt": "a3"})
    put(lib, "r32/a4.png")
    put(lib, "r32/a5.png", {"prompt": "a5"})
    put(lib, "cells/cell-1.png", {"grid": "../grids/g1.png", "prompt": "cell"})
    put(lib, "grids/g1.png", {"cut": True, "prompt": "grid"})
    put(lib, "inputs/x.png")
    put(lib, "other/o1.png", {"inputs": ["../r32/a3.png"], "prompt": "uses a3"})
    put(lib, "dup/v01.png", {"prompt": "on two pages"})
    put(lib, "loose/u1.png", {"prompt": "ungrouped"})
    put(lib, "_rejected/z.png", {"prompt": "rejected"})
    put(lib, "frm/p1.png", {"prompt": "in a frame"})
    put(lib, "added/261005/120000-paste.png", {"path": "added/261005/120000-paste.png", "source": "owner"})
    (lib / "frames/f1").mkdir(parents=True)
    (lib / "frames/f1/frame.json").write_text(json.dumps({"name": "Фрейм 1", "size": [100, 100], "layers": [{"id": "p1", "kind": "pic", "path": "frm/p1.png", "x": 0, "y": 0}]}))
    (refs / "moodboard").mkdir(parents=True)
    (refs / "moodboard/m1.jpg").write_bytes(png())
    main = {"schema": 1, "revision": 1, "removed": {"other/o1.png": "2026-10-01T10:00:00"}, "items": {
        "i1": pic("r30-studio-light/b1.png", 300, 300), "i2": pic("r30-studio-light/b2.png", 500, 300),
        "i3": pic("r31-dark/b1.png", 700, 300), "i3b": pic("zz/r31-dark/b1.png", 300, 500),
        "i7": pic("r32/a4.png", 1050, 650),
        "n1": {"type": "note", "text": "**Ряд один**\nподробности", "x": 250, "y": 900, "w": 320, "h": 320, "fs": 17, "color": "yellow",
               "reach": {"l": 0, "t": 700, "r": 800, "b": 0}, "to": []},
        "n2": {"type": "note", "text": "# Внутри: ряда", "x": 1000, "y": 600, "w": 200, "h": 200, "fs": 12, "color": "blue",
               "reach": {"l": 0, "t": 0, "r": 0, "b": 0}, "to": []},
        "f1": {"type": "imgframe", "x": 400, "y": 1800, "w": 300, "h": 300, "name": "Фрейм 1", "doc": "frames/f1/frame.json", "pics": ["frm/p1.png"]},
        "i14": pic("added/261005/120000-paste.png", 2500, 300),
        "i8": pic("r32/a3.png", 6100, 100), "i9": pic("cells/cell-1.png", 9100, 100),
        "i10": pic("dup/v01.png", -2000, 0), "i11": pic("loose/u1.png", -3000, 0),
        "i12": pic("_rejected/z.png", -4000, 0), "i13": pic("ext/moodboard/m1.jpg", -5000, 0),
        "t1": {"type": "text", "text": "Заголовок", "x": 0, "y": -400, "fs": 60}}, "groups": {
        "gA": {"title": "Отражения: студия / свет", "x": 0, "y": 0, "w": 4000, "h": 3000, "members": ["f1", "i14"]},
        "gB": {"title": "Внутренняя", "x": 200, "y": 150, "w": 1800, "h": 1300, "members": ["i1", "i2", "i3", "i3b", "i7", "n1", "n2"]},
        "gC": {"title": "Членство", "x": 6000, "y": 0, "w": 2000, "h": 2000, "members": ["i8", "gD"]},
        "gD": {"title": "Вложенная по членству", "x": 9000, "y": 0, "w": 1500, "h": 1500, "members": ["i9"]}}}
    p2 = {"schema": 1, "revision": 1, "removed": {}, "items": {
        "j1": pic("dup/v01.png", 0, 0), "j2": pic("r32/a5.png", 1200, 300),
        "m1": {"type": "note", "text": "Про всю группу", "x": 1500, "y": 300, "w": 200, "h": 200, "fs": 12, "reach": None, "to": []}}, "groups": {
        "gS": {"title": "Свет", "x": 1000, "y": 0, "w": 1200, "h": 1200, "members": ["j2", "m1"]}}}
    (state / "boards").mkdir(parents=True)
    (state / "boards/main.json").write_text(json.dumps(main, ensure_ascii=False))
    (state / "boards/p2.json").write_text(json.dumps(p2, ensure_ascii=False))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Main"}, {"id": "p2", "title": "Refs"}]}))
    return lib, state, refs


EXPECT = {   # where each picture of the boards lands (the library hides files in the root, so copies go to «В нескольких местах»)
    "r30-studio-light/b1.png": "Main/Отражения студия свет/Внутренняя/Ряд один/b1.png",
    "r30-studio-light/b2.png": "Main/Отражения студия свет/Внутренняя/Ряд один/b2.png",
    "r31-dark/b1.png": "Main/Отражения студия свет/Внутренняя/Ряд один/b1 (r31-dark).png",
    "zz/r31-dark/b1.png": "Main/Отражения студия свет/Внутренняя/Ряд один/b1 (r31-dark)-2.png",
    "r32/a4.png": "Main/Отражения студия свет/Внутренняя/Ряд один/Внутри ряда/a4.png",
    "frm/p1.png": "Main/Отражения студия свет/p1.png",
    "added/261005/120000-paste.png": "Main/Отражения студия свет/120000-paste.png",
    "r32/a3.png": "Main/Членство/a3.png",
    "cells/cell-1.png": "Main/Членство/Вложенная по членству/cell-1.png",
    "loose/u1.png": "Main/u1.png",
    "dup/v01.png": "В нескольких местах/v01.png",
    "r32/a5.png": "Refs (страница)/Свет/a5.png",
}


@pytest.fixture
def project(tmp_path):
    lib, state, refs = build(tmp_path)
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    pid = str(uuid.uuid4())
    # the board's library rules: files in the root are not frames, «refs» is a skipped name (the page «Refs» gets «(страница)»), the
    # reference folder's «moodboard» is a collection
    (tmp_path / "rules.json").write_text(json.dumps({pid: {"rootFiles": False, "skip": ["refs"], "mounts": [{"prefix": "ext/moodboard", "path": "moodboard"}]}}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=pid, HYIMG_STYLE_REFS=str(refs),
               HYIMG_LIBRARY_RULES=str(tmp_path / "rules.json"), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1", HOME=str(tmp_path / "home"))
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError:
                time.sleep(0.1)
        yield {"port": port, "lib": lib, "state": state, "refs": refs, "tmp": tmp_path}
    finally:
        process.terminate(); process.wait(5); log.close()


def call(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def tree(lib):
    """every file of the library but the notes the server regenerates, with its sha1"""
    out = {}
    for root, _d, files in os.walk(lib):
        for f in files:
            full = Path(root) / f; rel = str(full.relative_to(lib))
            if rel.startswith("notes/"): continue
            out[rel] = hashlib.sha1(full.read_bytes()).hexdigest()
    return out


def dirs(lib):
    return {str(Path(r).relative_to(lib)) for r, _d, _f in os.walk(lib)} - {"notes"}   # notes/: the server's own files of sticky notes


def board_paths(state, page):
    b = json.loads((state / f"boards/{page}.json").read_text())
    return [it["path"] for it in b["items"].values() if it.get("path")] + [p for it in b["items"].values() for p in it.get("pics", [])], b


def settle(port, state):
    """one save of each page as the canvas makes it: the notes' references get into the sidecars, as in a project in use"""
    for page in ("main", "p2"):
        code, _r = call(port, f"/api/board?name={page}", json.loads((state / f"boards/{page}.json").read_text()))
        assert code == 200


def test_plan_apply_aliases_undo(project):
    port, lib, state = project["port"], project["lib"], project["state"]
    settle(port, state)
    before, before_dirs = tree(lib), dirs(lib)
    code, p = call(port, "/api/layout/plan")
    assert code == 200, p
    assert tree(lib) == before, "the plan changed files"
    assert p["move"] == len(EXPECT), p
    assert p["multi"] == 1 and p["renamed"] == 2
    assert p["reasons"] == {"служебная папка": 1, "внешняя папка": 1}
    assert 3 <= len(p["examples"]) <= 5 and all(EXPECT[e["from"]] == e["to"] for e in p["examples"])
    assert p["auto"] is False

    code, r = call(port, "/api/layout/apply", {})
    assert code == 200 and r["status"] == "done" and r["moved"] == len(EXPECT), r
    for old, new in EXPECT.items():
        assert (lib / new).is_file(), new
        assert not (lib / old).exists(), old
    # sidecars came along, relative links still reach the same files
    side = lambda rel: json.loads((lib / (os.path.splitext(rel)[0] + ".json")).read_text())
    b1 = side(EXPECT["r30-studio-light/b1.png"])
    assert b1["feedback"] == {"fav": True}
    assert os.path.normpath(lib / os.path.dirname(EXPECT["r30-studio-light/b1.png"]) / b1["inputs"][0]) == str(lib / "inputs/x.png")
    cell = side(EXPECT["cells/cell-1.png"])
    assert os.path.normpath(lib / os.path.dirname(EXPECT["cells/cell-1.png"]) / cell["grid"]) == str(lib / "grids/g1.png")
    o1 = json.loads((lib / "other/o1.json").read_text())
    assert os.path.normpath(lib / "other" / o1["inputs"][0]) == str(lib / EXPECT["r32/a3.png"])
    assert side(EXPECT["added/261005/120000-paste.png"])["path"] == EXPECT["added/261005/120000-paste.png"]
    assert "main/n2" in json.dumps(side(EXPECT["r32/a4.png"]))   # the json the notes made for it came along
    # never moved
    for keep in ("_rejected/z.png", "grids/g1.png", "inputs/x.png", "other/o1.png", "frames/f1/frame.json"):
        assert (lib / keep).is_file(), keep
    assert (project["refs"] / "moodboard/m1.jpg").is_file()
    # boards, the frame's document and the archive follow
    for page in ("main", "p2"):
        paths, b = board_paths(state, page)
        for pth in paths:
            assert pth.startswith("ext/") or (lib / pth).is_file(), pth
    main = json.loads((state / "boards/main.json").read_text())
    assert main["revision"] == 3 and main["items"]["f1"]["pics"] == [EXPECT["frm/p1.png"]]
    assert json.loads((lib / "frames/f1/frame.json").read_text())["layers"][0]["path"] == EXPECT["frm/p1.png"]
    # emptied folders went, the ones with something left stayed
    for gone in ("r30-studio-light", "r31-dark", "zz/r31-dark", "zz", "loose", "dup", "cells", "frm", "r32", "added/261005", "added"):
        assert not (lib / gone).exists(), gone
    # old paths still open the pictures
    code, al = call(port, "/api/aliases")
    for old, new in EXPECT.items():
        assert al[old] == new
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p={urllib.parse.quote(old)}&s=96") as r: assert r.status == 200
    # laid out once, the next plan has nothing to move
    code, p2 = call(port, "/api/layout/plan")
    assert p2["move"] == 0 and p2["make"] == 0 and p2["remove"] == 0, p2
    journal = sorted((state / "layout-sync").glob("*.json"))
    assert len([j for j in journal if j.name != "auto.json"]) == 1

    # a heart given after the run makes a json the picture did not have: undo takes it back along
    code, _f = call(port, "/api/fav", {"paths": [EXPECT["r32/a4.png"]], "fav": True})
    assert code == 200
    code, u = call(port, "/api/layout/undo", {})
    assert code == 200 and u["status"] == "undone", u
    assert json.loads((lib / "r32/a4.json").read_text())["feedback"]["fav"] is True
    call(port, "/api/fav", {"paths": ["r32/a4.png"], "fav": False})
    assert tree(lib) == before, "undo did not restore the files byte for byte"
    assert dirs(lib) == before_dirs
    for page in ("main", "p2"):
        paths, _b = board_paths(state, page)
        assert all(pth.startswith("ext/") or pth in before for pth in paths)
    code, al = call(port, "/api/aliases")
    assert not any(k in EXPECT for k in al), "an undone run must not send the old paths away"
    assert all(al.get(new) == old for old, new in EXPECT.items())
    code, u2 = call(port, "/api/layout/undo", {})
    assert code == 409


def test_auto_mode_follows_a_group_rename(project):
    port, lib, state = project["port"], project["lib"], project["state"]
    assert call(port, "/api/layout/state")[1]["auto"] is False
    code, r = call(port, "/api/layout/apply", {"auto": True})
    assert code == 200 and r["auto"] is True
    b = json.loads((state / "boards/main.json").read_text())
    b["groups"]["gB"]["title"] = "Внутренняя новая"
    code, res = call(port, "/api/board?name=main", b)
    assert code == 200, res
    new = "Main/Отражения студия свет/Внутренняя новая/Ряд один/b1.png"
    for _ in range(100):
        if (lib / new).is_file(): break
        time.sleep(0.2)
    assert (lib / new).is_file()
    assert not (lib / "Main/Отражения студия свет/Внутренняя").exists()
    st = call(port, "/api/layout/state")[1]
    assert st["last"]["who"] == "auto" and st["last"]["status"] == "done" and st["auto"] is True
    # the old-old path follows two runs
    assert call(port, "/api/aliases")[1]["r30-studio-light/b1.png"] == new
    # a save that changes nothing about places moves nothing
    b = json.loads((state / "boards/main.json").read_text())
    b["items"]["i1"]["x"] += 5
    call(port, "/api/board?name=main", b)
    time.sleep(5.5)
    assert len([j for j in (state / "layout-sync").glob("*.json") if j.name != "auto.json"]) == 2
    # undo switches the mode off
    code, u = call(port, "/api/layout/undo", {})
    assert u["auto_was"] is True and call(port, "/api/layout/state")[1]["auto"] is False


def test_library_dialog(project):
    playwright = pytest.importorskip("playwright.sync_api")
    port, lib = project["port"], project["lib"]
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.skip(f"no Chromium for Playwright: {error}")
        page = browser.new_page(viewport={"width": 1280, "height": 860})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/?view=lib")
        page.wait_for_selector(".fbar .fsMore")
        page.click(".fbar .fsMore")
        page.wait_for_selector("#fsMenu.open")
        if SHOTS: page.screenshot(path=os.path.join(SHOTS, "menu.png"))
        page.click('#fsMenu [data-fs="plan"]')
        page.wait_for_selector("#fsDlg [data-go]")
        page.wait_for_timeout(500)
        text = page.inner_text("#fsDlg")
        assert "переедут" in text and "было" in text and "стало" in text and "Всегда держать папки как на доске" in text
        assert page.locator("#fsDlg .ex li").count() >= 3
        if SHOTS: page.screenshot(path=os.path.join(SHOTS, "dialog.png"))
        page.click("#fsDlg [data-go]")
        page.wait_for_selector("#fsDlg:not(.open)", state="attached")
        page.wait_for_function("document.querySelector('#hyToasts') && /Разложено/.test(document.querySelector('#hyToasts').innerText)")
        if SHOTS: page.screenshot(path=os.path.join(SHOTS, "done.png"))
        assert (lib / EXPECT["loose/u1.png"]).is_file()
        page.click(".fbar .fsMore")
        page.wait_for_selector('#fsMenu.open [data-fs="undo"]:not([disabled])')
        page.click('#fsMenu [data-fs="undo"]')
        page.wait_for_function("/Раскладка отменена/.test(document.querySelector('#hyToasts').innerText)")
        if SHOTS: page.screenshot(path=os.path.join(SHOTS, "undone.png"))
        assert (lib / "loose/u1.png").is_file()
        assert not errors, errors
        browser.close()
