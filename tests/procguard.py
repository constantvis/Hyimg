"""No test leaves a process behind (owner 2026-10-07, after 17 servers of tests and agents had run for up to 30 hours: «нужно за этим
тоже следить, чтобы не было этой бесконечной херни, которая запускается»). Loaded by the conftest.py of each of the four
repositories.

- Every process a test starts with subprocess.Popen whose command runs one of our servers (review/server.py, a plugin's server.py or
  serve.py, the Blender bridge, mcp/server.py) is remembered by its pid. When the session ends, also on ⌃C, each one still running
  gets SIGTERM and, 3 s later, SIGKILL. Only these: nothing the session did not start is ever signalled.
- Such a server gets HYIMG_CACHE_ROOT, a folder of this session that goes with it, unless the test set its own: a test never writes
  into ~/Library/Caches/Hyimg.
- If the session itself is killed, the servers end anyway: a server not started by the app ends with its parent (review/lifetime.py).
"""
import atexit
import os
import shutil
import subprocess
import tempfile

OURS = ("server.py", "serve.py", "bridge_server.py")
_BASE = subprocess.Popen
STARTED = []
CACHE = tempfile.mkdtemp(prefix="hyimg-test-cache-")


def ours(args):
    """does this command run one of our servers"""
    words = args.split() if isinstance(args, str) else [os.fsdecode(w) for w in ([args] if isinstance(args, (bytes, os.PathLike)) else args or [])]
    return any(w.endswith(OURS) for w in words)


class TrackedPopen(_BASE):
    def __init__(self, args, *a, **kw):
        mine = ours(args)
        if mine:
            env = kw.get("env")
            if env is not None and "HYIMG_CACHE_ROOT" not in env:
                kw["env"] = {**env, "HYIMG_CACHE_ROOT": CACHE}
        super().__init__(args, *a, **kw)
        if mine:
            STARTED.append(self)


def install():
    """from a conftest: Popen remembers our servers; the cache of this session is HYIMG_CACHE_ROOT for the tests' own imports too"""
    if subprocess.Popen is not TrackedPopen:
        subprocess.Popen = TrackedPopen
        os.environ.setdefault("HYIMG_CACHE_ROOT", CACHE)
        atexit.register(lambda: (sweep(), shutil.rmtree(CACHE, ignore_errors=True)))


def sweep():
    """ends every server this session started that is still running; returns their pids"""
    left = [p for p in STARTED if p.poll() is None]
    for p in left:
        try:
            p.terminate()
        except OSError:
            pass
    for p in left:
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            try:
                p.kill(); p.wait(3)
            except (OSError, subprocess.TimeoutExpired):
                pass
    STARTED.clear()
    return [p.pid for p in left]
