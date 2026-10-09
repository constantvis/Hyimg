"""A board's id in its folder and the boards in Dropbox (review/boardid.py, owner 2026-10-08: two Macs signed into one Dropbox account,
each with its own catalog). Temporary folders stand for the Dropbox root (HYIMG_DROPBOX_ROOT)."""
import json
import os
import uuid

import unit_env  # noqa: F401  (review/ on the path, a throwaway library)
import boardid
import hylink
import people


def board(root, rel, bid=None, name="", old=False):
    d = root / rel / "_review"
    (d / "boards").mkdir(parents=True) if old else d.mkdir(parents=True)
    if bid: (d / "board.json").write_text(json.dumps({"id": bid, "name": name, "created": "2026-10-08T10:00:00Z"}))
    return root / rel


def test_board_json_ids_and_conflicted_copies(tmp_path):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    state = board(tmp_path, "X", a.upper(), "Atlas") / "_review"
    assert boardid.read(state) == {"id": a, "name": "Atlas"} and boardid.read(tmp_path) is None
    (state / "board (Mac B's conflicted copy 2026-10-08).json").write_text(json.dumps({"id": b}))
    (state / "board.json.tmp").write_text(json.dumps({"id": str(uuid.uuid4())}))   # not a conflicted copy
    assert boardid.ids(state) == [a, b]
    (state / "board.json").write_text("{broken")
    assert boardid.read(state) is None and boardid.ids(state) == [b]


def test_roots_relative_paths_and_health(tmp_path, monkeypatch):
    drop, other = tmp_path / "Dropbox", tmp_path / "CloudStorage/Dropbox"
    drop.mkdir(); other.mkdir(parents=True)
    monkeypatch.setenv("HYIMG_DROPBOX_ROOT", f"{drop}:{tmp_path / 'missing'}:{other}:{drop}")
    assert boardid.roots() == [str(drop.resolve()), str(other.resolve())]
    b = board(other, "WORK/Studio & Co/Board", str(uuid.uuid4()), "Board")
    assert boardid.rel(b) == "WORK/Studio & Co/Board" and boardid.rel(tmp_path) == "" and boardid.rel(drop) == ""
    h = boardid.health(b / "_review", b)
    assert h == {"boardId": boardid.read(b / "_review")["id"], "dir": "WORK/Studio & Co/Board"}
    assert boardid.health(tmp_path / "nothing", tmp_path) == {"boardId": "", "dir": ""}


def test_scan_finds_boards_not_in_the_catalog(tmp_path, monkeypatch):
    """two boards, one in this Mac's catalog by its folder id: one is listed; old boards without board.json count; a board is not
    entered, hidden folders and code folders are skipped, the depth is bounded"""
    root = tmp_path / "Dropbox"; root.mkdir()
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    board(root, "WORK/Atlas", a, "Atlas")
    board(root, "WORK/Old", old=True)
    board(root, "WORK/Here", b, "Here")
    board(root, "WORK/Atlas/inner", str(uuid.uuid4()))            # inside a board: never looked for
    board(root, ".hidden/Secret", str(uuid.uuid4()))
    board(root, "code/node_modules/Pkg", str(uuid.uuid4()))
    board(root, "/".join(["d"] * 9) + "/Deep", str(uuid.uuid4()))  # deeper than 8
    cat = tmp_path / "projects.json"
    cat.write_text(json.dumps([{"id": str(uuid.uuid4()), "folderId": b, "libraryRoot": "/elsewhere", "stateRoot": "/elsewhere/_review", "port": 4180}]))
    r = boardid.scan([str(root)], str(cat))
    assert [(x["name"], x["rel"], x["id"]) for x in r["boards"]] == [("Old", "WORK/Old", ""), ("Atlas", "WORK/Atlas", a)] and r["complete"]
    cat.write_text(json.dumps([{"id": str(uuid.uuid4()), "libraryRoot": str(root / "WORK/Atlas"), "stateRoot": "/x", "port": 4180}]))
    assert [x["name"] for x in boardid.scan([str(root)], str(cat))["boards"]] == ["Here", "Old"]   # by the folder
    assert boardid.scan([str(root)], max_dirs=2)["complete"] is False


def test_profile_never_lands_in_dropbox(tmp_path, monkeypatch):
    """a server started by hand on a board keeps its settings in the board's _review; the profile is this Mac's, not the shared folder's"""
    root = tmp_path / "Dropbox"; state = board(root, "WORK/B", str(uuid.uuid4())) / "_review"
    monkeypatch.setenv("HYIMG_DROPBOX_ROOT", str(root)); monkeypatch.delenv("HYIMG_PROFILE_DIR", raising=False)
    assert people.root_dir(str(state / "app-settings.json")) == os.path.realpath(os.path.expanduser("~/Library/Application Support/Hyimg"))
    assert people.root_dir(str(tmp_path / "s/settings.json")) == str((tmp_path / "s").resolve())   # outside Dropbox: as before (tests)
    monkeypatch.setenv("HYIMG_PROFILE_DIR", str(state))   # named on purpose: kept
    assert people.root_dir("") == str(state.resolve())


def test_app_link_carries_the_folder():
    pid = "6F1C2B9E-7D35-4C1B-9B7A-2E8D5A0C4F11"
    app, web = hylink.links(pid, 4180, "main", ["i1"], folder="WORK/Studio & Co/#1 + ёлка")
    assert app == "hyimg://board/6f1c2b9e-7d35-4c1b-9b7a-2e8d5a0c4f11?page=main&obj=i1&dir=WORK/Studio%20%26%20Co/%231%20%2B%20%D1%91%D0%BB%D0%BA%D0%B0"
    assert "dir" not in web
    for bad in ("../x", "/abs", "a//b", "a/./b", "x\n"):
        assert "dir=" not in hylink.links(pid, 4180, "main", folder=bad)[0]
