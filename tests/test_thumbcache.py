"""Thumbnails out of Dropbox (owner 2026-10-07, docs/storage-plan.md decision 1): review/thumbcache.py moves <state>/_thumbs into
~/Library/Caches/Hyimg/<board>/thumbs (here a temporary HYIMG_CACHE_ROOT), idempotent and resumable, the thumbnails of files that are
gone to the Trash (here a stand-in), and keeps a ceiling by evicting the oldest used. On temporary libraries: the originals, the boards,
the history and the notes stay byte for byte."""
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def put(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return p


def stem(lib, rel):
    return rel.replace("/", "_") + "." + str(int((lib / rel).stat().st_mtime))


@pytest.fixture
def board(tmp_path):
    lib, cache = tmp_path / "Board", tmp_path / "cache"
    pid = str(uuid.uuid4()).upper()
    for n in range(3):   # real pictures, each its own
        buf = io.BytesIO(); Image.new("RGB", (40 + n, 30), (n * 60, 20, 20)).save(buf, "PNG"); put(lib / f"a/{n}.png", buf.getvalue())
    put(lib / "_review/boards/main.json", '{"items": {}}')
    put(lib / "_review/boards/_history/main/261007-120000-auto.json.gz", b"h" * 50)
    put(lib / "notes/n.md", "note")
    old = lib / "_review/_thumbs"
    for n in range(3):
        for s in (96, 320):
            put(old / f"{stem(lib, f'a/{n}.png')}.{s}.jpg", b"t" * (100 + s))
    put(old / "gone_file.png.1700000000.320.jpg", b"o" * 99)   # a thumbnail of a file that is gone
    put(old / "models_x.glb.17.sprite.webp", b"s" * 10)       # a turntable: its version is not the file's time, kept
    trash = tmp_path / "trash.sh"
    trash.write_text(f'#!/bin/bash\nmkdir -p "{tmp_path}/Trash" && mv "$1" "{tmp_path}/Trash/"\n'); trash.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=pid, HYIMG_CACHE_ROOT=str(cache), HYIMG_TRASH=str(trash),
               HYIMG_SETTINGS=str(tmp_path / "settings.json"), HYIMG_LIBRARY_RULES=str(tmp_path / "rules.json"), PYTHONDONTWRITEBYTECODE="1")
    return {"lib": lib, "old": old, "new": cache / pid / "thumbs", "cache": cache, "pid": pid, "env": env, "tmp": tmp_path}


