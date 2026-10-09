"""Where Hyimg's disk goes (owner 2026-10-07: «мне гораздо важнее, чтобы было свободнее на диске»; «надежно: никогда случайно не
удалять файлы»). The measurements and the plan: docs/storage-plan.md.

The scan only reads: stat of every file, and the sha1 of the files that share a byte size with another (duplicates). A file Dropbox
keeps only in the cloud (dataless) is never read, so a scan never downloads anything. What the scan writes is its own: the summary
and a cache of the hashes it read (storage.json and storage-hashes.json beside the catalog of boards, ~/Library/Application
Support/Hyimg), outside Dropbox. One scan runs at a time (a lock), in its own process at low priority, so no page ever waits for it.

Two things delete, each only on the person's request and each guarded (storage_clean.py):
- clear_cache(): what Hyimg makes again by itself, inside the app's cache folder only.
- trash_backups(keep): the app's old copies Hyimg.backup.*.app beyond the newest `keep`, into the macOS Trash, never rm.

  python3 storage.py summary [--max-age 300]   the last summary as JSON; a scan starts behind it when it is older
  python3 storage.py scan                      scan now, write the summary
  python3 storage.py clear-cache [--dry-run]   {"freed", "removed", "paths"}
  python3 storage.py backups --keep 2 [--dry-run]
  python3 storage.py caps [--board 2] [--total 8]  the thumbnail cache's ceiling in GB (thumbcache.py)
  python3 storage.py stop <pid>                a lost server or Blender of Hyimg (procs.py), nothing else
The places come from the environment, so tests never see the person's folders: HYIMG_CACHE_ROOT (~/Library/Caches/Hyimg),
HYIMG_SUPPORT_ROOT (the catalog's folder; else the folder of HYIMG_SETTINGS), HYIMG_INSTALL_DIR (~/Applications), HYIMG_LOGS.
"""
import fcntl, hashlib, heapq, json, os, re, subprocess, sys, time

import procs

HOME = os.path.expanduser("~")
UUID_RE = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
DATALESS = 0x40000000   # SF_DATALESS: the bytes are in the cloud only (Dropbox, iCloud)
MAX_AGE = 300           # a summary older than this starts a new scan when someone asks


def cache_root():
    return os.path.realpath(os.environ.get("HYIMG_CACHE_ROOT") or os.path.join(HOME, "Library/Caches/Hyimg"))


def support_root():
    if os.environ.get("HYIMG_SUPPORT_ROOT"):
        return os.path.realpath(os.environ["HYIMG_SUPPORT_ROOT"])
    if os.environ.get("HYIMG_SETTINGS"):
        return os.path.dirname(os.path.realpath(os.environ["HYIMG_SETTINGS"]))
    return os.path.join(HOME, "Library/Application Support/Hyimg")


def apps_dir():
    return os.environ.get("HYIMG_INSTALL_DIR") or os.path.join(HOME, "Applications")


def summary_path():
    return os.path.join(support_root(), "storage.json")


def hashes_path():   # beside the summary: a test's catalog keeps its own, the person's cache folder never gets a test's files
    return os.path.join(support_root(), "storage-hashes.json")


def catalog():
    """the boards of the catalog, plus the server's own board when it runs on one that is not in it (tests, a page opened by hand)"""
    try:
        boards = [p for p in json.load(open(os.path.join(support_root(), "projects.json"), encoding="utf-8")) if isinstance(p, dict)]
    except (OSError, ValueError):
        boards = []
    out = [{"id": str(p.get("id", "")), "name": str(p.get("name", "")), "lib": os.path.realpath(p["libraryRoot"]),
            "state": os.path.realpath(p.get("stateRoot") or os.path.join(p["libraryRoot"], "_review")),
            "refs": p.get("styleRefs") if isinstance(p.get("styleRefs"), str) else ""} for p in boards if isinstance(p.get("libraryRoot"), str)]
    lib, pid = os.environ.get("HYIMG_LIBRARY_ROOT"), os.environ.get("HYIMG_PROJECT_ID", "")
    if lib and os.path.isabs(lib) and not any(b["id"].upper() == pid.upper() for b in out):
        lib = os.path.realpath(lib)
        out.append({"id": pid, "name": os.path.basename(lib), "lib": lib,
                    "state": os.path.realpath(os.environ.get("HYIMG_STATE_ROOT") or os.path.join(lib, "_review")),
                    "refs": os.environ.get("HYIMG_STYLE_REFS", "")})
    return out


