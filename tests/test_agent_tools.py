"""What an agent gets from a running Hyimg: /agent (owner 2026-10-01: "дал ссылку на локалхост, и агент все понял") and the hy.py
commands that keep its board edits tidy: block near= (free room by itself), remove, check, the owner's open page as the default."""
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HY = ROOT / "review/hy.py"


def png(w=40, h=60, c=(0x80, 0x80, 0x80)):   # every file of the fixture its own colour: identical files are one picture to the library
    raw = b"".join(b"\x00" + bytes(c) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def hyimg(tmp_path):
    lib, state = tmp_path / "lib", tmp_path / "lib/_review"
    for k, folder in enumerate(("old", "new")):
        (lib / folder).mkdir(parents=True)
        for n in range(6):
            (lib / folder / f"{n}.png").write_bytes(png(c=(40 + 100 * k, 20 + 30 * n, 90)))
    (lib / "AGENTS.md").write_text("# Тестовый проект\n\nПАРОЛЬ-ПРАВИЛ-ПРОЕКТА: класть партии справа.\n")
    (state / "boards").mkdir(parents=True)
    items = {f"o{n}": {"path": f"old/{n}.png", "x": n * 344, "y": 0, "w": 320, "ar": 2 / 3} for n in range(6)}
    board = {"schema": 1, "revision": 1, "items": items, "removed": {},
             "groups": {"g1": {"title": "Старые", "x": -480, "y": -480, "w": 6 * 344 - 24 + 960, "h": 480 + 960, "members": list(items)}}}
    (state / "boards/main.json").write_text(json.dumps(board))
    (state / "boards/p2.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (state / "boards/pages.json").write_text(json.dumps({"pages": [{"id": "main", "title": "Главная"}, {"id": "p2", "title": "Вторая"}]}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    # the interface in Russian: these tests check its Russian words (owner 2026-10-06: English by default, Russian by the setting)
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "ru"}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError:
            time.sleep(0.1)

    def hy(*args):
        r = subprocess.run([sys.executable, str(HY), *args], env={**env, "HYIMG_PORT": str(port)}, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout

    def board(page="main"):
        return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/board?name={page}"))

    try:
        yield port, hy, board, state
    finally:
        proc.terminate(); proc.wait(5); log.close()


def get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as r:
        return r.read().decode()


def test_agent_page_has_project_rules_skills_and_rules(hyimg):
    port, hy, _, _ = hyimg
    page = get(port, "/agent")
    assert "ПАРОЛЬ-ПРАВИЛ-ПРОЕКТА" in page            # the project's AGENTS.md, pasted in full
    assert "skills/hyimg-board/SKILL.md" in page and "hy.py" in page
    assert "«Главная» (`main`" in page
    assert get(port, "/llms.txt") == page
    assert hy("guide").strip() == page.strip()
    assert "name: hyimg-board" in get(port, "/agent/hyimg-board") and "name: hyimg-generate" in get(port, "/agent/hyimg-generate")
    assert "/agent" in get(port, "/canvas.html") and "/agent" in get(port, "/")   # the pages point an agent there


def test_block_near_finds_free_room_and_check_stays_clean(hyimg):
    _, hy, board, _ = hyimg
    out = hy("do", 'block "new/*" near=Старые side=right cols=3 note="# Новые" group="Новые · 1"', "--label", "тест")
    assert "⚠" not in out
    b = board()
    old, new = b["groups"]["g1"], next(g for g in b["groups"].values() if g["title"] == "Новые · 1")
    assert new["x"] >= old["x"] + old["w"] + 480 - 1 and new["y"] == old["y"]   # to the right, with a group's air, top aligned
    assert "проблем не нашел" in hy("check")
    hist = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{hyimg[0]}/api/history?name=main")))
    assert [e["label"] for e in hist[:2]] == ["после: тест", "до: тест"]


def test_check_reports_pictures_laid_on_top_of_each_other(hyimg):
    _, hy, _, _ = hyimg
    out = hy("do", 'block "new/*" x=100 y=0 cols=6', "--dry")
    assert "⚠" in out and "друг на друге" in out
    assert "проба, не сохранено" in out


def test_remove_marks_pictures_gone_from_every_page(hyimg):
    _, hy, board, _ = hyimg
    hy("do", 'remove "old/1.png" "old/2.png"')
    b = board()
    assert {it["path"] for it in b["items"].values()} == {f"old/{n}.png" for n in (0, 3, 4, 5)}
    assert set(b["removed"]) == {"old/1.png", "old/2.png"}
    assert all("o1" not in g["members"] for g in b["groups"].values())
    hy("do", "remove Старые only=frame")   # like ⇧⌘G: the frame goes, the pictures stay
    assert board()["groups"] == {} and len(board()["items"]) == 4


def test_removing_a_group_takes_its_contents_like_delete_on_the_canvas(hyimg):
    _, hy, board, _ = hyimg
    hy("do", 'note "заметка" x=0 y=0; group "Вторая" заметка')
    hy("do", "remove Старые")
    b = board()
    assert [g["title"] for g in b["groups"].values()] == ["Вторая"]
    assert not any(it.get("path", "").startswith("old/") for it in b["items"].values())
    assert set(b["removed"]) == {f"old/{n}.png" for n in range(6)}


def test_default_page_is_the_one_the_owner_has_open(hyimg):
    port, hy, board, state = hyimg
    assert hy("map").splitlines()[0] == "# страница «Главная» (main)"
    (state / "live.json").write_text(json.dumps({"canvas": {"page": "p2", "sel": [], "t": "2026-10-01 12:00:00"}}))
    assert hy("map").splitlines()[0] == "# страница «Вторая» (p2)"
    hy("do", 'text "Заголовок" x=0 y=0')
    assert any(it.get("text") == "Заголовок" for it in board("p2")["items"].values())
    assert hy("map", "--page", "main").splitlines()[0] == "# страница «Главная» (main)"


def test_arrange_tidies_pictures_already_on_the_page(hyimg):
    _, hy, board, _ = hyimg
    hy("do", 'block "new/*" x=60 y=40 cols=6')            # dropped on top of the old row
    assert "друг на друге" in hy("check")
    assert "pic new/0.png" in hy("find", "new/0")
    out = hy("do", 'arrange "new/*" near=Старые side=below cols=3 group="Новые"')
    assert "⚠" not in out and "проблем не нашел" in hy("check")
    b = board(); new = [it for it in b["items"].values() if it.get("path", "").startswith("new/")]
    assert len(new) == 6 and len({it["y"] for it in new}) == 2   # two even rows of three


def test_one_odd_sidecar_does_not_take_the_library_down(hyimg):
    """2026-10-01: an agent wrote "qa" as plain text in one picture's json and /api/items failed for the whole project"""
    port, _, _, state = hyimg
    lib = state.parent
    (lib / "new/0.json").write_text(json.dumps({"qa": "лишний остров вокруг объективов", "prompt": "p"}))
    (lib / "new/1.json").write_text(json.dumps(["not", "an", "object"]))
    (lib / "new/2.json").write_text(json.dumps({"feedback": "текст вместо объекта", "qa": {"gate": "ok", "defects": ["форма предмета"]}}))
    items = {i["path"]: i for i in json.loads(get(port, "/api/items"))}
    assert {"new/0.png", "new/1.png", "new/2.png"} <= set(items)
    assert items["new/0.png"]["prompt"] == "p" and items["new/2.png"]["gate"] == "ok"


def test_into_adds_a_sub_group_inside_the_theme_and_makes_room(hyimg):
    """owner 2026-10-02: not a new group for every render, a note with its rows inside the theme group; the group grows and keeps order"""
    _, hy, board, _ = hyimg
    hy("do", 'block "new/0.png" "new/1.png" x=0 y=3000 group="Ниже"')          # something standing under the theme group
    b0 = board(); old = b0["groups"]["g1"]; below = next(g for g in b0["groups"].values() if g["title"] == "Ниже")
    out = hy("do", 'block "new/*" into=Старые note="# Новый рендер\\nпять попыток"', "--label", "подгруппа")
    assert "⚠" not in out and "подгруппой в «Старые»" in out, out
    b = board(); g = b["groups"]["g1"]
    assert len(b["groups"]) == 2                                               # no new group
    new = [i for i, it in b["items"].items() if it.get("path", "").startswith("new/") and i in g["members"]]
    assert len(new) == 6
    note = next(it for it in b["items"].values() if it.get("type") == "note" and it["text"].startswith("# Новый рендер"))
    assert note["x"] == min(b["items"][m]["x"] for m in g["members"] if m in b["items"])   # in the group's left column
    assert g["h"] > old["h"]
    moved = next(x for x in b["groups"].values() if x["title"] == "Ниже")
    assert moved["y"] - below["y"] == g["h"] - old["h"]                      # the group below moved down by as much
    assert "проблем не нашел" in hy("check")


def test_a_running_batch_fills_its_sub_group_as_frames_appear(hyimg):
    """owner 2026-10-02: put the first frames on the board at once and grow the block, do not wait for all 500"""
    _, hy, board, state = hyimg
    lib = state.parent
    hy("do", 'block "new/0.png" "new/1.png" into=Старые note="# Партия" cols=3')
    hy("do", 'block "old/0.png" into=Старые note="# Ниже в группе"')       # a block under it, inside the same group
    under = next(it for it in board()["items"].values() if it.get("text", "").startswith("# Ниже"))["y"]
    out = hy("do", 'block "new/*" into=Старые note="# Партия"')             # four more frames of the same batch appeared
    assert "+4 кадров в «Партия»" in out and "⚠" not in out, out
    b = board()
    assert sum(1 for it in b["items"].values() if it.get("path", "").startswith("new/")) == 6   # no duplicates
    assert len(b["groups"]) == 1
    assert next(it for it in b["items"].values() if it.get("text", "").startswith("# Ниже"))["y"] > under   # moved down to make room
    assert "проблем не нашел" in hy("check")
    assert "новых кадров нет" in hy("do", 'block "new/*" into=Старые note="# Партия"')


def test_a_sub_block_moves_whole_and_a_frame_fits_its_contents(hyimg):
    _, hy, board, _ = hyimg
    hy("do", 'block "new/0.png" "new/1.png" into=Старые note="# Блок"')
    before = {it["path"]: (it["x"], it["y"]) for it in board()["items"].values() if it.get("path", "").startswith("new/")}
    hy("do", 'move "# Блок" dy=700')
    after = {it["path"]: (it["x"], it["y"]) for it in board()["items"].values() if it.get("path", "").startswith("new/")}
    assert all(after[p][1] - before[p][1] == 700 for p in before)
    hy("do", "fit Старые")
    assert "проблем не нашел" in hy("check")


def test_event_timeline_records_what_happened_with_pictures(hyimg):
    """owner 2026-10-02: not snapshots but events (added, grouped, written, moved) with the pictures, newest first"""
    port, hy, board, _ = hyimg
    hy("do", 'block "new/*" near=Старые side=right note="# Партия" group="Новая тема"', "--label", "партия на доску")
    ev = json.loads(get(port, "/api/events?name=main"))
    kinds = {e["kind"]: e for e in ev}
    assert {"group", "note"} <= set(kinds), kinds.keys()
    g = kinds["group"]
    assert g["title"] == "Новая тема" and g["count"] == 6 and len(g["paths"]) == 6 and g["who"] == "ai" and g["label"] == "партия на доску"
    assert kinds["note"]["text"].startswith("# Партия") and kinds["note"]["color"] == "blue"
    hy("do", 'move "Новая тема" dx=100'); hy("do", 'move "Новая тема" dx=100')
    ev = json.loads(get(port, "/api/events?name=main"))
    assert ev[0]["kind"] == "move" and ev[1]["kind"] != "move"            # two quick moves are one event
    hy("do", 'remove "Новая тема"')
    ev = json.loads(get(port, "/api/events?name=main"))
    assert {"group-remove", "remove"} <= {e["kind"] for e in ev[:4]}


def wait_hashed(port, n):   # the library hashes new files in the background, every 3 s
    for _ in range(100):
        items = json.loads(get(port, "/api/items?all=1"))
        if sum(1 for i in items if i.get("copy_of")) >= n: return items
        time.sleep(0.2)
    raise AssertionError("copies never folded")


def test_library_shows_each_picture_once_and_save_skips_known(hyimg, tmp_path):
    """Owner 2026-10-02: the same pictures should not land in the library ten times. A byte-identical copy under another name and
    folder is folded into the first file; hy.py save leaves out what the library has; the board takes the shown file, once."""
    port, hy, board, state = hyimg
    lib = state.parent
    (lib / "again").mkdir()
    (lib / "again" / "dl-1.png").write_bytes((lib / "new/2.png").read_bytes())   # a re-collected download
    items = wait_hashed(port, 1)
    copy = next(i for i in items if i["path"] == "again/dl-1.png")
    assert copy["copy_of"] == "new/2.png" and copy["hidden"]
    shown = [i["path"] for i in json.loads(get(port, "/api/items"))]
    assert "again/dl-1.png" not in shown and "new/2.png" in shown
    main = next(i for i in json.loads(get(port, "/api/items")) if i["path"] == "new/2.png")
    assert main["copies"] == ["again/dl-1.png"]
    # save: a known picture (under a UUID name without extension) is left out, a new one gets its extension, a repeat in the batch once
    dl = tmp_path / "dl"; dl.mkdir()
    (dl / "8f1c2e7a-uuid").write_bytes((lib / "old/0.png").read_bytes())
    (dl / "b3d9-new").write_bytes(png(c=(1, 2, 3)))
    (dl / "b3d9-new-again").write_bytes(png(c=(1, 2, 3)))
    (dl / "notes.txt").write_text("не картинка")
    out = hy("save", *sorted(str(p) for p in dl.iterdir()), "--to", "arc/2610022200-batch")
    assert "уже есть: 8f1c2e7a-uuid = old/0.png" in out, out
    assert sorted(os.listdir(lib / "arc/2610022200-batch")) == ["b3d9-new-again.png"] or sorted(os.listdir(lib / "arc/2610022200-batch")) == ["b3d9-new.png"], out
    assert "сохранил 1" in out and "не картинка" in out, out
    # a second save of the same files saves nothing
    assert "сохранил 0" in hy("save", str(dl / "b3d9-new"), "--to", "arc/2610022200-batch")
    # the board: a hidden copy is placed as the file the library shows, a copy of a picture already on the page is skipped
    hy("do", 'block "again/*" x=0 y=0', "--page", "p2", "--label", "копия")
    assert [it["path"] for it in board("p2")["items"].values()] == ["new/2.png"]
    hy("do", 'block "new/*" near=Старые', "--label", "партия")
    out = hy("do", 'block "again/*" near=Старые', "--label", "копия")
    paths = [it["path"] for it in board()["items"].values()]
    assert paths.count("new/2.png") == 1 and "again/dl-1.png" not in paths and "новых кадров нет" in out and "пропустил 1" in out, out
    assert "1 картинок лежат в библиотеке больше одного раза" in hy("dupes")


def test_library_list_is_reused_but_never_stale_after_a_save(hyimg):
    """Owner 2026-10-02: at 21 000 frames every page refetched a 21 s list on each change and the canvas stopped loading pictures.
    The list is reused while nothing changes, a ♥ shows at once, a new file shows within a few seconds."""
    port, hy, board, state = hyimg
    lib = state.parent
    first = json.loads(get(port, "/api/items"))
    t = time.time(); json.loads(get(port, "/api/items")); assert time.time() - t < 2
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/fav", data=json.dumps({"paths": ["old/1.png"], "fav": True}).encode(),
                                 headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}, method="POST")
    urllib.request.urlopen(req).read()
    item = next(i for i in json.loads(get(port, "/api/items")) if i["path"] == "old/1.png")
    assert (item.get("feedback") or {}).get("fav") is True, item
    (lib / "fresh").mkdir(); (lib / "fresh" / "a.png").write_bytes(png(c=(9, 9, 9)))
    for _ in range(60):
        if any(i["path"] == "fresh/a.png" for i in json.loads(get(port, "/api/items"))): break
        time.sleep(0.25)
    else:
        raise AssertionError("a new file never reached the library list")
    assert len(first) == 12


