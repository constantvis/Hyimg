"""Lost processes of Hyimg (owner 2026-10-07: «нужно за этим тоже следить, чтобы не было этой бесконечной херни, которая
запускается»): board servers (review/server.py), Blender bridges (bridge_server.py) and the programs a server starts (qlmanage,
ffmpeg...) whose parent is gone, so the system adopted them (parent 1).
The app's own servers have the app as their parent and are never listed. Since lifetime.py a server ends with its parent, so a lost one
is from before that or a server of another copy of the code; Settings › Storage lists them with their memory and stops one when asked.

stop(pid) looks again right before it acts: the pid must still be a lost process of ours (its command line, its parent 1), it gets
SIGTERM, and SIGKILL after 3 s only if it is still that same process. Nothing else is ever signalled.
"""
import ctypes
import os
import re
import signal
import subprocess
import time

SERVER_RE = re.compile(r"(?:^|\s)(\S*/)?review/server\.py(?:\s+(\d+))?(?:\s|$)")
# the programs a server starts (helpers.py), known by their program and by a path of ours in their command line
HELPER_EXES = {"qlmanage", "ffmpeg", "ffprobe", "sips", "osascript", "pdftoppm", "pdfinfo", "mdls", "freecadcmd", "freecad"}
HELPER_MARKS = ("/_thumbs/", "/Caches/Hyimg/", "hyimg-test-cache-", "/.stills/", "/_review/", "cad_freecad.py", "render_html.py")
BRIDGE_RE = re.compile(r"\s-P\s+(\S*/)?blender/bridge_server\.py(?:\s|$)")
try:
    _LIBPROC = ctypes.CDLL("/usr/lib/libproc.dylib")
except OSError:
    _LIBPROC = None


def footprint(pid):
    """physical footprint in bytes (Activity Monitor's Memory; proc_pid_rusage RUSAGE_INFO_V4 ri_phys_footprint), None if unknown"""
    if _LIBPROC is None:
        return None
    buf = ctypes.create_string_buffer(512)
    if _LIBPROC.proc_pid_rusage(ctypes.c_int(pid), ctypes.c_int(4), buf) != 0:
        return None
    return int.from_bytes(buf.raw[72:80], "little")


def _seconds(etime):
    """ps etime [[dd-]hh:]mm:ss -> seconds"""
    days, _, rest = etime.rpartition("-")
    parts = [int(p) for p in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return (int(days) if days else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def kind_of(command):
    """("server", port) for Python running a review/server.py, ("blender", "") for Blender running our bridge, ("helper", program)
    for a program a server starts working on our files (qlmanage on a thumbnail folder...), else None"""
    m = SERVER_RE.search(command)
    if m and "python" in os.path.basename(command[:m.start()].strip().split(" ")[0]).lower():
        return "server", m.group(2) or ""
    b = BRIDGE_RE.search(command)
    if b and "blender" in command[:b.start()].lower():
        return "blender", ""
    exe = os.path.basename(command.split(" -", 1)[0].strip().split(" ")[0]).lower()
    if (exe in HELPER_EXES or "python" in exe or exe.startswith("freecad")) and any(m in command for m in HELPER_MARKS):
        return "helper", exe if "python" not in exe else "render_html"
    return None


def _ps():
    out = subprocess.run(["ps", "-axww", "-o", "pid=,ppid=,etime=,command="], capture_output=True, text=True, timeout=5).stdout
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)", line)
        if m:
            yield int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)


def lost():
    """[{pid, kind, port, code, age, bytes, command}] of our processes whose parent is gone, the biggest first"""
    out = []
    for pid, ppid, etime, command in _ps():
        k = kind_of(command)
        if not k or ppid != 1 or pid == os.getpid():
            continue
        m = SERVER_RE.search(command) if k[0] == "server" else BRIDGE_RE.search(command) if k[0] == "blender" else None
        code = (m.group(1) or "").rstrip("/") if m else ""
        try:
            age = _seconds(etime)
        except ValueError:
            age = 0
        out.append({"pid": pid, "kind": k[0], "port": k[1], "code": code.replace(os.path.expanduser("~"), "~"), "age": age,
                    "bytes": footprint(pid) or 0, "command": command[:300]})
    return sorted(out, key=lambda p: -p["bytes"])


def _still_lost(pid):
    return next((p for p in lost() if p["pid"] == pid), None)


def stop(pid, wait=3.0):
    """{"stopped": pid, "freed": bytes} or {"error"}: only a process that is still one of ours and lost"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"error": "not a process id"}
    p = _still_lost(pid)
    if not p:
        return {"error": "not a lost Hyimg process"}
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"stopped": pid, "freed": p["bytes"]}
    end = time.time() + wait
    while time.time() < end:
        if not _alive(pid):
            return {"stopped": pid, "freed": p["bytes"]}
        time.sleep(0.1)
    if _still_lost(pid):   # the same process, still there: it did not take SIGTERM
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return {"stopped": pid, "freed": p["bytes"]} if not _alive(pid, 1.0) else {"error": "the process did not end"}


def _alive(pid, grace=0.0):
    end = time.time() + grace
    while True:
        try:
            os.kill(pid, 0)
            # a zombie of a child of ours counts as gone
            st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
            if st.startswith("Z") or not st:
                return False
        except ProcessLookupError:
            return False
        if time.time() >= end:
            return True
        time.sleep(0.1)
