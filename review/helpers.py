"""The programs a board's server starts (qlmanage, ffmpeg, ffprobe, sips, osascript, pdftoppm, mdls, FreeCAD, Blender, Chromium for
HTML stills) never outlive it and never run without a limit (owner 2026-10-07: about 400 qlmanage of test runs hung on fake PSDs, up
to 27 h, adopted by the system when their server ended).

install(), called once by lifetime.start() in the server's main thread:
- every process started through subprocess.Popen in the server (subprocess.run uses it too, and so do the plugins' modules, which run
  inside the server) starts in a process group of its own, unless the caller chose its group itself, and is remembered;
- subprocess.run gets a hard limit: the caller's timeout, else 900 s, never more than HYIMG_HELPER_TIMEOUT when that is set (the
  tests make it short); on the limit the whole group is killed, so a helper's own children go too;
- when the server ends (lifetime's end, SIGTERM, ⌃C, a normal exit) every remembered group still running is killed.
A server killed outright (SIGKILL) cannot do this: its helpers then show in Settings › Storage as lost processes (procs.py).
"""
import atexit
import os
import signal
import subprocess
import threading

DEFAULT_LIMIT = 900
_BASE_POPEN = subprocess.Popen
_BASE_RUN = subprocess.run
_LIVE = set()
_LOCK = threading.Lock()


def limit(timeout):
    """the limit for one run: the caller's, else DEFAULT_LIMIT, capped by HYIMG_HELPER_TIMEOUT"""
    t = DEFAULT_LIMIT if timeout is None else timeout
    try:
        cap = float(os.environ.get("HYIMG_HELPER_TIMEOUT") or 0)
    except ValueError:
        cap = 0
    return min(t, cap) if cap > 0 else t


def kill_group(p):
    """the process and everything in its group, at once"""
    try:
        if getattr(p, "_hy_group", False):
            os.killpg(p.pid, signal.SIGKILL)
        else:
            p.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass


class Popen(_BASE_POPEN):
    """subprocess.Popen in a group of its own, remembered until it ends"""
    def __init__(self, *a, **kw):
        own = not kw.get("start_new_session") and kw.get("process_group") is None and kw.get("preexec_fn") is None
        if own:
            kw["start_new_session"] = True
        super().__init__(*a, **kw)
        self._hy_group = own or bool(kw.get("start_new_session"))
        with _LOCK:
            _LIVE.add(self)

    def _hy_done(self):
        with _LOCK:
            _LIVE.discard(self)

    def wait(self, timeout=None):
        r = super().wait(timeout)
        self._hy_done()
        return r

    def poll(self):
        r = super().poll()
        if r is not None:
            self._hy_done()
        return r


def run(*popenargs, input=None, capture_output=False, timeout=None, check=False, **kw):
    """subprocess.run with a hard limit that kills the helper's whole group"""
    if input is not None:
        kw["stdin"] = subprocess.PIPE
    if capture_output:
        kw["stdout"] = subprocess.PIPE; kw["stderr"] = subprocess.PIPE
    with Popen(*popenargs, **kw) as p:
        try:
            out, err = p.communicate(input, timeout=limit(timeout))
        except subprocess.TimeoutExpired as ex:
            kill_group(p)
            out, err = p.communicate()
            raise subprocess.TimeoutExpired(p.args, ex.timeout, output=out, stderr=err) from None
        except BaseException:
            kill_group(p)
            raise
        code = p.poll()
    if check and code:
        raise subprocess.CalledProcessError(code, p.args, output=out, stderr=err)
    return subprocess.CompletedProcess(p.args, code, out, err)


def live():
    with _LOCK:
        return [p for p in _LIVE if p.returncode is None]


def kill_all():
    """every helper still running, with its group; returns their pids"""
    left = live()
    for p in left:
        kill_group(p)
    return [p.pid for p in left]


def _on_term(signum, _frame):
    kill_all()
    os._exit(0 if signum == signal.SIGTERM else 128 + signum)


def install():
    """from the server's main thread, once"""
    if subprocess.Popen is Popen:
        return
    subprocess.Popen = Popen
    subprocess.run = run
    atexit.register(kill_all)
    try:
        signal.signal(signal.SIGTERM, _on_term)
        signal.signal(signal.SIGHUP, _on_term)
    except ValueError:   # not the main thread: atexit and lifetime's end still do it
        pass
