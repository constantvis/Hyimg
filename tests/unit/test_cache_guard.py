"""Tests stay out of the person's ~/Library/Caches/Hyimg (2026-10-08: about 10,800 folders of throwaway boards, named by lowercase
UUIDs, had landed there from 2026-10-04 on). tests/procguard.py: the session's own cache folder, and the check at the end that fails
the run when a test wrote there anyway; review/config.py: a library in the temporary folder keeps its cache there too. Here against a
made-up cache folder, never the person's."""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import procguard

REVIEW = Path(__file__).resolve().parents[2] / "review"


def test_this_session_has_its_own_cache():
    assert os.environ["HYIMG_CACHE_ROOT"] == procguard.CACHE
    assert os.path.realpath(procguard.CACHE) != procguard.REAL
    import config
    assert config.CACHE_ROOT == os.path.realpath(procguard.CACHE)


def test_a_throwaway_board_or_its_perf_entry_is_a_leak_the_persons_are_not(tmp_path, monkeypatch):
    root = tmp_path / "Caches/Hyimg"
    (root / "4A3621CA-84A1-4029-B8A5-D3571447BDF7").mkdir(parents=True); (root / "perf").mkdir()
    log = root / "perf/perf-2026-10-08.jsonl"
    log.write_text(json.dumps({"board": "4a3621ca-84a1-4029-b8a5-d3571447bdf7", "action": "zoom"}) + "\n")
    start = procguard.snapshot(str(root))
    assert procguard.leaks(start, str(root)) == []

    # the owner's app meanwhile: a board of its own (uppercase), entries of its boards, a new day's log
    (root / "2C4C1BC6-CEC9-44F1-BA0A-449CFB940009").mkdir()
    with log.open("a") as f:
        f.write(json.dumps({"board": "4a3621ca-84a1-4029-b8a5-d3571447bdf7", "action": "key"}) + "\n")
    (root / "perf/perf-2026-10-09.jsonl").write_text(json.dumps({"board": "2c4c1bc6-cec9-44f1-ba0a-449cfb940009"}) + "\n")
    (root / "video").mkdir()
    assert procguard.leaks(start, str(root)) == []

    # a test's board: its folder, and an entry of it in the log
    pid = str(uuid.uuid4())
    (root / pid).mkdir(); (root / pid / "library.json").write_text(json.dumps({"root": "/tmp/pytest/test_x0/lib", "items": []}))
    with log.open("a") as f:
        f.write(json.dumps({"board": pid, "action": "idle"}) + "\n")
    found = procguard.leaks(start, str(root))
    assert len(found) == 2 and found[0].startswith(str(root / pid)) and "/tmp/pytest/test_x0/lib" in found[0]
    assert pid in found[1] and "perf-2026-10-08.jsonl" in found[1]

    # an uppercase id this session gave a server counts too; the person's board that had its folder before never does
    made_up = "6B1F3C2A-1111-4222-8333-944455556666"
    monkeypatch.setattr(procguard, "IDS", {made_up.lower(), "4a3621ca-84a1-4029-b8a5-d3571447bdf7"})
    (root / made_up).mkdir()
    found = procguard.leaks(start, str(root))
    assert any(made_up in f for f in found) and not any("4A3621CA" in f or "4a3621ca" in f for f in found)


def test_a_server_gets_the_sessions_cache_unless_home_is_moved(tmp_path):
    show = [sys.executable, "-c", "import os; print(os.environ.get('HYIMG_CACHE_ROOT', ''))"]
    run = lambda env: subprocess.run(show, env=env, capture_output=True, text=True, timeout=20).stdout.strip()
    assert run({"PATH": os.environ["PATH"]}) == procguard.CACHE                                    # the person's HOME: the session's
    assert run({"PATH": os.environ["PATH"], "HYIMG_CACHE_ROOT": procguard.REAL}) == procguard.CACHE  # the person's cache: replaced
    assert run({"PATH": os.environ["PATH"], "HYIMG_CACHE_ROOT": str(tmp_path)}) == str(tmp_path)    # a test's own: kept
    assert run({"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home")}) == ""                 # HOME moved: the test's default


def test_a_library_in_the_temporary_folder_keeps_its_cache_there(tmp_path):
    show = "import os, config; print(config.CACHE_ROOT); print(os.environ['HYIMG_CACHE_ROOT'] if 'HYIMG_CACHE_ROOT' in os.environ else '')"
    home = tmp_path / "home"; home.mkdir()
    base = {"PATH": os.environ["PATH"], "HOME": str(home), "HYIMG_PROJECT_ID": str(uuid.uuid4()),
            "HYIMG_LIBRARY_RULES": str(tmp_path / "no-rules.json"), "PYTHONDONTWRITEBYTECODE": "1"}

    def cache_of(lib, **more):
        out = subprocess.run([sys.executable, "-c", show], cwd=REVIEW, env={**base, "HYIMG_LIBRARY_ROOT": str(lib), **more},
                             capture_output=True, text=True, timeout=20)
        assert out.returncode == 0, out.stderr
        return out.stdout.splitlines()

    lib = tmp_path / "lib"; lib.mkdir()
    root, env = cache_of(lib)
    assert "hyimg-test-cache-" in root and not root.startswith(str(home)) and env and os.path.realpath(env) == root
    assert cache_of(lib, HYIMG_CACHE_ROOT=str(tmp_path / "mine"))[0] == os.path.realpath(tmp_path / "mine")
    # a library outside the temporary folder (here the code's own folder, only read): the app's cache under HOME, as before
    root, env = cache_of(REVIEW)
    assert root == os.path.realpath(home / "Library/Caches/Hyimg") and env == ""