def in_dropbox(path):
    p = os.path.realpath(path)
    return any(p == d or p.startswith(d + os.sep) for d in (os.path.join(HOME, "Dropbox"), os.path.join(HOME, "Library/CloudStorage")))


# What a file is. Precious: the person's files and what the boards remember; regenerable: Hyimg draws it again from the originals;
# consent: it can go, but only when the person says so (copies, old versions, backups of Blender files, logs).
KINDS = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".avif", ".heic", ".heif", ".gif", ".tif", ".tiff", ".bmp", ".jxl"},
    "psd": {".psd", ".psb", ".ai", ".sketch", ".fig", ".afphoto", ".kra", ".xcf", ".eps"},
    "pdf": {".pdf"},
    "video": {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"},
    "model": {".glb", ".gltf", ".obj", ".stl", ".fbx", ".usdz", ".usd", ".step", ".stp", ".iges", ".igs", ".3mf", ".ply", ".c4d", ".3dm", ".f3d"},
    "blend": {".blend"},
    "text": {".json", ".jsonl", ".md", ".txt", ".csv", ".html", ".htm", ".css", ".js", ".py", ".yaml", ".yml", ".svg", ".xml"},
}
EXT_KIND = {e: k for k, es in KINDS.items() for e in es}
CLASS = {   # category -> precious | regenerable | consent
    "image": "precious", "psd": "precious", "pdf": "precious", "video": "precious", "model": "precious", "blend": "precious",
    "text": "precious", "other": "precious", "notes": "precious", "boards": "precious", "history": "precious", "state": "precious",
    "thumbs": "regenerable", "posters": "regenerable", "junk": "regenerable",
    "frames": "precious", "versions3d": "precious", "blendBackups": "consent", "logs": "consent",
}
ORIGINALS = ("image", "psd", "pdf", "video", "model", "blend", "other")


def classify(parts, in_state):
    """the category of a file by its path parts (relative to the board's folder, or to its state folder when in_state)"""
    name = parts[-1]
    if name == ".DS_Store" or "__pycache__" in parts:
        return "junk"
    if in_state:
        if parts[0] == "_thumbs":
            return "thumbs"
        if parts[0] == "boards":
            return "history" if len(parts) > 1 and parts[1] == "_history" else "boards"
        return "state"
    if ".posters" in parts or ".stills" in parts:
        return "posters"
    if ".versions" in parts:
        return "versions3d"
    if parts[0] == "frames" and len(parts) > 2:
        return "frames"
    if parts[0] == "notes":
        return "notes"
    low = name.lower()
    if re.search(r"\.blend\d+$", low):
        return "blendBackups"
    if low.endswith(".log") or (low.startswith("_log-") and low.endswith(".txt")):
        return "logs"
    return EXT_KIND.get(os.path.splitext(low)[1], "other")


def _walk(top, skip=()):
    """(path, lstat) of every file under top, links not followed, the folders in skip left out"""
    stack = [top]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.path not in skip:
                            stack.append(e.path)
                    else:
                        yield e.path, e.stat(follow_symlinks=False)
                except OSError:
                    continue


def dir_size(path):
    """{"bytes", "disk", "files"} of everything under path (a file alone too); disk is what the blocks take"""
    out = {"bytes": 0, "disk": 0, "files": 0}
    try:
        st = os.lstat(path)
    except OSError:
        return out
    items = _walk(path) if os.path.isdir(path) and not os.path.islink(path) else [(path, st)]
    for _p, st in items:
        out["bytes"] += st.st_size; out["disk"] += st.st_blocks * 512; out["files"] += 1
    return out


def _add(acc, key, st):
    a = acc.setdefault(key, {"bytes": 0, "disk": 0, "files": 0})
    a["bytes"] += st.st_size; a["disk"] += st.st_blocks * 512; a["files"] += 1


