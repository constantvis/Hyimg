"""One picture, one place in the library (owner 2026-10-02: "so we don't load the same pictures ten times with one hash").

Agents re-collect downloads (Chrome, Gemini, Firefly) into new batch folders and the same file lands in the library again under
another name. Measured that day: 5738 frames, 50 byte-identical extra copies, nearly all from re-collected downloads.

Every library file gets its sha1 once, cached in <state>/sha-index.json by path with size and mtime, so only new or changed files
are read again (hashing the whole 8.5 GB library took 16 s). The library shows each picture once: copies are folded into the
first one (the one the owner reacted to, else the oldest). Tools ask before saving (POST /api/known, hy.py save) and the board
places the original instead of a copy (hy.py block).
"""
import hashlib, json, os, threading

from config import HERE, W

INDEX = os.path.join(HERE, "sha-index.json")
EXT = (".jpg", ".jpeg", ".png", ".webp")
_LOCK = threading.Lock()
_IDX = None   # rel path -> [size, mtime_ns, sha1]


def sha_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _index():
    global _IDX
    if _IDX is None:
        try:
            _IDX = json.load(open(INDEX, encoding="utf-8"))
        except (OSError, ValueError):
            _IDX = {}
    return _IDX


def _save():
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_IDX, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, INDEX)


def library_files(skip=(), here=HERE):
    """rel path -> (size, mtime_ns) of every picture file under the library root, without the state folder and skipped folders"""
    out = {}
    for root, dirs, files in os.walk(W):
        if os.path.realpath(root) == os.path.realpath(here):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for f in files:
            if f.lower().endswith(EXT):
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out[os.path.relpath(p, W)] = (st.st_size, st.st_mtime_ns)
    return out


def fill(skip=()):
    """hash the files that are new or changed since the last pass, forget the ones gone; returns how many were read"""
    files = library_files(skip)
    with _LOCK:
        idx = _index()
        # a file with no bytes is not a picture to fold: they all hash alike, so the library showed one of 105 and lost the rest (owner 2026-10-06)
        gone = [p for p in idx if p not in files or files[p][0] == 0]
        for p in gone:
            del idx[p]
        todo = [p for p, (size, mt) in files.items() if size and (idx.get(p) or [None, None])[:2] != [size, mt]]
    n = 0
    for p in todo:
        size, mt = files[p]
        try:
            sha = sha_file(os.path.join(W, p))
        except OSError:
            continue
        with _LOCK:
            _index()[p] = [size, mt, sha]
        n += 1
        if n % 300 == 0:
            with _LOCK:
                _save()
    if n or gone:
        with _LOCK:
            _save()
    return n


def sha_of(rel):
    e = _index().get(rel)
    return e[2] if e else None


def by_sha():
    out = {}
    for p, e in list(_index().items()):
        out.setdefault(e[2], []).append(p)
    return out


def _reacted(i):
    fb = i.get("feedback") or {}
    return bool(fb) and any(v not in (None, "", [], {}, False) for v in fb.values())


def collapse(items, keep_copies=False):
    """the library list with each picture once: the first of identical files carries copies=[...] and the others go
    (keep_copies: they all stay, the ones a library would hide marked hidden=True; the canvas needs them for copies on a board).
    Every copy is marked copy_of=<first>. A copy the owner reacted to (♥, rating, comment) is never hidden."""
    groups = {}
    for i in items:
        s = None if i.get("empty") or not i.get("size") else sha_of(i.get("path", ""))   # empty files are never copies of each other (2026-10-06)
        if s:
            groups.setdefault(s, []).append(i)
    hide = set()
    for same in groups.values():
        if len(same) < 2:
            continue
        same.sort(key=lambda i: (not _reacted(i), bool(i.get("archived")), i.get("born", 0), len(i["path"]), i["path"]))
        main = same[0]
        main["copies"] = [i["path"] for i in same[1:]]
        for i in same[1:]:
            i["copy_of"] = main["path"]
            if not _reacted(i):
                if keep_copies: i["hidden"] = True
                else: hide.add(id(i))
    return [i for i in items if id(i) not in hide]


def known(shas):
    """sha1 -> library path of the first file with it, for the ones the library has"""
    rev = by_sha()
    return {s: sorted(rev[s], key=lambda p: (len(p), p))[0] for s in shas if s in rev}


def rekey(pairs):
    """files that moved (folders as on the board, foldersync.py, 2026-10-05): their sha1 goes with them, nothing is read again"""
    with _LOCK:
        idx = _index(); n = 0
        for a, b in pairs:
            if a in idx and b not in idx:
                idx[b] = idx.pop(a); n += 1
        if n: _save()
    return n