def test_block_warns_about_frames_without_a_description(hyimg):
    """Owner 2026-10-03: a frame made by a one-off script came onto the board with no json and its card said nothing. block says so,
    undocumented lists such frames by folder."""
    port, hy, board, state = hyimg
    lib = state.parent
    for n in range(6):
        (lib / "new" / f"{n}.json").write_text(json.dumps({"prompt": "кадр", "model": "test"}) if n < 4 else "{}")
    time.sleep(0.2)
    out = hy("do", 'block "new/*" near=Старые', "--label", "партия")
    assert "2 кадров без описания" in out and "new/4.png" in out, out
    assert "2 кадров без описания в 1 папках" in hy("undocumented", "new")


def test_a_pasted_picture_comes_with_a_description(hyimg):
    """Owner 2026-10-03: cards of pasted pictures were empty. The server says what it knows: pasted by the owner, when, from where."""
    port, hy, board, state = hyimg
    lib = state.parent
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/upload?name=moodboard-ref.png", data=png(c=(200, 10, 10)),
                                 headers={"Content-Type": "image/png", "Origin": f"http://127.0.0.1:{port}"}, method="POST")
    path = json.loads(urllib.request.urlopen(req).read())["path"]
    meta = json.loads((lib / (path[:-4] + ".json")).read_text())
    assert meta["model"] == "вставлено владельцем" and "из файла moodboard-ref.png" in meta["prompt"], meta