def _sha(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _thumb_stem(rel, mtime):   # server.py thumb(): a file's thumbnails start with this
    return re.sub(r"[^A-Za-z0-9._-]", "_", rel) + f".{int(mtime)}"


def _mounts(board):
    """outside folders a board shows as collections (config.py _mounts): their thumbnails are not orphans"""
    try:
        rules = json.load(open(os.environ.get("HYIMG_LIBRARY_RULES") or os.path.join(support_root(), "library-rules.json"), encoding="utf-8"))
        rules = {str(k).lower(): v for k, v in rules.items()}
    except (OSError, ValueError, AttributeError):
        rules = {}
    mine = {}
    for part in (rules.get("*"), rules.get(board["id"].lower())):
        if isinstance(part, dict):
            mine.update(part)
    refs, out = board.get("refs") or "", {}
    for m in mine.get("mounts") or []:
        if isinstance(m, dict) and isinstance(m.get("prefix"), str) and isinstance(m.get("path"), str) and m["path"]:
            if os.path.isabs(m["path"]) or refs:
                out[m["prefix"]] = os.path.join(refs, m["path"]) if not os.path.isabs(m["path"]) else m["path"]
    if "mounts" not in mine and refs and os.path.isdir(refs):   # a board with a reference folder and no rules: each folder in it
        out.update({"ext/" + d: os.path.join(refs, d) for d in os.listdir(refs) if os.path.isdir(os.path.join(refs, d))})
    return out


KEEP_HISTORY = 200   # the plan's numbers (docs/storage-plan.md): what would stay, for the estimate only; nothing is deleted here
KEEP_VERSIONS = 20


def scan_board(b, hashes, top, now=None):
    """one board: its folder and its state folder by category, the duplicates among its originals, what its thumbnails hold for files
    that are gone, and the history beyond the plan's keep. hashes: {path: [size, mtime_ns, sha1]} reused and filled in place."""
    t0 = time.time(); lib, state = b["lib"], b["state"]
    cats, kinds, sizes, stems, thumbs = {}, {}, {}, set(), []
    hist = {}; vers = {}; dataless = 0
    state_in_lib = state == lib or state.startswith(lib + os.sep)
    for root in [lib] + ([state] if not state_in_lib else []):
        for path, st in _walk(root):
            in_state = path.startswith(state + os.sep)
            rel = os.path.relpath(path, state if in_state else lib); parts = rel.split(os.sep); cat = classify(parts, in_state)
            _add(cats, cat, st)
            if st.st_flags & DATALESS:
                dataless += 1
            heapq.heappush(top, (st.st_size, path, b["name"], cat)) if len(top) < 30 else heapq.heappushpop(top, (st.st_size, path, b["name"], cat))
            if cat == "thumbs":
                thumbs.append((parts[-1], st))
            elif cat == "history" and len(parts) > 3 and parts[-1].endswith(".json.gz"):
                hist.setdefault(parts[2], []).append((parts[-1], st))
            elif cat == "versions3d":
                vers.setdefault(os.path.dirname(rel), []).append((parts[-1], st))
            if cat in ORIGINALS and not in_state:
                _add(kinds, cat, st)
                stems.add(_thumb_stem(rel.replace(os.sep, "/"), st.st_mtime))
                if st.st_size and not st.st_flags & DATALESS:
                    sizes.setdefault(st.st_size, []).append((path, st))
    for prefix, folder in _mounts(b).items():   # their thumbnails belong to files outside the board
        for path, st in _walk(folder):
            stems.add(_thumb_stem(prefix + "/" + os.path.relpath(path, folder).replace(os.sep, "/"), st.st_mtime))
    # duplicates: identical bytes, found by size first and then by sha1 (the state's sha-index.json first, it is read only)
    try:
        known = json.load(open(os.path.join(state, "sha-index.json"), encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    groups = {}
    for size, files in sizes.items():
        if len(files) < 2:
            continue
        for path, st in files:
            rel = os.path.relpath(path, lib); k = known.get(rel); h = hashes.get(path)
            if isinstance(k, list) and len(k) == 3 and k[:2] == [st.st_size, st.st_mtime_ns]:
                sha = k[2]
            elif isinstance(h, list) and len(h) == 3 and h[:2] == [st.st_size, st.st_mtime_ns]:
                sha = h[2]
            else:
                try:
                    sha = _sha(path)
                except OSError:
                    continue
                hashes[path] = [st.st_size, st.st_mtime_ns, sha]
            groups.setdefault(sha, []).append((path, st))
    same = [g for g in groups.values() if len(g) > 1]
    dups = {"groups": len(same), "extra": sum(len(g) - 1 for g in same), "wasted": sum(g[0][1].st_size * (len(g) - 1) for g in same),
            "top": [{"bytes": g[0][1].st_size, "n": len(g), "paths": sorted(os.path.relpath(p, lib) for p, _ in g)[:4]}
                    for g in sorted(same, key=lambda g: -g[0][1].st_size * (len(g) - 1))[:10]]}
    # thumbnails whose file is gone or changed (server.py keys them by path and mtime): they are never asked for again
    orphan = {"bytes": 0, "disk": 0, "files": 0}
    cache_thumbs = os.path.join(cache_root(), b["id"], "thumbs") if b["id"] else ""   # since 2026-10-07 (thumbcache.py)
    cached = list(_walk(cache_thumbs)) if cache_thumbs and os.path.isdir(cache_thumbs) else []
    in_cache = {"bytes": 0, "disk": 0, "files": 0}
    for _p, st in cached:
        _add({"o": in_cache}, "o", st)
    for name, st in thumbs + [(os.path.basename(p), st) for p, st in cached]:
        dots = [i for i, c in enumerate(name) if c == "."]
        if not any(name[:i] in stems for i in dots):
            _add({"o": orphan}, "o", st)
    keep_h = {"bytes": 0, "disk": 0, "files": 0}
    for _page, snaps in hist.items():   # newest first: beyond the newest KEEP_HISTORY of a page
        for _n, st in sorted(snaps, key=lambda s: s[0], reverse=True)[KEEP_HISTORY:]:
            _add({"o": keep_h}, "o", st)
    keep_v = {"bytes": 0, "disk": 0, "files": 0}
    for _scene, vs in vers.items():
        for _n, st in sorted(vs, key=lambda s: s[1].st_mtime, reverse=True)[KEEP_VERSIONS:]:
            _add({"o": keep_v}, "o", st)
    total = {"bytes": 0, "disk": 0, "files": 0}
    for c in cats.values():
        for k in total:
            total[k] += c[k]
    by_class = {}
    for cat, c in cats.items():
        a = by_class.setdefault(CLASS.get(cat, "precious"), {"bytes": 0, "disk": 0, "files": 0})
        for k in a:
            a[k] += c[k]
    return {"id": b["id"], "name": b["name"], "library": lib, "state": state, "dropbox": in_dropbox(lib),
            "available": os.path.isdir(lib), "total": total, "classes": by_class, "cats": cats, "kinds": kinds, "dups": dups,
            "orphanThumbs": orphan, "cacheThumbs": in_cache, "historyBeyond": keep_h, "historyPages": len(hist), "versionsBeyond": keep_v,
            "dataless": dataless, "seconds": round(time.time() - t0, 2)}


def _cache_part(name, path, ids):
    """what one entry of the cache folder is: (key, regenerable, cleared by «Clear cache»)"""
    if name in ("video", "cad"):
        return name, True, True
    if name == "blender":
        return "blender", True, True
    if name == "Chromium":
        return "engine", True, False   # the engine's own HTTP cache: capped by Chromium itself (native/cef, disk-cache-size)
    if name == "models":
        return "models", False, False   # downloaded once with consent (LaMa)
    if name.startswith("cef_binary_"):
        return "buildTools", False, False
    if name == "storage":
        return "storage", True, False
    if name in ("firefly-profile", "Chrome"):
        return "browserProfiles", False, False   # browsers agents sign in with: a sign-in is not made again by itself
    if UUID_RE.fullmatch(name):
        return ("boardCaches", True, False) if name.upper() in ids else ("stale", True, True)   # a board's list and thumbnails
    return "other", False, False


def scan_global(boards):
    ids = {b["id"].upper() for b in boards}
    root = cache_root(); parts = {}
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for n in names:
        key, regen, clear = _cache_part(n, os.path.join(root, n), ids)
        if key == "engine":   # the profiles of boards that are gone are stale; the others are the engine's cache
            for p in sorted(os.listdir(os.path.join(root, n))) if os.path.isdir(os.path.join(root, n)) else []:
                k = "engine" if not UUID_RE.fullmatch(p) or p.upper() in ids else "stale"
                s = dir_size(os.path.join(root, n, p)); a = parts.setdefault(k, {"bytes": 0, "disk": 0, "files": 0, "regenerable": True, "clear": k == "stale"})
                for x in ("bytes", "disk", "files"):
                    a[x] += s[x]
            continue
        s = dir_size(os.path.join(root, n)); a = parts.setdefault(key, {"bytes": 0, "disk": 0, "files": 0, "regenerable": regen, "clear": clear})
        for x in ("bytes", "disk", "files"):
            a[x] += s[x]
    sup = support_root(); support = {}
    for n in (sorted(os.listdir(sup)) if os.path.isdir(sup) else []):
        s = dir_size(os.path.join(sup, n)); k = n if n in ("Chromium", "Chrome", "props-clipboard-files") else "other"
        a = support.setdefault(k, {"bytes": 0, "disk": 0, "files": 0})
        for x in a:
            a[x] += s[x]
    ad = apps_dir()
    backups = [{"name": n, **dir_size(os.path.join(ad, n))} for n in (sorted(os.listdir(ad)) if os.path.isdir(ad) else [])
               if re.fullmatch(r"Hyimg\.backup\.\d{8}-\d{6}\.app", n) and not os.path.islink(os.path.join(ad, n))]
    app = dir_size(os.path.join(ad, "Hyimg.app"))
    logs = dir_size(os.environ.get("HYIMG_LOGS") or os.path.join(HOME, "Library/Logs/Hyimg"))
    return {"cacheRoot": root, "cache": parts, "support": support, "backups": backups, "app": app, "logs": logs}


def _sum(*parts):
    out = {"bytes": 0, "disk": 0, "files": 0}
    for p in parts:
        for k in out:
            out[k] += (p or {}).get(k, 0)
    return out


def scan():
    """everything, written to the summary; one at a time: a second scan while one runs returns None"""
    os.makedirs(support_root(), exist_ok=True)
    lock = open(summary_path() + ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close(); return None
    try:
        t0 = time.time(); boards = catalog(); top = []
        hp = hashes_path()
        try:
            hashes = json.load(open(hp, encoding="utf-8"))
        except (OSError, ValueError):
            hashes = {}
        out = [scan_board(b, hashes, top) for b in boards if os.path.isdir(b["lib"])]
        out += [{"id": b["id"], "name": b["name"], "library": b["lib"], "available": False, "total": _sum()} for b in boards if not os.path.isdir(b["lib"])]
        os.makedirs(os.path.dirname(hp), exist_ok=True)
        with open(hp + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(hashes, fh, separators=(",", ":"))
        os.replace(hp + ".tmp", hp)
        g = scan_global(boards)
        made = _sum(*[c for b in out for k, c in (b.get("cats") or {}).items() if CLASS.get(k) == "regenerable"])
        cache = _sum(*g["cache"].values()); clear = _sum(*[v for v in g["cache"].values() if v.get("clear")])
        res = {"t": time.time(), "seconds": 0, "boards": out, "global": g, "top": [
            {"bytes": s, "path": p, "board": n, "cat": c} for s, p, n, c in sorted(top, reverse=True)],
            "totals": {"boards": _sum(*[b["total"] for b in out]), "made": made, "cache": cache, "clearable": clear,
                       "backups": _sum(*g["backups"]), "app": g["app"], "support": _sum(*g["support"].values()),
                       "dups": sum(b.get("dups", {}).get("wasted", 0) for b in out),
                       "dropbox": _sum(*[b["total"] for b in out if b.get("dropbox")])}}
        res["seconds"] = round(time.time() - t0, 2)
        tmp = summary_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False)
        os.replace(tmp, summary_path())
        return res
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN); lock.close()


def scanning():
    try:
        with open(summary_path() + ".lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(lock, fcntl.LOCK_UN)
        return False
    except OSError:
        return True


def start_scan():
    """a scan in its own process at low priority, detached: the caller never waits and never shares its memory"""
    if scanning():
        return False
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "scan"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    return True


def caps_path():
    return os.path.join(support_root(), "storage-settings.json")


def caps_read():
    """the ceiling of the thumbnail cache in GB: {"board", "total"} (thumbcache.py), 2 and 8 unless set"""
    try:
        d = json.load(open(caps_path(), encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    out = {"board": 2, "total": 8}
    for k in out:
        if isinstance(d.get(k), (int, float)) and 0 < d[k] <= 10000:
            out[k] = d[k]
    return out


def caps_write(board=None, total=None):
    """sets either or both (GB, 0.1 to 10 000); ValueError for anything else"""
    cur = caps_read()
    for k, v in (("board", board), ("total", total)):
        if v is not None:
            v = float(v)
            if not 0.1 <= v <= 10000:
                raise ValueError(f"{k} out of range")
            cur[k] = int(v) if v == int(v) else v
    os.makedirs(support_root(), exist_ok=True)
    with open(caps_path() + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(cur, fh)
    os.replace(caps_path() + ".tmp", caps_path())
    return cur


def summary(max_age=MAX_AGE, start=True):
    """the last summary with its age (None: never scanned); a scan starts behind it when it is older than max_age"""
    try:
        res = json.load(open(summary_path(), encoding="utf-8"))
    except (OSError, ValueError):
        res = None
    age = time.time() - res["t"] if res else None
    busy = scanning()
    if start and not busy and (res is None or age > max_age):
        busy = start_scan()
    return {"summary": res, "age": age, "scanning": busy, "lost": procs.lost(), "caps": caps_read()}   # lost processes: looked at now, a ps away


def server_memory():
    """this process's memory now, for the web version (the Mac app reports every process itself, native/Storage.swift)"""
    try:
        rss = int(subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, timeout=2).stdout.strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        rss = 0
    return {"pid": os.getpid(), "bytes": rss * 1024}


def http(handler, method):
    """GET /api/storage, POST /api/storage/clear, /backups and /stop for server.py (it only passes the request on)"""
    import storage_clean
    path = handler.path.split("?", 1)[0]
    if method == "GET" and path == "/api/storage":
        import perflog   # Settings › Storage › Performance log, its size beside the cache (perflog.py)
        body = {**summary(), "server": server_memory(), "perflog": perflog.size()}
    elif method == "POST" and path == "/api/storage/caps":   # {"board", "total"} in GB: the thumbnail cache's ceiling (thumbcache.py)
        n = int(handler.headers.get("Content-Length", 0) or 0)
        try:
            req = json.loads(handler.rfile.read(n) or b"{}")
            body = {"caps": caps_write(req.get("board"), req.get("total"))}
        except (ValueError, TypeError, AttributeError) as ex:
            return handler.send(400, json.dumps({"error": str(ex)[:200]}).encode(), "application/json")
    elif method == "POST" and path == "/api/storage/stop":   # {"pid"}: one lost server or Blender (procs.py), asked first by the page
        n = int(handler.headers.get("Content-Length", 0) or 0)
        try:
            body = procs.stop(json.loads(handler.rfile.read(n) or b"{}").get("pid"))
        except (ValueError, AttributeError):
            body = {"error": "bad request"}
        if body.get("error"):
            return handler.send(400, json.dumps(body).encode(), "application/json")
    elif method == "POST" and path in ("/api/storage/clear", "/api/storage/backups"):
        n = int(handler.headers.get("Content-Length", 0) or 0)
        try:
            req = json.loads(handler.rfile.read(n) or b"{}") if n else {}
            dry = bool(req.get("dryRun"))
            body = storage_clean.clear_cache(dry_run=dry) if path.endswith("clear") else storage_clean.trash_backups(int(req.get("keep", 2)), dry_run=dry)
        except (ValueError, TypeError, AttributeError, storage_clean.Refused) as ex:
            return handler.send(400, json.dumps({"error": str(ex)[:300]}).encode(), "application/json")
        if not dry:
            start_scan()   # the numbers follow what was freed
    else:
        return handler.send(404, b"not found", "text/plain")
    return handler.send(200, json.dumps(body, ensure_ascii=False).encode(), "application/json")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "summary"
    opt = lambda k, d: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    if cmd == "scan":
        os.nice(15)   # behind everything the person does
        res = scan()
        print(json.dumps({"ok": res is not None, "seconds": res and res["seconds"]}))
    elif cmd == "summary":   # the app's answer to Home: the performance log is the app's (its cache), so Home shows its size too
        import perflog
        print(json.dumps({**summary(float(opt("--max-age", MAX_AGE))), "perflog": perflog.size()}, ensure_ascii=False))
    elif cmd == "caps":   # storage.py caps [--board GB] [--total GB]
        try:
            print(json.dumps({"caps": caps_write(opt("--board", None), opt("--total", None)) if len(a) > 1 else caps_read()}))
        except ValueError as ex:
            print(json.dumps({"error": str(ex)})); sys.exit(2)
    elif cmd == "stop":   # storage.py stop <pid>: a lost server or Blender (procs.py)
        res = procs.stop(a[1] if len(a) > 1 else None)
        print(json.dumps(res)); sys.exit(2 if res.get("error") else 0)
    elif cmd in ("clear-cache", "backups"):
        import storage_clean
        try:
            res = storage_clean.clear_cache(dry_run="--dry-run" in a) if cmd == "clear-cache" else \
                storage_clean.trash_backups(opt("--keep", "2"), dry_run="--dry-run" in a)
        except storage_clean.Refused as ex:
            print(json.dumps({"error": str(ex)})); sys.exit(2)
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(__doc__); sys.exit(2)
