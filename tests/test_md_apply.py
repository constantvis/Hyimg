"""hy.py md apply (owner 2026-10-09 on «Board structure» › «Markdown as edits»: «реализуй это»): an agent reads a page with hy.py md, edits
the text and applies it. Lines become board operations by reference: a renamed heading and group, a note's text and arrow, a table's cells
in another order and a library picture in a new cell, a picture moved into another group, a struck line removed, and a change the owner
made after the view skipped by name. A dry run saves nothing; a real one saves versions before and after. A temporary server and library.

  nice -n 10 python3 -m pytest -q tests/test_md_apply.py
"""
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request
import uuid
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HY = ROOT / "review/hy.py"


def png(c):
    raw = b"".join(b"\x00" + bytes(c) * 40 for _ in range(60))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 60, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


@pytest.fixture
def srv(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "lib/_review"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    for n in range(9): (lib / "a" / f"{n}.png").write_bytes(png((30 + 20 * n, 90, 200 - 15 * n)))
    pic = lambda n, x, y: {"path": f"a/{n}.png", "x": x, "y": y, "w": 300, "ar": 2 / 3}
    items = {f"p{n}": pic(n, n * 324, 0) for n in range(3)}
    items.update({"p3": pic(3, 0, 600), "p4": pic(4, 324, 600), "p5": pic(5, 3000, 0), "p6": pic(6, 3324, 0),
                  "h1": {"type": "text", "text": "Свет", "x": 0, "y": -700, "w": 400, "fs": 120, "size": 3},
                  "n1": {"type": "note", "text": "мягкий свет", "x": -500, "y": 0, "w": 300, "fs": 23, "size": 2, "h": 0, "color": "yellow", "to": ["p0"]}})
    board = {"schema": 1, "revision": 1, "items": items, "removed": {},
             "groups": {"gA": {"title": "Свет", "x": -900, "y": -1000, "w": 2400, "h": 2200, "members": ["p0", "p1", "p2", "p3", "p4", "h1", "n1"]},
                        "gB": {"title": "Другое", "x": 2600, "y": -500, "w": 1400, "h": 1200, "members": ["p5", "p6"]}},
             "grids": {"gr1": {"members": ["p0", "p1", "p2"], "cols": 3, "rows": 1, "gap": 24, "cell": "fit"}}}
    (state / "boards/main.json").write_text(json.dumps(board))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Главная"}]}))
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               PYTHONDONTWRITEBYTECODE="1", HYIMG_PORT=str(port), TMPDIR=str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError: time.sleep(0.1)

    def hy(*args, stdin=None, ok=True):
        r = subprocess.run([sys.executable, str(HY), *args], env=env, capture_output=True, text=True, timeout=90, input=stdin)
        if ok: assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout + r.stderr

    def get(path):
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}"))

    def post(path, body):
        rq = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(rq))

    try:
        yield hy, get, post, tmp_path
    finally:
        proc.terminate(); proc.wait(5); log.close()


def test_view_has_its_version_and_an_edit_goes_back_by_reference(srv):
    hy, get, post, tmp = srv
    md = hy("md", "--page", "main")
    b0 = get("/api/board?name=main")
    assert md.startswith(f"<!-- hyimg md page=main rev={b0['revision']} vid={b0.get('vid') or '-'} -->"), md[:120]
    assert "▦ сетка 3 × 1 [gr1]" in md and "- 3.png [p3]" in md and "> мягкий свет [n1]" in md
    e = (md.replace("### Свет [h1]", "### Свет и тень [h1]").replace("▣ Группа «Другое» [gB]", "▣ Группа «Прочее» [gB]")
         .replace("> мягкий свет [n1]", "> мягкий свет слева [n1]\n→ 4.png [p4]")
         .replace("| 0.png [p0] | 1.png [p1] | 2.png [p2] |", "| 1.png [p1] | 0.png [p0] | 2.png [p2] |\n| a/7.png | | |")
         .replace("- 5.png [p5]\n", "").replace("- 4.png [p4]", "- 4.png [p4]\n- 5.png [p5]").replace("- 6.png [p6]", "- ~~6.png [p6]~~"))
    f = tmp / "edit.md"; f.write_text(e)
    dry = hy("md", "apply", str(f), "--dry")
    for want in ("~ заголовок «Свет» → «Свет и тень»", "~ группа «Другое» → «Прочее»", "~ заметка [n1]", "→ стрелка [n1] → 4.png [p4]",
                 "▦ сетка gr1", "⇢ 5.png [p5] в группу «Свет»", "− 6.png [p6]", "(проба, не сохранено)"):
        assert want in dry, dry
    assert get("/api/board?name=main")["revision"] == b0["revision"]   # a dry run saves nothing
    out = hy("md", "apply", str(f), "--quiet")
    b = get("/api/board?name=main")
    I, G = b["items"], b["groups"]
    assert I["h1"]["text"] == "Свет и тень" and G["gB"]["title"] == "Прочее" and I["n1"]["text"] == "мягкий свет слева"
    assert I["n1"]["to"] == ["p0", "p4"]
    ms = b["grids"]["gr1"]["members"]
    assert ms[:3] == ["p1", "p0", "p2"] and len(ms) == 4 and I[ms[3]]["path"] == "a/7.png"   # the new cell: the library's picture
    assert (I["p1"]["x"], I["p0"]["x"]) == (I["p0"]["x"] - 324, I["p1"]["x"] + 324) or I["p1"]["x"] < I["p0"]["x"]
    assert "p5" in G["gA"]["members"] and "p5" not in G["gB"]["members"]
    r5, gA = I["p5"], G["gA"]
    assert gA["x"] <= r5["x"] and r5["x"] + r5["w"] <= gA["x"] + gA["w"] and gA["y"] <= r5["y"] <= gA["y"] + gA["h"]   # inside, the frame grew
    assert "p6" not in I and "a/6.png" in b["removed"]   # struck: gone, a picture gone from every page is the archive
    hist = get("/api/history?name=main")
    assert any((e.get("label") or "").startswith("до: ") for e in hist) and any((e.get("label") or "").startswith("после: ") for e in hist), out