def test_a_cut_frame_shows_the_references_of_its_grid(hyimg):
    """Owner 2026-10-03: strips cut from a grid lost "inputs" and showed no references; the GPT strips of a "-mj-" batch were tagged
    Midjourney. A frame with "grid" or "derived_from" shows its source's references, the model wins over the folder name, and block
    warns when a prompt names Image 1 but the frame has no references."""
    port, hy, board, state = hyimg
    lib = state.parent
    d = lib / "arc" / "2610030900-mj-test"; (d / "grids").mkdir(parents=True); (d / "rows").mkdir()
    (d / "grids" / "g1.png").write_bytes(png(c=(5, 6, 7))); (d / "rows" / "g1-r1.png").write_bytes(png(c=(8, 9, 10)))
    (d / "rows" / "g1-r2.png").write_bytes(png(c=(11, 12, 13)))
    (d / "grids" / "g1.json").write_text(json.dumps({"prompt": "sheet", "model": "GPT Image", "inputs": ["../../../old/0.png"]}))
    (d / "rows" / "g1-r1.json").write_text(json.dumps({"prompt": "Image 1 is the phone", "model": "GPT Image (Codex)", "grid": "../grids/g1.png"}))
    (d / "rows" / "g1-r2.json").write_text(json.dumps({"prompt": "Image 1 is the phone", "model": "GPT Image (Codex)"}))
    (d / "rows" / "g1-r3.png").write_bytes(png(c=(14, 15, 16)))
    (d / "rows" / "g1-r3.json").write_text(json.dumps({"prompt": "a strip", "grid": "../grids/g1.png"}))   # no model: the grid's
    for _ in range(40):
        items = {i["path"]: i for i in json.loads(get(port, "/api/items"))}
        if "arc/2610030900-mj-test/rows/g1-r1.png" in items: break
        time.sleep(0.25)
    r1 = items["arc/2610030900-mj-test/rows/g1-r1.png"]
    assert r1["refpaths"] == ["old/0.png"], r1["refpaths"]
    assert "GPT Image" in r1["tags"] and "Midjourney" not in r1["tags"], r1["tags"]
    r3 = items["arc/2610030900-mj-test/rows/g1-r3.png"]
    assert r3["model"] == "GPT Image" and "GPT Image" in r3["tags"] and "Midjourney" not in r3["tags"], (r3["model"], r3["tags"])
    out = hy("do", 'block "arc/2610030900-mj-test/rows/*" near=Старые', "--label", "полосы")
    assert "у 1 кадров промпт ссылается на Image" in out and "g1-r2.png" in out, out


