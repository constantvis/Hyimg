"""How long a board's server lives (owner 2026-10-07, after 17 forgotten servers of tests and agents had run up to 30 hours: «нужно за
этим тоже следить, чтобы не было этой бесконечной херни, которая запускается»).

- The app's server (HYIMG_PARENT_PID, the app's pid, which must be the server's parent) lives as long as the app: it ends within half
  a second of the app ending, and never for being idle.
- Any other server (a test's, an agent's, one started by hand) ends when the process that started it ends (its parent changes: the
  system adopted it), checked every 2 s, and after HYIMG_IDLE_EXIT seconds without a request (default 1200, 20 minutes; 0: never).
  An open page asks /api/changes every 2 s, so a server someone is looking at is never idle.
The end kills the programs the server started (helpers.py), then os._exit(0): the listeners close and the writer lease of the
state folder is released with the process.
"""
import os
import threading
import time

import helpers

IDLE_DEFAULT = 20 * 60
_LAST = [time.monotonic()]


def stamp():
    _LAST[0] = time.monotonic()


def idle_seconds():
    return time.monotonic() - _LAST[0]


def app_parent():
    """the app's pid when the app started this server, else None; a wrong HYIMG_PARENT_PID stops the start"""
    setting = os.environ.get("HYIMG_PARENT_PID")
    if setting is None:
        return None
    try:
        pid = int(setting)
    except ValueError as exc:
        raise SystemExit("HYIMG_PARENT_PID must be an integer greater than one") from exc
    if pid <= 1 or pid != os.getppid():
        raise SystemExit("HYIMG_PARENT_PID must identify the launching parent process")
    return pid


def idle_limit():
    try:
        return max(0.0, float(os.environ.get("HYIMG_IDLE_EXIT", IDLE_DEFAULT)))
    except ValueError:
        return float(IDLE_DEFAULT)


def _end(why):
    helpers.kill_all()   # its qlmanage, ffmpeg, Blender... with their children (helpers.py)
    print(f"Hyimg server ends: {why}", flush=True)
    os._exit(0)


def watch(parent, idle, every):
    """ends the process when its parent is gone or it has been idle too long"""
    while True:
        if os.getppid() != parent:
            _end("the process that started it is gone")
        if parent > 1:
            try:
                os.kill(parent, 0)
            except ProcessLookupError:
                _end("the process that started it is gone")
            except PermissionError:
                pass
        if idle and idle_seconds() > idle:
            _end(f"no request for {int(idle)} s")
        time.sleep(every)


def start(handler):
    """counts every request of the handler class and starts the watch; returns {"app", "parent", "idle"}"""
    app = app_parent()
    helpers.install()   # every program it starts: its own group, a hard limit, killed when the server ends
    parent, idle = (app, 0.0) if app else (os.getppid(), idle_limit())
    if not getattr(handler, "_hy_stamped", False):
        before = handler.handle_one_request

        def handle_one_request(self):
            stamp()
            return before(self)
        handler.handle_one_request = handle_one_request
        handler._hy_stamped = True
    stamp()
    threading.Thread(target=watch, args=(parent, idle, 0.5 if app else 2.0), daemon=True, name="hyimg-lifetime").start()
    return {"app": bool(app), "parent": parent, "idle": idle}
