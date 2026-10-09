"""The performance log (owner 2026-10-08, a 14 s screen recording of the «UI» board: zooming lags and parts of the board go blank; «нужен
механизм дебага: лог, который пишется, только когда падает частота кадров, с тем, что было на экране»). Off by default: Settings ›
Diagnostics › Performance log (the app's setting cv.perflog, "1" on). The board (ui/perflog.js) watches its frames while the person pans,
zooms or drags, and when frames drop (3 frames over 50 ms within a second, or one over 250 ms) it sends one entry: the time, the board and
its page, the action, the zoom, the rendering mode, the engine, what was on screen (objects by kind, the visible ones, live pages, comment
pins, note dots, groups), the panels open, the JS heap and the worst frames.

Where it goes: the app's cache, ~/Library/Caches/Hyimg/perf/perf-<date>[-n].jsonl (HYIMG_CACHE_ROOT moves it), one JSON object a line,
never in Dropbox. Limits, so it never grows to gigabytes: an entry at most every 5 s per board's page (the page holds back too), an entry
at most 16 KB, a file at most 2 MB, all files at most 20 MB together (the oldest go first). Settings › Storage shows its size with «Clear».

  GET  /api/perflog?last=N       {"on", "bytes", "files", "entries": the newest N, newest last}
  POST /api/perflog              an entry from the board: written when the log is on, else {"skipped": "off"}
  POST /api/perflog/clear        every file of the log goes: {"freed", "removed"}
  python3 perflog.py [--last N]  the worst episodes and what was on screen (hy.py perf does the same through the server)
  python3 perflog.py clear       the same as POST /api/perflog/clear, its JSON printed: Home's «Clear» through the app (native/StorageBridge.swift)"""
import fcntl, json, os, re, sys, threading, time

CAP = 20 * 1024 * 1024      # all files together
FILE_MAX = 2 * 1024 * 1024  # one file, then the next one of the day
ENTRY_MAX = 16 * 1024       # one entry
GAP = 5.0                   # seconds between two entries of one page
NAME = re.compile(r"^perf-\d{4}-\d{2}-\d{2}(-\d+)?\.jsonl$")
_LAST, _LOCK = {}, threading.Lock()


def folder():
    root = os.environ.get("HYIMG_CACHE_ROOT") or os.path.expanduser("~/Library/Caches/Hyimg")
    return os.path.join(os.path.realpath(root), "perf")


def in_dropbox(path):
    home, p = os.path.expanduser("~"), os.path.realpath(path)
    return any(p == d or p.startswith(d + os.sep) for d in (os.path.join(home, "Dropbox"), os.path.join(home, "Library/CloudStorage")))


def files(d=None):
    """the log's files, oldest first (by name: the date, then the number of the day's file)"""
    d = d or folder()
    try: names = [n for n in os.listdir(d) if NAME.match(n)]
    except OSError: return []
    key = lambda n: (n[5:15], int(n[16:-6]) if n[15] == "-" else 1)
    return [os.path.join(d, n) for n in sorted(names, key=key)]


def size():
    fs = files(); total = 0
    for f in fs:
        try: total += os.path.getsize(f)
        except OSError: pass
    return {"bytes": total, "files": len(fs)}


def enabled(settings):
    return str((settings or {}).get("cv.perflog") or "") != "0"   # on until turned off (owner 2026-10-08)


def _target(d, day, add):
    """the file of the day the next line goes to: the day's last one while it has room, else a new one"""
    mine = [f for f in files(d) if os.path.basename(f).startswith(f"perf-{day}")]
    if mine and os.path.getsize(mine[-1]) + add <= FILE_MAX: return mine[-1]
    last = os.path.basename(mine[-1]) if mine else ""
    k = (int(last[16:-6]) if last[15:16] == "-" else 1) + 1 if mine else 1   # after the day's last one, also when older ones went
    return os.path.join(d, f"perf-{day}.jsonl" if k == 1 else f"perf-{day}-{k}.jsonl")


def _trim(d):
    """the oldest files go until all of them fit under CAP"""
    fs = files(d); sizes = []
    for f in fs:
        try: sizes.append(os.path.getsize(f))
        except OSError: sizes.append(0)
    total, removed = sum(sizes), []
    for f, s in zip(fs, sizes):
        if total <= CAP: break
        try: os.remove(f); total -= s; removed.append(os.path.basename(f))
        except OSError: pass
    return removed


def append(entry, settings, now=None, key=None):
    """one entry into the log; {"ok": file} or {"skipped": why}: off, rate (another one of this page under GAP s ago), big, bad, dropbox"""
    if not enabled(settings): return {"skipped": "off"}
    if not isinstance(entry, dict): return {"skipped": "bad"}
    now = time.time() if now is None else now
    key = key or f"{entry.get('board', '')}|{entry.get('page', '')}"
    with _LOCK:
        if now - _LAST.get(key, -1e9) < GAP: return {"skipped": "rate"}
        _LAST[key] = now
    entry = {**entry, "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))}
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(line.encode()) > ENTRY_MAX: return {"skipped": "big"}
    d = folder()
    if in_dropbox(d): return {"skipped": "dropbox"}
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ".lock"), "w") as lk:   # one writer at a time across the boards' servers
        fcntl.flock(lk, fcntl.LOCK_EX)
        f = _target(d, time.strftime("%Y-%m-%d", time.localtime(now)), len(line) + 1)
        with open(f, "a", encoding="utf-8") as out: out.write(line + "\n")
        _trim(d)
    return {"ok": os.path.basename(f)}