def py(b, code):
    """thumbcache in a process of its own (it reads its places from the environment at import)"""
    out = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, 'review'); import thumbcache as t\n" + code],
                         cwd=ROOT, env=b["env"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else None


def precious(lib):
    return {str(p.relative_to(lib)): hashlib.sha1(p.read_bytes()).hexdigest() for p in lib.rglob("*")
            if p.is_file() and "_thumbs" not in p.parts}


def test_migration_moves_sweeps_and_is_idempotent(board):
    before, names = precious(board["lib"]), sorted(os.listdir(board["old"]))
    assert py(board, "print(json.dumps(t.migrate()))") == {"step": "renamed"}
    assert not board["old"].exists() and sorted(os.listdir(board["new"])) == names
    assert py(board, "print(json.dumps(t.sweep_orphans()))") == 1
    assert sorted(os.listdir(board["new"])) == [n for n in names if not n.startswith("gone_")]
    trashed = list((board["tmp"] / "Trash").iterdir())
    assert len(trashed) == 1 and os.listdir(trashed[0]) == ["gone_file.png.1700000000.320.jpg"]
    # again: nothing to do, nothing changes
    assert py(board, "print(json.dumps(t.migrate()))") == {"step": "nothing to move"}
    assert py(board, "print(json.dumps(t.sweep_orphans()))") == 0
    assert precious(board["lib"]) == before   # originals, boards, history, notes: byte for byte
    log = (board["new"].parent / "thumbs-migration.log").read_text()
    assert "one rename" in log and "1 thumbnails of files that are gone" in log


def test_an_interrupted_move_resumes(board):
    names = sorted(os.listdir(board["old"]))
    board["new"].mkdir(parents=True)
    for n in names[:3]:   # the first files had moved when the move stopped; the old folder still has them too (a machine wrote them again)
        (board["new"] / n).write_bytes((board["old"] / n).read_bytes())
    res = py(board, "print(json.dumps(t.migrate()))")
    assert res == {"step": "merged", "moved": len(names) - 3, "left": 3}
    assert sorted(os.listdir(board["new"])) == names and not board["old"].exists()
    assert [p.name for p in (board["tmp"] / "Trash").iterdir()] == ["_thumbs"]   # the leftovers, copies of what is in place, once
    assert py(board, "print(json.dumps(t.migrate()))") == {"step": "nothing to move"}


def test_another_volume_copies_checks_and_trashes(board):
    names = sorted(os.listdir(board["old"]))
    res = py(board, "t._same_volume = lambda a, b: False\nprint(json.dumps(t.migrate()))")
    assert res["step"] == "merged" and res["moved"] == len(names)
    assert sorted(os.listdir(board["new"])) == names and not board["old"].exists()
    assert all((board["new"] / n).stat().st_size > 0 for n in names)


def test_a_request_during_the_move_takes_the_old_thumbnail(board):
    board["new"].mkdir(parents=True)   # a move in progress: the new folder exists, the old one has the files
    n = next(x for x in os.listdir(board["old"]) if x.endswith(".320.jpg"))
    assert py(board, f"print(json.dumps(t.adopt({n!r})))") is True
    assert (board["new"] / n).exists() and not (board["old"] / n).exists()
    assert py(board, "print(json.dumps(t.adopt('no-such.jpg')))") is False


def test_the_ceiling_evicts_the_oldest_used_first(board):
    d = board["new"]; d.mkdir(parents=True)
    for i in range(10):
        p = put(d / f"f{i}.jpg", b"x" * 40960); os.utime(p, (1000 + i, 1000 + i))
    os.utime(d / "f0.jpg")   # handed out just now: the newest
    res = py(board, "print(json.dumps(t.evict({'board': 6 * 40960, 'total': 10 ** 12})))")
    assert res["removed"] == 4 and sorted(os.listdir(d)) == ["f0.jpg", "f5.jpg", "f6.jpg", "f7.jpg", "f8.jpg", "f9.jpg"]
    # the total over its cap with another board in the cache: this board gives up its share
    other = board["cache"] / "OTHER" / "thumbs"
    for i in range(6):
        put(other / f"o{i}.jpg", b"y" * 40960)
    res = py(board, "print(json.dumps(t.evict({'board': 10 ** 12, 'total': 9 * 40960})))")
    assert res["removed"] == 2 and len(os.listdir(d)) == 4 and len(os.listdir(other)) == 6   # never another board's files
    # the caps from storage-settings.json beside the catalog, in GB
    (board["tmp"] / "storage-settings.json").write_text(json.dumps({"board": 1.5, "total": 3}))
    assert py(board, "print(json.dumps(t.caps()))") == {"board": 1_500_000_000, "total": 3_000_000_000}


def test_used_moves_the_time_at_most_hourly(board):
    p = put(board["new"] / "a.jpg", b"x"); os.utime(p, (1000, 1000))
    py(board, f"t.used({str(p)!r}); print(1)")
    assert p.stat().st_mtime > time.time() - 60
    os.utime(p, (time.time() - 60, time.time() - 60)); before = p.stat().st_mtime
    py(board, f"t.used({str(p)!r}); print(1)")
    assert p.stat().st_mtime == before


def test_the_sweep_waits_when_the_folder_looks_unavailable(board):
    py(board, "print(json.dumps(t.migrate()))")
    for p in (board["lib"] / "a").iterdir():   # the board's files away at once (an unmounted or not yet synced folder)
        p.rename(board["tmp"] / p.name)
    assert py(board, "print(json.dumps(t.sweep_orphans()))") == 0 and len(os.listdir(board["new"])) == 8


def test_the_server_moves_at_start_and_serves_from_the_cache(board):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    before = precious(board["lib"])
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=board["env"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except OSError:
                time.sleep(0.1)
        assert not board["old"].exists() and board["new"].is_dir()   # moved before the first request
        n = len(os.listdir(board["new"]))
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p=a/0.png&s=320", timeout=5).read()
        assert body == b"t" * 420   # the moved thumbnail, not a new one
        urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p=a/1.png&s=640", timeout=5).read()
        assert len(os.listdir(board["new"])) >= n and not board["old"].exists()   # a new size is made in the cache, never in the board
        after = precious(board["lib"])   # the server's own state files (its lease, the hash index) are new; nothing else changed
        assert {k: v for k, v in after.items() if k not in ("_review/.hyimg-server.lock", "_review/sha-index.json")} == before
    finally:
        proc.terminate(); proc.wait(5)
