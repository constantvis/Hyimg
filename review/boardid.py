"""A board's identity in its own folder, and the boards a shared Dropbox holds (owner 2026-10-08: he and his partner use two Macs signed
into the same Dropbox account, so every board folder syncs to both Macs while each Mac's catalog gives the board its own UUID).

  <state>/board.json   {"id": a UUID made once, "name": the board's name then, "created": ISO time}
                       written by the app when a board is first opened on any Mac (native/BoardIdentity.swift), never rewritten. Both
                       Macs read it, so hyimg:// links carry this id and open the same board on either Mac. Two Macs writing it before
                       Dropbox synced leave a «board (… conflicted copy …).json» beside it: its id still names the board (ids()).

Here: reading it for the server (GET /api/health boardId, dir: hy.py link and ui/applink.js build the app's link from them), the Dropbox
roots of this Mac and a folder's path relative to them (both Macs mount Dropbox at ~/Dropbox or ~/Library/CloudStorage/Dropbox, the
relative path is the same on both), and the scan for boards in Dropbox (Home's «Boards in Dropbox not on this Mac», the app runs it in the
background and keeps the result beside its catalog):
  python3 boardid.py scan [--catalog projects.json]      JSON {t, roots, boards: [{id, name, path, rel}]}, the catalog's boards left out
HYIMG_DROPBOX_ROOT (folders split by ":") names the roots instead of this Mac's Dropbox (tests).
"""
import collections
import glob
import json
import os
import re
import sys
import time
import uuid

FILE = "board.json"
STATE = "_review"
# folders never looked into: code, caches, packages; a board's own folder is not entered either (boards do not nest)
SKIP = {"node_modules", "__pycache__", ".git", "_thumbs", "_review", "dist", "build", ".venv", "venv", "_ARCHIVE"}
PACKAGES = (".app", ".photoslibrary", ".fcpbundle", ".logicx", ".band", ".bundle", ".framework", ".xcodeproj", ".blend1")
CONFLICT = re.compile(r"^board \(.*\)\.json$")


def _uuid(v):
    try: return str(uuid.UUID(str(v))).lower()
    except (ValueError, TypeError, AttributeError): return ""


def read(state):
    """{"id", "name"} of a board's board.json, or None"""
    try:
        with open(os.path.join(state, FILE), encoding="utf-8") as fh: d = json.load(fh)
    except (OSError, ValueError):
        return None
    i = _uuid(d.get("id")) if isinstance(d, dict) else ""
    return {"id": i, "name": str(d.get("name") or "")} if i else None


def ids(state):
    """the ids that name this board: board.json's, then those of its Dropbox conflicted copies"""
    out = [r["id"]] if (r := read(state)) else []
    try: names = sorted(n for n in os.listdir(state) if CONFLICT.match(n))
    except OSError: names = []
    for n in names:
        try:
            with open(os.path.join(state, n), encoding="utf-8") as fh: i = _uuid(json.load(fh).get("id"))
        except (OSError, ValueError, AttributeError): i = ""
        if i and i not in out: out.append(i)
    return out


def roots():
    """this Mac's Dropbox folders, real paths, without repeats: HYIMG_DROPBOX_ROOT, else ~/.dropbox/info.json, ~/Dropbox and
    ~/Library/CloudStorage/Dropbox*"""
    env = os.environ.get("HYIMG_DROPBOX_ROOT")
    if env is not None: found = [p for p in env.split(":") if p]
    else:
        home, found = os.path.expanduser("~"), []
        try:
            with open(os.path.join(home, ".dropbox/info.json"), encoding="utf-8") as fh: info = json.load(fh)
            found += [v.get("path") for v in info.values() if isinstance(v, dict) and isinstance(v.get("path"), str)]
        except (OSError, ValueError, AttributeError):
            pass
        found += [os.path.join(home, "Dropbox")] + sorted(glob.glob(os.path.join(home, "Library/CloudStorage/Dropbox*")))
    out = []
    for p in found:
        r = os.path.realpath(p)
        if os.path.isabs(p) and os.path.isdir(r) and r not in out: out.append(r)
    return out


def rel(path, rs=None):
    """a folder's path relative to the Dropbox root it is in ("Studio/Brand/Board"), or "" outside Dropbox"""
    p = os.path.realpath(path)
    for r in rs if rs is not None else roots():
        if p.startswith(r.rstrip("/") + "/"): return p[len(r.rstrip("/")) + 1:]
    return ""


def in_dropbox(path):
    return bool(rel(path))


def health(state, lib):
    """what GET /api/health adds: the board's id in its folder and its folder relative to Dropbox (both may be "")"""
    r = read(state)
    return {"boardId": r["id"] if r else "", "dir": rel(lib)}


def board_at(path, root=""):
    """a board found at a folder (its _review has board.json or saved pages), or None"""
    state = os.path.join(path, STATE)
    if not (os.path.isfile(os.path.join(state, FILE)) or os.path.isdir(os.path.join(state, "boards"))): return None
    r = read(state) or {}
    real = os.path.realpath(path)
    return {"id": r.get("id", ""), "name": r.get("name") or os.path.basename(real), "path": real, "rel": rel(real, [root] if root else None)}


def catalog(file):
    """(library roots, ids) of a catalog (projects.json): what this Mac already has"""
    try:
        with open(file, encoding="utf-8") as fh: c = json.load(fh)
    except (OSError, ValueError):
        return set(), set()
    c = c if isinstance(c, list) else []
    paths = {os.path.realpath(p["libraryRoot"]) for p in c if isinstance(p, dict) and isinstance(p.get("libraryRoot"), str)}
    known = {_uuid(p.get(k)) for p in c if isinstance(p, dict) for k in ("id", "folderId")} - {""}
    return paths, known


def scan(rs=None, cat=None, depth=8, max_dirs=60000, budget=30.0):
    """the boards in the Dropbox folders, breadth first, each folder listed once: a folder whose _review holds a board is a board and is
    not entered; hidden folders, packages and SKIP are not entered. Bounded by depth, folders and seconds: Home never waits for it"""
    rs = roots() if rs is None else rs
    paths, known = catalog(cat) if cat else (set(), set())
    t0, seen, out, queue = time.monotonic(), 0, [], collections.deque((r, r, 0) for r in rs)
    while queue and seen < max_dirs and time.monotonic() - t0 < budget:
        d, root, level = queue.popleft(); seen += 1
        try: entries = [e for e in os.scandir(d) if e.is_dir(follow_symlinks=False)]
        except OSError: continue
        if level and any(e.name == STATE for e in entries):
            b = board_at(d, root)
            if b:
                if b["path"] not in paths and not (b["id"] and b["id"] in known): out.append(b)
                continue
        if level >= depth: continue
        queue.extend((e.path, root, level + 1) for e in sorted(entries, key=lambda e: e.name.lower())
                  if not e.name.startswith(".") and e.name not in SKIP and not e.name.lower().endswith(PACKAGES))
    return {"t": time.time(), "roots": rs, "boards": out, "complete": not queue, "folders": seen}


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] != "scan": raise SystemExit(__doc__)
    cat = a[a.index("--catalog") + 1] if "--catalog" in a and a.index("--catalog") + 1 < len(a) else None
    print(json.dumps(scan(cat=cat), ensure_ascii=False))