def clear():
    """every file of the log goes; under the folder's lock too, as the app clears from its own process while boards may be writing"""
    d = folder(); freed, removed = 0, 0
    with _LOCK:
        try: lk = open(os.path.join(d, ".lock"), "w") if os.path.isdir(d) else None
        except OSError: lk = None   # a folder it cannot write in: the files go without the lock
        try:
            if lk: fcntl.flock(lk, fcntl.LOCK_EX)
            for f in files(d):
                try: s = os.path.getsize(f); os.remove(f); freed += s; removed += 1
                except OSError: pass
        finally:
            if lk: lk.close()
        _LAST.clear()
    return {"freed": freed, "removed": removed}


def read(last=20):
    """the newest `last` entries, oldest of them first"""
    out = []
    for f in reversed(files()):
        try: lines = open(f, encoding="utf-8").read().splitlines()
        except OSError: continue
        for ln in reversed(lines):
            try: out.append(json.loads(ln))
            except ValueError: continue
            if len(out) >= last: return out[::-1]
    return out[::-1]


def _worst(e):
    w = ((e.get("frames") or {}).get("worst") or [0])
    return max(w) if w else 0


def summary(entries, n=5):
    """lines for an agent: how many episodes, the worst ones with what was on screen, what they share"""
    if not entries: return ["Лог производительности пуст (Настройки › Диагностика › Журнал производительности, затем подвигать доску)."]
    L = [f"Эпизодов: {len(entries)}, с {entries[0].get('at', '?')} по {entries[-1].get('at', '?')}"]
    by = {}
    for e in entries: by[e.get("action") or "?"] = by.get(e.get("action") or "?", 0) + 1
    L.append("По действию: " + ", ".join(f"{k} {v}" for k, v in sorted(by.items(), key=lambda kv: -kv[1])))
    L.append(f"Худшие {min(n, len(entries))}:")
    for e in sorted(entries, key=_worst, reverse=True)[:n]:
        fr, c, p = e.get("frames") or {}, e.get("counts") or {}, e.get("panels") or {}
        vis = c.get("visible") or {}
        panels = ", ".join(k if v is True else f"{k} {v}" for k, v in p.items() if v and k != "bellRows") or "нет"
        L.append(f"- {e.get('at', '?')} «{e.get('pageTitle') or e.get('page')}» {e.get('action')}, зум {e.get('zoom')}, "
                 f"отрисовка {(e.get('lod') or {}).get('mode')}{' (издали)' if (e.get('lod') or {}).get('far') else ''}, {e.get('engine')}")
        L.append(f"  кадры: {fr.get('n')} всего, {fr.get('slow')} больше 50 мс, медиана {fr.get('median')} мс, худшие {fr.get('worst')}")
        L.append(f"  на экране: {', '.join(f'{k} {v}' for k, v in vis.items()) or '?'}; живых страниц {c.get('liveFrames')}, iframe {c.get('iframes')}, "
                 f"пинов {c.get('pins')}, точек заметок {c.get('dots')}, групп {c.get('groups')}, картинок {c.get('imgs')} ({c.get('decodedMB')} МБ)")
        rows = f" (строк в колокольчике {p.get('bellRows')})" if p.get("bell") else ""
        L.append(f"  панели: {panels}{rows}; "
                 f"память JS {e.get('heapMB')} МБ, узлов {c.get('nodes')}, пропущено эпизодов {e.get('dropped', 0)}")
    return L


def cli(argv, api=None):
    """hy.py perf [--last N]: through the board's server when there is one, else the files on this Mac"""
    n = int(argv[argv.index("--last") + 1]) if "--last" in argv and argv.index("--last") + 1 < len(argv) else 50
    entries, on = None, None
    if api:
        try:
            code, d = api(f"/api/perflog?last={n}")
            if code == 200 and isinstance(d, dict): entries, on = d.get("entries"), d.get("on")
        except Exception: entries = None
    if entries is None: entries = read(n)
    if on is False: print("Журнал выключен: Настройки › Диагностика › Журнал производительности.")
    print("\n".join(summary(entries)))


def http(handler, method, settings):
    """GET /api/perflog, POST /api/perflog and /api/perflog/clear for server.py (it only passes the request on)"""
    path, _, qs = handler.path.partition("?")
    send = lambda code, body: handler.send(code, json.dumps(body, ensure_ascii=False).encode(), "application/json")
    if method == "GET" and path == "/api/perflog":
        m = re.search(r"(?:^|&)last=(\d+)", qs); last = min(500, int(m.group(1))) if m else 20
        return send(200, {"on": enabled(settings()), **size(), "entries": read(last)})
    if method == "POST" and path == "/api/perflog/clear": return send(200, clear())
    if method == "POST" and path == "/api/perflog":
        n = int(handler.headers.get("Content-Length", 0) or 0)
        if n > ENTRY_MAX: handler.rfile.read(n); return send(200, {"skipped": "big"})
        try: entry = json.loads(handler.rfile.read(n) or b"{}")
        except ValueError: return send(400, {"error": "bad json"})
        return send(200, append(entry, settings()))
    return handler.send(404, b"not found", "text/plain")


def main(argv):
    """python3 perflog.py clear: the JSON of POST /api/perflog/clear on stdout; anything else is the summary (cli)"""
    if argv[:1] == ["clear"]: print(json.dumps(clear(), ensure_ascii=False)); return
    cli(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
