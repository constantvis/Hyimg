"""No server runs forever (owner 2026-10-07: «нужно за этим тоже следить, чтобы не было этой бесконечной херни, которая запускается»).
review/lifetime.py: a server the app did not start ends with the process that started it and after its idle time; the app's server
ends with the app and never for being idle. tests/procguard.py: the tests' servers are remembered and ended with the session, and get
a cache folder of their own. review/procs.py: servers and Blender whose parent is gone are found and stopped, nothing else."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

import procguard

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "review"))
import procs  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def env_for(tmp_path, **more):
    lib = tmp_path / "lib"; lib.mkdir(exist_ok=True)
    e = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    e.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
             HYIMG_CACHE_ROOT=str(tmp_path / "cache"), HYIMG_PLUGINS=str(tmp_path / "no-plugins"), PYTHONDONTWRITEBYTECODE="1", **more)
    return e


def up(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).read()
        return True
    except OSError:
        return False


def wait_for(cond, t=15.0):
    end = time.time() + t
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(st) and not st.startswith("Z")


def test_a_server_not_started_by_the_app_ends_with_its_parent(tmp_path):
    port = free_port()
    # a parent that starts a server without HYIMG_PARENT_PID (a test's, an agent's) and is then killed outright
    helper = "import subprocess,sys; p=subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]]); print(p.pid, flush=True); p.wait()"
    parent = subprocess.Popen([sys.executable, "-c", helper, str(ROOT / "review/server.py"), str(port)], env=env_for(tmp_path),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    pid = int(parent.stdout.readline())
    try:
        assert wait_for(lambda: up(port))
        parent.kill(); parent.wait(5)
        assert wait_for(lambda: not alive(pid), 10), "the server outlived the process that started it"
    finally:
        if alive(pid):
            os.kill(pid, signal.SIGKILL)


def start(tmp_path, **more):
    port = free_port()
    p = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env_for(tmp_path, **more),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: up(port))
    return p, port


def test_an_idle_server_ends_and_one_in_use_does_not(tmp_path):
    p, port = start(tmp_path, HYIMG_IDLE_EXIT="3")
    try:
        t = time.time()
        while time.time() - t < 5:   # asked every 0.5 s, as an open page asks /api/changes: it stays
            assert up(port) and p.poll() is None
            time.sleep(0.5)
        assert p.wait(10) == 0   # then no request: it ends by itself, and cleanly
    finally:
        if p.poll() is None:
            p.kill()


def test_the_apps_server_is_never_idle_and_ends_with_the_app(tmp_path):
    port = free_port()
    helper = ("import os,subprocess,sys; os.environ['HYIMG_PARENT_PID']=str(os.getpid()); os.environ['HYIMG_IDLE_EXIT']='1';"
              "p=subprocess.Popen([sys.executable,sys.argv[1],sys.argv[2]]); print(p.pid, flush=True); p.wait()")
    app = subprocess.Popen([sys.executable, "-c", helper, str(ROOT / "review/server.py"), str(port)], env=env_for(tmp_path),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    pid = int(app.stdout.readline())
    try:
        assert wait_for(lambda: up(port))
        time.sleep(3.5)   # far past its idle setting: the app's server ignores it
        assert alive(pid)
        app.kill(); app.wait(5)
        assert wait_for(lambda: not alive(pid), 5)
    finally:
        if alive(pid):
            os.kill(pid, signal.SIGKILL)


def test_guard_remembers_our_servers_gives_them_a_cache_and_ends_them(tmp_path):
    assert subprocess.Popen is procguard.TrackedPopen   # installed by conftest.py
    assert procguard.ours([sys.executable, "/x/review/server.py", "4180"]) and procguard.ours("blender -P /b/blender/bridge_server.py")
    assert not procguard.ours(["ps", "-ax"]) and not procguard.ours([sys.executable, "-c", "print(1)"])
    fake = tmp_path / "review" / "server.py"; fake.parent.mkdir()
    fake.write_text("import os, sys, time\nprint(os.environ.get('HYIMG_CACHE_ROOT'), flush=True)\ntime.sleep(60)\n")
    mine = subprocess.Popen([sys.executable, str(fake)], env={"PATH": os.environ["PATH"]}, stdout=subprocess.PIPE, text=True)
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert mine.stdout.readline().strip() == procguard.CACHE   # not ~/Library/Caches/Hyimg
        assert os.environ["HYIMG_CACHE_ROOT"] == procguard.CACHE
        kept = list(procguard.STARTED)
        assert mine in kept and other not in kept
        assert mine.pid in procguard.sweep()
        assert mine.poll() is not None and other.poll() is None   # only what it started, and only ours
    finally:
        other.kill(); other.wait(5)
        if mine.poll() is None:
            mine.kill()


def orphan(tmp_path, script):
    """a process of ours whose parent is gone: started by a parent that exits at once, so the system adopts it (parent 1)"""
    helper = ("import subprocess,sys; p=subprocess.Popen(sys.argv[1:], start_new_session=True, stdin=subprocess.DEVNULL,"
              " stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); print(p.pid, flush=True)")
    out = subprocess.run([sys.executable, "-c", helper, *script], capture_output=True, text=True, timeout=10).stdout
    pid = int(out.strip())
    assert wait_for(lambda: subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() == "1", 5)
    return pid


def test_lost_processes_are_found_and_only_they_are_stopped(tmp_path):
    assert procs.kind_of(f"{sys.executable} /x/review/server.py 4180") == ("server", "4180")
    assert procs.kind_of("/Applications/Blender 5.1.1.app/Contents/MacOS/Blender -b --factory-startup -P /r/blender/bridge_server.py -- x")[0] == "blender"
    assert procs.kind_of("/usr/bin/vim /x/review/server.py") is None and procs.kind_of("grep review/server.py") is None
    fake = tmp_path / "review" / "server.py"; fake.parent.mkdir()
    fake.write_text("import time\ntime.sleep(120)\n")
    other = tmp_path / "other.py"; other.write_text("import time\ntime.sleep(120)\n")
    pid = orphan(tmp_path, [sys.executable, str(fake), "4999"])
    stranger = orphan(tmp_path, [sys.executable, str(other)])   # lost too, but not ours: never listed, never stopped
    try:
        found = {p["pid"]: p for p in procs.lost()}
        assert pid in found and stranger not in found
        assert found[pid]["kind"] == "server" and found[pid]["port"] == "4999" and found[pid]["bytes"] > 0
        assert procs.stop(stranger).get("error") and alive(stranger)
        assert procs.stop(os.getpid()).get("error") and procs.stop("x").get("error")
        res = procs.stop(pid)
        assert res["stopped"] == pid and not alive(pid)
        assert pid not in {p["pid"] for p in procs.lost()}
    finally:
        for p in (pid, stranger):
            if alive(p):
                os.kill(p, signal.SIGKILL)


def test_storage_endpoint_lists_lost_processes_and_stops_only_them(tmp_path):
    from test_storage import post
    fake = tmp_path / "x" / "review" / "server.py"; fake.parent.mkdir(parents=True)
    fake.write_text("import time\ntime.sleep(120)\n")
    pid = orphan(tmp_path, [sys.executable, str(fake), "4998"])
    p, port = start(tmp_path, HYIMG_SUPPORT_ROOT=str(tmp_path / "support"))
    try:
        d = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/storage", timeout=5).read())
        assert pid in {x["pid"] for x in d["lost"]} and p.pid not in {x["pid"] for x in d["lost"]}   # its own server is not lost
        with pytest.raises(urllib.error.HTTPError) as no:
            post(port, "/api/storage/stop", {"pid": p.pid})
        assert no.value.code == 400 and p.poll() is None
        assert post(port, "/api/storage/stop", {"pid": pid})["stopped"] == pid and not alive(pid)
    finally:
        p.terminate(); p.wait(5)
        if alive(pid):
            os.kill(pid, signal.SIGKILL)