def test_plugin_endpoints_snapshot_and_model_files(hyimg):
    """Owner 2026-10-03: modules such as 3D objects live outside the repository. The server lists plugins, serves library files of any
    type (3D models) and saves a picture a plugin made, with the plugin's json beside it."""
    port, hy, board, state = hyimg
    lib = state.parent
    assert isinstance(json.loads(get(port, "/api/plugins")), list)
    (lib / "3d" / "models" / "m").mkdir(parents=True); (lib / "3d/models/m/a.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/file?p=3d/models/m/a.glb") as r:
        assert r.headers["Content-Type"] == "model/gltf-binary" and r.read().startswith(b"glTF")
    meta = {"prompt": "3D-снимок", "model": "Hyimg 3D", "camera": {"az": -32, "el": 14}}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/snapshot?name=3d-test&folder=3d/shots&meta=" + urllib.parse.quote(json.dumps(meta)),
                                 data=png(c=(30, 60, 90)), headers={"Content-Type": "image/png", "Origin": f"http://127.0.0.1:{port}"}, method="POST")
    res = json.loads(urllib.request.urlopen(req).read())
    assert res["path"].startswith("3d/shots/") and res["path"].endswith("-3d-test.png")
    side = json.loads((lib / (res["path"][:-4] + ".json")).read_text())
    assert side["camera"] == {"az": -32, "el": 14} and side["prompt"] == "3D-снимок" and side["path"] == res["path"]
    bad = urllib.request.Request(f"http://127.0.0.1:{port}/api/snapshot?name=x&folder=../evil", data=png(), headers={"Origin": f"http://127.0.0.1:{port}"}, method="POST")
    try: urllib.request.urlopen(bad); assert False, "a folder outside the library must be refused"
    except urllib.error.HTTPError as e: assert e.code == 400


