"""Settings › Storage (owner 2026-10-07): the scan of review/storage.py on disposable libraries (sizes by category, duplicates,
thumbnails of files that are gone, the summary), GET /api/storage of a board's server, and the two deletions of storage_clean.py:
«Clear cache» removes only regenerable caches inside the cache folder (links, folders outside it, recent files and the person's
files are never touched) and the app's old copies go to the Trash, the newest kept."""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "review"))
import storage  # noqa: E402
import storage_clean  # noqa: E402

OLD = time.time() - 3600


def touch_old(p):
    os.utime(p, (OLD, OLD))


def put(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return p


@pytest.fixture
def env(tmp_path, monkeypatch):
    """a catalog of one board (its folder with a state folder inside), a cache folder and an apps folder, all disposable"""
    lib, cache, apps, support = tmp_path / "Board", tmp_path / "Caches/Hyimg", tmp_path / "Applications", tmp_path / "support"
    for d in (lib, cache, apps, support):
        d.mkdir(parents=True)
    pid = str(uuid.uuid4()).upper()
    (support / "projects.json").write_text(json.dumps([{"id": pid, "name": "Board", "libraryRoot": str(lib), "stateRoot": str(lib / "_review")}]))
    for k in ("HYIMG_LIBRARY_ROOT", "HYIMG_STATE_ROOT", "HYIMG_PROJECT_ID", "HYIMG_SETTINGS", "HYIMG_STYLE_REFS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HYIMG_SUPPORT_ROOT", str(support)); monkeypatch.setenv("HYIMG_CACHE_ROOT", str(cache))
    monkeypatch.setenv("HYIMG_INSTALL_DIR", str(apps)); monkeypatch.setenv("HYIMG_LIBRARY_RULES", str(support / "rules.json"))
    monkeypatch.setenv("HYIMG_LOGS", str(tmp_path / "logs"))
    return {"lib": lib, "cache": cache, "apps": apps, "support": support, "pid": pid, "tmp": tmp_path}


def library(lib):
    """pictures (one of them twice, one empty), a Photoshop file, a video, a Blender file and its backup, thumbnails (one of a file
    that is gone), history, a 3D card's poster, a note, a log"""
    a = put(lib / "a/one.png", b"P" * 5000)
    put(lib / "b/one-copy.png", b"P" * 5000)          # the same bytes: a duplicate
    put(lib / "b/two.png", b"Q" * 5000)               # the same size, other bytes: not one
    put(lib / "b/empty.png", b"")
    put(lib / "art.psd", b"8BPS" + b"x" * 3000)
    put(lib / "clip.mp4", b"v" * 7000)
    put(lib / "scene.blend", b"B" * 2000); put(lib / "scene.blend1", b"B" * 1900)
    stem = "a_one.png." + str(int(a.stat().st_mtime))
    put(lib / f"_review/_thumbs/{stem}.320.jpg", b"t" * 300)
    put(lib / "_review/_thumbs/gone_file.png.1700000000.320.jpg", b"o" * 200)
    put(lib / "_review/boards/main.json", "{}")
    for n in range(3):
        put(lib / f"_review/boards/_history/main/2610{n:02d}-120000-auto.json.gz", b"h" * 100)
    put(lib / "3d/scenes/s/.posters/c1-v.jpg", b"p" * 400)
    put(lib / "3d/scenes/s/.versions/3.json", b"{}")
    put(lib / "notes/n1.md", "a note")
    put(lib / "_log-batch1.txt", "log")


def test_scan_measures_a_board_by_category_with_duplicates_and_orphans(env):
    library(env["lib"])
    res = storage.scan()
    assert res and Path(storage.summary_path()).is_file() and Path(storage.hashes_path()).is_file()
    assert storage.hashes_path().startswith(str(env["support"]))   # its own files beside the catalog, never in the board's folder
    b = res["boards"][0]; c = b["cats"]
    assert c["image"]["bytes"] == 15000 and c["image"]["files"] == 4
    assert c["psd"]["bytes"] == 3004 and c["video"]["bytes"] == 7000 and c["blend"]["bytes"] == 2000 and c["blendBackups"]["bytes"] == 1900
    assert c["thumbs"] == {"bytes": 500, "disk": c["thumbs"]["disk"], "files": 2}
    assert c["history"]["files"] == 3 and c["posters"]["bytes"] == 400 and c["versions3d"]["files"] == 1
    assert c["notes"]["files"] == 1 and c["logs"]["files"] == 1 and c["boards"]["files"] == 1
    assert b["dups"]["groups"] == 1 and b["dups"]["extra"] == 1 and b["dups"]["wasted"] == 5000
    assert sorted(b["dups"]["top"][0]["paths"]) == ["a/one.png", "b/one-copy.png"]
    assert b["orphanThumbs"]["files"] == 1 and b["orphanThumbs"]["bytes"] == 200
    assert b["total"]["bytes"] == sum(v["bytes"] for v in c.values())
    assert b["classes"]["regenerable"]["bytes"] == 900   # thumbnails and posters
    assert res["totals"]["boards"]["bytes"] == b["total"]["bytes"] and res["totals"]["dups"] == 5000
    assert res["top"][0]["path"].endswith("clip.mp4") and len(res["top"]) <= 30
    # a second scan reuses the hashes it read (one entry per file that shares its size)
    assert len(json.load(open(storage.hashes_path()))) == 3
    # the summary answers at once and does not start a scan while it is fresh
    s = storage.summary(max_age=300)
    assert s["summary"]["t"] == res["t"] and not s["scanning"] and s["age"] < 60


def test_scan_reads_nothing_it_does_not_need_and_writes_nothing_in_the_library(env):
    library(env["lib"])
    before = {p: (p.stat().st_mtime_ns, hashlib.sha1(p.read_bytes()).hexdigest()) for p in env["lib"].rglob("*") if p.is_file()}
    storage.scan()
    after = {p: (p.stat().st_mtime_ns, hashlib.sha1(p.read_bytes()).hexdigest()) for p in env["lib"].rglob("*") if p.is_file()}
    assert before == after


def test_one_scan_at_a_time(env):
    import fcntl
    with open(storage.summary_path() + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert storage.scan() is None and storage.scanning()
    assert not storage.scanning()


def test_classify():
    assert storage.classify(["_thumbs", "x.320.jpg"], True) == "thumbs"
    assert storage.classify(["boards", "_history", "main", "a.json.gz"], True) == "history"
    assert storage.classify(["frames", "2610", "render.3.png"], False) == "frames"
    assert storage.classify(["x", "__pycache__", "a.pyc"], False) == "junk"
    assert storage.classify(["IMG.PSB"], False) == "psd" and storage.classify(["m.GLB"], False) == "model"
    assert storage.classify(["a.blend12"], False) == "blendBackups" and storage.classify(["what.xyz"], False) == "other"


def cache_tree(env, ids_in_catalog):
    c = env["cache"]
    put(c / "video/old.webm", b"w" * 1000); touch_old(c / "video/old.webm")
    put(c / "video/new.webm", b"w" * 1000)                        # written a moment ago: something may be using it
    put(c / "cad/m.glb", b"g" * 500); touch_old(c / "cad/m.glb")
    stale = str(uuid.uuid4()).lower()
    put(c / stale / "library.json", "{}"); touch_old(c / stale / "library.json"); touch_old(c / stale)
    put(c / ids_in_catalog / "library.json", "{}"); touch_old(c / ids_in_catalog)   # a board of the catalog keeps its list
    gone_profile = str(uuid.uuid4()).upper()
    put(c / "Chromium" / gone_profile / "Cache/x", b"c" * 100); touch_old(c / "Chromium" / gone_profile)
    put(c / "Chromium" / ids_in_catalog / "Cache/x", b"c" * 100); touch_old(c / "Chromium" / ids_in_catalog)
    put(c / "models/lama/lama.onnx", b"m" * 100); touch_old(c / "models")
    put(c / "firefly-profile/Default/Cookies", b"k"); touch_old(c / "firefly-profile")
    return stale, gone_profile


def test_clear_cache_removes_only_regenerable_caches(env):
    library(env["lib"])
    stale, profile = cache_tree(env, env["pid"])
    outside = put(env["tmp"] / "precious.png", b"keep me")
    os.symlink(outside, env["cache"] / "video/link.png")
    os.utime(env["cache"] / "video/link.png", (OLD, OLD), follow_symlinks=False)
    os.symlink(env["lib"], env["cache"] / "video/board"); os.utime(env["cache"] / "video/board", (OLD, OLD), follow_symlinks=False)
    lib_before = {p: p.read_bytes() for p in env["lib"].rglob("*") if p.is_file()}
    dry = storage_clean.clear_cache(dry_run=True)
    assert dry["removed"] == 6 and (env["cache"] / "video/old.webm").exists()   # counted, nothing removed
    res = storage_clean.clear_cache()
    gone = {os.path.relpath(p, env["cache"]) for p in res["paths"]}
    assert gone == {"video/old.webm", "video/link.png", "video/board", "cad/m.glb", stale, "Chromium/" + profile}
    assert res["freed"] > 0 and res["removed"] == 6
    c = env["cache"]
    assert (c / "video/new.webm").exists() and (c / env["pid"] / "library.json").exists() and (c / "Chromium" / env["pid"]).exists()
    assert (c / "models/lama/lama.onnx").exists() and (c / "firefly-profile/Default/Cookies").exists()
    assert outside.read_bytes() == b"keep me"   # a link goes as a link, what it points at stays
    assert {p: p.read_bytes() for p in env["lib"].rglob("*") if p.is_file()} == lib_before   # the board, through the link too


def test_clear_cache_refuses_a_cache_folder_that_overlaps_a_board(env, monkeypatch):
    library(env["lib"])
    monkeypatch.setenv("HYIMG_CACHE_ROOT", str(env["lib"] / "_review"))      # inside a board's folder
    with pytest.raises(storage_clean.Refused):
        storage_clean.clear_cache()
    monkeypatch.setenv("HYIMG_CACHE_ROOT", str(env["tmp"]))                  # around it
    with pytest.raises(storage_clean.Refused):
        storage_clean.clear_cache()
    monkeypatch.setenv("HYIMG_CACHE_ROOT", os.path.expanduser("~"))          # the home folder
    with pytest.raises(storage_clean.Refused):
        storage_clean.clear_cache()
    monkeypatch.setenv("HYIMG_CACHE_ROOT", "/")
    with pytest.raises(storage_clean.Refused):
        storage_clean.clear_cache()


def test_guard_refuses_paths_that_climb_out_or_lead_into_a_board(env):
    boards = storage.catalog(); root = os.path.realpath(env["cache"]); now = time.time() + 7200
    put(env["cache"] / "video/a.webm", b"x")
    assert storage_clean._guarded(str(env["cache"] / "video/a.webm"), root, boards, now)
    assert not storage_clean._guarded(str(env["cache"] / "video/../../precious"), root, boards, now)
    assert not storage_clean._guarded(str(env["cache"] / ".."), root, boards, now)
    assert not storage_clean._guarded(str(env["lib"] / "a"), root, boards, now)
    assert not storage_clean._guarded(root, root, boards, now)
    # a folder inside the cache that is really a board's folder (a link two levels up): it resolves into the board, refused
    (env["cache"] / "video/sub").mkdir(); os.symlink(env["lib"], env["cache"] / "video/sub/b")
    assert not storage_clean._guarded(str(env["cache"] / "video/sub/b/a"), root, boards, now)


def fake_trash(tmp):
    bin_ = tmp / "trash.sh"; bin_.write_text(f'#!/bin/bash\nmkdir -p "{tmp}/Trash" && mv "$1" "{tmp}/Trash/"\n'); bin_.chmod(0o755)
    return bin_


def test_old_app_copies_go_to_the_trash_the_newest_stay(env, monkeypatch):
    apps = env["apps"]
    names = [f"Hyimg.backup.202610{d:02d}-120000.app" for d in range(1, 6)]
    for n in names:
        put(apps / n / "Contents/MacOS/Hyimg", b"x" * 1000)
    put(apps / "Hyimg.app/Contents/MacOS/Hyimg", b"app")
    put(apps / "Other.backup.20261001-120000.app/x", b"y")
    os.symlink(apps / names[0], apps / "Hyimg.backup.20250101-000000.app")   # a link with a backup's name: not a copy, left alone
    monkeypatch.setenv("HYIMG_TRASH", str(fake_trash(env["tmp"])))
    assert storage_clean.trash_backups("all")["trashed"] == []
    dry = storage_clean.trash_backups(2, dry_run=True)
    assert dry["trashed"] == names[:3] and all((apps / n).exists() for n in names)
    with pytest.raises(storage_clean.Refused):
        storage_clean.trash_backups(0)
    res = storage_clean.trash_backups(2)
    assert res["trashed"] == names[:3] and res["kept"] == names[3:] and res["freed"] > 0
    assert sorted(os.listdir(env["tmp"] / "Trash")) == names[:3]
    assert (apps / "Hyimg.app").exists() and (apps / "Other.backup.20261001-120000.app").exists()
    assert os.path.islink(apps / "Hyimg.backup.20250101-000000.app")
    # the summary lists them as a reclaimable category
    s = storage.scan_global(storage.catalog())
    assert [b["name"] for b in s["backups"]] == names[3:] and s["app"]["files"] == 1


def test_no_trash_command_moves_nothing(env, monkeypatch):
    for d in range(1, 5):
        put(env["apps"] / f"Hyimg.backup.202610{d:02d}-120000.app/x", b"x")
    monkeypatch.setenv("HYIMG_TRASH", str(env["tmp"] / "no-such-trash"))
    with pytest.raises(storage_clean.Refused):
        storage_clean.trash_backups(2)
    assert len(os.listdir(env["apps"])) == 4


def test_install_keeps_two_copies_through_the_trash():
    """scripts/install.sh prunes through storage.py (the Trash), keeps 2 unless told otherwise, and stays valid bash"""
    sh = (ROOT / "scripts/install.sh").read_text()
    assert 'storage.py" backups --keep "${HYIMG_KEEP_BACKUPS:-2}"' in sh and "rm -rf" not in sh
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts/install.sh")]).returncode == 0


# GET /api/storage of a board's server ------------------------------------------------------------------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(env):
    port = free_port(); lib = env["lib"]
    (lib / "_review/boards").mkdir(parents=True, exist_ok=True)
    (lib / "_review/boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (env["support"] / "settings.json").write_text("{}")
    e = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    e.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(lib / "_review"), HYIMG_PROJECT_ID=env["pid"], HYIMG_SETTINGS=str(env["support"] / "settings.json"),
             HYIMG_CACHE_ROOT=str(env["cache"]), HYIMG_INSTALL_DIR=str(env["apps"]), HYIMG_PLUGINS=str(env["tmp"] / "no-plugins"),
             HYIMG_LIBRARY_RULES=str(env["support"] / "rules.json"), PYTHONDONTWRITEBYTECODE="1")
    log = open(env["tmp"] / "server.log", "w+")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=e, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
        except OSError:
            time.sleep(0.1)
    return port, proc


def get(port, path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5).read())


def post(port, path, body, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def test_endpoint_answers_at_once_and_the_scan_follows(env):
    library(env["lib"]); cache_tree(env, env["pid"])
    port, proc = serve(env)
    try:
        t = time.time(); first = get(port, "/api/storage")
        assert time.time() - t < 2 and first["summary"] is None and first["scanning"] is True
        assert first["server"]["bytes"] > 0
        for _ in range(100):
            d = get(port, "/api/storage")
            if d["summary"]:
                break
            time.sleep(0.2)
        b = d["summary"]["boards"][0]
        assert b["id"] == env["pid"] and b["dups"]["wasted"] == 5000 and d["summary"]["totals"]["clearable"]["files"] >= 4
        # a page of another site may not clear anything
        with pytest.raises(urllib.error.HTTPError) as no:
            post(port, "/api/storage/clear", {}, {"Origin": "http://evil.example"})
        assert no.value.code == 403 and (env["cache"] / "video/old.webm").exists()
        res = post(port, "/api/storage/clear", {})
        assert res["removed"] >= 4 and not (env["cache"] / "video/old.webm").exists() and (env["cache"] / "video/new.webm").exists()
        assert (env["lib"] / "a/one.png").read_bytes() == b"P" * 5000
        with pytest.raises(urllib.error.HTTPError) as bad:   # keep at least one copy
            post(port, "/api/storage/backups", {"keep": 0})
        assert bad.value.code == 400
    finally:
        proc.terminate(); proc.wait(5)



def test_thumbnails_in_the_cache_are_counted_apart_and_the_ceiling_is_kept(env):
    """since thumbcache.py the board's thumbnails live in the cache: counted as cacheThumbs, outside the board's own size"""
    library(env["lib"])
    put(env["cache"] / env["pid"] / "thumbs/gone.png.1700000000.96.jpg", b"g" * 700)
    b = storage.scan()["boards"][0]
    assert b["cacheThumbs"]["files"] == 1 and b["cacheThumbs"]["bytes"] == 700
    assert b["orphanThumbs"]["files"] == 2   # the old folder's and the cache's
    assert storage.caps_read() == {"board": 2, "total": 8}
    assert storage.caps_write(board=5) == {"board": 5, "total": 8} and storage.caps_read()["board"] == 5
    with pytest.raises(ValueError):
        storage.caps_write(total=0)
    assert storage.summary(max_age=10 ** 9)["caps"] == {"board": 5, "total": 8}
