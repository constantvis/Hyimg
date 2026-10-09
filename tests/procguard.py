"""No test leaves a process behind (owner 2026-10-07, after 17 servers of tests and agents had run for up to 30 hours: «нужно за этим
тоже следить, чтобы не было этой бесконечной херни, которая запускается»). Loaded by the conftest.py of each of the four
repositories, their tests/unit/conftest.py too (pytest tests/unit does not load tests/conftest.py); one guard a session.

- Every process a test starts with subprocess.Popen whose command runs one of our servers (review/server.py, a plugin's server.py or
  serve.py, the Blender bridge, mcp/server.py) is remembered by its pid. When the session ends, also on ⌃C, each one still running
  gets SIGTERM and, 3 s later, SIGKILL. Only these: nothing the session did not start is ever signalled.
- HYIMG_CACHE_ROOT is a folder of this session that goes with it: for the tests' own imports, for our servers unless the test set
  its own, and for any other command given an environment of its own that keeps the person's HOME. A test never writes into
  ~/Library/Caches/Hyimg; a cache root that points there is replaced.
- The person's cache is listed when the session starts and again when it ends (finish()): a new folder named by a lowercase UUID
  (a throwaway board: the app's boards are named by uppercase ids) or a performance log entry of a board this session started fails
  the run. The owner's own app and servers (ports 4180-4184) write there meanwhile: their boards are uppercase, their perf entries
  are of their boards, so they never count. On 2026-10-08 about 10,800 such folders were found there from 2026-10-04 on.
- If the session itself is killed, the servers end anyway: a server not started by the app ends with its parent (review/lifetime.py).
"""
import atexit
import json
import os
import re
import shutil
import subprocess
import tempfile

OURS = ("server.py", "serve.py", "bridge_server.py")
_BASE = subprocess.Popen
STARTED = []
CACHE = tempfile.mkdtemp(prefix="hyimg-test-cache-")
HOME = os.path.realpath(os.path.expanduser("~"))
REAL = os.path.realpath(os.path.join(HOME, "Library/Caches/Hyimg"))   # the person's cache
THROWAWAY = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
IDS = set()   # the board ids (lowercase) of the processes this session started
_START = None
_DONE = False


def ours(args):
    """does this command run one of our servers"""
    words = args.split() if isinstance(args, str) else [os.fsdecode(w) for w in ([args] if isinstance(args, (bytes, os.PathLike)) else args or [])]
    return any(w.endswith(OURS) for w in words)


def _real_cache(path):
    return bool(path) and os.path.realpath(path) == REAL


class TrackedPopen(_BASE):
    def __init__(self, args, *a, **kw):
        mine = ours(args)
        env = kw.get("env")
        if env is not None:
            cache = env.get("HYIMG_CACHE_ROOT")
            # HOME moved to a temporary folder moves the cache with it: such a test checks the default places itself
            home = os.path.realpath(os.path.expanduser(env["HOME"])) if env.get("HOME") else HOME
            if _real_cache(cache) or (not cache and (mine or home == HOME)):
                kw["env"] = env = {**env, "HYIMG_CACHE_ROOT": CACHE}
        if env is not None and env.get("HYIMG_PROJECT_ID"):   # a board the test made up, not one the session inherited
            IDS.add(env["HYIMG_PROJECT_ID"].lower())
        super().__init__(args, *a, **kw)
        if mine:
            STARTED.append(self)


def install():
    """from a conftest: Popen remembers our servers; the cache of this session is HYIMG_CACHE_ROOT for the tests' own imports too; the
    person's cache is listed for finish(). Once a session: every conftest takes sys.modules["procguard"] when there is one"""
    global _START
    if subprocess.Popen is not TrackedPopen:
        subprocess.Popen = TrackedPopen
        if not os.environ.get("HYIMG_CACHE_ROOT") or _real_cache(os.environ["HYIMG_CACHE_ROOT"]):
            os.environ["HYIMG_CACHE_ROOT"] = CACHE
        _START = snapshot()
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


def snapshot(root=None):
    """the person's cache: the names right in it, and the size of each performance log"""
    root = root or REAL
    try:
        top = set(os.listdir(root))
    except OSError:
        top = set()
    perf = {}
    try:
        for name in os.listdir(os.path.join(root, "perf")):
            try:
                perf[name] = os.path.getsize(os.path.join(root, "perf", name))
            except OSError:
                pass
    except OSError:
        pass
    return top, perf


def leaks(start=None, root=None):
    """what appeared in the person's cache since `start` that a test made: a throwaway board's folder (lowercase UUID, or a board this
    session started), a performance log entry of such a board. One line each, the board's library named when its list tells it"""
    root = root or REAL
    top0, perf0 = start or _START or snapshot(root)
    top1, perf1 = snapshot(root)
    out, boards = [], IDS - {n.lower() for n in top0}   # a board that had its folder before is the person's
    for name in sorted(top1 - top0):
        if THROWAWAY.fullmatch(name) or name.lower() in IDS:
            boards.add(name.lower())
            try:
                lib = json.load(open(os.path.join(root, name, "library.json"), encoding="utf-8")).get("root", "")
            except (OSError, ValueError, AttributeError):
                lib = ""
            out.append(os.path.join(root, name) + (f"  (library {lib})" if lib else ""))
    for name, size in sorted(perf1.items()):
        if size <= perf0.get(name, 0):
            continue
        try:
            with open(os.path.join(root, "perf", name), "rb") as f:
                f.seek(perf0.get(name, 0)); new = f.read().decode("utf-8", "replace").splitlines()
        except OSError:
            continue
        for line in new:
            try:
                board = str(json.loads(line).get("board", "")).lower()
            except (ValueError, AttributeError):
                continue
            if board and board in boards:
                out.append(f"{os.path.join(root, 'perf', name)}: an entry of the test board {board}")
    return out


def finish(session):
    """from pytest_sessionfinish, once a session however many conftests call it: ends the servers left running, then fails the run if
    anything of a test landed in the person's cache"""
    global _DONE
    if _DONE:
        return
    _DONE = True
    left = sweep()
    if left:
        print(f"\nprocguard: stopped {len(left)} server(s) a test left running: {left}")
    found = leaks()
    if found:
        print(f"\nprocguard: tests wrote into the person's cache {REAL} (nothing was removed there):\n  " + "\n  ".join(found))
        session.exitstatus = 1