def test_plugin_scene_file_written_in_place_and_weighed(hyimg):
    """Owner 2026-10-03: a 3D scene is a json in the library that the canvas rewrites while a camera turns and an agent applies in
    Blender. The canvas writes it under 3d/ only, in place (its folder keeps its time, so the library does not rescan), never cached
    when read back; HEAD gives a file's size so a plugin weighs a scene before loading it."""
    port, hy, board, state = hyimg
    lib = state.parent
    origin = {"Origin": f"http://127.0.0.1:{port}"}
    def put(rel, body):
        return urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/file?p=" + urllib.parse.quote(rel), data=body, headers=origin, method="POST"))
    put("3d/scenes/s1/scene.json", json.dumps({"rev": 1}).encode())
    folder = lib / "3d/scenes/s1"; t0 = folder.stat().st_mtime_ns; time.sleep(0.05)
    put("3d/scenes/s1/scene.json", json.dumps({"rev": 2}).encode())
    assert json.loads((folder / "scene.json").read_text()) == {"rev": 2}
    assert folder.stat().st_mtime_ns == t0, "rewriting the scene must not touch its folder"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/file?p=3d/scenes/s1/scene.json") as r:
        assert r.headers["Cache-Control"] == "no-store" and json.loads(r.read()) == {"rev": 2}
    put("3d/scenes/s1/scene.glb", b"glTF" + b"\0" * 996)
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/file?p=3d/scenes/s1/scene.glb", method="HEAD")) as r:
        assert r.headers["Content-Length"] == "1000" and r.read() == b""
    for rel, body in (("a/x.json", b"{}"), ("3d/../x.json", b"{}"), ("3d/x.png", b"x"), ("3d/x.json", b"not json")):
        try: put(rel, body); assert False, f"{rel} must be refused"
        except urllib.error.HTTPError as e: assert e.code == 400


