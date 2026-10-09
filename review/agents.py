"""Which agent made a write (owner 2026-10-07: «Продумать, как участники будут устроены, чтобы Claude или Codex не наплодили 2000
участников», and «желательно, чтобы это работало без отдельного участия агентов, а то агент что-то забудет и не впишет»).

An agent is never a participant of its own. It is always «<kind> of <person>»: the person is this Mac's profile (people.py), the kind
comes from a small fixed catalog. Whatever name arrives (the header X-Hyimg-Agent, HYIMG_AGENT, ?agent=, an old event's free text) is
folded into the catalog before anything is stored, so a thousand sessions, model versions and spellings stay six kinds at most.

The server finds the kind by itself (detect): for a write that comes over loopback it looks up the client process by the connection's
port (netstat -anv names the process of every socket on macOS), walks its parents up to launchd and names the first ancestor that is a
known agent (claude, codex, agy, kimi, opencode, by executable, its path and its first arguments). Ancestors the server shares with the
client do not count: a test server started by an agent, with its browser started by the same agent, is not that agent's work. The
lookup runs in a thread started when the request comes in; the stamp waits for it WAIT seconds at most and falls back to the header.
"""
import ctypes
import ctypes.util
import os
import re
import subprocess
import sys
import threading
import time

CATALOG = ("claude", "codex", "gemini", "kimi", "opencode", "agent")
LABEL = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "kimi": "Kimi", "opencode": "OpenCode", "agent": "Agent"}
# case-insensitive aliases, first match wins; ui/avatar.js holds the same table (tests/unit/test_agents.py compares them)
ALIASES = (
    ("opencode", r"open[\s_-]?code"),
    ("claude", r"claude|anthropic|\bopus|\bsonnet|\bhaiku"),
    ("codex", r"codex|openai|chatgpt|\bgpt|\bo[134](\b|-)"),
    ("gemini", r"gemini|antigravity|\bagy\b|\bbard\b|google"),
    ("kimi", r"kimi|moonshot"),
)
_ALIAS = [(k, re.compile(p, re.I)) for k, p in ALIASES]
APP = ("", "app", "owner", "human", "person", "you")
WAIT = 0.15   # seconds a stamp waits for the lookup at most (measured on an M1: netstat 8-15 ms, the parents well under 1 ms)
# the writes that are stamped start the lookup as they come in; the frequent ones that are not (/api/live on every camera move, /api/stat,
# a plugin's hold) never run it; a stamp on a path not listed starts it itself and only waits a little longer
EAGER = ("/api/board", "/api/history", "/api/notifications", "/api/snapshot", "/api/file", "/api/propsclip", "/api/presets", "/api/plugin/",
         "/api/comments", "/api/annotations", "/api/profile")


def kind(v):
    """the catalog kind of any agent name; "" for none or the app itself, "agent" for an agent the catalog does not know"""
    s = " ".join(str(v or "").split()).lower()[:120]
    if s in APP: return ""
    if s in CATALOG: return s
    return next((k for k, rx in _ALIAS if rx.search(s)), "agent")


def label(k):
    return LABEL.get(kind(k) or "", "")


# ---- the process tree (macOS: libproc and sysctl through ctypes, no process started) ---------------------------------------------
class _BSDInfo(ctypes.Structure):   # struct proc_bsdinfo, <sys/proc_info.h>
    _fields_ = [("pbi_flags", ctypes.c_uint32), ("pbi_status", ctypes.c_uint32), ("pbi_xstatus", ctypes.c_uint32), ("pbi_pid", ctypes.c_uint32),
                ("pbi_ppid", ctypes.c_uint32), ("pbi_uid", ctypes.c_uint32), ("pbi_gid", ctypes.c_uint32), ("pbi_ruid", ctypes.c_uint32),
                ("pbi_rgid", ctypes.c_uint32), ("pbi_svuid", ctypes.c_uint32), ("pbi_svgid", ctypes.c_uint32), ("rfu_1", ctypes.c_uint32),
                ("pbi_comm", ctypes.c_char * 16), ("pbi_name", ctypes.c_char * 32), ("pbi_nfiles", ctypes.c_uint32), ("pbi_pgid", ctypes.c_uint32),
                ("pbi_pjobc", ctypes.c_uint32), ("e_tdev", ctypes.c_uint32), ("e_tpgid", ctypes.c_uint32), ("pbi_nice", ctypes.c_int32),
                ("pbi_start_tvsec", ctypes.c_uint64), ("pbi_start_tvusec", ctypes.c_uint64)]


_LIB = None


def _lib():
    global _LIB
    if _LIB is None:
        try: _LIB = ctypes.CDLL("/usr/lib/libproc.dylib") if sys.platform == "darwin" else False
        except OSError: _LIB = False
    return _LIB


def proc(pid):
    """{ppid, start, names: [executable, path, comm, argv0, argv1]} of a process, None when it is gone or not readable"""
    lib = _lib()
    if not lib or pid <= 0: return None
    info = _BSDInfo()
    if lib.proc_pidinfo(ctypes.c_int(pid), 3, ctypes.c_uint64(0), ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info): return None
    buf = ctypes.create_string_buffer(4096)
    path = buf.value.decode(errors="replace") if lib.proc_pidpath(ctypes.c_int(pid), buf, 4096) > 0 else ""
    names = [path, info.pbi_name.decode(errors="replace"), info.pbi_comm.decode(errors="replace")] + _argv(pid)[:2]
    return {"ppid": info.pbi_ppid, "start": info.pbi_start_tvsec, "names": [n for n in names if n]}


