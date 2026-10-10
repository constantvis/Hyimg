"""The board's clipboard from board to board (P4 B-05, П4 audit 2026-10-10: ⌘C on one board and ⌘V on another pasted the copy's link as a
heading). Each board is its own address, so the page's own clipboard (localStorage cv.clip, canvas.html copySel) reached only the pages of
one project. ⌘C now also keeps what it copied (the things, their layout, their groups) in one file beside the app's settings, as the
properties clipboard does (server.py PROPS_CLIP): any board of any project can paste it (ui/boardclip.js).

  POST /api/boardclip {"clip"}         a copy made here; this server writes beside it which library it came from, a page never says
  POST /api/boardclip {"read": true}   {"clip", "here"}: the copy made last on any board; here, it was made in this library
  POST /api/boardclip/take             before a paste in another library: the copy's files brought here, {"map": {there: here}, "missing"}
All three are POST, one line in server.py's do_POST (the file is at its size ceiling, AGENTS.md «Размер файлов»).

A picture comes in as a pasted one (server.add_image: added/<day>/ with its json, or the place where this library already holds the same
bytes); a video or a PDF the same way, its bytes kept as they are. A file of the copy that is gone, or is neither, is named in "missing"
and the page leaves its card out. The copy's files stay where they are."""
import hashlib
import json
import os
import time

LIMIT = 8 << 20          # the copy itself (a big selection of a big board), not its files
FILE_LIMIT = 1 << 30     # one file brought over
RAW = {"video", "pdf", "doc", "model"}   # brought over byte for byte; pictures go through add_image


def where(srv):
    return os.path.join(os.path.dirname(os.path.abspath(srv.SETTINGS)), "board-clipboard.json")


def read(srv):
    try:
        d = json.load(open(where(srv), encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("clip"), dict) else None
    except (OSError, ValueError):
        return None


def post(srv, h):
    n = int(h.headers.get("Content-Length", 0))
    if n > LIMIT: return 413, b"too big", "text/plain"
    try:
        body = json.loads(h.rfile.read(n) or b"{}")
        if not isinstance(body, dict): raise ValueError("body")
        if h.path == "/api/boardclip/take": return 200, json.dumps(take(srv), ensure_ascii=False).encode(), "application/json"
        if body.get("read"):
            d = read(srv) or {}
            return 200, json.dumps({"clip": d["clip"], "here": d.get("lib") == os.path.realpath(srv.W)} if d else {}, ensure_ascii=False).encode(), "application/json"
        clip = body.get("clip")
        if not isinstance(clip, dict) or not isinstance(clip.get("items"), list): raise ValueError("clip")
        out = {"at": int(time.time() * 1000), "lib": os.path.realpath(srv.W), "project": srv.PROJECT_ID, "clip": clip}
        f = where(srv); os.makedirs(os.path.dirname(f), exist_ok=True)
        with srv.LOCK:
            with open(f + ".tmp", "w", encoding="utf-8") as fh: json.dump(out, fh, ensure_ascii=False)
            os.replace(f + ".tmp", f)
        return 200, b"{}", "application/json"
    except (ValueError, TypeError, AttributeError) as ex:
        return 400, str(ex)[:160].encode(), "text/plain; charset=utf-8"


def take(srv):
    """the copy's files in this library: the same path when this library holds the same bytes there, else brought in as pasted"""
    d = read(srv)
    if not d: return {"map": {}, "missing": []}
    lib = os.path.realpath(str(d.get("lib") or ""))
    paths = sorted({str(i["path"]) for i in d["clip"].get("items", []) if isinstance(i, dict) and isinstance(i.get("path"), str) and i["path"]})
    if lib == os.path.realpath(srv.W): return {"map": {p: p for p in paths}, "missing": []}
    out, missing = {}, []
    for rel in paths[:500]:
        src = os.path.realpath(os.path.join(lib, rel))
        if not lib or not src.startswith(lib + os.sep) or not os.path.isfile(src) or os.path.getsize(src) > FILE_LIMIT:
            missing.append(rel); continue
        data = open(src, "rb").read()
        try:
            mine = srv.safe(rel)
            if os.path.isfile(mine) and os.path.getsize(mine) == len(data) and open(mine, "rb").read() == data: out[rel] = rel; continue
        except (PermissionError, OSError):
            pass
        kind = srv.kind_of(rel)
        try:
            if kind == "image": out[rel] = srv.add_image(data, os.path.basename(rel))["path"]
            elif kind in RAW: out[rel] = raw(srv, data, os.path.basename(rel))
            else: missing.append(rel)
        except (ValueError, OSError):
            missing.append(rel)
    return {"map": out, "missing": missing}


def raw(srv, data, name):
    """a video, a PDF, a document or a model into added/<day>/ as it is, or where this library already has the same bytes"""
    sha = hashlib.sha1(data).hexdigest()
    with srv.LOCK:
        known = srv.dedup.known([sha]).get(sha)
        if known and os.path.exists(srv.real(known)): return known
        day = time.strftime("%y%m%d"); folder = os.path.join(srv.W, srv.ADDED, day); os.makedirs(folder, exist_ok=True)
        stem, ext = os.path.splitext(name)
        base = time.strftime("%H%M%S") + "-" + (stem[:40] or "file"); n = 2
        while os.path.exists(os.path.join(folder, base + ext)): base = base.rsplit("~", 1)[0] + f"~{n}"; n += 1
        with open(os.path.join(folder, base + ext + ".tmp"), "wb") as fh: fh.write(data)
        os.replace(os.path.join(folder, base + ext + ".tmp"), os.path.join(folder, base + ext))
        srv.lib_dirty()
        return f"{srv.ADDED}/{day}/{base}{ext}"