def test_3d_card_posters_live_with_the_scene(hyimg):
    """Owner 2026-10-03: 3D cards show at once like pictures, also for someone opening the project elsewhere (a link, the cloud later),
    and the stills must not pile up. A card's still view is a file of the project, <scene>/.posters/<card>-<view>.jpg|png, rewritten in
    place; the card's previous view goes when a new one is written; the folder is never a frame of the library. One /api/stat call
    gives the times of many files, so a board of thousands of cards asks once which stills are older than their scenes."""
    port, hy, board, state = hyimg
    lib = state.parent
    origin = {"Origin": f"http://127.0.0.1:{port}"}
    def put(rel, body):
        return json.loads(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/file?p=" + urllib.parse.quote(rel), data=body, headers=origin, method="POST")).read())
    put("3d/scenes/s1/scene.json", b"{}")
    put("3d/scenes/s1/.posters/m1-aaaa.jpg", png())
    put("3d/scenes/s1/.posters/m2-cccc.jpg", png())
    put("3d/scenes/s1/.posters/m1-bbbb.png", png())   # the card changed its view: its old still goes, another card's stays
    assert sorted(p.name for p in (lib / "3d/scenes/s1/.posters").iterdir()) == ["m1-bbbb.png", "m2-cccc.jpg"]
    paths = ["3d/scenes/s1/scene.json", "3d/scenes/s1/.posters/m1-bbbb.png", "3d/scenes/s1/.posters/m9-none.jpg"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/stat", data=json.dumps({"paths": paths}).encode(), headers=dict(origin, **{"Content-Type": "application/json"}), method="POST")
    got = json.loads(urllib.request.urlopen(req).read())
    assert got[paths[0]] and got[paths[1]] and got[paths[2]] is None
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p=3d/scenes/s1/.posters/m2-cccc.jpg&s=320") as r:
        assert r.headers["Content-Type"] == "image/jpeg"
    for rel in ("3d/scenes/s1/.posters/../x.png", "3d/scenes/s1/posters/m1-a.png", "3d/scenes/s1/.posters/m1 a.gif"):
        try: put(rel, png()); assert False, rel
        except urllib.error.HTTPError as e: assert e.code == 400
    assert not any(".posters" in i["path"] for i in json.loads(get(port, "/api/items")))


def test_agents_tell_the_owner_what_they_put_on_a_board(hyimg):
    """Owner 2026-10-03: a bell with a red dot shows what agents put on the boards, a few words, previews, a jump to the place. Every
    «do» that adds something writes one by itself (no agent can forget); --say gives the words, --quiet skips a pure rearrangement;
    «notify» writes one for anything else. Reading clears the dot."""
    port, hy, board, state = hyimg
    out = hy("do", 'block "new/*" near=Старые side=right cols=3 note="# Новые" group="Новые · 1"', "--say", "Собрал новую партию справа от старых")
    assert "уведомление: Собрал новую партию справа от старых" in out
    d = json.loads(get(port, "/api/notifications"))
    n = d["items"][0]
    assert d["unread"] == 1 and n["page"] == "main" and n["title"] == "Собрал новую партию справа от старых"
    assert n["text"].startswith("На доске новое: 6 кадров, 1 заметка, 1 группа") and len(n["previews"]) == 6 and n["previews"][0].startswith("new/")
    b = board()
    assert set(n["ids"]) == {i for i in b["items"] if i not in {f"o{k}" for k in range(6)}} | {g for g in b["groups"] if g != "g1"}
    assert n["area"]["x"] > 6 * 344 and n["area"]["w"] > 0
    hy("do", 'move "Новые · 1" dx=100', "--quiet")   # only moved: no news
    hy("do", 'note "проверка" x=0 y=900')            # added without words: counted words of its own
    d = json.loads(get(port, "/api/notifications"))
    assert d["unread"] == 2 and d["items"][0]["title"] == "На доске новое: 1 заметка"
    out = hy("notify", "Проверил партию, 2 кадра с браком отложил", "--text", "брак: new/1, new/4", "--ids", "o1,o2")
    n = json.loads(get(port, "/api/notifications"))["items"][0]
    assert n["text"] == "брак: new/1, new/4" and n["ids"] == ["o1", "o2"] and n["previews"] == ["old/1.png", "old/2.png"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/notifications", data=json.dumps({"action": "read"}).encode(),
                                 headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}, method="POST")
    assert json.loads(urllib.request.urlopen(req).read())["unread"] == 0
    assert json.loads(get(port, "/api/notifications"))["unread"] == 0