def _argv(pid):
    """the first arguments of a process (sysctl KERN_PROCARGS2): a script run by node or sh is named by them"""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        mib, size = (ctypes.c_int * 3)(1, 49, pid), ctypes.c_size_t(0)
        if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0 or not size.value: return []
        buf = ctypes.create_string_buffer(size.value)
        if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0: return []
        raw = buf.raw[:size.value]
        argc = int.from_bytes(raw[:4], "little")
        parts = [p for p in raw[4:].split(b"\0") if p]   # the executable's path, then argv
        return [p.decode(errors="replace") for p in parts[1:1 + min(argc, 3)]]
    except (OSError, ValueError, AttributeError):
        return []


def of_names(names):
    """the agent kind a process's names point at, "" for none"""
    for n in names:
        low = n.lower()
        base = os.path.basename(low.rstrip("/")) or low
        base = re.sub(r"\.(app|js|mjs|cjs|py|exe)$", "", base)
        if base in ("claude", "codex", "agy", "antigravity", "gemini", "kimi", "opencode"): return kind(base)
        if re.match(r"(claude|codex|antigravity|gemini|kimi|opencode)\b", base): return kind(base)
        if "/claude-code/" in low or "/claude.app/" in low or "/codex-cli/" in low or "/chatgpt.app/" in low or "/antigravity.app/" in low: return kind(low)
    return ""


_KIND = {}   # (pid, start) -> kind of that process alone


def _own(pid):
    p = proc(pid)
    if not p: return None, ""
    k = (pid, p["start"])
    if k not in _KIND:
        if len(_KIND) > 4000: _KIND.clear()
        _KIND[k] = of_names(p["names"])
    return p, _KIND[k]


_SERVER = None


def server_chain():
    """this server's own ancestors: they are not the client's agent (a test server and its browser started by the same agent)"""
    global _SERVER
    if _SERVER is None:
        out, pid = set(), os.getpid()
        while pid > 1 and pid not in out:
            out.add(pid)
            p = proc(pid)
            if not p: break
            pid = p["ppid"]
        _SERVER = out
    return _SERVER


def of_pid(pid):
    """the agent kind of a client process: the nearest ancestor that is an agent and not one of the server's; "" for none"""
    seen, mine = set(), server_chain()
    while pid > 1 and pid not in seen and pid not in mine and len(seen) < 64:
        seen.add(pid)
        p, k = _own(pid)
        if p is None: return ""
        if k: return k
        pid = p["ppid"]
    return ""


# ---- the client of a connection ------------------------------------------------------------------------------------------------
_NET = re.compile(r"^tcp\S*\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+ESTABLISHED\s+\d+\s+\d+\s+\d+\s+\d+\s+.*?:(\d+)\s+[0-9a-f]{5}\s")
_SNAP = {"t": 0.0, "map": {}}
_NETLOCK = threading.Lock()


def _port(addr):
    m = re.search(r"[.:](\d+)$", addr)
    return int(m.group(1)) if m else -1


def _table():
    out = subprocess.run(["netstat", "-anv", "-p", "tcp"], capture_output=True, timeout=2).stdout.decode("utf-8", "replace")
    found = {}
    for line in out.splitlines():
        m = _NET.match(line)
        if m: found[(_port(m.group(1)), _port(m.group(2)))] = int(m.group(3))
    return found


def peer_pid(peer_port, server_port, since):
    """the process holding the client end of a loopback connection: a table read after the connection came in serves every lookup"""
    with _NETLOCK:
        if _SNAP["t"] < since:
            t = time.time()
            _SNAP.update(map=_table(), t=t)
        return _SNAP["map"].get((peer_port, server_port))


def _lookup(handler, since):
    try:
        host, port = handler.client_address[:2]
        if host not in ("127.0.0.1", "::1", "::ffff:127.0.0.1") or sys.platform != "darwin": return None
        pid = peer_pid(int(port), int(handler.server.server_address[1]), since)
        return None if pid is None else of_pid(pid)
    except (OSError, ValueError, AttributeError, IndexError, subprocess.SubprocessError):
        return None


def start(handler, eager=True):
    """begin the lookup as the request comes in (do_POST), so it runs while the body is read and handled; only for writes that are stamped"""
    if getattr(handler, "_hy_agent", None) is not None or os.environ.get("HYIMG_DETECT") == "0": return
    if eager and not str(getattr(handler, "path", "")).startswith(EAGER): return
    box = {"done": threading.Event(), "kind": None}
    since = time.time() - 0.001

    def run():
        try: box["kind"] = _lookup(handler, since)
        finally: box["done"].set()
    handler._hy_agent = box
    threading.Thread(target=run, daemon=True, name="hyimg-agent").start()


def detect(handler, wait=WAIT):
    """the kind of agent behind a request: a catalog kind, "" for a person's own app or browser, None when it cannot tell"""
    if os.environ.get("HYIMG_DETECT") == "0": return None
    start(handler, eager=False)
    box = getattr(handler, "_hy_agent", None)
    if not box or not box["done"].wait(wait): return None
    return box["kind"]


if __name__ == "__main__":   # python3 agents.py PID | NAME: the kind of a process (its parents) or of a name
    for a in sys.argv[1:]:
        print(a, "->", (of_pid(int(a)) if a.isdigit() else kind(a)) or "(app)")
