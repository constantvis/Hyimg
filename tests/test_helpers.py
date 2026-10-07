"""The programs a server starts never outlive it (owner 2026-10-07: about 400 qlmanage of test runs, hung on fake PSDs, ran up to 27 h
after their server). review/helpers.py: a hard limit that kills the helper's whole group, and every helper killed when the server ends.
A fake qlmanage that never ends, and starts a child of its own, stands in for the real one."""
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "review"))
import procs  # noqa: E402


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(st) and not st.startswith("Z")


def wait_for(cond, t=15.0):
    end = time.time() + t
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def setup(tmp_path, limit):
    """a library with one PSD the browser cannot draw, and a qlmanage on PATH that hangs with a child: their pids in a file"""
    lib = tmp_path / "lib"; lib.mkdir()
    (lib / "art.psd").write_bytes(b"8BPS" + b"x" * 200)   # not a real PSD: Pillow cannot read it either
    bin_ = tmp_path / "bin"; bin_.mkdir()
    pids = tmp_path / "pids"
    (bin_ / "qlmanage").write_text(f"#!/bin/bash\nsleep 1000 &\necho $$ $! >> '{pids}'\nwait\n")
    (bin_ / "qlmanage").chmod(0o755)
    port = socket.socket(); port.bind(("127.0.0.1", 0)); n = port.getsockname()[1]; port.close()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_CACHE_ROOT=str(tmp_path / "cache"), HYIMG_PLUGINS=str(tmp_path / "no-plugins"), HYIMG_HELPER_TIMEOUT=str(limit),
               PATH=f"{bin_}:{env['PATH']}", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(n)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: _up(n))
    return proc, n, pids


def _up(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).read(); return True
    except OSError:
        return False


def started(pids):
    return [int(x) for x in pids.read_text().split()] if pids.exists() and pids.read_text().strip() else []


def test_a_hung_helper_is_killed_with_its_children_at_its_limit(tmp_path):
    proc, port, pids = setup(tmp_path, 2)
    try:
        t = time.time()
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p=art.psd&s=320", timeout=30).read()
        assert body[:2] == b"\xff\xd8" and time.time() - t < 15   # the grey card after the limit, not a hang
        ql, child = started(pids)
        assert wait_for(lambda: not alive(ql) and not alive(child), 5)   # the whole group, its sleep too
        assert proc.poll() is None   # the server goes on
    finally:
        proc.terminate(); proc.wait(5)
        for p in started(pids):
            if alive(p): os.kill(p, signal.SIGKILL)


def test_helpers_are_killed_when_the_server_ends(tmp_path):
    proc, port, pids = setup(tmp_path, 600)
    threading.Thread(target=lambda: _get(port), daemon=True).start()
    try:
        assert wait_for(lambda: len(started(pids)) == 2)
        ql, child = started(pids)
        assert alive(ql) and alive(child)
        proc.terminate(); proc.wait(5)   # SIGTERM, as a test or the app ends it
        assert wait_for(lambda: not alive(ql) and not alive(child), 5)
    finally:
        if proc.poll() is None: proc.kill()
        for p in started(pids):
            if alive(p): os.kill(p, signal.SIGKILL)


def _get(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/thumb?p=art.psd&s=320", timeout=60).read()
    except OSError:
        pass


def test_lost_helpers_are_listed_by_their_command_line():
    assert procs.kind_of("qlmanage -t -s 2048 -o /Volumes/x/Library/Caches/Hyimg/AB/thumbs/tmpq /x/a.psd") == ("helper", "qlmanage")
    assert procs.kind_of("/opt/homebrew/bin/ffmpeg -v error -i /a.mov /s/_review/_thumbs/tmp/f.png") == ("helper", "ffmpeg")
    assert procs.kind_of("qlmanage -t -s 2048 -o /Volumes/x/Desktop /x/a.psd") is None   # the person's own Quick Look
    assert procs.kind_of("/opt/homebrew/bin/ffmpeg -i /Volumes/x/Movies/a.mov /Volumes/x/Movies/b.mp4") is None


def test_run_kills_the_group_and_keeps_the_callers_choices():
    import helpers
    out = subprocess.run([sys.executable, "-c", "import helpers, subprocess, sys, time\n"
                          "helpers.install(); t = time.time()\n"
                          "try:\n    subprocess.run(['bash', '-c', 'sleep 1000 & echo $!; wait'], capture_output=True, timeout=1)\n"
                          "except subprocess.TimeoutExpired as ex:\n    print(ex.output.decode().strip(), round(time.time() - t))\n"
                          "print(subprocess.run(['echo', 'ok'], capture_output=True, text=True).stdout.strip())\n"
                          "p = subprocess.Popen(['sleep', '30'], start_new_session=True); print(p in helpers.live()); helpers.kill_all()\n"
                          "print(p.wait(5) != 0)"],
                         cwd=ROOT / "review", capture_output=True, text=True, timeout=30)
    lines = out.stdout.split("\n")
    sleeper, secs = lines[0].split()
    assert int(secs) <= 3 and wait_for(lambda: not alive(int(sleeper)), 3), out.stderr
    assert lines[1:4] == ["ok", "True", "True"], out
    assert helpers.limit(None) == helpers.DEFAULT_LIMIT and helpers.limit(30) == 30