def test_what_the_owner_changed_after_the_view_is_skipped(srv):
    hy, get, post, tmp = srv
    md = hy("md", "--page", "main")
    b = get("/api/board?name=main")   # the owner renames the heading and moves a picture after the agent read the page
    b["items"]["h1"]["text"] = "Свет (владелец)"; b["items"]["p3"]["x"] += 40
    post("/api/board?name=main", b)
    e = md.replace("### Свет [h1]", "### Свет агента [h1]").replace("> мягкий свет [n1]", "> теплый [n1]").replace("- 3.png [p3]\n", "")
    e = e.replace("- 5.png [p5]", "- 5.png [p5]\n- 3.png [p3]")
    out = hy("md", "apply", "-", "--quiet", stdin=e)
    assert "! пропуск заголовок «Свет» → «Свет агента»" in out and "! пропуск 3.png [p3]" in out, out
    now = get("/api/board?name=main")
    assert now["items"]["h1"]["text"] == "Свет (владелец)" and "p3" in now["groups"]["gA"]["members"]
    assert now["items"]["n1"]["text"] == "теплый"   # what nobody else touched applies


def test_a_part_of_the_page_new_things_and_nothing_removed_by_omission(srv):
    hy, get, post, tmp = srv
    md = hy("md", "--page", "main")
    stamp = md.split("\n", 1)[0]
    part = "\n".join([stamp, "## ▣ Группа «Другое» [gB]", "", "> новая заметка агента", "", "Свободно:", "- 5.png [p5]", "- a/8.png", ""])
    dry = hy("md", "apply", "-", "--dry", stdin=part)
    assert "+ заметка «новая заметка агента»" in dry and "+ кадр a/8.png" in dry and "−" not in dry, dry
    hy("md", "apply", "-", "--quiet", stdin=part)
    b = get("/api/board?name=main")
    assert all(k in b["items"] for k in ("p0", "p1", "p2", "p3", "p4", "p6", "h1", "n1"))   # absent from the part: untouched
    new = [i for i, it in b["items"].items() if it.get("path") == "a/8.png"]
    note = [i for i, it in b["items"].items() if it.get("text") == "новая заметка агента"]
    assert len(new) == 1 and len(note) == 1 and b["items"][note[0]]["color"] == "blue"
    assert new[0] in b["groups"]["gB"]["members"] and note[0] in b["groups"]["gB"]["members"]
    again = hy("md", "--page", "main")
    assert "- 8.png [" in again and "> новая заметка агента [" in again


def test_comments_show_in_table_cells_and_are_left_alone_by_apply(srv):
    hy, get, post, tmp = srv
    hy("comments", "add", "p1", "темнее", "--page", "main")
    md = hy("md", "--page", "main")
    assert "| 0.png [p0] | 1.png [p1] 💬1 |" in md, md
    assert "## 💬 Комментарии и пометки" in md and "1.png [p1], сетка gr1: ряд 1, колонка 2: " in md and ": ?: «" not in md, md
    out = hy("md", "apply", "-", "--dry", stdin=md)
    assert "изменений нет" in out, out
    e = md.replace("| 0.png [p0] | 1.png [p1] 💬1 | 2.png [p2] |", "| 2.png [p2] | 0.png [p0] | 1.png [p1] 💬1 |")
    hy("md", "apply", "-", "--quiet", stdin=e)
    b = get("/api/board?name=main")
    assert b["grids"]["gr1"]["members"] == ["p2", "p0", "p1"]
    t = [x for x in get("/api/annotations?name=main&describe=1")["threads"]][0]
    assert t["anchor"]["obj"] == "p1"   # the thread rides with its picture into the new cell: anchored as a share of its box
