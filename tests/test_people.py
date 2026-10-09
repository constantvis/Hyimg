"""Who made a change (owner 2026-10-07: two people, each on his own Mac, share boards through a shared Dropbox folder). review/people.py
keeps this Mac's profile and address book, every write is stamped by {person, via}; review/places.py keeps the shared and the private
folder and moves a board's folder between them. Temporary folders only: the profile lives beside the test server's settings."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "review"))
import people  # noqa: E402
import places  # noqa: E402
from test_shortcuts import run_server  # noqa: E402

HY = ROOT / "review/hy.py"


def test_profile_address_book_and_sign_out(tmp_path):
    """the id is made once; a rename keeps it; sign out forgets the profile only; the address book keeps names and local renames"""
    assert people.me(tmp_path) is None
    a = people.save_me(tmp_path, "  Ann   Lee ", "green")
    assert uuid.UUID(a["id"]) and a["name"] == "Ann Lee" and a["color"] == "green" and a["created"]
    b = people.save_me(tmp_path, "Ann", "nonsense")
    assert b["id"] == a["id"] and b["name"] == "Ann" and b["color"] == "green"   # an unknown colour keeps the one before
    with pytest.raises(ValueError): people.save_me(tmp_path, "   ", "red")
    # another person's card on a shared board: learnt into the book; a local rename wins over their own name
    other = str(uuid.uuid4()); state = tmp_path / "board/_review"
    people.card_write(state, {"id": other, "name": "Bob", "color": "orange"})
    v = people.view(tmp_path, state)
    assert v["people"][other] == {"name": "Bob", "own": "Bob", "color": "orange"} and v["people"][a["id"]]["me"] is True
    people.alias(tmp_path, other, "Partner")
    assert people.view(tmp_path, state)["people"][other]["name"] == "Partner"
    people.card_write(state, {"id": other, "name": "Robert", "color": "orange"})   # he renamed himself on his Mac
    p = people.view(tmp_path, state)["people"][other]
    assert p["name"] == "Partner" and p["own"] == "Robert"
    people.alias(tmp_path, other, "")
    assert people.view(tmp_path, state)["people"][other]["name"] == "Robert"
    # sign out: the profile goes, the book keeps the name for the changes made so far, nothing else is touched
    files = sorted(os.listdir(tmp_path))
    people.sign_out(tmp_path)
    assert people.me(tmp_path) is None and people.book(tmp_path)[a["id"]]["name"] == "Ann"
    assert sorted(os.listdir(tmp_path)) == [f for f in files if f != "profile.json"]
    # the stamp: without a profile only via; with one, the person too
    assert people.by(tmp_path, "", "owner") == {"via": "app"} and people.by(tmp_path, "", "ai") == {"via": "agent"}
    c = people.save_me(tmp_path, "Ann", "green")
    assert c["id"] != a["id"] and people.by(tmp_path, "Codex", "ai") == {"person": c["id"], "via": "codex"}   # a catalog kind (agents.py)


def test_places_and_moving_a_board(tmp_path, monkeypatch):
    """the two folders are this Mac's settings; a board's folder moves between them: one rename on a volume, a checked copy and the
    old folder to the Trash between volumes; an existing name or a target inside the board is refused and nothing moves"""
    shared, private, root = tmp_path / "Shared", tmp_path / "Private", tmp_path / "support"
    shared.mkdir(); private.mkdir()
    assert places.read(root) == {"shared": "", "private": ""}
    with pytest.raises(ValueError): places.write(root, shared=str(tmp_path / "nope"))
    with pytest.raises(ValueError): places.write(root, shared=str(shared), private=str(shared / "inner"))
    pl = places.write(root, shared=str(shared), private=str(private))
    board = private / "Board"; (board / "_review/boards").mkdir(parents=True)
    (board / "a.png").write_bytes(b"x" * 100); (board / "_review/boards/main.json").write_text("{}")
    assert places.visibility(str(board), pl) == "private" and places.visibility(str(tmp_path), pl) == ""
    res = places.move(str(board), pl["shared"], str(board / "_review"))
    moved = Path(res["libraryRoot"])
    assert res["how"] == "rename" and moved == (shared / "Board").resolve() and res["stateRoot"] == str(moved / "_review")
    assert (moved / "a.png").read_bytes() == b"x" * 100 and not board.exists() and places.visibility(str(moved), pl) == "shared"
    (private / "Board").mkdir()
    with pytest.raises(ValueError, match="already there"): places.move(str(moved), pl["private"])
    assert (moved / "a.png").exists()
    with pytest.raises(ValueError): places.move(str(moved), str(moved / "_review"))
    (private / "Board").rmdir()
    # another volume: copied, checked, then the old folder to the Trash (a fake Trash here)
    trash = tmp_path / "Trash"; trash.mkdir()
    fake = tmp_path / "trash.sh"; fake.write_text(f'#!/bin/sh\nmv "$1" "{trash}/"\n'); fake.chmod(0o755)
    monkeypatch.setenv("HYIMG_TRASH", str(fake)); monkeypatch.setattr(places, "_same_volume", lambda a, b: False)
    res = places.move(str(moved), pl["private"], str(moved / "_review"))
    assert res["how"] == "copy" and res["trashed"] and (private / "Board/a.png").read_bytes() == b"x" * 100
    assert (trash / "Board/a.png").exists() and not moved.exists() and not list(private.glob("*.hyimg-moving"))
    # the command line the app runs
    env = {**os.environ, "HYIMG_PROFILE_DIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run([sys.executable, str(ROOT / "review/places.py"), "move", str(private / "Board"), "shared", "--state", str(private / "Board/_review")],
                         env=env, capture_output=True, text=True, timeout=30)
    res = json.loads(out.stdout)
    assert out.returncode == 0 and res["libraryRoot"] == str((shared / "Board").resolve()), out.stdout + out.stderr


@pytest.fixture
def server(tmp_path):
    me = people.save_me(tmp_path, "Ann", "green")   # the test server's settings are in tmp_path, so is its profile
    other = str(uuid.uuid4())
    (tmp_path / "people.json").write_text(json.dumps({**people.book(tmp_path), other: {"name": "Bob", "color": "orange", "alias": "Partner"}}))
    for port in run_server(tmp_path):
        yield port, tmp_path, me, other


def api(port, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)


def test_every_write_says_who(server):
    """a canvas save is the app's, a hy.py edit the agent's (HYIMG_AGENT), both this Mac's person; history, events, file writes, the
    board's people card and /api/edited carry it"""
    port, tmp, me, other = server
    state = tmp / "state"
    b = api(port, "/api/board?name=main")
    b["items"]["n1"] = {"type": "note", "text": "from the canvas", "x": 0, "y": 900, "w": 320, "fs": 18, "color": "yellow"}
    api(port, "/api/board?name=main&who=owner", b)   # what canvas.html sends on a save
    ev = api(port, "/api/events?name=main")[0]
    assert ev["kind"] == "note" and ev["by"] == {"person": me["id"], "via": "app"}
    assert json.loads((state / "people" / f"{me['id']}.json").read_text())["name"] == "Ann"   # the other Mac learns the name from it
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")}
    r = subprocess.run([sys.executable, str(HY), "do", 'note "from an agent" x=400 y=900', "--page", "main"],
                       env={**env, "HYIMG_PORT": str(port), "HYIMG_AGENT": "Codex"}, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    ev = api(port, "/api/events?name=main")[0]
    assert ev["kind"] == "note" and ev["by"] == {"person": me["id"], "via": "codex"} and ev["who"] == "ai"
    hist = api(port, "/api/history?name=main")
    assert any(h.get("by") == {"person": me["id"], "via": "codex"} and h["who"] == "ai" for h in hist), hist
    # a plugin's file (a 3D scene): its own log line, and «edited by» finds it
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/file?p=3d/scenes/s/scene.json", data=b'{"v": 1}', method="POST",
                                 headers={"Content-Type": "application/octet-stream", "X-Hyimg-Agent": "Claude"})
    urllib.request.urlopen(req, timeout=10).read()
    e = api(port, "/api/edited?name=main&p=3d/scenes/s/scene.json")
    assert e["by"] == {"person": me["id"], "via": "claude"} and e["kind"] == "file"
    nid = next(i for i, it in api(port, "/api/board?name=main")["items"].items() if it.get("text") == "from an agent")
    assert api(port, f"/api/edited?name=main&id={nid}")["by"]["via"] == "codex"
    # the page's view: me, the address book with the local rename, the places
    v = api(port, "/api/profile")
    assert v["me"]["name"] == "Ann" and v["people"][other]["name"] == "Partner" and v["places"] == {"shared": "", "private": ""}
    v = api(port, "/api/profile", {"op": "alias", "person": other, "name": "Bobby"})
    assert v["people"][other]["name"] == "Bobby" and json.loads((tmp / "people.json").read_text())[other]["alias"] == "Bobby"
    assert api(port, "/api/profile", {"op": "save", "name": "Ann B", "color": "pink"})["me"]["id"] == me["id"]
    assert "error" in api_err(port, {"op": "places", "shared": str(tmp / "missing")})


def api_err(port, body):
    try: return api(port, "/api/profile", body)
    except urllib.error.HTTPError as e: return json.loads(e.read())
