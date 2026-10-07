# Hyimg's server for one board: its library, canvas and history.
# Serves every image of the board's folder with its prompt sidecar (<name>.json next to the image)
# and writes the owner's verdict, tags and comment into that same sidecar under "feedback".
# Identical copies of the image elsewhere in the library (same name and byte size, e.g. in _favs)
# get the same feedback. Every change is also appended to _review/feedback-log.jsonl as history.
# Run: python3 server.py [port]   (default 4180), open http://localhost:4180
import fcntl, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.parse, urllib.request
from contextlib import ExitStack
from config import CACHE_ROOT, CODE_DIR, HERE, W, BOARDS, NOTES, PROJECT_ID, RULES, MOUNTS, MOUNT_SETS, real
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image
import tags
import history   # version snapshots of the boards (2026-09-30)
import events    # what happened on a page, event by event (2026-10-02)
import dedup     # one picture, one place in the library: sha1 of every file (2026-10-02)
import foldersync   # folders as on the board, «Разложить по папкам как на доске» (2026-10-05)
import webvideo     # a WebM copy for an engine without H.264, the app's Chromium (2026-10-05)
import pdfpages, lib3d   # a PDF's pages as pictures, one page at a time (2026-10-06); 3D files as files of their folders (2026-10-07)
import filters      # the dock's pinned filters and a project's own tags (owner 2026-10-06)
import thumbcache    # thumbnails and previews in the app's cache, not in Dropbox (2026-10-07)
import lifetime      # how long a server lives: with the app, or with whoever started it (2026-10-07)
import storage       # where the disk goes, Settings › Storage, and the one safe cleanup (owner 2026-10-07)
import foldercolors   # a folder's colour in the library's tree, a mark for finding your way (owner 2026-10-06)
tags.configure(RULES)   # the board's theme tags, from its rules

THUMBS = thumbcache.THUMBS   # ~/Library/Caches/Hyimg/<board>/thumbs, outside Dropbox, capped; moved from <state>/_thumbs (thumbcache.py)
LOG = os.path.join(HERE, "feedback-log.jsonl")
# What the library leaves out: the server's own folders always, the rest by the board's rules (config.py RULES, the person's file of
# library rules, owner 2026-10-05: no project of anyone's in the code). .posters and .stills are still views of 3D cards and HTML frames.
SKIP = {"_review", "__pycache__", ".git", ".posters", ".stills"} | {d for d in RULES.get("skip") or [] if isinstance(d, str) and d}
HIDE = [h.strip("/") for h in RULES.get("hide") or [] if isinstance(h, str) and h.strip("/")]   # folder paths, with what is in them
HIDE_NAMED = {d for d in RULES.get("hideNamed") or [] if isinstance(d, str) and d}   # folder names, at any depth
HIDE_PREFIXES = tuple(p for p in RULES.get("hideFolderPrefixes") or [] if isinstance(p, str) and p)   # a folder named so shows no files
SKIP_FILES = tuple(p for p in RULES.get("skipFilePrefixes") or [] if isinstance(p, str) and p)   # intermediates, not frames
ROOT_FILES = RULES.get("rootFiles", True) is not False   # files right in the board's folder are frames
EXT = (".jpg", ".jpeg", ".png", ".webp")
# Owner 2026-10-04 (a photo board: «add video and Photoshop files; even if we do not open them, there must be a preview»). They sit in the
# library and on the canvas like pictures. The browser cannot draw them, so the server shows a preview instead: Quick Look's (qlmanage
# reads the composite a PSD or PSB keeps, the PDF inside an .ai), and one frame of a video. The file itself is never touched. Its
# ratings live in <file>.<ext>.json: IMG_1604.psd and IMG_1604.JPG lie side by side and must not share one json.
DOC_EXT = (".psd", ".psb", ".ai", ".tif", ".tiff", ".heic", ".heif", ".svg")
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")
# Owner 2026-10-06: a PDF is in the library and on the board with its first page as the picture, and its card steps through the pages
# (pdfpages.py draws a page as an image on demand: the app's Chromium has no PDF plugin). Its ratings live in <file>.pdf.json.
PDF_EXT = (".pdf",)
MEDIA_EXT = EXT + DOC_EXT + VIDEO_EXT + PDF_EXT


def kind_of(path):
    e = os.path.splitext(path)[1].lower()
    pk = plugin_kinds().get(e) if e not in MEDIA_EXT else None   # a plugin's own kind of file (html: Dev studio, owner 2026-10-06)
    return pk[0] if pk else "video" if e in VIDEO_EXT else "pdf" if e in PDF_EXT else "doc" if e in DOC_EXT else "model" if e in MODEL_EXT else "image"


# A plugin's own kinds of library files (owner 2026-10-06: «dev studio and html are a plugin too»): manifest.json
# "kinds": {"html": [".html", ".htm"]} lists those files in the library like the others, kind "html" with its ext; preview() asks the
# plugin's server module for their picture (preview(full, out_png)), Quick Look when it has none. A kind never takes over the app's own
# extensions or names. Read from the manifests at most every 10 s: scan() asks for every file.
_PKINDS = [0.0, {}]
PLAIN_KINDS = ("image", "video", "pdf", "doc", "model")


def plugin_kinds():
    """{".html": ("html", "<plugin>")} of the plugins the server finds"""
    if time.time() - _PKINDS[0] > 10:
        out = {}
        for n, (_d, m) in plugins().items():
            ks = m.get("kinds")
            if not isinstance(ks, dict): continue
            for k, exts in ks.items():
                if not (isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9]{0,15}", k) and k not in PLAIN_KINDS and isinstance(exts, list)): continue
                for e in exts:
                    if isinstance(e, str) and re.fullmatch(r"\.[a-z0-9]{1,8}", e) and e not in MEDIA_EXT + MODEL_EXT: out.setdefault(e, (k, n))
        _PKINDS[:] = [time.time(), out]
    return _PKINDS[1]
# Outside folders shown in the library as their own collections without copying (2026-09-30), from the board's rules (config.py
# MOUNTS). Virtual path "ext/<name>/<file>" maps to the real folder; feedback sidecars <name>.json are written next to the image, a
# gallery-dl <name>.jpg.json stays as it is and only feeds the caption.


LOCK = threading.Lock()



def titles():
    # Collection titles from the board's rules: a file of the library with ("folder", "title") pairs (parsed as text so nothing runs),
    # then the rules' own titles
    out = {}
    src_file = RULES.get("titlesFrom")
    if isinstance(src_file, str) and src_file and not os.path.isabs(src_file) and ".." not in src_file.split("/"):
        try:
            src = open(os.path.join(W, src_file), encoding="utf-8").read()
            for folder, title in re.findall(r'\(\s*"([^"]+)",\s*"([^"]+)"', src):
                out[folder] = title
        except OSError:
            pass
    for folder, title in (RULES.get("titles") or {}).items():
        if isinstance(title, str): out.setdefault(folder, title)
    out.setdefault(ADDED, "Добавлено вручную (вставка и перетаскивание на холст)")
    return out


def refpaths(meta, root):
    # reference images given with the prompt, as workroom paths (2026-09-29). Batches wrote them three ways:
    # "refs" = names inside refs/, "inputs" = paths relative to the frame's folder, "images" = paths relative to the frame's folder
    out = []
    for r in meta.get("refs") or []:
        for cand in (os.path.join(W, "refs", r), os.path.join(root, r)):
            if os.path.isfile(cand):
                out.append(os.path.relpath(cand, W)); break
    for r in (meta.get("inputs") or []) + (meta.get("images") or []):
        cand = os.path.normpath(os.path.join(root, r))
        if os.path.isfile(cand) and cand.startswith(W + os.sep):
            out.append(os.path.relpath(cand, W))
    return list(dict.fromkeys(out))


def source_meta(meta, root):
    """(json, folder) of the file a frame was cut or made from ("grid" / "derived_from", relative to its folder or the library root)"""
    for key in ("grid", "derived_from"):
        src = meta.get(key)
        if not isinstance(src, str) or not src: continue
        for full in (os.path.normpath(os.path.join(root, src)), os.path.normpath(os.path.join(W, src))):
            if full.startswith(W + os.sep) and os.path.isfile(full):
                sm = _sidecar(os.path.splitext(full)[0] + ".json")
                if isinstance(sm, dict) and sm: return sm, os.path.dirname(full)
    return None, None


def inherited_refs(meta, root):
    # a frame cut from a grid or made from another picture shows that picture's references when it has none of its own (owner 2026-10-03:
    # the strips of a 4x4 grid lost "inputs" when they were cut, and their card showed no references). "grid" and "derived_from" are
    # paths relative to the frame's folder (cut_rows.py) or to the library root (cut_grids.py); one step back is enough
    for key in ("grid", "derived_from"):
        src = meta.get(key)
        if not isinstance(src, str) or not src: continue
        for full in (os.path.normpath(os.path.join(root, src)), os.path.normpath(os.path.join(W, src))):
            if not full.startswith(W + os.sep) or not os.path.isfile(full): continue
            sm = _sidecar(os.path.splitext(full)[0] + ".json")
            got = refpaths(sm, os.path.dirname(full)) if isinstance(sm, dict) else []
            if got: return got
    return []


def folder_key(folder):
    m = re.match(r"v(\d+)", folder)
    if m:
        return (0, int(m.group(1)), folder)
    return (1 if folder == "_favs" else 2, 0, folder)


_SIDE = {}   # sidecar json by path: (mtime_ns, size, parsed); a scan re-reads only the ones that changed (10 000 files, 6 s each scan)


def _sidecar(side):
    try:
        st = os.stat(side)
    except OSError:
        _SIDE.pop(side, None); return {}
    hit = _SIDE.get(side)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return json.loads(hit[2])   # a fresh copy: scan changes the dict
    try:
        raw = open(side, encoding="utf-8").read(); json.loads(raw)
    except (OSError, ValueError):
        return {}
    _SIDE[side] = (st.st_mtime_ns, st.st_size, raw)
    return json.loads(raw)


# The library list (owner 2026-10-02: zoom left pictures empty and "сохраняю…" hung once the library reached 21 000 frames): one scan
# took 21 s, every open page asked for it again on each folder change and the scans ran side by side, so thumbnails and board saves
# waited minutes. Now one scan serves every request that arrives while it runs, and its result is reused until the folders change,
# the server itself writes a frame's json or a minute passes (an agent may edit a json in place, which no folder notices).
_LIST = {"items": None, "key": None, "t": 0, "dur": 0.0, "busy": False}
_LIST_LOCK = threading.Lock()
LIB_GEN = [0]   # bumped by every write of the server's own that changes what scan returns


def lib_dirty():
    LIB_GEN[0] += 1


# A big library answers at once (owner 2026-10-04: «opening Studio North takes over 20 s»; 18 500 frames over Dropbox scan in about
# 20 s, and a board's server starts afresh with the app). The last list is kept on this Mac outside Dropbox; a server that has just
# started answers with it, and a list older than a minute or changed by an agent is answered as it is while a new scan runs behind:
# the pages hear of a difference through /api/changes (LIB_SIG["v"]) and fetch it again. The server's own writes, a first start
# with nothing kept and a library that scans in under 2 s are still scanned before the answer, so what was just written is in it.
SNAP = os.path.join(CACHE_ROOT, PROJECT_ID or hashlib.sha1(W.encode()).hexdigest()[:16], "library.json")
_SNAP_HASH = [None]


def snap_load():
    try:
        d = json.load(open(SNAP, encoding="utf-8"))
        return d["items"] if d.get("root") == W and isinstance(d.get("items"), list) else None
    except (OSError, ValueError, KeyError):
        return None


def snap_save(items):
    try:
        raw = json.dumps({"root": W, "items": items}, ensure_ascii=False)
        h = hashlib.sha1(raw.encode()).hexdigest()
        if h == _SNAP_HASH[0]:
            return
        os.makedirs(os.path.dirname(SNAP), exist_ok=True)
        tmp = SNAP + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(raw)
        os.replace(tmp, SNAP)
        _SNAP_HASH[0] = h
    except OSError:
        pass


def _scan_now():   # under _LIST_LOCK
    t0 = time.time(); key = (LIB_SIG["sig"], LIB_GEN[0])
    _LIST.update(items=scan(), key=key, t=time.time(), dur=time.time() - t0)
    threading.Thread(target=snap_save, args=(_LIST["items"],), daemon=True).start()


def _scan_behind():
    try:
        t0 = time.time(); key = (LIB_SIG["sig"], LIB_GEN[0]); items = scan()
    except Exception:
        with _LIST_LOCK:
            _LIST["busy"] = False
        return
    with _LIST_LOCK:
        old = _LIST["items"]
        _LIST.update(items=items, key=key, t=time.time(), dur=time.time() - t0, busy=False)
    if old != items:
        LIB_SIG["v"] += 1   # the pages fetch the new list
    snap_save(items)


def scan_cached():
    with _LIST_LOCK:
        if _LIST["items"] is None:
            kept = snap_load()
            if kept is None:
                _scan_now()
            else:
                _LIST.update(items=kept, key=("kept", LIB_GEN[0]), t=0, dur=99.0)   # the last list at once; a scan follows behind
        key = (LIB_SIG["sig"], LIB_GEN[0])
        if _LIST["key"] != key or time.time() - _LIST["t"] > 60:
            own = _LIST["key"] is not None and _LIST["key"][1] != LIB_GEN[0]
            if own or _LIST["dur"] < 2.0:
                _scan_now()
            elif not _LIST["busy"]:
                _LIST["busy"] = True
                threading.Thread(target=_scan_behind, daemon=True).start()
        return [dict(i) for i in _LIST["items"]]   # copies: with_archive and dedup mark them per request


def scan():
    items = []
    t = titles()
    for root, dirs, files in os.walk(W):
        rel_root = os.path.relpath(root, W)
        if rel_root == ".":
            # Top level holds scripts and specs; only image folders below it are scanned.
            dirs[:] = [d for d in dirs if d not in SKIP]
            if not ROOT_FILES:
                continue
        if os.path.realpath(root) == HERE:
            dirs[:] = []
            continue
        if HIDE_PREFIXES and os.path.basename(rel_root).startswith(HIDE_PREFIXES):  # e.g. service masks, not for review
            continue
        # SKIP must hold at every depth: recolor/irid/_prev and _qa-fail were shown as collections (2026-09-25),
        # and the owner re-commented old versions believing they were new
        if any(part in SKIP for part in rel_root.split(os.sep)):
            dirs[:] = []
            continue
        # HTML frames' pages and their own pictures, and image frames' renders, masks and painted layers (Hyimg-frames, owner
        # 2026-10-05: «the frame's render must not show in the library as a picture») are not library frames
        if rel_root.split(os.sep)[0] in ("html", "frames"):
            dirs[:] = []
            continue
        # folders the rules hide by name at any depth (e.g. 3D storyboard renders; single such frames elsewhere go by SKIP_FILES)
        if HIDE_NAMED and HIDE_NAMED.intersection(rel_root.split(os.sep)):
            dirs[:] = []
            continue
        # folders the rules take out of the gallery by path (2026-09-29: test renders, debug overlays, intermediates)
        if any(rel_root == h or rel_root.startswith(h + os.sep) for h in HIDE):
            dirs[:] = []
            continue
        for f in files:
            if not f.lower().endswith(MEDIA_EXT + tuple(plugin_kinds())) or (SKIP_FILES and f.startswith(SKIP_FILES)):  # e.g. raw AI crops are intermediates (2026-09-27); a plugin's kinds too (html)
                continue
            path = f if rel_root == "." else os.path.join(rel_root, f)   # files right in the project folder (226 on one board): no "./" in front
            name = os.path.splitext(f)[0]
            kind = kind_of(f)
            meta = _sidecar(os.path.join(root, (name if kind == "image" else f) + ".json"))
            # every agent writes these files: one odd one (a list, "qa" or "feedback" as plain text, 2026-10-01) must not take the
            # whole library down, it only loses what cannot be read
            if not isinstance(meta, dict):
                meta = {}
            for k in ("feedback", "qa", "grid_feedback"):
                if k in meta and not isinstance(meta[k], dict):
                    meta[k + "_text"] = meta.pop(k)
            if isinstance(meta, dict) and meta.get("cut"):   # grid already cut into single frames (arc/cut_grids.py, 2026-09-29); its cells are shown instead
                continue
            folder = rel_root
            items.append({
                "name": name,
                "path": path,
                "folder": folder,
                "title": "В корне доски" if folder == "." else t.get(folder, t.get(folder.split(os.sep)[0], folder)),
                "mtime": int(os.path.getmtime(os.path.join(root, f))),
                "born": int(getattr(os.stat(os.path.join(root, f)), "st_birthtime", os.path.getmtime(os.path.join(root, f)))),
                "model": meta.get("model") or (source_meta(meta, root)[0] or {}).get("model", ""),   # a cut strip without a model has its grid's (2026-10-03)
                "aspect": meta.get("aspect", ""),
                "prompt": meta.get("prompt", ""),
                "refs": meta.get("refs", []),
                "refpaths": refpaths(meta, root) or inherited_refs(meta, root),
                "owner_tags": meta.get("owner_tags", []) if isinstance(meta, dict) else [],   # the owner's own groupings (former _favs subfolders)
                "size": os.path.getsize(os.path.join(root, f)),
                "feedback": meta.get("feedback", {}),
                "gate": (meta.get("qa") or {}).get("gate"),
                # my questions to the owner about what a comment meant, with his answers (2026-09-29); kept outside "feedback" so the page's saves never drop them
                "questions": meta.get("questions", []),
                "grid": meta.get("grid", ""),
                "grid_feedback": meta.get("grid_feedback", {}),
                "board_notes": notes_for(meta),   # sticky notes from the canvas that touch this frame, resolved through their files (2026-09-30)
                **({"kind": kind, "ext": os.path.splitext(f)[1][1:].upper()} if kind != "image" else {}),
                # a file with nothing in it or one that cannot be read (Dropbox had not brought it down, owner 2026-10-06): the library lists it
                # with a mark instead of losing it, the board does not take it as a picture
                **({"empty": True} if is_empty(os.path.join(root, f)) else {}),
                **({"pages": n} if kind == "pdf" and (n := pdf_pages_known(path)) else {}),
                # length, picture size and codecs for the board's card; the codecs tell a page whether its engine plays the file (2026-10-05)
                **(dict(zip(("duration", "vsize", "vcodec", "acodec"), video_probe(os.path.join(root, f)))) if kind == "video" else {}),
            })
    # theme tags from the prompt (tags.py): batch style blocks are learned from all prompts first, then each scene is tagged
    tags.learn(items)
    for i in items:
        i["tags"] = tags.tags(i)
    items += scan_mounts() + lib3d.as_frames(scan3d(), real)   # 3D files are files of their folders too (2026-10-07)
    # Owner 2026-09-29: collections in order of when they were started, labelled YYMMDDHHmm. The start is the creation time of the
    # oldest image in the folder (birth time survives edits; renaming folders would break the feedback paths and scripts).
    first = {}
    for i in items:
        first[i["folder"]] = min(first.get(i["folder"], i["born"]), i["born"])
    for i in items:
        i["start"] = time.strftime("%y%m%d%H%M", time.localtime(first[i["folder"]]))
    items.sort(key=lambda i: (-first[i["folder"]], i["folder"], i["name"]))
    return items


def scan_mounts():
    # external folders (MOUNTS): one collection each; caption and post date come from the gallery-dl json, the owner's feedback from <name>.json
    out = []
    sets = []
    for pre, (root, title, model) in MOUNTS.items():
        if not os.path.isdir(root):
            continue
        if pre in MOUNT_SETS:   # each subfolder its own collection; titles and the why of each source in <mount>/sources.json
            try:
                srcs = {x["folder"]: x for x in json.load(open(os.path.join(root, "sources.json"), encoding="utf-8"))}
            except (OSError, ValueError, KeyError, TypeError):
                srcs = {}
            for d in sorted(os.listdir(root)):
                if os.path.isdir(os.path.join(root, d)):
                    x = srcs.get(d, {})
                    sets.append((pre + "/" + d, os.path.join(root, d), f"{title} · {x.get('category_ru', '')} · {x.get('title', d)}".replace(" ·  · ", " · "), x.get("model", model)))
            continue
        sets.append((pre, root, title, model))
    for pre, root, title, model in sets:
        for f in sorted(os.listdir(root)):
            if not f.lower().endswith(EXT):
                continue
            full = os.path.join(root, f); name = os.path.splitext(f)[0]
            meta = {}
            try:
                meta = json.load(open(os.path.join(root, name + ".json"), encoding="utf-8"))
            except (OSError, ValueError):
                pass
            src = {}
            try:
                src = json.load(open(full + ".json", encoding="utf-8"))
            except (OSError, ValueError):
                pass
            w, h = int(src.get("width") or 0), int(src.get("height") or 0)
            st = os.stat(full)
            rb = os.stat(root)   # gallery-dl stamps the files with the post date; the collection starts when the folder was made
            out.append({"name": name, "path": pre + "/" + f, "folder": pre, "title": title,
                        "mtime": int(st.st_mtime), "born": int(getattr(rb, "st_birthtime", rb.st_mtime)),
                        "model": model, "aspect": f"{w}:{h}" if w and h else "",
                        "prompt": meta.get("prompt") if isinstance(meta, dict) and meta.get("prompt") else f"{src.get('post_date', '')[:10]} · {src.get('post_url', '')}\n{src.get('description', '')}".strip(),
                        "refs": [], "refpaths": [], "owner_tags": [], "size": st.st_size,
                        "feedback": meta.get("feedback", {}) if isinstance(meta, dict) else {},
                        "gate": None, "questions": [], "grid": "", "grid_feedback": {}, "tags": [], "board_notes": notes_for(meta)})
    return out


def sidecar(rel):
    return (os.path.splitext(real(rel))[0] if kind_of(rel) == "image" else real(rel)) + ".json"


def save_feedback(entry):
    with LOCK:
        rel = entry["path"]
        safe(rel)
        size = os.path.getsize(real(rel))
        name = os.path.splitext(os.path.basename(rel))[0]
        targets = [i["path"] for i in scan_cached() if i["name"] == name and i["size"] == size] or [rel]
        fb = {k: entry[k] for k in ("verdict", "fav", "good", "bad", "comment", "scores", "use", "notes") if k in entry}
        # "scores": one row per criterion, 1 bad, 2 middle, 3 great (review v2, 2026-09-28); "use": ad/animation/site; "notes": [{kind arrow|mark, pts [[x,y] 0..1], text}] drawn on the frame
        empty = not fb.get("verdict") and not fb.get("fav") and not fb.get("good") and not fb.get("bad") and not fb.get("comment") and not fb.get("scores") and not fb.get("use") and not fb.get("notes")
        fb["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        for t in targets:
            sp = sidecar(t)
            try:
                meta = json.load(open(sp, encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            if empty:
                meta.pop("feedback", None)
            else:
                meta["feedback"] = fb
            tmp = sp + ".tmp"
            json.dump(meta, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, sp); lib_dirty()
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"t": fb["updated"], "paths": targets, **{k: v for k, v in entry.items() if k != "path"}}, ensure_ascii=False) + "\n")
        return {"feedback": {} if empty else fb, "paths": targets}


def save_fav(paths, fav):
    # ♥ from the canvas for many frames at once (owner 2026-10-01): one library scan for the whole batch, and only the fav field
    # changes, so scores, comments and marks set in the library stay as they are (save_feedback replaces the whole block)
    with LOCK:
        for rel in paths:
            safe(rel)
        by = {}
        for i in scan_cached():
            by.setdefault((i["name"], i["size"]), []).append(i["path"])
        now, out = time.strftime("%Y-%m-%d %H:%M:%S"), {}
        for rel in paths:
            name, size = os.path.splitext(os.path.basename(rel))[0], os.path.getsize(real(rel))
            for t in by.get((name, size)) or [rel]:
                sp = sidecar(t)
                try:
                    meta = json.load(open(sp, encoding="utf-8"))
                except (OSError, ValueError):
                    meta = {}
                fb = dict(meta.get("feedback") or {})
                if fav: fb["fav"] = True
                else: fb.pop("fav", None)
                fb.pop("updated", None)
                if any(fb.get(k) for k in ("verdict", "fav", "good", "bad", "comment", "scores", "use", "notes")):
                    fb["updated"] = now; meta["feedback"] = fb
                else:
                    fb = {}; meta.pop("feedback", None)
                tmp = sp + ".tmp"
                json.dump(meta, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                os.replace(tmp, sp); lib_dirty()
                out[t] = fb
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"t": now, "paths": sorted(out), "fav": bool(fav), "via": "canvas"}, ensure_ascii=False) + "\n")
        return {"feedback": out}


def save_answer(entry):
    # owner's answer to one of my questions: {"path", "id", "a"}; written into the sidecar's "questions" list and the log
    with LOCK:
        rel = entry["path"]
        safe(rel)
        sp = sidecar(rel)
        meta = json.load(open(sp, encoding="utf-8"))
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        for q in meta.get("questions", []):
            if q.get("id") == entry["id"]:
                q["a"] = entry.get("a", "")
                q["answered"] = now if q["a"].strip() else ""
        tmp = sp + ".tmp"
        json.dump(meta, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, sp); lib_dirty()
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"t": now, "paths": [rel], "answer": entry.get("id"), "a": entry.get("a", "")}, ensure_ascii=False) + "\n")
        return {"questions": meta.get("questions", [])}


def board_path(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise PermissionError(name)
    return os.path.join(BOARDS, name + ".json")


def load_board(name):
    p = board_path(name)
    if not os.path.exists(p):
        return {"schema": 1, "revision": 0, "items": {}, "groups": {}}
    return json.load(open(p, encoding="utf-8"))


# ---- sticky notes on the canvas (owner 2026-09-30) ----
# A note is a board item {type:"note", text, x, y, w, h, reach:{l,t,r,b}|null, to:[item or group ids]}. It touches a picture when
#   overlap: the note card overlaps the picture, zone: the dashed zone (the card grown by reach margins) overlaps it,
#   arrow: an arrow from the note points at the picture, or at a group (then every picture of that group),
#   group: the note has none of those but sits inside a group frame, so it speaks for the whole group.
# Stored once, linked many times (owner: "not the whole text into every json"): the note lives in one file NOTES/<board>__<id>.json
# (text as Markdown, colour, scope, the list of pictures it touches and how); each touched picture's sidecar gets only a short
# "related_notes": [{"note": "<board>/<id>", "via": [...]}]. Changing a note's text rewrites one file, not fifty sidecars.
# The board stays the master (positions, text, arrows); the files here are regenerated from it on every save.
# boards/<name>.notes-index.json remembers which sidecars carry references, so a note that moved away or was deleted is taken out again.



def _pic_rect(it):
    c = it.get("crop") or [0, 0, 1, 1]; w = float(it["w"]); ar = float(it.get("ar") or 1)
    return (float(it["x"]), float(it["y"]), w, w * ((c[3] - c[1]) / ar) / (c[2] - c[0]))


def _hit(a, b):
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def note_index(b):
    """{note id: {text, color, group, scope, pics: {path: set(via)}}} for one board dict; notes without text are left out"""
    items, groups = b.get("items", {}), b.get("groups", {})
    pics = {i: v for i, v in items.items() if v.get("path")}
    rects = {i: _pic_rect(v) for i, v in pics.items()}
    # pictures by cells of the board: a note is tested only against the frames near it (owner 2026-10-02: 520 notes x 3600 frames on
    # every save took 0.26 s), as canvas.html picIndex
    C, cells = 2048, {}
    for i, r in rects.items():
        for cx in range(int(r[0] // C), int((r[0] + r[2]) // C) + 1):
            for cy in range(int(r[1] // C), int((r[1] + r[3]) // C) + 1): cells.setdefault((cx, cy), []).append(i)
    def near(a):
        seen = []
        for cx in range(int(a[0] // C), int((a[0] + a[2]) // C) + 1):
            for cy in range(int(a[1] // C), int((a[1] + a[3]) // C) + 1): seen += cells.get((cx, cy), ())
        return dict.fromkeys(seen)
    out = {}
    for nid, n in items.items():
        if n.get("type") != "note" or not (n.get("text") or "").strip():
            continue
        nw = float(n.get("w") or 0)   # a note is at least a square on the canvas (min-height = width), as canvas.html reachRect
        nr = (float(n["x"]), float(n["y"]), nw, max(nw, float(n.get("h") or float(n.get("fs") or 16) * 1.2)))
        z = n.get("reach")
        zr = (nr[0] - z["l"], nr[1] - z["t"], nr[2] + z["l"] + z["r"], nr[3] + z["t"] + z["b"]) if z else None
        via, grp = {}, None
        box = (min(nr[0], zr[0]), min(nr[1], zr[1]), max(nr[0] + nr[2], zr[0] + zr[2]) - min(nr[0], zr[0]), max(nr[1] + nr[3], zr[1] + zr[3]) - min(nr[1], zr[1])) if zr else nr
        for i in near(box):
            r = rects[i]
            if _hit(nr, r): via.setdefault(i, set()).add("overlap")
            # a picture is in a zone when its centre is (owner 2026-09-30): a roomy zone must not catch the edges of the next row
            if zr and zr[0] <= r[0] + r[2] / 2 <= zr[0] + zr[2] and zr[1] <= r[1] + r[3] / 2 <= zr[1] + zr[3]: via.setdefault(i, set()).add("zone")
        for t in n.get("to") or []:
            if t in pics:
                via.setdefault(t, set()).add("arrow")
            elif t in groups:
                grp = grp or (groups[t].get("title") or "").strip()
                for m in groups[t].get("members", []):
                    if m in pics: via.setdefault(m, set()).add("arrow")
        scope = "pictures"
        if not via and not z and not (n.get("to") or []):   # nothing of its own and no zone or arrow: a note inside a group frame speaks for the whole group (the smallest frame holding its centre)
            cx, cy = nr[0] + nr[2] / 2, nr[1] + nr[3] / 2
            hit = sorted(((g["w"] * g["h"], gid) for gid, g in groups.items() if g["x"] <= cx <= g["x"] + g["w"] and g["y"] <= cy <= g["y"] + g["h"]))
            if hit:
                g = groups[hit[0][1]]; grp = (g.get("title") or "").strip(); scope = "group"
                for m in g.get("members", []):
                    if m in pics: via.setdefault(m, set()).add("group")
        e = {"text": n["text"].strip(), "color": n.get("color") or "yellow", "scope": scope, "pics": {}}
        if grp: e["group"] = grp
        for i, v in via.items():
            e["pics"].setdefault(pics[i]["path"], set()).update(v)   # a picture that sits twice on the board is one entry
        out[nid] = e
    return out


_NC = {}


def note_doc(ref):
    """the note file behind a reference "<board>/<id>", cached by modification time"""
    name, _, nid = ref.partition("/")
    p = os.path.join(NOTES, f"{name}__{nid}.json")
    try: mt = os.path.getmtime(p)
    except OSError: return None
    if _NC.get(p, (0, None))[0] != mt:
        try: _NC[p] = (mt, json.load(open(p, encoding="utf-8")))
        except (OSError, ValueError): return None
    return _NC[p][1]


def notes_for(meta):
    """what the pages show for a picture: its references resolved through the note files"""
    out = []
    if not isinstance(meta, dict): return out
    for r in meta.get("related_notes", []):
        d = note_doc(r.get("note", ""))
        if not d: continue
        e = {"note": d["id"].split("/")[-1], "board": d["board"], "text": d["text"], "color": d.get("color", "yellow"), "via": r.get("via", [])}
        if d.get("group"): e["group"] = d["group"]
        out.append(e)
    return out


def _write_json(path, doc, indent=1):
    tmp = path + ".tmp"; json.dump(doc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=indent); os.replace(tmp, path)
    # only writes into the library change what scan returns; the state folder (live.json twice a second, board indexes) does not
    if not os.path.realpath(path).startswith(os.path.realpath(HERE) + os.sep): lib_dirty()


_SYNCED = {}   # page -> the note index last written out: a save that changes no note-to-picture link touches no file (owner 2026-10-02)


def sync_notes(name):
    with LOCK:
        index = note_index(load_board(name))
        if _SYNCED.get(name) == index and os.path.exists(os.path.join(BOARDS, name + ".notes-index.json")):
            return 0
        os.makedirs(NOTES, exist_ok=True)
        # 1. one file per note that touches at least one picture
        want, now = {}, time.strftime("%Y-%m-%d %H:%M")
        for nid, n in index.items():
            if not n["pics"]: continue
            doc = {"id": f"{name}/{nid}", "board": name, "text": n["text"], "color": n["color"], "scope": n["scope"]}
            if n.get("group"): doc["group"] = n["group"]
            doc["pictures"] = [{"path": p, "via": sorted(v)} for p, v in sorted(n["pics"].items())]
            want[f"{name}__{nid}.json"] = doc
        touched = 0
        for f, doc in want.items():
            p = os.path.join(NOTES, f)
            try: old = json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError): old = None
            if old is not None and {k: v for k, v in old.items() if k != "updated"} == doc: continue
            _write_json(p, dict(doc, updated=now)); touched += 1
        for f in os.listdir(NOTES):
            if f.startswith(name + "__") and f.endswith(".json") and f not in want:
                os.remove(os.path.join(NOTES, f)); touched += 1
        # 2. the short references in the pictures' sidecars (and the old full copies, "board_notes", taken out)
        refs = {}
        for nid, n in index.items():
            for path, v in n["pics"].items():
                refs.setdefault(path, []).append({"note": f"{name}/{nid}", "via": sorted(v)})
        idx = os.path.join(BOARDS, name + ".notes-index.json")
        try: old_paths = set(json.load(open(idx, encoding="utf-8")).get("paths", []))
        except (OSError, ValueError): old_paths = set()
        for path in sorted(old_paths | set(refs)):
            try: safe(path)
            except PermissionError: continue
            sp = sidecar(path)
            try: meta = json.load(open(sp, encoding="utf-8"))
            except (OSError, ValueError): meta = {}
            if not isinstance(meta, dict): continue
            mine = sorted(refs.get(path, []), key=lambda e: e["note"])
            cur = meta.get("related_notes", [])
            new = [e for e in cur if not e.get("note", "").startswith(name + "/")] + mine
            legacy = [e for e in meta.get("board_notes", []) if e.get("board") != name]
            if new == cur and len(legacy) == len(meta.get("board_notes", [])): continue
            if new: meta["related_notes"] = new
            else: meta.pop("related_notes", None)
            if legacy: meta["board_notes"] = legacy
            else: meta.pop("board_notes", None)
            if not meta:   # the sidecar existed only to carry references
                if os.path.exists(sp): os.remove(sp)
            else: _write_json(sp, meta)
            touched += 1
        _write_json(idx, {"paths": sorted(refs)}, indent=None)
        _SYNCED[name] = index
        return touched


def save_board(name, board):
    # optimistic lock: the page sends the revision it loaded; a stale save is refused so two tabs never overwrite each other
    with LOCK:
        cur = load_board(name)
        if board.get("revision", 0) != cur.get("revision", 0):
            return 409, cur
        board["revision"] = cur.get("revision", 0) + 1
        board["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(BOARDS, exist_ok=True)
        p = board_path(name); tmp = p + ".tmp"
        json.dump(board, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, p)
        return 200, {"revision": board["revision"], "saved": board["saved"], "mtime": os.stat(p).st_mtime_ns}


# Pages of the canvas (owner 2026-09-29, like Figma): every page is its own board file, only the open one is loaded.
# boards/pages.json keeps their order and names; "main" is the first page from before pages existed.
def load_pages():
    try:
        L = json.load(open(os.path.join(BOARDS, "pages.json"), encoding="utf-8"))["pages"]
    except (OSError, ValueError, KeyError):
        L = []
    return L or [{"id": "main", "title": tr("Page 1", "Страница 1")}]   # a board with no pages yet: its first one in the app's language


def pages_state():
    # every page with its frame count, plus what the library marks: frames on any page, and frames gone from all of them
    out, on, removed = [], set(), set()
    for pg in load_pages():
        b = load_board(pg["id"])
        paths = {i.get("path") for i in b.get("items", {}).values() if i.get("type") != "text" and i.get("path")}
        # the pictures inside an image frame lie on the page too (owner 2026-10-05: «a picture in a frame counts as lying on the
        # board, inside the frame»): the frame's card lists them in pics
        paths |= {p for i in b.get("items", {}).values() if isinstance(i.get("pics"), list) for p in i["pics"] if isinstance(p, str)}
        on |= paths; removed |= set(b.get("removed", {}))
        out.append({**pg, "on": sorted(paths), "removed": sorted(b.get("removed", {}))})
    return {"pages": out, "on": sorted(on), "removed": sorted(removed - on)}


def save_pages(pages):
    with LOCK:
        clean, seen = [], set()
        for pg in pages:
            board_path(pg["id"])   # same id rules as boards
            if pg["id"] not in seen:
                seen.add(pg["id"]); clean.append({"id": pg["id"], "title": (pg.get("title") or "").strip()[:80] or tr("Untitled", "Без названия")})
        if not clean:
            raise PermissionError("no pages")
        # a page taken out of the list keeps its board: moved to boards/_deleted, never erased
        for pg in load_pages():
            if pg["id"] not in seen and os.path.exists(board_path(pg["id"])):
                os.makedirs(os.path.join(BOARDS, "_deleted"), exist_ok=True)
                os.replace(board_path(pg["id"]), os.path.join(BOARDS, "_deleted", f"{pg['id']}-{time.strftime('%y%m%d%H%M%S')}.json"))
        os.makedirs(BOARDS, exist_ok=True)
        p = os.path.join(BOARDS, "pages.json"); tmp = p + ".tmp"
        json.dump({"pages": clean}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    return pages_state()


def _tool(name):
    # the app starts the server without the shell's PATH, Homebrew's tools are looked for where they live
    return shutil.which(name) or next((p for p in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}") if os.path.exists(p)), None)


_PREV_LOCKS, _PREV_GUARD = {}, threading.Lock()
_PREV_SLOTS = threading.BoundedSemaphore(3)   # a grid of 160 PSDs asks for all at once: three Quick Looks at a time, the rest queue
_DUR = {}


def video_seconds(full):
    return video_probe(full)[0]


def video_probe(full):
    """a video's length in seconds, its picture's [width, height] as it is shown (a phone clip turned by 90 degrees swaps them) and the
    codec names of its picture and sound ("h264", "aac"), once per version of the file; one ffprobe for all (the board's info card shows
    them, owner 2026-10-05; the codecs tell the app's Chromium, which has no H.264, to ask for /video), else Spotlight's length"""
    key = (full, os.path.getmtime(full))
    if key not in _DUR:
        sec, wh, vc, ac = None, None, None, None
        probe = _tool("ffprobe")
        try:
            if probe:
                out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height:stream_tags=rotate:stream_side_data=rotation",
                                      "-of", "json", full], capture_output=True, text=True, timeout=20).stdout
                d = json.loads(out or "{}")
                streams = d.get("streams") or []
                st = next((x for x in streams if x.get("codec_type") == "video"), {})
                vc = st.get("codec_name"); ac = next((x.get("codec_name") for x in streams if x.get("codec_type") == "audio"), None)
                if st.get("width") and st.get("height"):
                    turn = st.get("tags", {}).get("rotate") or next((x.get("rotation") for x in st.get("side_data_list", []) if "rotation" in x), 0)
                    wh = [int(st["width"]), int(st["height"])]
                    if abs(int(float(turn or 0))) % 180 == 90: wh.reverse()
                if (d.get("format") or {}).get("duration"):
                    sec = round(float(d["format"]["duration"]), 1)
            else:
                out = subprocess.run(["mdls", "-raw", "-name", "kMDItemDurationSeconds", full], capture_output=True, text=True, timeout=20).stdout
                sec = round(float(out.strip()), 1)
        except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
            pass
        _DUR[key] = (sec, wh, vc, ac)
    return _DUR[key]


def preview(rel):
    """a picture of a file the browser cannot draw (PSD, PSB, AI, TIFF, HEIC, SVG, video), made once per version of the file, 2048 px"""
    src = real(rel); st = os.stat(src)
    if kind_of(rel) == "pdf" and st.st_size:
        return pdf_master(rel, 1)   # PDFKit draws the page, a grey card when nothing can
    if kind_of(rel) == "model": return lib3d.preview(rel, sprite_file)   # a 3D file: its turntable's first view, never Quick Look
    base = os.path.join(THUMBS, re.sub(r"[^A-Za-z0-9._-]", "_", rel) + f".{int(st.st_mtime)}.prev")
    have = lambda: next((base + e for e in (".jpg", ".png") if os.path.exists(base + e)), None)
    if have():
        return have()
    with _PREV_GUARD:
        lock = _PREV_LOCKS.setdefault(base, threading.Lock())
    with lock:   # the grid asks for many sizes of one file at once: one qlmanage, the rest wait for it
        if have():
            return have()
        os.makedirs(THUMBS, exist_ok=True)
        tmp = tempfile.mkdtemp(dir=THUMBS)
        try:
            _PREV_SLOTS.acquire()
            made = None
            empty = st.st_size == 0   # a 0-byte file (two such PSDs in «Lookbook FW27»): Quick Look hangs on it, it gets the grey card at once
            pk = plugin_kinds().get(os.path.splitext(rel)[1].lower()) if not empty else None
            if pk:   # a plugin's kind (html: Dev studio draws the page in Chromium); Quick Look below when it cannot
                try:
                    fn = getattr(plugin_module(pk[1]), "preview", None)
                    if fn: fn(src, os.path.join(tmp, "k.png"))
                    if os.path.isfile(os.path.join(tmp, "k.png")) and os.path.getsize(os.path.join(tmp, "k.png")): made = os.path.join(tmp, "k.png")
                except Exception:
                    pass
            ff = _tool("ffmpeg") if kind_of(rel) == "video" and not empty else None
            if ff:   # a frame a second in, or the first one of a shorter clip
                for at in ("1", "0"):
                    p = os.path.join(tmp, "f.png")
                    try: subprocess.run([ff, "-v", "error", "-y", "-ss", at, "-i", src, "-frames:v", "1", "-vf", "scale='min(2048,iw)':-2", p], capture_output=True, timeout=60)
                    except subprocess.SubprocessError: break
                    if os.path.exists(p) and os.path.getsize(p):
                        made = p; break
            if not made and not empty:
                try: subprocess.run(["qlmanage", "-t", "-s", "2048", "-o", tmp, src], capture_output=True, timeout=60)
                except subprocess.SubprocessError: pass
                made = next((os.path.join(tmp, n) for n in os.listdir(tmp) if n.endswith(".png")), None)
            if not made and not empty:
                try:
                    with Image.open(src) as im:   # Pillow reads TIFF and a PSD saved with its composite even where Quick Look has nothing
                        im.thumbnail((2048, 2048)); im.save(os.path.join(tmp, "p.png")); made = os.path.join(tmp, "p.png")
                except Exception:
                    pass
            if not made:   # nothing could draw it: a grey card, so the grid and the board keep their place; a new version of the file tries again
                im = Image.new("RGB", (640, 640), (58, 58, 62)); made = os.path.join(tmp, "p.png"); im.save(made)
            # a jpeg unless the picture really is see-through: the state folder sits in Dropbox, 169 png previews of «Lookbook FW27» were 500 MB
            with Image.open(made) as im:
                clear = im.mode in ("RGBA", "LA", "PA") and im.getchannel("A").getextrema()[0] < 255
                out = base + (".png" if clear else ".jpg")
                if clear: os.replace(made, out)
                else: im.convert("RGB").save(out, quality=88)
        finally:
            _PREV_SLOTS.release()
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def is_empty(full):
    """a file with no bytes or one this process cannot read: shown, but not taken for a picture (owner 2026-10-06, a board folder of
    111 files had 105 at 0 bytes: Dropbox never brought them down, and the library showed almost nothing). Nothing is downloaded."""
    try:
        return os.path.getsize(full) == 0 or not os.access(full, os.R_OK)
    except OSError:
        return True


def _pdf_base(rel):
    return os.path.join(THUMBS, re.sub(r"[^A-Za-z0-9._-]", "_", rel) + f".{int(os.stat(real(rel)).st_mtime)}")


def pdf_pages_known(rel):
    """the page count if an earlier read saved it (a few bytes beside the thumbnails); the library list never starts a renderer"""
    try:
        d = pdfpages.cached(_pdf_base(rel))
    except OSError:
        return 0
    return d["pages"] if d else 0


_PDF_LOCK, _PDF_GUARD = {}, threading.Lock()


def pdf_info(rel):
    """{pages, ars} of a PDF (ars: width / height of each page), read once per version of the file; {pages: 0, error} when it is empty,
    locked or unreadable. The pages are 1-based everywhere."""
    full = real(rel)
    if is_empty(full):
        return {"pages": 0, "ars": [], "error": "empty"}
    base = _pdf_base(rel); d = pdfpages.cached(base)
    if d:
        return d
    with _PDF_GUARD:
        lock = _PDF_LOCK.setdefault(base, threading.Lock())
    with lock:
        d = pdfpages.cached(base)
        if d:
            return d
        with _PREV_SLOTS:
            try:
                d = pdfpages.read(full)
            except pdfpages.PdfError as ex:
                return {"pages": 0, "ars": [], "error": str(ex)}
        pdfpages.remember(base, d)
        return {"pages": d["pages"], "ars": d.get("ars", [])}


def pdf_master(rel, page=1):
    """page `page` of a PDF drawn as a picture, 2048 px on its long side, once per version of the file (a jpeg: the state folder sits in
    Dropbox). The first call also saves the page count. A grey card when nothing can draw it; a page past the end is the last page."""
    full = real(rel)
    n = (pdf_info(rel).get("pages") or 1) if os.path.getsize(full) else 1
    page = max(1, min(int(page), n)); base = _pdf_base(rel)
    out = f"{base}.pdf{page}.jpg"
    if os.path.exists(out):
        return out
    with _PDF_GUARD:
        lock = _PDF_LOCK.setdefault(out, threading.Lock())
    with lock:
        if os.path.exists(out):
            return out
        os.makedirs(THUMBS, exist_ok=True)
        tmp = tempfile.mkdtemp(dir=THUMBS)
        try:
            _PREV_SLOTS.acquire()
            made = os.path.join(tmp, "p.png")
            try:
                d = pdfpages.read(full, page, made, 2048)
                pdfpages.remember(base, d)
            except pdfpages.PdfError:
                made = None
            if made:
                with Image.open(made) as im:   # a page is drawn on white: the renderer leaves it see-through, and in the display's colours (a profile)
                    im.load(); icc = im.info.get("icc_profile"); im = im.convert("RGBA"); rgb = im.convert("RGB")
                    if icc:   # to sRGB, which is what a browser takes an untagged jpeg for: without it a green page came out grey-green
                        try:
                            from PIL import ImageCms
                            import io
                            rgb = ImageCms.profileToProfile(rgb, ImageCms.ImageCmsProfile(io.BytesIO(icc)), ImageCms.createProfile("sRGB"))
                        except Exception:
                            pass
                    bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(rgb, mask=im.getchannel("A"))
                    bg.save(out + ".tmp", "JPEG", quality=88)
            else:   # a locked or broken PDF: a grey card, so the grid and the board keep their place; a new version of the file tries again
                Image.new("RGB", (640, 640), (58, 58, 62)).save(out + ".tmp", "JPEG", quality=88)
            os.replace(out + ".tmp", out)
        finally:
            _PREV_SLOTS.release()
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def psd_size(full):
    # width and height from the header of a PSD or PSB (big ones take seconds to preview, the canvas needs only the shape)
    with open(full, "rb") as fh:
        head = fh.read(26)
    if head[:4] != b"8BPS":
        return None
    return [int.from_bytes(head[18:22], "big"), int.from_bytes(head[14:18], "big")]


def thumb(rel, size=640, page=1):
    st = os.stat(real(rel))
    pdf = kind_of(rel) == "pdf" and st.st_size > 0
    if pdf and size == 2048:   # the large preview of a page (owner 2026-10-06): the page as drawn
        return pdf_master(rel, page)
    src = (pdf_master(rel, page) if pdf and page > 1 else real(rel) if kind_of(rel) == "image" and st.st_size else preview(rel))   # an empty picture: the grey card
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", rel) + f".{int(st.st_mtime)}" + (f".p{page}" if pdf and page > 1 else "")   # page 1 keeps the key of a plain thumbnail
    key = f"{stem}.{size}.jpg"
    out = os.path.join(THUMBS, key)
    if not os.path.exists(out) and not thumbcache.adopt(key):   # one still in the old folder while it moves
        # small thumbs come from the 640 one when it exists: opening a 4K png for a 320 px card is the slow part
        big = os.path.join(THUMBS, f"{stem}.640.jpg")
        mid = os.path.join(THUMBS, f"{stem}.320.jpg")
        im = Image.open(mid if size < 320 and os.path.exists(mid) else big if size < 640 and os.path.exists(big) else src).convert("RGB")
        im.thumbnail((size, size * 2))
        im.save(out, quality=82)
    return thumbcache.used(out)   # handed out: the ceiling keeps it longer


# 3D files in the library (owner 2026-10-06: «Open media library, where everything is already filtered to 3D files, and on hover they
# turn»), listed here for the «3D» filter and, since 2026-10-07, in scan() as files of their folders (lib3d.py). A project model is one entry.
# Each file has a turntable: one sheet of N views around the vertical axis (a webp, cols x rows of cell px) that a page with three.js
# draws once and posts here (the plugin's sprites.js); it is kept like a thumbnail, per version of the file, in _thumbs. The sheet
# turns on hover without a WebGL context per tile, its first view is the still picture.
# STEP and IGES (owner 2026-10-06: «convert a STEP file once to a 3D model with FreeCAD»): listed like the rest; the 3D plugin's cad.py turns
# each into a glb once, in the app's cache, and its turntable is drawn from that glb. The state «converting…» is the page's, not a field here.
MODEL_EXT = (".glb", ".gltf", ".obj", ".stl", ".fbx", ".step", ".stp", ".iges", ".igs")
MODEL_SKIP = ("3d/scenes", "3d/shots", "3d/converted")   # a scene's own scene.glb, snapshots, a converted copy of a file listed already
SPRITE_MAX = 32 * 1024 * 1024
_M3 = {"v": None, "items": None, "t": 0.0}
_M3_LOCK = threading.Lock()


def _model_version(full):
    """a model's version: its file's time; for model.json the newest of its folder's files (a part changed)"""
    if os.path.basename(full) != "model.json": return int(os.path.getmtime(full))
    d = os.path.dirname(full)
    return int(max(os.path.getmtime(os.path.join(d, n)) for n in os.listdir(d) if os.path.isfile(os.path.join(d, n))))


def _sprite_base(rel, version):
    return os.path.join(THUMBS, re.sub(r"[^A-Za-z0-9._-]", "_", rel) + f".{version}.sprite")


def sprite_info(rel, version):
    """the turntable of a file as the page needs it ({n, cols, cell, v}), or None while nobody has drawn it"""
    try: meta = json.load(open(_sprite_base(rel, version) + ".json", encoding="utf-8"))
    except (OSError, ValueError): return None
    return meta if isinstance(meta, dict) and os.path.exists(_sprite_base(rel, version) + ".webp") else None


def _model_item(rel, full, titles_, folder, born):
    ext = os.path.splitext(rel)[1].lower()
    st = os.stat(full); ver = _model_version(full); name = os.path.splitext(os.path.basename(rel))[0]
    out = {"name": name, "path": rel, "folder": folder, "mtime": int(st.st_mtime), "born": born, "size": st.st_size, "kind": "model",
           "ext": ext[1:].upper(), "aspect": "1:1", "tags": [], "feedback": {}, "questions": [], "ver": ver, "sprite": sprite_info(rel, ver)}
    if ext == ".json":   # model.json: the model's own title, the id its folder is named by
        try: title = json.load(open(full, encoding="utf-8")).get("title")
        except (OSError, ValueError, AttributeError): title = None
        out.update(name=str(title or os.path.basename(os.path.dirname(rel))), ext="MODEL", model=os.path.basename(os.path.dirname(rel)))
        out["size"] = sum(os.path.getsize(os.path.join(os.path.dirname(full), n)) for n in os.listdir(os.path.dirname(full)) if os.path.isfile(os.path.join(os.path.dirname(full), n)))
    t = titles_
    out["title"] = "В корне доски" if folder == "." else t.get(folder, t.get(folder.split("/")[0], folder))
    return out


def scan3d():
    """every 3D file of the library, by the same rules as scan() for the folders it looks in"""
    items, t = [], titles()
    for root, dirs, files in os.walk(W):
        rel_root = os.path.relpath(root, W).replace(os.sep, "/")
        if rel_root == ".":
            dirs[:] = [d for d in dirs if d not in SKIP]
        if os.path.realpath(root) == HERE or any(part in SKIP for part in rel_root.split("/")):
            dirs[:] = []; continue
        if rel_root.split("/")[0] in ("html", "frames") or (HIDE_NAMED and HIDE_NAMED.intersection(rel_root.split("/"))) \
           or any(rel_root == h or rel_root.startswith(h + "/") for h in HIDE) or (HIDE_PREFIXES and os.path.basename(rel_root).startswith(HIDE_PREFIXES)):
            dirs[:] = []; continue
        if any(rel_root == s or rel_root.startswith(s + "/") for s in MODEL_SKIP):
            dirs[:] = []; continue
        whole = rel_root.startswith("3d/models/") and "model.json" in files   # a project model: one entry for its folder
        names = ["model.json"] if whole else [f for f in files if f.lower().endswith(MODEL_EXT) and not (SKIP_FILES and f.startswith(SKIP_FILES))]
        for f in names:
            full = os.path.join(root, f)
            try: items.append(_model_item(f if rel_root == "." else f"{rel_root}/{f}", full, t, rel_root, int(getattr(os.stat(full), "st_birthtime", os.path.getmtime(full)))))
            except OSError: continue
    first = {}
    for i in items: first[i["folder"]] = min(first.get(i["folder"], i["born"]), i["born"])
    for i in items: i["start"] = time.strftime("%y%m%d%H%M", time.localtime(first[i["folder"]]))
    items.sort(key=lambda i: (-first[i["folder"]], i["folder"], i["name"]))
    return items


def models3d(fresh=False):
    """the list, kept while the library's folders do not change (and at most a minute), with the turntables as they stand now"""
    with _M3_LOCK:
        key = (LIB_SIG["sig"], LIB_GEN[0])
        if fresh or _M3["items"] is None or _M3["v"] != key or time.time() - _M3["t"] > 60:
            _M3.update(items=scan3d(), v=key, t=time.time())
        items = [dict(i) for i in _M3["items"]]
    for i in items: i["sprite"] = sprite_info(i["path"], i["ver"])   # a turntable drawn since the walk
    return ui_items(items)


def models3d_info(paths):
    """the same entry for given paths (a card's recent files), None for one that is gone: no walk of the library"""
    out, t = [], titles()
    for rel in paths[:60]:
        try:
            rel = resolve(rel); full = safe(rel)
            if not os.path.isfile(full) or not (rel.lower().endswith(MODEL_EXT) or os.path.basename(rel) == "model.json"): raise FileNotFoundError(rel)
            out.append(ui_items([_model_item(rel, full, t, os.path.dirname(rel) or ".", int(os.path.getmtime(full)))])[0])
        except (OSError, PermissionError, ValueError): out.append(None)
    return out


def save_sprite(rel, data, n, cols, cell):
    """a turntable drawn by a page: a png sheet of n views, cols across, cell px each; kept as webp (the browser's own encoder is not the same
    everywhere: WebKit has none) beside its numbers; the sheets of older versions of the file go"""
    rel = resolve(rel); full = safe(rel)
    if not (rel.lower().endswith(MODEL_EXT) or os.path.basename(rel) == "model.json") or not os.path.isfile(full): raise ValueError("not a 3D file of the library")
    rows = -(-n // cols)
    if not (2 <= n <= 120 and 1 <= cols <= 16 and 32 <= cell <= 512): raise ValueError("bad sheet numbers")
    with Image.open(io.BytesIO(data)) as im:
        if im.size != (cols * cell, rows * cell): raise ValueError(f"the sheet is {im.size[0]}x{im.size[1]}, {cols * cell}x{rows * cell} expected")
        im = im.convert("RGBA")
    ver = _model_version(full); base = _sprite_base(rel, ver)
    os.makedirs(THUMBS, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", rel) + "."
    for old in os.listdir(THUMBS):   # one version of a file's turntable is kept
        if old.startswith(stem) and ".sprite" in old and not old.startswith(os.path.basename(base)): os.remove(os.path.join(THUMBS, old))
    tmp = base + ".tmp.webp"
    im.save(tmp, "WEBP", quality=80, alpha_quality=90, method=4); os.replace(tmp, base + ".webp")
    for still in os.listdir(THUMBS):   # the stills cut from an earlier sheet of this version
        if re.fullmatch(re.escape(os.path.basename(base)) + r"\.[0-9]+\.webp", still): os.remove(os.path.join(THUMBS, still))
    meta = {"n": n, "cols": cols, "cell": cell, "v": ver}
    with open(base + ".json.tmp", "w", encoding="utf-8") as fh: json.dump(meta, fh)
    os.replace(base + ".json.tmp", base + ".json")
    return dict(meta, bytes=os.path.getsize(base + ".webp"))


def sprite_file(rel, size=0):
    """the sheet's webp, or with size the first view (the still picture) cut from it; None while there is no sheet"""
    rel = resolve(rel); full = safe(rel); ver = _model_version(full); base = _sprite_base(rel, ver)
    meta = sprite_info(rel, ver)
    if not meta: return None
    if not size: return base + ".webp"
    out = f"{base}.{size}.webp"
    if not os.path.exists(out):
        with Image.open(base + ".webp") as im:
            im.load(); im.crop((0, 0, meta["cell"], meta["cell"])).resize((size, size), Image.LANCZOS).save(out + ".tmp.webp", "WEBP", quality=82, alpha_quality=90)
        os.replace(out + ".tmp.webp", out)
    return out


def aliases():
    # old paths of frames that moved (the _favs cleanup, 2026-09-29): boards and links made before still resolve
    try:
        L = json.load(open(os.path.join(HERE, "_favs-moved.json"), encoding="utf-8"))
        base = {e["from"]: e["to"] for e in L.get("moved_back", []) + L.get("hearted_originals", [])}
    except (OSError, ValueError, KeyError, TypeError):
        base = {}
    # and every move of «Разложить по папкам как на доске» (owner 2026-10-05): old links, notes, prompts and other boards still open
    # the pictures; an undone run turns its moves back
    return foldersync.aliases(base)


# ---- folders as on the board (owner 2026-10-05, foldersync.py): the board is the source of truth, the files follow it. Off by default:
# a run only when the owner presses «Разложить» in the library (or an agent with the owner's word), or after board saves when the owner
# switched on «Всегда держать папки как на доске». Every run is journalled in <state>/layout-sync and the last one can be undone.
_LAYOUT = {"timer": None, "error": None}


def layout_env():
    return foldersync.Env(skip=SKIP, hide=HIDE, media=MEDIA_EXT, images=EXT, mounts=list(MOUNTS), root_shown=ROOT_FILES, aliases=aliases,
                          hide_named=HIDE_NAMED, hide_prefixes=HIDE_PREFIXES)


def layout_state():
    return {"auto": foldersync.auto_on(), "last": foldersync.last_run(), "error": _LAYOUT["error"], "running": foldersync.RUN.locked()}


def _layout_after(j, back=False):
    """what follows the files: sha1 index, thumbnails, the notes' files, the pages (live reload)"""
    pairs = [(m["from"], m["to"]) for m in j.get("moves", [])] + [(f, t) for m in j.get("moves", []) for f, t, w in m.get("side", []) if w == "move"]
    if back: pairs = [(b, a) for a, b in pairs]
    try: dedup.rekey(pairs)
    except Exception: pass
    foldersync.thumbs_rekey(THUMBS, pairs)
    for page in j.get("boards", []) or (j.get("undo") or {}).get("boards", []):
        _SYNCED.pop(page, None)
        try: sync_notes(page)
        except Exception: pass
    lib_dirty(); LIB_SIG["v"] += 1


def layout_apply(who="owner", auto=None, wait=0):
    env = layout_env()
    got = foldersync.RUN.acquire(timeout=wait) if wait else foldersync.RUN.acquire(blocking=False)
    if not got: raise foldersync.Failed(tr("a layout is already running", "раскладка уже идет"))
    try:
        pre = foldersync.plan(env)
        if not pre["moves"] and not pre["fixes"]:   # nothing to do: the lock is not taken (a save in the auto mode, 3 s of plan on Studio North)
            if auto is not None: foldersync.set_auto(auto)
            return {"id": "", "status": "nothing", "moves": []}
        names = sorted({os.path.basename(m["from"]) for m in pre["moves"]})
        cands = foldersync.json_candidates(env, names) if names else []   # read outside the lock: board saves do not wait for it
        with LOCK:
            j = foldersync.apply(env, who, cands, foldersync.plan(env))   # planned again under the lock: the boards may have changed
        if j.get("status") == "done": _layout_after(j)
        if auto is not None: foldersync.set_auto(auto)
        _LAYOUT["error"] = None
        return j
    finally:
        foldersync.RUN.release()


def layout_undo():
    if not foldersync.RUN.acquire(timeout=30): raise foldersync.Failed(tr("a layout is already running", "раскладка уже идет"))
    try:
        with LOCK:
            j = foldersync.undo_last(layout_env())
        was = foldersync.auto_on()
        if was: foldersync.set_auto(False)   # left on, the next save would lay the files out again
        _layout_after(j, back=True)
        return dict(j, auto_was=was)
    finally:
        foldersync.RUN.release()


def _layout_auto():
    try:
        if foldersync.auto_on(): layout_apply("auto", wait=120)
    except Exception as ex:
        _LAYOUT["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"


def layout_kick():
    """after a save that may change groups, titles, pages or notes: a run a few seconds after the last one, only in the auto mode"""
    if not foldersync.auto_on(): return
    if _LAYOUT["timer"]: _LAYOUT["timer"].cancel()
    t = threading.Timer(4.0, _layout_auto); t.daemon = True; _LAYOUT["timer"] = t; t.start()


# Pictures the owner pastes (⌘V) or drops onto the canvas (owner 2026-09-30: "to build moodboards and comment on them").
# One folder for everything added by hand, a subfolder per day: added/260930/174012-name.jpg, with a sidecar json saying where it came from.
# jpeg, png and webp are kept byte for byte; anything else Pillow can open is stored as png. The same bytes added twice reuse the first file.
ADDED = "added"
MAX_UPLOAD = 80 * 1024 * 1024


def _added_sha():
    out = {}
    for root, _d, files in os.walk(os.path.join(W, ADDED)):
        for f in files:
            if f.endswith(".json"):
                try:
                    m = json.load(open(os.path.join(root, f), encoding="utf-8")); out[m["sha1"]] = m["path"]
                except (OSError, ValueError, KeyError, TypeError):
                    pass
    return out


def add_image(data, name="", url=""):
    if not data:
        raise ValueError("empty")
    sha = hashlib.sha1(data).hexdigest()
    with LOCK:
        known = _added_sha().get(sha) or dedup.known([sha]).get(sha)   # anywhere in the library, not only among pasted pictures
        if known and os.path.exists(real(known)):
            im = Image.open(real(known)); return {"path": known, "ar": im.width / im.height, "again": True}
        try:
            im = Image.open(io.BytesIO(data)); im.load()
        except Exception:
            raise ValueError(tr("not an image, or a format that does not open (jpg, png, webp, gif and tiff work)",
                                "это не картинка или формат не открывается (подходят jpg, png, webp, gif, tiff)"))
        fmt = (im.format or "").upper()
        ext = {"JPEG": ".jpg", "MPO": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(fmt)
        if not ext:   # gif, tiff, bmp, heic (if a plugin is there): store the first frame as png
            buf = io.BytesIO(); (im if im.mode in ("RGB", "RGBA", "L", "LA") else im.convert("RGBA")).save(buf, "PNG"); data, ext = buf.getvalue(), ".png"
        stem = re.sub(r"[^a-z0-9а-яё_-]+", "-", os.path.splitext(os.path.basename(name or url.split("?")[0]))[0].lower()).strip("-")[:40] or "image"
        day = time.strftime("%y%m%d"); d = os.path.join(W, ADDED, day); os.makedirs(d, exist_ok=True)
        base = time.strftime("%H%M%S") + "-" + stem; n = 2
        while os.path.exists(os.path.join(d, base + ext)): base = base.rsplit("~", 1)[0] + f"~{n}"; n += 1
        open(os.path.join(d, base + ext), "wb").write(data)
        rel = f"{ADDED}/{day}/{base}{ext}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        # what is known about a pasted picture is said in "prompt" and "model", so its card is not empty (owner 2026-10-03); the owner
        # knows the rest and may add it
        # written in the app's language at the moment of pasting (owner 2026-10-06: two languages); the owner's data from then on
        if lang() == "ru":
            what = f"вставлено владельцем на холст {now[:16]}" + (f" со страницы {url}" if url else f" из файла {name}" if name and name != "image.png" else " из буфера обмена")
        else:
            what = f"pasted on the canvas by the owner {now[:16]}" + (f" from the page {url}" if url else f" from the file {name}" if name and name != "image.png" else " from the clipboard")
        meta = {"source": "owner", "how": "url" if url else "file", "added": now, "original_name": name, "url": url,
                "sha1": sha, "path": rel, "size": [im.width, im.height], "model": tr("pasted by the owner", "вставлено владельцем"), "prompt": what}
        _write_json(os.path.join(d, base + ".json"), meta)
        return {"path": rel, "ar": im.width / im.height}


# Plugins (owner 2026-10-03: modules such as 3D objects or an editor live outside this repository). A plugin is a folder with
# manifest.json {"title", "canvas": "<module.js>"} in HYIMG_PLUGINS (paths split by ":") or ~/Library/Application Support/Hyimg/plugins
# (a symlink to the plugin's own repository is fine). The canvas imports its module, which registers new kinds of cards.
CTYPES = {".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".json": "application/json", ".css": "text/css",
          ".wasm": "application/wasm", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".htm": "text/html; charset=utf-8", ".woff2": "font/woff2", ".gif": "image/gif",
          ".glb": "model/gltf-binary", ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".gltf": "model/gltf+json", ".bin": "application/octet-stream", ".hdr": "application/octet-stream", ".html": "text/html; charset=utf-8"}


def plugins():
    # the tests (tests/conftest.py sets HY_TEST_ONLY_PLUGINS) see only the plugins they name, never what is installed on the machine:
    # the installed ones are links to the plugins' working copies, so a test's result depended on someone's unfinished work there
    user = [] if os.environ.get("HY_TEST_ONLY_PLUGINS") == "1" else [os.path.expanduser("~/Library/Application Support/Hyimg/plugins")]
    roots = [r for r in os.environ.get("HYIMG_PLUGINS", "").split(os.pathsep) if r] + user
    out = {}
    for root in roots:
        if not os.path.isdir(root): continue
        for n in sorted(os.listdir(root)):
            d = os.path.realpath(os.path.join(root, n)); m = os.path.join(d, "manifest.json")
            if n in out or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", n) or not os.path.isfile(m): continue
            try: man = json.load(open(m, encoding="utf-8"))
            except (OSError, ValueError): continue
            if isinstance(man, dict): out[n] = (d, man)
    return out


def plugin_file(name, rel):
    d, _m = plugins()[name]
    full = os.path.realpath(os.path.join(d, rel))
    if not full.startswith(d + os.sep) or not os.path.isfile(full): raise PermissionError(rel)
    return full


# A plugin's server side (owner 2026-10-05: the frames plugin's content-aware fill and subject mask move into Hyimg's server, without its
# python written into this file). manifest.json "server": "<module.py>" in the plugin's folder; the module has ROUTES = {name: fn},
# fn(body: bytes, query: dict) -> (content type, bytes) or (status, content type, bytes), served at POST /api/plugin/<plugin>/<name>.
# The module loads on its first request and stays in this process (a model it keeps loads once); a newer file is loaded again.
_PLUGIN_SRV, _PLUGIN_SRV_LOCK = {}, threading.Lock()


def plugin_module(name):   # the plugin's server module, loaded once per version of its file (a kind's preview() asks for it too)
    _d, man = plugins()[name]
    if not isinstance(man.get("server"), str): raise KeyError(name)
    full = plugin_file(name, man["server"]); key = (full, os.path.getmtime(full))
    with _PLUGIN_SRV_LOCK:
        if name not in _PLUGIN_SRV or _PLUGIN_SRV[name][0] != key:
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"hyimg_plugin_{re.sub(r'[^a-z0-9_]', '_', name)}", full)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            _PLUGIN_SRV[name] = (key, mod)
        return _PLUGIN_SRV[name][1]


def plugin_routes(name):
    routes = getattr(plugin_module(name), "ROUTES", None)
    if not isinstance(routes, dict): raise KeyError(name)
    return routes


# Library pages shown sandboxed (owner 2026-10-06, Dev studio: «Dev mode is for HTML, and on the left the HTML tree»). A plugin shows a
# library HTML page in <iframe sandbox="allow-scripts"> without allow-same-origin: the page runs with an opaque origin ("null"), so it
# never reads the app's pages, storage or API (a write from it has Origin null and request_allowed refuses it). Its css, scripts,
# fonts and pictures come by relative links from the same address, /sandbox/<key>/<library path>. A font or a module script from an
# opaque origin is a CORS request with «Origin: null»: it is let in only here, only with the key, which the app's own pages get from
# /api/sandbox, so another site's sandboxed frame cannot read the library. Read-only, GET only; a path with .., an absolute one or one
# outside the library is refused (safe()). An HTML page is sent with «CSP: sandbox», so it stays sandboxed even opened alone; with
# ?hyp=<plugin> it gets that plugin's manifest "pageScript" as the first script of its <head> (Dev studio's inspector), served at
# /sandbox/<key>/~hyp/<plugin> («~» starts no library path). The file itself is never written.
import hmac, secrets
SANDBOX_KEY = secrets.token_urlsafe(18)
SANDBOX_TYPES = {".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
                 ".avif": "image/avif", ".xml": "application/xml", ".map": "application/json", ".mp3": "audio/mpeg", ".wav": "audio/wav"}


def sandbox_inject(body, plugin):
    """the page with <script src=…/~hyp/<plugin>> first in its <head> (after <head>, else after <html>, else in front)"""
    tag = f'<script src="/sandbox/{SANDBOX_KEY}/~hyp/{plugin}"></script>'.encode()
    m = re.search(rb"<head\b[^>]*>", body[:65536], re.I) or re.search(rb"<html\b[^>]*>", body[:65536], re.I)
    at = m.end() if m else 0
    return body[:at] + tag + body[at:]


def save_snapshot(data, name, folder, meta):
    """a picture made on the canvas by a plugin (a frozen 3D view): <folder>/<YYMMDD>/<HHMMSS>-<name>.png with the plugin's json beside it"""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_/-]*", folder or "") or ".." in folder or folder.split("/")[0] in SKIP:
        raise ValueError("bad folder")
    im = Image.open(io.BytesIO(data)); im.load()
    stem = re.sub(r"[^a-z0-9_-]+", "-", (name or "shot").lower()).strip("-")[:40] or "shot"
    with LOCK:
        day = time.strftime("%y%m%d"); d = os.path.join(W, folder, day); os.makedirs(d, exist_ok=True)
        base = time.strftime("%H%M%S") + "-" + stem; n = 2
        while os.path.exists(os.path.join(d, base + ".png")): base = base.rsplit("~", 1)[0] + f"~{n}"; n += 1
        buf = io.BytesIO(); im.save(buf, "PNG"); open(os.path.join(d, base + ".png"), "wb").write(buf.getvalue())
        rel = f"{folder}/{day}/{base}.png"
        doc = dict(meta if isinstance(meta, dict) else {}, path=rel, size=[im.width, im.height], added=time.strftime("%Y-%m-%d %H:%M:%S"))
        _write_json(os.path.join(d, base + ".json"), doc)
    return {"path": rel, "ar": im.width / im.height}


PLUGIN_DATA = re.compile(r"3d/[^\x00]+\.(json|glb)|3d/[^\x00]+/\.posters/[A-Za-z0-9_-]+\.(jpg|png)"
                         r"|html/[^\x00]+\.(html|css|js|json|svg|png|jpg)"   # HTML frames (Hyimg-frames): a page and its files under html/
                         # image frames (Hyimg-frames, owner 2026-10-05): each frame is one folder frames/<stamp>/ with its document, its render
                         # and the masks and painted layers as png; nothing else, and nothing outside its folder (the pictures in it are never written).
                         # Each Save is a new version beside the old ones (frame.<n>.json, render.<n>.png, <layer>.<n>.png), so undo on the
                         # board finds the version it goes back to (owner 2026-10-05); the plugin keeps the last 10
                         r"|frames/[A-Za-z0-9_-]+/(frame(\.[0-9]{1,6})?\.json|render(\.[0-9]{1,6})?\.png|(masks|layers)/[A-Za-z0-9_-]+(\.[0-9]{1,6})?\.png)")
FRAME_MAX = 400 * 1024 * 1024   # an image frame's render at 8000 × 8000 px is a png of 100-200 MB


_STILL = threading.Lock()


def html_still(rel, w, h, port):
    """a still of an HTML frame at its viewport (w × h css px): <folder>/.stills/<name>-<w>x<h>.png next to the page. Chromium from
    Playwright runs its scripts; without it Quick Look draws the page without them. One at a time: each starts a browser."""
    full = safe(resolve(rel))
    if not full.lower().endswith((".html", ".htm")): raise ValueError("not an html page")
    w, h = max(200, min(4000, int(w))), max(200, min(8000, int(h)))
    d, base = os.path.split(rel)
    out_rel = (d + "/" if d else "") + f".stills/{os.path.splitext(base)[0]}-{w}x{h}.png"
    out = os.path.join(W, out_rel); os.makedirs(os.path.dirname(out), exist_ok=True)
    with _STILL:
        tmp = out + ".tmp.png"
        try:
            subprocess.run([sys.executable, os.path.join(CODE_DIR, "render_html.py"), f"http://127.0.0.1:{port}/lib/" + urllib.parse.quote(rel), str(w), str(h), tmp],
                           capture_output=True, timeout=90, check=True)
        except (OSError, subprocess.SubprocessError):
            qd = tempfile.mkdtemp(dir=os.path.dirname(out))
            try:
                subprocess.run(["qlmanage", "-t", "-s", str(max(w, h)), "-o", qd, full], capture_output=True, timeout=60)
                made = next((os.path.join(qd, n) for n in os.listdir(qd) if n.endswith(".png")), None)
                if not made: raise ValueError("no still")
                os.replace(made, tmp)
            finally:
                shutil.rmtree(qd, ignore_errors=True)
        os.replace(tmp, out)
    return {"path": out_rel, "mtime": os.path.getmtime(out)}


# Settings of the whole app (owner 2026-10-04: «the theme must not change with the project, the settings are one for the whole app»).
# Each project is its own address, so a page's localStorage was per project. The settings below live in one file beside the app's
# catalog, every project's server reads and writes it; /ui/settings.js puts them into localStorage before a page reads anything
# and sends a change of one of them back. What belongs to a project (its camera, page, folder, filters, clipboard) stays in the page.
# The Mac app names the file (beside projects.json); a server started without it (tests, by hand) keeps its own in its state folder,
# so a test never changes the owner's settings.
SETTINGS = os.environ.get("HYIMG_SETTINGS") or os.path.join(HERE, "app-settings.json")
APP_KEYS = r"^cv\.(lang|theme|ui|bg|grain|dotsv|dotsgl|lod|glass|shadow|shape|paperDark|paperLight|paperv|notesize|notecolor|nolib|histTab|m3\..+)$|^(view|lw|fw|ftree|notesOn|autonext|rej|lwide|lmode|lsize)$"


def settings_read():
    try:
        d = json.load(open(SETTINGS, encoding="utf-8"))
        return {k: str(v) for k, v in d.items() if re.match(APP_KEYS, k) and v is not None} if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def settings_write(change):
    """merges {key: value | null}; one writer at a time across the servers of every project (a lock file beside it)"""
    change = {k: (None if v is None else str(v)[:2000]) for k, v in change.items() if isinstance(k, str) and re.match(APP_KEYS, k)}
    if not change: return settings_read()
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        cur = settings_read()
        for k, v in change.items():
            if v is None: cur.pop(k, None)
            else: cur[k] = v
        tmp = SETTINGS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(cur, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, SETTINGS)
    return cur


def lang():
    """the interface's language, the app's setting cv.lang (owner 2026-10-06: «make 2 versions, Russian and English, switchable in
    settings»): "en" by default, "ru" when chosen"""
    return "ru" if settings_read().get("cv.lang") == "ru" else "en"


def tr(en, ru):
    """a text the server makes for the interface (a toast, an error, a library collection's name) in the app's language"""
    return ru if lang() == "ru" else en


# the imported modules' texts for the interface (foldersync's reasons and errors, history's and events' labels) in the same language
foldersync.tr = history.tr = events.tr = tr

# The library's own names in /api/items: the scan keeps them in Russian (its list is cached in memory and on disk, and a language
# switch must not wait for a new scan), the answer puts them into the app's language: the collections of the files in the board's
# folder itself and of the pasted pictures. The engine tags tags.py names itself stay as they are: they are the library's filter ids
# (a saved filter keeps them), the pages show them in the app's language
LIB_NAMES = {"В корне доски": "Board root", "Добавлено вручную (вставка и перетаскивание на холст)": "Added by hand (pasted or dropped on the canvas)"}


def ui_items(items):
    if lang() == "ru": return items
    for i in items:   # copies from scan_cached: the cached list keeps its words
        t = LIB_NAMES.get(i.get("title"))
        if t: i["title"] = t
    return items


# Copy / paste properties (owner 2026-10-06, canvas.html «Copy properties ›»): the clipboard goes from project to project, so it is one
# file beside the app's settings (a server started without them keeps its own beside its own settings, as tests do); the presets are
# the project's, presets.json in its state folder, where hy.py reads them too. Both are JSON at fixed places, size-capped.
PROPS_CLIP = os.path.join(os.path.dirname(os.path.abspath(SETTINGS)), "props-clipboard.json")


PROPS_FILES = PROPS_CLIP[:-5] + "-files"   # the bytes of the files a copied value refers to (a mask's png), by their hash


def props_files_keep(paths):
    """a copy that refers to library files (a kind's files(value), canvas.html copyProps): their bytes beside the clipboard, so a board of
    another project can have them; {path: blob name}. Only what this project's library holds, at most 64 MB a file"""
    out = {}
    os.makedirs(PROPS_FILES, exist_ok=True)
    for rel in paths[:50]:
        try: full = safe(resolve(str(rel)))
        except (PermissionError, OSError): continue
        if not os.path.isfile(full) or os.path.getsize(full) > 64 << 20: continue
        data = open(full, "rb").read(); name = hashlib.sha1(data).hexdigest() + os.path.splitext(full)[1].lower()
        dst = os.path.join(PROPS_FILES, name)
        if not os.path.exists(dst):
            with open(dst + ".tmp", "wb") as fh: fh.write(data)
            os.replace(dst + ".tmp", dst)
        out[str(rel)] = name
    keep = set(out.values())   # only the last copy's files stay
    for f in os.listdir(PROPS_FILES):
        if f not in keep and not f.endswith(".tmp"):
            try: os.remove(os.path.join(PROPS_FILES, f))
            except OSError: pass
    return out


def props_files_take():
    """the clipboard's files into this project's library before a paste: the same path when it is free or already holds the same bytes,
    else the same name with the bytes' hash; {path in the clipboard: path here}. Written like a plugin's data (save_plugin_file: only its
    folders, so a value can bring nothing else)"""
    try: c = json.load(open(PROPS_CLIP, encoding="utf-8"))
    except (OSError, ValueError): return {}
    out = {}
    for rel, name in (c.get("files") or {}).items():
        src = os.path.join(PROPS_FILES, os.path.basename(str(name)))
        if not os.path.isfile(src): continue
        data = open(src, "rb").read()
        try: full = safe(rel)
        except (PermissionError, OSError): full = None
        if full and os.path.isfile(full) and open(full, "rb").read() == data: out[rel] = rel; continue
        dst = rel if full is None or not os.path.exists(full) else f"{os.path.splitext(rel)[0]}-{str(name)[:8]}{os.path.splitext(rel)[1]}"
        try:
            have = safe(dst)
            if not (os.path.isfile(have) and open(have, "rb").read() == data): save_plugin_file(dst, data); lib_dirty()
            out[rel] = dst
        except (PermissionError, ValueError, OSError): continue
    return out


def presets_path():
    return os.path.join(HERE, "presets.json")


def presets_read():
    try: L = json.load(open(presets_path(), encoding="utf-8")).get("presets", [])
    except (OSError, ValueError, AttributeError): L = []
    return [p for p in L if isinstance(p, dict) and isinstance(p.get("name"), str) and isinstance(p.get("kinds"), dict)]


def settings_js():
    return """// the app's settings (server.py SETTINGS), into localStorage before the page reads it; a change of one of them goes back
(() => {
  const S = %s, U = new RegExp(%s), ls = window.localStorage, P = Storage.prototype, set = P.setItem, rm = P.removeItem;
  // the file decides: what it has is set, an app setting it does not have goes back to the page's default, in every project alike;
  // a change this page made and the server has not confirmed yet (a reload right after it) wins and is sent again
  const PK = "hy.settings.pending"; let P0 = {}; try { P0 = JSON.parse(ls.getItem(PK) || "{}") || {}; } catch {}
  try {
    for (const k of Object.keys(S)) set.call(ls, k, S[k]);
    for (const k of Object.keys(P0)) if (U.test(k)) { if (P0[k] === null) rm.call(ls, k); else set.call(ls, k, P0[k]); }
    for (const k of Object.keys(ls)) if (U.test(k) && !(k in S) && !(k in P0)) rm.call(ls, k);
  } catch {}
  let pend = { ...P0 }, t = 0;
  const keep = () => { try { const all = JSON.parse(ls.getItem(PK) || "{}") || {}; Object.assign(all, pend); set.call(ls, PK, JSON.stringify(all)); } catch {} };
  const flush = () => { t = 0; const sent = pend; pend = {}; if (!Object.keys(sent).length) return;
    fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sent), keepalive: true })
      .then(r => { if (!r.ok) return; try { const all = JSON.parse(ls.getItem(PK) || "{}") || {}; for (const k of Object.keys(sent)) if (all[k] === sent[k]) delete all[k];
        if (Object.keys(all).length) set.call(ls, PK, JSON.stringify(all)); else rm.call(ls, PK); } catch {} }).catch(() => {}); };
  const send = (k, v) => { if (!U.test(k)) return; pend[k] = v; keep(); if (!t) t = setTimeout(flush, 250); };
  if (Object.keys(pend).length) t = setTimeout(flush, 0);
  P.setItem = function (k, v) { set.call(this, k, v); if (this === ls) send(k, String(v)); };
  P.removeItem = function (k) { rm.call(this, k); if (this === ls) send(k, null); };
  addEventListener("pagehide", () => { if (t) { clearTimeout(t); flush(); } });
  // changed in another project while this one waited: taken when it comes back to the front
  const pull = async () => {
    try {
      const now = await (await fetch("/api/settings", { cache: "no-store" })).json(); let changed = false;
      for (const k of Object.keys(now)) if (ls.getItem(k) !== now[k]) { set.call(ls, k, now[k]); changed = true; }
      if (changed && typeof window.hyimgSettingsChanged === "function") window.hyimgSettingsChanged();
    } catch {}
  };
  addEventListener("focus", pull); document.addEventListener("visibilitychange", () => { if (!document.hidden) pull(); });
  window.hyimgSettingsPull = pull;   // the app calls it after a change on Home and when it brings a board to the front
})();
""" % (json.dumps(settings_read(), ensure_ascii=False), json.dumps(APP_KEYS))


def save_plugin_file(rel, data):
    """plugin data in the library (a 3D scene file the canvas edits and an agent applies in Blender, its geometry, the still view of a
    3D card in the scene's .posters folder): only under 3d/, json or glb, or a jpg or png poster. An existing file is written in place: its folder keeps its time, so turning a 3D camera on the canvas (a write every
    few tenths of a second) does not make the library rescan, and the list cache stays (no lib_dirty)."""
    if not PLUGIN_DATA.fullmatch(rel or "") or ".." in rel.split("/") or rel.startswith("/"):
        raise ValueError("only 3d/<...>.json or .glb, html/<...>, frames/<stamp>/(frame[.n].json|render[.n].png|masks/*.png|layers/*.png)")
    if rel.endswith(".json"): json.loads(data)
    poster = "/.posters/" in rel
    full = os.path.realpath(os.path.join(W, rel))
    if not full.startswith(os.path.realpath(W) + os.sep): raise PermissionError(rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with LOCK:
        if rel.endswith(".json"):   # in place: its folder keeps its time; a reader that catches it half written reads it again
            with open(full, "wb") as f: f.write(data)
        else:   # a model or a still is read by Blender and the pages: whole or not at all
            with open(full + ".tmp", "wb") as f: f.write(data)
            os.replace(full + ".tmp", full)
        if poster:   # a card has one poster: <card>-<view>.<ext>; the one it showed before (another camera or background) goes
            d, name = os.path.split(full); card = name.split("-")[0] + "-"
            for other in os.listdir(d):
                if other.startswith(card) and other != name: os.remove(os.path.join(d, other))
    return {"path": rel, "mtime": os.stat(full).st_mtime_ns}


# Notifications (owner 2026-10-03): what an agent put on a board, in a few words, with previews and the place it went; the owner sees
# a red dot on the bell and jumps there. Only the agents' news, not the owner's own edits (those are in the history).
NOTIFS = os.path.join(HERE, "notifications.json")


def notifications():
    try: return json.load(open(NOTIFS, encoding="utf-8"))
    except (OSError, ValueError): return []


def notify(d):
    """d: {title, text, who, page, ids, previews, area}; returns the stored notification"""
    title = str(d.get("title") or "").strip()[:200]
    if not title: raise ValueError("no title")
    n = {"id": time.strftime("%y%m%d%H%M%S") + "-" + os.urandom(2).hex(), "t": time.strftime("%Y-%m-%d %H:%M:%S"), "read": False, "title": title,
         "text": str(d.get("text") or "")[:2000], "who": str(d.get("who") or tr("agent", "агент"))[:60], "page": str(d.get("page") or ""),
         "ids": [str(x) for x in (d.get("ids") or [])][:500], "previews": [str(x) for x in (d.get("previews") or [])][:8]}
    if isinstance(d.get("area"), dict) and all(isinstance(d["area"].get(k), (int, float)) for k in "xywh"): n["area"] = {k: d["area"][k] for k in "xywh"}
    with LOCK:
        L = notifications() + [n]
        _write_json(NOTIFS, L[-500:])
    return n


def read_notifications(ids=None):
    with LOCK:
        L = notifications()
        for n in L:
            if ids is None or n["id"] in ids: n["read"] = True
        _write_json(NOTIFS, L)
    return sum(not n["read"] for n in L)


def fetch_image(url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("not a web address")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) review-board", "Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise ValueError("too big")
    return data


_SIZES = {}


def image_sizes(paths):
    """width and height from the file header only (Pillow opens lazily): a thousand frames take well under a second"""
    out = {}
    for rel in paths:
        try:
            full = safe(resolve(rel)); key = (full, os.path.getmtime(full))
            if key not in _SIZES:
                wh = psd_size(full) if full.lower().endswith((".psd", ".psb")) else None
                if not wh:
                    with Image.open(full if kind_of(full) == "image" else preview(resolve(rel))) as im:
                        wh = list(im.size)
                _SIZES[key] = wh
            out[rel] = _SIZES[key]
        except Exception:
            pass
    return out


REPO = os.path.dirname(CODE_DIR)
SKILLS = os.path.join(REPO, "skills")


def project_name():
    """the project's name as the app's catalog has it, else the folder's name"""
    try:
        cat = json.load(open(os.path.expanduser("~/Library/Application Support/Hyimg/projects.json"), encoding="utf-8"))
        return next((p.get("name", "") for p in cat if p.get("id") == PROJECT_ID), "") or os.path.basename(W)
    except (OSError, ValueError, AttributeError):
        return os.path.basename(W)


# The plugins an agent asks the person about (owner 2026-10-05: «if we give this repository to an agent, it must know and ASK the person
# whether they want to install the plugins, 3D and image frames, so it doesn't slip past their attention»).
KNOWN_PLUGINS = [
    ("frames", "Фреймы", "https://github.com/constantvis/hyimg-frames", "редактор картинок на доске (слои, маски, Color Grading, заливка) и HTML-фреймы,"
     " маска объекта через macOS Vision, для заливки по желанию модель LaMa около 208 МБ (скачивать только с согласия человека)"),
    ("3d", "3D-объекты", "https://github.com/constantvis/hyimg-3d-studio", "3D-сцена карточкой на доске, свой редактор, снимок в картинку,"
     " для переноса в Blender нужен Blender"),
]


def plugins_brief():
    """Lines for /agent: the plugins this server sees, and the known ones it does not, named once so the agent asks the person."""
    try:
        have = plugins()
    except Exception:
        have = {}
    L = ["## Плагины", ""]
    L += [f"- Подключен «{m.get('title_ru') or m.get('title', n)}» (`{n}`): {d}" for n, (d, m) in have.items()] or ["- Плагинов нет."]
    missing = [k for k in KNOWN_PLUGINS if k[0] not in have]
    if missing:
        L += ["", "Не установлены плагины Hyimg. Спроси человека про каждый по имени, ставить ли его, и ставь только после «да»"
              f" (`{os.path.join(REPO, 'scripts', 'install_plugins.sh')} --frames --3d --yes`, только нужные флаги, потом перезапуск сервера)."
              " Если человек уже отказался, не спрашивай снова:", ""]
        L += [f"- «{t}» (`{n}`, {url}): {what}." for n, t, url, what in missing]
    return L


FEATURES = os.path.join(CODE_DIR, "features.json")   # the feature catalog: what Hyimg can do and how an agent does it (2026-10-06)


def features_read():
    try: d = json.load(open(FEATURES, encoding="utf-8"))
    except (OSError, ValueError): return {"features": []}
    return d if isinstance(d, dict) and isinstance(d.get("features"), list) else {"features": []}


def features_brief(hy):
    """Lines for /agent (owner 2026-10-06: «agents that come to our app must get this information about skills, so I don't have to
    explain things»): every feature in one line with the agent's way to it and its skill, from review/features.json; a plugin's
    feature says when that plugin is not installed here"""
    try: have = set(plugins())
    except Exception: have = set()
    alias = {"3d": ("3d", "hyimg-3d-studio", "hyimg-3d"), "frames": ("frames", "hyimg-frames"), "dev": ("dev", "hyimg-dev-studio", "dev-studio")}
    F = features_read()["features"]
    L = ["## Что умеет Hyimg", "",
         f"Каталог функций ({len(F)}): что это, как агент это делает и какой скилл объясняет. `hy.py` ниже значит `{hy}`."
         f" Подробно по слову: `{hy} features <слово>`, весь каталог JSON: `GET /api/features`. Тот же доступ через MCP:"
         f" `python3 {os.path.join(REPO, 'mcp', 'server.py')}` (как подключить: README репозитория, раздел MCP).", ""]
    for f in F:
        pl = f.get("plugin")
        off = pl and not (set(alias.get(pl, (pl,))) & have)
        cmd = lambda a, m: f"`{m.group(1)}`{m.group(2) or ''}" if a.startswith(("hy.py", "GET ", "POST ", "python3 ", "scripts/")) else a
        how = " · ".join(cmd(a, re.match(r"(.*?)( \(.*\))?$", a)) for a in f.get("agent", [])[:2])   # a command in backticks, its note after it
        L.append(f"- **{f['title']}**" + (f" (плагин `{pl}`" + (", здесь не установлен" if off else "") + ")" if pl else "")
                 + f": {how}" + (f" · скилл `{f['skill']}`" if f.get("skill") else ""))
    return L


def more_skills():
    """the skills /agent does not describe by hand: every skills/<name>/SKILL.md is named, so a new skill is never missed (2026-10-06)"""
    told = ("hyimg", "hyimg-board", "hyimg-generate", "gemini-web")
    try: return [n for n in sorted(os.listdir(SKILLS)) if n not in told and os.path.isfile(os.path.join(SKILLS, n, "SKILL.md"))]
    except OSError: return []


def agent_page(port):
    """/agent: everything an agent needs when the owner only gives it a localhost link (owner 2026-10-01: "дал ссылку, и агент все
    понял"). What is open, the project's own rules (<libraryRoot>/AGENTS.md, pasted in full), the Hyimg skills and the commands."""
    name = ""
    try:
        cat = json.load(open(os.path.expanduser("~/Library/Application Support/Hyimg/projects.json"), encoding="utf-8"))
        name = next((p.get("name", "") for p in cat if p.get("id") == PROJECT_ID), "")
    except (OSError, ValueError, AttributeError):
        pass
    try:
        live = json.load(open(os.path.join(HERE, "live.json"), encoding="utf-8"))
    except (OSError, ValueError):
        live = {}
    st = pages_state(); cv = live.get("canvas") or {}
    titles = {p["id"]: p.get("title", p["id"]) for p in st["pages"]}
    base = f"http://localhost:{port}"
    hy = (f"HYIMG_PORT={port} " if port != 4180 else "") + "python3 " + os.path.join(CODE_DIR, "hy.py")   # another port: say it in every command
    L = [f"# Hyimg: инструкция для ИИ-агента", "",
         f"Hyimg: приложение владельца для Mac, библиотека картинок и холст (доска как в Figma). Этот адрес отдает проект"
         f" «{name or os.path.basename(W)}».", "",
         "## Что открыто", "",
         f"- Папка проекта (libraryRoot): `{W}`",
         f"- Состояние (доски, история, live.json): `{HERE}`",
         f"- Сервер: {base}, холст {base}/canvas, библиотека {base}/",
         "- Страницы холста: " + ", ".join(f"«{p.get('title', p['id'])}» (`{p['id']}`, кадров {len(p['on'])})" for p in st["pages"])]
    if cv:
        L.append(f"- У владельца сейчас: страница «{titles.get(cv.get('page'), cv.get('page'))}» (`{cv.get('page')}`), зум {cv.get('zoom')},"
                 f" выделено {len(cv.get('sel') or [])}, обновлено {cv.get('t', '?')}")
    L += ["", "## С чего начать", "",
          "1. Правила этого проекта ниже, раздел «Правила проекта». Они главнее общих правил Hyimg.",
          f"2. Скиллы Hyimg, читать по задаче: `{SKILLS}/hyimg/SKILL.md` (общее: данные, библиотека, как улучшать эти правила),"
          f" `{SKILLS}/hyimg-board/SKILL.md` (доска: читать, класть, двигать, убирать, проверять),"
          f" `{SKILLS}/hyimg-generate/SKILL.md` (генерация картинок в проект)."
          f" Те же файлы по HTTP: {base}/agent/hyimg, /agent/hyimg-board, /agent/hyimg-generate."
          + "".join(f" Еще: `{SKILLS}/{n}/SKILL.md` ({base}/agent/{n})." for n in more_skills()),
          f"3. Что владелец выделил и видит: `python3 {os.path.join(REPO, 'scripts', 'active.py')}`; ссылка с `?obj=` или `&at=`:"
          f" `python3 {os.path.join(REPO, 'scripts', 'active.py')} --link '<ссылка>'`.",
          f"4. Доска: `{hy} map` (оглавление), `{hy} find <слово>`, `{hy} do '...'`, `{hy} check`. Этот проект на порту {port}:"
          f" без HYIMG_PORT={port} (или `--port {port}`) hy.py пойдет на 4180, в другой проект.",
          f"5. Что умеет Hyimg и какой командой: раздел «Что умеет Hyimg» ниже, подробно `{hy} features <слово>`. Не угадывай и не пиши JSON доски:"
          " у каждой функции есть команда.", "",
          *plugins_brief(), "",
          "## Пять правил, которые нельзя нарушать", "",
          "1. Доску меняй только через `hy.py do`. JSON доски руками не пиши и целиком не отправляй: владелец правит ее вживую,"
          " а hy.py сам делает версии «до» и «после» и повторяет запись, если доска изменилась."
          " Холст в браузере мышью не трогай: такая правка записывается как правка владельца, без версии «до», и ее легко сделать не там."
          " Что на доске, узнавай через `hy.py map` и `find`, а не скриншотами. Мышь только когда без нее никак:"
          " посмотреть, как легло, или проверить ошибку интерфейса.",
          "2. Не заводи группу на каждый рендер: партия ложится подгруппой (заметка и ряды) в тематическую группу, `block ... into=<группа>`,"
          " группа растет, все ниже сдвигается. Кадры клади сразу, как появились первые, и докладывай тем же вызовом. Координаты не придумывай."
          " После правки `hy.py check` и один взгляд на результат.",
          "3. Кадры, убранные со всех страниц, это архив, то есть отказ владельца. Не бери их в выборки, эталоны и промпты."
          " Исключение на минуты: ⌘X тоже кладет в архив до ⌘V, свежую отметку не считай отказом."
          " Чужие кадры и заметки не двигай и не удаляй без просьбы.",
          "4. Генерируй только маршрутами из правил проекта. Эталоны подавай в оригинальном разрешении, отдельными файлами, не пережимай и не клей"
          " со сжатием. У каждой картинки рядом json с промптом, моделью и эталонами. Скачанное и собранное из загрузок клади"
          f" через `{hy} save <файлы> --to <папка партии>`: картинку, которая уже есть в библиотеке, она не положит второй раз.",
          "5. Непонятно или правило мешает: спроси владельца коротко, с вариантами. Его поправку запиши туда, где она будет работать"
          " дальше (см. «Как улучшать» в скилле hyimg).", ""]
    L += features_brief(hy) + [""]
    brief = os.path.join(W, "AGENTS.md")
    L += ["## Правила проекта", "", f"Файл `{brief}`" + (":" if os.path.exists(brief) else
          " пока не создан. Спроси владельца о цели проекта и создай его по шаблону из скилла hyimg."), ""]
    if os.path.exists(brief):
        L += [open(brief, encoding="utf-8").read().strip(), ""]
    return "\n".join(L) + "\n"


def with_archive(items):
    """Frames taken off every canvas page are the archive (owner 2026-10-01: "в архиве = отказались"): they carry archived=True
    so the library can say so and no agent takes them into context."""
    try:
        gone = set(pages_state().get("removed", []))
    except Exception:
        gone = set()
    for i in items:
        if i.get("path") in gone: i["archived"] = True
    return items


def resolve(rel):
    return rel if os.path.exists(real(rel)) else aliases().get(rel, rel)


def safe(rel):
    full = os.path.realpath(real(rel))
    roots = [os.path.realpath(W)] + [os.path.realpath(r) for r, _t, _m in MOUNTS.values()]
    if not any(full.startswith(r + os.sep) for r in roots):
        raise PermissionError(rel)
    return full


REVEAL_CMD = os.environ.get("HYIMG_REVEAL_CMD") or "/usr/bin/open"   # tests put a recorder here instead of Finder


def reveal(paths):
    """Finder shows library files selected (owner 2026-10-05: «a button to open the folder with the file»). Only files of the library
    or its mounts: an absolute path or one with .. is refused before anything is resolved. Files of one folder go in one `open -R`
    (Finder selects them together in one window); at most 5 folders, each its own window."""
    by_dir = {}
    for p in dict.fromkeys(paths):
        if os.path.isabs(p) or p.startswith("~") or ".." in p.replace("\\", "/").split("/"): raise PermissionError(p)
        full = safe(resolve(p))
        if not os.path.exists(full): raise FileNotFoundError(p)
        by_dir.setdefault(os.path.dirname(full), []).append(full)
    dirs = list(by_dir)[:5]
    for d in dirs:
        subprocess.run([REVEAL_CMD, "-R", *by_dir[d]], capture_output=True, timeout=20)   # an argument list, no shell
    return {"revealed": sum(len(by_dir[d]) for d in dirs), "folders": len(dirs), "skipped": max(0, len(by_dir) - 5)}


# «Open in <App>» on a card's right-click menu (owner 2026-10-06: «right click can add "open in the app" that is default, maybe you can also
# see what's the default app to be opened in so you can right away write it there»): LaunchServices names the app macOS opens a file
# with (osascript JXA, NSWorkspace), asked once per file extension and kept; its icon is drawn once per app as a 64 px PNG.
# HYIMG_DEFAULT_APP='{"name": ..., "path": ...}' answers for every file instead (tests: nothing depends on what this Mac has installed)
DEFAULT_APPS, APP_ICONS = {}, {}
JXA_DEFAULT_APP = """ObjC.import('AppKit');
function run(argv) {
  const u = $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL($.NSURL.fileURLWithPath(argv[0]));
  if (!u || u.isNil()) return "";
  const p = ObjC.unwrap(u.path), n = ObjC.unwrap($.NSFileManager.defaultManager.displayNameAtPath(p));
  return JSON.stringify({ name: String(n).replace(/[.]app$/, ""), path: p });
}"""
JXA_APP_ICON = """ObjC.import('AppKit');
function run(argv) {
  const img = $.NSWorkspace.sharedWorkspace.iconForFile(argv[0]), s = 64;
  const rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(null, s, s, 8, 4, true, false, $.NSDeviceRGBColorSpace, 0, 0);
  $.NSGraphicsContext.saveGraphicsState;
  $.NSGraphicsContext.setCurrentContext($.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep));
  img.drawInRectFromRectOperationFraction($.NSMakeRect(0, 0, s, s), $.NSZeroRect, $.NSCompositingOperationSourceOver, 1);
  $.NSGraphicsContext.restoreGraphicsState;
  rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $()).writeToFileAtomically(argv[1], true);
  return "ok";
}"""


def default_app(full):
    """{"name": "Adobe Photoshop 2026", "path": "/Applications/..."} for a file, or {} when no app opens it"""
    fake = os.environ.get("HYIMG_DEFAULT_APP")
    if fake:
        try: return json.loads(fake)
        except ValueError: return {}
    ext = os.path.splitext(full)[1].lower()
    if ext in DEFAULT_APPS: return DEFAULT_APPS[ext]
    try:
        out = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", JXA_DEFAULT_APP, full], capture_output=True, text=True, timeout=10).stdout.strip()
        app = json.loads(out) if out else {}
    except (OSError, ValueError, subprocess.SubprocessError):
        app = {}
    if not (isinstance(app, dict) and isinstance(app.get("name"), str) and isinstance(app.get("path"), str)): app = {}
    DEFAULT_APPS[ext] = app
    return app


def app_icon(app_path):
    """the PNG of an app that default_app named (no other path is drawn), or None"""
    if app_path in APP_ICONS: return APP_ICONS[app_path]
    if app_path not in {a.get("path") for a in DEFAULT_APPS.values()} or not app_path.endswith(".app") or not os.path.isdir(app_path): return None
    png = None
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "icon.png")
        try:
            subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", JXA_APP_ICON, app_path, out], capture_output=True, timeout=10)
            if os.path.isfile(out): png = open(out, "rb").read()
        except (OSError, subprocess.SubprocessError):
            pass
    APP_ICONS[app_path] = png
    return png


def library_file(p):
    """a library path from a page, refused when absolute or with .., resolved and kept inside the library (as reveal does)"""
    if not isinstance(p, str) or not p or os.path.isabs(p) or p.startswith("~") or ".." in p.replace("\\", "/").split("/"): raise PermissionError(p)
    full = safe(resolve(p))
    if not os.path.isfile(full): raise FileNotFoundError(p)
    return full


def open_file(p):
    """the file opens in its default app (`open <file>`, as a double click in Finder would)"""
    full = library_file(p)
    subprocess.run([REVEAL_CMD, full], capture_output=True, timeout=20)   # an argument list, no shell
    return {"opened": p}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.end_headers()
        # a piece at a time (2026-10-05): one write of a 40 MB frame render or a 17 MP original failed on macOS with
        # «[Errno 55] No buffer space available» and the picture never came
        mv = memoryview(body)
        for k in range(0, len(mv), 1 << 20): self.wfile.write(mv[k:k + (1 << 20)])

    def file(self, path, ctype, cache=True):
        self.send(200, open(path, "rb").read(), ctype, cache)

    def ranged(self, path, ctype):
        size = os.path.getsize(path)
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        a, b = 0, size - 1
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                a = int(m.group(1)); b = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            else:
                a = max(0, size - int(m.group(2)))
            if a > b or a >= size:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.send_header("Content-Length", "0"); self.end_headers(); return
        b = min(b, a + 8 * 1024 * 1024 - 1) if m else b   # a piece at a time: a 2 GB clip is never read whole
        self.send_response(206 if m else 200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes"); self.send_header("Cache-Control", "no-store")
        if m: self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("Content-Length", str(b - a + 1)); self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(a); left = b - a + 1
            while left > 0:
                chunk = fh.read(min(1 << 20, left))
                if not chunk: break
                self.wfile.write(chunk); left -= len(chunk)

    def request_allowed(self, *, writing: bool = False) -> bool:
        """Reject rebinding hosts and browser requests from foreign origins."""
        port = self.server.server_port
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        host_headers = self.headers.get_all("Host", [])
        origins = self.headers.get_all("Origin", [])
        valid_host = len(host_headers) == 1 and host_headers[0] in hosts
        valid_origin = not origins or (len(origins) == 1 and origins[0] in {f"http://{host}" for host in hosts})
        cross_site_write = writing and "cross-site" in self.headers.get_all("Sec-Fetch-Site", [])
        if valid_host and valid_origin and not cross_site_write:
            return True
        self.send(403, b"Forbidden request origin", "text/plain")
        return False

    def do_HEAD(self):   # the size of a library file without reading it (a 3D plugin weighs a scene before it loads it)
        if not self.request_allowed():
            return
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        try:
            if u.path != "/file": raise FileNotFoundError(u.path)
            full = safe(resolve(q["p"][0]))
            size = os.path.getsize(full)
        except (KeyError, OSError, PermissionError):
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", CTYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(size)); self.send_header("Cache-Control", "no-store"); self.end_headers()

    def sandbox_get(self):   # /sandbox/<key>/<library path>: a library page and its files for a sandboxed frame (SANDBOX_KEY above)
        port = self.server.server_port
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        hh, origins = self.headers.get_all("Host", []), self.headers.get_all("Origin", [])
        if not (len(hh) == 1 and hh[0] in hosts and (not origins or (len(origins) == 1 and origins[0] in {"null"} | {f"http://{h}" for h in hosts}))):
            return self.send(403, b"Forbidden request origin", "text/plain")
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        parts = u.path.split("/", 3)
        if len(parts) < 4 or not hmac.compare_digest(parts[2].encode(), SANDBOX_KEY.encode()): return self.send(404, b"not found", "text/plain")
        rel = urllib.parse.unquote(parts[3])
        try:
            if rel.startswith("~hyp/"):   # a plugin's script for the page (manifest "pageScript")
                d, man = plugins()[rel[5:]]
                if not isinstance(man.get("pageScript"), str): raise KeyError(rel)
                full, ctype = plugin_file(rel[5:], man["pageScript"]), "text/javascript; charset=utf-8"
            else:
                if not rel or rel.startswith(("/", "~")) or "\\" in rel or "\x00" in rel or ".." in rel.split("/"): raise PermissionError(rel)
                full = safe(resolve(rel))
                if os.path.isdir(full): full = os.path.join(full, "index.html")
                if not os.path.isfile(full): raise FileNotFoundError(rel)
                ext = os.path.splitext(full)[1].lower(); ctype = SANDBOX_TYPES.get(ext) or CTYPES.get(ext, "application/octet-stream")
            body = open(full, "rb").read()
        except (KeyError, OSError, PermissionError, ValueError):
            return self.send(404, b"not found", "text/plain")
        page = ctype.startswith("text/html")
        if page and q.get("hyp") and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", q["hyp"][0]): body = sandbox_inject(body, q["hyp"][0])
        self.send_response(200)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Vary", "Origin")
        if origins == ["null"]: self.send_header("Access-Control-Allow-Origin", "null")
        if page: self.send_header("Content-Security-Policy", "sandbox allow-scripts")
        self.end_headers()
        mv = memoryview(body)
        for k in range(0, len(mv), 1 << 20): self.wfile.write(mv[k:k + (1 << 20)])

    def do_GET(self):
        if self.path.startswith("/sandbox/"):   # a sandboxed library page: its own origin rule (sandbox_get)
            return self.sandbox_get()
        if not self.request_allowed():
            return
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/storage": return storage.http(self, "GET")   # the summary of the last scan, never waits for one (storage.py)
        try:
            if u.path == "/api/sandbox":   # where the app's own pages find sandboxed library pages (SANDBOX_KEY)
                return self.send(200, json.dumps({"base": f"/sandbox/{SANDBOX_KEY}/"}).encode(), "application/json")
            if u.path == "/api/health":
                body = {"app": "Hyimg", "projectId": PROJECT_ID, "libraryRoot": W, "pid": os.getpid(), "port": self.server.server_port}
                return self.send(200, json.dumps(body).encode(), "application/json")
            # v2 (criteria rows + zoom) is the main page since 2026-09-28; the tag-cloud page stays at /v1
            if u.path in ("/", "/index.html", "/v2", "/v2.html"):
                return self.file(os.path.join(CODE_DIR, "v2.html"), "text/html; charset=utf-8", cache=False)
            if u.path in ("/canvas", "/canvas.html"):
                return self.file(os.path.join(CODE_DIR, "canvas.html"), "text/html; charset=utf-8", cache=False)
            if u.path == "/ui/settings.js":   # the app's settings, put into the page before anything reads them
                return self.send(200, settings_js().encode(), "text/javascript; charset=utf-8")
            if u.path == "/api/settings":
                return self.send(200, json.dumps(settings_read(), ensure_ascii=False).encode(), "application/json")
            if u.path.startswith("/ui/"):   # what every page shares (owner 2026-10-04: one kind of notification): review/ui/<name>.js|css
                name = u.path[4:]
                if re.fullmatch(r"fonts/[a-z0-9-]+\.woff2", name) and os.path.isfile(os.path.join(CODE_DIR, "ui", name)):   # Geist, 2026-10-07: no Google Fonts
                    return self.file(os.path.join(CODE_DIR, "ui", name), "font/woff2")
                if not re.fullmatch(r"(hy/)?[a-z0-9-]+\.(js|css)", name) or not os.path.isfile(os.path.join(CODE_DIR, "ui", name)):   # hy/: the primitives
                    return self.send(404, b"no such ui file", "text/plain")
                return self.file(os.path.join(CODE_DIR, "ui", name), "text/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8", cache=False)
            if u.path in ("/agent", "/llms.txt", "/AGENTS.md"):   # instructions for an AI agent given only this address (owner 2026-10-01)
                return self.send(200, agent_page(self.server.server_port).encode(), "text/markdown; charset=utf-8")
            if u.path == "/api/features":   # the feature catalog (review/features.json): what Hyimg can do and how an agent does it
                return self.send(200, json.dumps(features_read(), ensure_ascii=False).encode(), "application/json")
            if u.path.startswith("/agent/"):   # one Hyimg skill: /agent/hyimg-board
                nm = u.path[len("/agent/"):].strip("/")
                if not re.fullmatch(r"[a-z0-9-]+", nm): raise FileNotFoundError(nm)
                return self.file(os.path.join(SKILLS, nm, "SKILL.md"), "text/markdown; charset=utf-8", cache=False)
            if u.path == "/api/live":   # the same state live.py reads; hy.py takes the owner's open page from it
                try: body = open(os.path.join(HERE, "live.json"), "rb").read()
                except OSError: body = b"{}"
                return self.send(200, body, "application/json")
            if u.path == "/api/bench":   # in-app speed test: only a test copy of a project has _bench.json in its state folder (canvas.html bench())
                f = os.path.join(HERE, "_bench.json")
                return self.file(f, "application/json", cache=False) if os.path.exists(f) else self.send(404, b"no bench", "text/plain")
            if u.path == "/api/changes":   # {"board": {mtime, revision}, "lib": n}: cheap, asked every 2 s by the pages
                body = {"lib": LIB_SIG["v"], "fs": foldersync.stamp()}   # fs: a folder layout ran or its mode changed (2026-10-05)
                if q.get("board"): body["board"] = board_stamp(q["board"][0])
                return self.send(200, json.dumps(body).encode(), "application/json")
            if u.path == "/api/board":
                return self.send(200, json.dumps(load_board(q.get("name", ["main"])[0]), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/pages":
                return self.send(200, json.dumps(pages_state(), ensure_ascii=False).encode(), "application/json")
            if u.path in ("/v1", "/v1.html"):
                return self.file(os.path.join(CODE_DIR, "index.html"), "text/html; charset=utf-8", cache=False)
            if u.path == "/api/taggroups":
                return self.send(200, json.dumps(tags.groups(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/foldercolors":   # {"colors": {folder path: colour}}: the library tree's folder colours (foldercolors.py)
                return self.send(200, json.dumps(foldercolors.read(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/filters":   # {"pins": [filter ids] | null}: what this project pinned in the dock's filter bar; null: not chosen yet (filters.py)
                return self.send(200, json.dumps(filters.read(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/events":   # newest first: what was added, removed, grouped, written, moved on a page
                nm = q.get("name", ["main"])[0]; board_path(nm)
                bf = q.get("before", [None])[0]
                return self.send(200, json.dumps(events.read(nm, int(q.get("limit", ["300"])[0]), float(bf) if bf else None), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/propsclip":   # the properties copied last, in any project (canvas.html copyProps)
                try: d = json.load(open(PROPS_CLIP, encoding="utf-8"))
                except (OSError, ValueError): d = {}
                return self.send(200, json.dumps(d if isinstance(d, dict) else {}, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/presets":   # the project's presets of properties: {"presets": [{name, at, from, kinds}]}
                return self.send(200, json.dumps({"presets": presets_read()}, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/history":
                nm = q.get("name", ["main"])[0]; board_path(nm)
                ex = lambda p: os.path.exists(real(resolve(p)))
                out = [dict(e, missing=len(history.missing(nm, e["id"], ex))) for e in reversed(history.entries(nm))]
                return self.send(200, json.dumps(out, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/history/board":   # one saved version in full, for looking at it on the canvas without restoring it
                nm = q.get("name", ["main"])[0]; board_path(nm)
                return self.send(200, json.dumps(history.load(nm, q["id"][0]), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/history/missing":
                nm = q.get("name", ["main"])[0]; board_path(nm)
                return self.send(200, json.dumps(history.missing(nm, q["id"][0], lambda p: os.path.exists(real(resolve(p)))), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/notes":
                return self.send(200, json.dumps({k: dict(v, pics={p: sorted(x) for p, x in v["pics"].items()}) for k, v in note_index(load_board(q.get("name", ["main"])[0])).items()}, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/items":   # each picture once; ?all=1 keeps the copies too (copy_of, hidden), the canvas needs them
                items = ui_items(lib3d.fresh(dedup.collapse(with_archive(scan_cached()), keep_copies=q.get("all") == ["1"]), sprite_info))
                return self.send(200, json.dumps(items, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/project":   # the canvas's plate «⌂ › project › page» (owner 2026-10-04)
                return self.send(200, json.dumps({"name": project_name(), "root": W}, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/layout/plan":   # what «Разложить по папкам как на доске» would do; changes nothing
                env = layout_env()
                return self.send(200, json.dumps(dict(foldersync.summary(foldersync.plan(env, count_library=True)), auto=foldersync.auto_on()), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/layout/state":
                return self.send(200, json.dumps(layout_state(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/aliases":
                return self.send(200, json.dumps(aliases(), ensure_ascii=False).encode(), "application/json")
            if u.path == "/thumb":
                rel = resolve(q["p"][0]); safe(rel)
                size = int(q.get("s", ["640"])[0])
                try: pg = max(1, int(q.get("pg", ["1"])[0]))   # a PDF's page (2026-10-06)
                except ValueError: pg = 1
                if size == 2048 and kind_of(rel) == "pdf": return self.file(thumb(rel, 2048, pg), "image/jpeg")   # the large preview's page
                return self.file(thumb(rel, size if size in (96, 320, 640, 1280) else 640, pg), "image/jpeg")   # 96: far-out canvas (fast mode)
            if u.path == "/api/defaultapp":   # {name, path}: the app macOS opens this library file with ({} when none), for «Open in <App>»
                return self.send(200, json.dumps(default_app(library_file(q["p"][0])), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/appicon":   # that app's icon, a 64 px PNG
                png = app_icon(q["app"][0])
                if not png: return self.send(404, b"no icon", "text/plain")
                return self.send(200, png, "image/png", cache=True)
            if u.path == "/api/pdf":   # {pages, ars}: a PDF's page count and the shape of each page, for the card's «2 / 5» and the viewer (2026-10-06)
                rel = resolve(q["p"][0]); full = safe(rel)
                if kind_of(full) != "pdf" or not os.path.isfile(full): raise FileNotFoundError(full)
                return self.send(200, json.dumps(pdf_info(rel), ensure_ascii=False).encode(), "application/json")
            if u.path == "/img":
                rel = resolve(q["p"][0])
                full = safe(rel)
                if kind_of(full) != "image":
                    pv = preview(rel)
                    return self.file(pv, "image/png" if pv.endswith(".png") else "image/jpeg")
                ctype = "image/png" if full.lower().endswith(".png") else "image/jpeg"
                return self.file(full, ctype)
            if u.path == "/api/notifications":   # newest first, with how many are unread
                L = notifications()
                return self.send(200, json.dumps({"items": L[::-1][:int(q.get("limit", ["60"])[0])], "unread": sum(not n.get("read") for n in L)}, ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/models3d":   # the library's 3D files, each with its turntable if one is drawn (the library's «3D» filter, 2026-10-06)
                return self.send(200, json.dumps(models3d(q.get("fresh") == ["1"]), ensure_ascii=False).encode(), "application/json")
            if u.path == "/api/sprite":   # a 3D file's turntable sheet; &s=<px>: its first view as a still picture; 404 until a page has drawn it
                try:
                    size = int(q.get("s", ["0"])[0])
                    if size not in (0, 96, 160, 240, 320, 480): return self.send(400, b"s: 0, 96, 160, 240, 320 or 480", "text/plain")
                    out = sprite_file(q["p"][0], size)
                except ValueError: out = None
                if not out: return self.send(404, b"no turntable yet", "text/plain")
                return self.file(out, "image/webp")   # the page's url carries the file's version (v=), so it is kept
            if u.path == "/api/plugins":
                body = [dict(name=n, title=tr(m.get("title", n), m.get("title_ru") or m.get("title", n)), version=m.get("version", ""), canvas=f"/plugins/{n}/{m['canvas']}" if m.get("canvas") else None,
                             sprites=f"/plugins/{n}/{m['sprites']}" if isinstance(m.get("sprites"), str) else None)   # sprites: a module that draws 3D files' turntables for the library (2026-10-06)
                        for n, (d, m) in plugins().items()]
                return self.send(200, json.dumps(body, ensure_ascii=False).encode(), "application/json")   # title: the manifest's title_ru in Russian (2026-10-06)
            if u.path.startswith("/plugins/"):
                parts = u.path.split("/", 3)
                if len(parts) < 4: return self.send(404, b"no plugin file", "text/plain")
                try: full = plugin_file(parts[2], urllib.parse.unquote(parts[3]))
                except (KeyError, PermissionError): return self.send(404, b"no plugin file", "text/plain")
                return self.file(full, CTYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream"), cache=False)
            if u.path.startswith("/lib/"):   # a library file by its path: an HTML frame's page finds its css, scripts and pictures by relative links
                full = safe(resolve(urllib.parse.unquote(u.path[len("/lib/"):])))
                if os.path.isdir(full): full = os.path.join(full, "index.html")
                ext = os.path.splitext(full)[1].lower()
                return self.file(full, CTYPES.get(ext, "application/octet-stream"), cache=False)
            if u.path == "/api/vstrip":   # the trim strip's frames, frame i of n along the clip (webvideo.strip, owner 2026-10-06)
                full = safe(resolve(q["p"][0]))
                if os.path.splitext(full)[1].lower() not in VIDEO_EXT or not os.path.isfile(full): raise FileNotFoundError(full)
                try: n, i = max(2, min(24, int(q.get("n", ["10"])[0]))), int(q.get("i", ["0"])[0])
                except ValueError: return self.send(400, b"n and i are numbers", "text/plain")
                if not 0 <= i < n: return self.send(400, b"i out of range", "text/plain")
                dur = video_probe(full)[0]
                if not dur: return self.send(404, b"length unknown", "text/plain")
                try: outs = webvideo.strip(full, n, dur)
                except RuntimeError as ex:
                    return self.send(501 if str(ex) == "noffmpeg" else 500, json.dumps({"error": str(ex)[:300]}, ensure_ascii=False).encode(), "application/json")
                return self.file(outs[i], "image/jpeg")
            if u.path == "/video":   # a WebM copy of a library video for an engine that cannot play it (webvideo.py, owner 2026-10-05)
                full = safe(resolve(q["p"][0]))
                if os.path.splitext(full)[1].lower() not in VIDEO_EXT or not os.path.isfile(full): raise FileNotFoundError(full)
                if q.get("fmt", ["webm"])[0] != "webm": return self.send(400, b"only fmt=webm", "text/plain")
                if q.get("prep") == ["1"]:   # start it in the background (the card came on screen) and say how it stands
                    if webvideo.ffmpeg(): webvideo.start(full)
                    return self.send(200, json.dumps({"state": webvideo.state(full)}).encode(), "application/json")
                try: out = webvideo.ensure(full)
                except RuntimeError as ex:
                    code = 501 if str(ex) == "noffmpeg" else 500
                    return self.send(code, json.dumps({"error": str(ex)[:300]}, ensure_ascii=False).encode(), "application/json")
                return self.ranged(out, "video/webm")
            if u.path == "/file":   # any file of the library by its type (3D models for plugins); inside the library only
                full = safe(resolve(q["p"][0]))
                ext = os.path.splitext(full)[1].lower()   # a json is plugin data that changes (a 3D scene the canvas rewrites): never cached
                if ext in VIDEO_EXT:
                    return self.ranged(full, CTYPES.get(ext, "application/octet-stream"))
                return self.file(full, CTYPES.get(ext, "application/octet-stream"), cache=ext != ".json")
            if u.path == "/ref":
                rel = os.path.join("refs", q["n"][0].lstrip("/"))  # refs may sit in subfolders; safe() keeps it inside the workroom
                safe(rel)
                return self.file(thumb(rel, 320), "image/jpeg")
        except (KeyError, FileNotFoundError, PermissionError):
            return self.send(404, b"not found", "text/plain")
        self.send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self.request_allowed(writing=True):
            return
        if self.path.startswith("/api/storage/"): return storage.http(self, "POST")   # «Clear cache», old app copies to the Trash (storage_clean.py)
        if self.path == "/api/pages":
            n = int(self.headers.get("Content-Length", 0))
            try:
                res = save_pages(json.loads(self.rfile.read(n) or b"{}").get("pages", []))
            except (PermissionError, KeyError, TypeError, AttributeError):
                return self.send(400, b"bad pages", "text/plain")
            layout_kick()   # a page renamed or deleted: its folder follows, in the auto mode only
            return self.send(200, json.dumps(res, ensure_ascii=False).encode(), "application/json")
        if self.path in ("/api/layout/apply", "/api/layout/undo", "/api/layout/auto"):   # folders as on the board (2026-10-05)
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/api/layout/auto":
                    return self.send(200, json.dumps(dict(layout_state(), auto=foldersync.set_auto(bool(d.get("on"))))).encode(), "application/json")
                if self.path == "/api/layout/undo":
                    j = layout_undo()
                    return self.send(200, json.dumps({"status": j["status"], "undo": j.get("undo"), "auto_was": j.get("auto_was"), "id": j["id"]}, ensure_ascii=False).encode(), "application/json")
                who = d.get("who") if d.get("who") in ("owner", "agent") else "owner"
                j = layout_apply(who, d.get("auto") if isinstance(d.get("auto"), bool) else None)
                return self.send(200, json.dumps({"status": j["status"], "id": j["id"], "moved": len(j.get("moves", [])), "made": len(j.get("dirs_made", [])),
                                                  "removed": len(j.get("dirs_removed", [])), "boards": j.get("boards", []), "json": len(j.get("json", [])),
                                                  "auto": foldersync.auto_on()}, ensure_ascii=False).encode(), "application/json")
            except foldersync.Failed as ex:
                return self.send(409, json.dumps({"error": str(ex)}, ensure_ascii=False).encode(), "application/json")
            except Exception as ex:
                return self.send(500, json.dumps({"error": f"{type(ex).__name__}: {str(ex)[:200]}"}, ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/foldercolors":   # {"path", "color" | null}: one folder's colour set or taken off (foldercolors.py)
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(d, dict): raise ValueError("body")
                out = foldercolors.write(d.get("path"), d.get("color"))
            except ValueError:
                return self.send(400, b"bad folder colour", "text/plain")
            except OSError:
                return self.send(500, b"not saved", "text/plain")
            return self.send(200, json.dumps(out, ensure_ascii=False).encode(), "application/json")
        if self.path in ("/api/filters", "/api/tagrule"):   # {"pins": [ids]}: the dock's pinned filters; {"group", "tag", "words"}: a project's own tag (filters.py, owner 2026-10-06)
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(d, dict): raise ValueError("body")
                if self.path == "/api/filters":
                    return self.send(200, json.dumps(filters.write(d.get("pins")), ensure_ascii=False).encode(), "application/json")
                entry = filters.add_tag(d.get("group"), d.get("tag"), d.get("words"))
            except KeyError:
                return self.send(409, b"this tag exists", "text/plain")
            except (ValueError, re.error):
                return self.send(400, b"bad filter", "text/plain")
            except OSError:
                return self.send(500, b"not saved", "text/plain")
            tags.configure(filters.reload_rules()); lib_dirty()   # the next list is scanned afresh and carries the tag
            return self.send(200, json.dumps({"group": entry[0], "tag": entry[1]}, ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/reveal":   # {"paths": [...]}: Finder shows these library files selected (owner 2026-10-05, «Показать в Finder»)
            n = int(self.headers.get("Content-Length", 0))
            try:
                paths = json.loads(self.rfile.read(n) or b"{}").get("paths")
                if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths): raise ValueError("paths")
            except (ValueError, AttributeError):
                return self.send(400, b"bad reveal", "text/plain")
            try:
                return self.send(200, json.dumps(reveal(paths[:500])).encode(), "application/json")
            except PermissionError:
                return self.send(403, b"outside the library", "text/plain")
            except FileNotFoundError:
                return self.send(404, b"no such file", "text/plain")
        if self.path == "/api/openfile":   # {"path"}: the library file opens in its default app (owner 2026-10-06, «Open in <App>»)
            n = int(self.headers.get("Content-Length", 0))
            try:
                path = json.loads(self.rfile.read(n) or b"{}").get("path")
            except (ValueError, AttributeError):
                return self.send(400, b"bad open", "text/plain")
            try:
                return self.send(200, json.dumps(open_file(path), ensure_ascii=False).encode(), "application/json")
            except PermissionError:
                return self.send(403, b"outside the library", "text/plain")
            except FileNotFoundError:
                return self.send(404, b"no such file", "text/plain")
        if self.path == "/api/known":   # {"sha": [sha1, ...]} -> which of these pictures the library already has, and where
            n = int(self.headers.get("Content-Length", 0))
            try:
                shas = [str(x) for x in json.loads(self.rfile.read(n) or b"{}").get("sha", [])][:5000]
            except (ValueError, AttributeError, TypeError):
                return self.send(400, b"bad request", "text/plain")
            return self.send(200, json.dumps({"known": dedup.known(shas)}, ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/propsclip/take":   # before a paste: the copied value's files here, {"map": {path there: path here}}
            try: return self.send(200, json.dumps({"map": props_files_take()}, ensure_ascii=False).encode(), "application/json")
            except Exception as ex: return self.send(500, str(ex)[:160].encode(), "text/plain")
        if self.path in ("/api/propsclip", "/api/presets"):   # {from, src, at, kinds} | {name, at, from, kinds} or {name, delete: true}
            n = int(self.headers.get("Content-Length", 0))
            if n > 512 * 1024: return self.send(413, b"too big", "text/plain")
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(d, dict) or (not isinstance(d.get("kinds"), dict) and not d.get("delete")): raise ValueError("kinds")
                if self.path == "/api/propsclip":
                    if isinstance(d.get("files"), list): d["files"] = props_files_keep(d["files"])
                    with LOCK:
                        os.makedirs(os.path.dirname(PROPS_CLIP), exist_ok=True); tmp = PROPS_CLIP + ".tmp"
                        with open(tmp, "w", encoding="utf-8") as fh: json.dump(d, fh, ensure_ascii=False)
                        os.replace(tmp, PROPS_CLIP)
                    return self.send(200, b"{}", "application/json")
                name = str(d.get("name") or "").strip()[:60]
                if not name: raise ValueError("name")
                with LOCK:
                    L = [p for p in presets_read() if p["name"] != name]
                    if not d.get("delete"): L.append({"name": name, "at": int(d.get("at") or time.time() * 1000), "from": str(d.get("from") or "")[:80], "kinds": d["kinds"]})
                    L.sort(key=lambda p: p["name"].lower()); _write_json(presets_path(), {"presets": L})
                return self.send(200, json.dumps({"presets": L}, ensure_ascii=False).encode(), "application/json")
            except (ValueError, TypeError) as ex:
                return self.send(400, str(ex)[:120].encode(), "text/plain")
        if self.path == "/api/history":
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}"); nm = req.get("name", "main"); board_path(nm)
                if req.get("action") == "save":
                    who = req.get("who") if req.get("who") in ("owner", "ai") else "owner"   # hy.py marks its own before/after versions as ai
                    with LOCK: e = history.snapshot(nm, who, (req.get("label") or "").strip()[:120] or tr("version", "версия"))
                    return self.send(200, json.dumps(e, ensure_ascii=False).encode(), "application/json")
                if req.get("action") == "restore":
                    def write(b):
                        with LOCK:
                            cur = load_board(nm); b["revision"] = cur.get("revision", 0) + 1; b["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
                            p = board_path(nm); tmp = p + ".tmp"
                            json.dump(b, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, p)
                            try: events.record(nm, cur, b, req.get("who") if req.get("who") in ("owner", "ai") else "owner", tr("restored a version", "возврат к версии"))
                            except Exception: pass
                            return b["revision"]
                    rev = history.restore(nm, req["id"], write)
                    try: sync_notes(nm)
                    except Exception: pass
                    layout_kick()
                    return self.send(200, json.dumps({"revision": rev}).encode(), "application/json")
            except (PermissionError, KeyError, OSError, ValueError) as ex:
                return self.send(400, str(ex)[:200].encode(), "text/plain")
            return self.send(400, b"unknown action", "text/plain")
        if self.path == "/api/sizes":   # {"paths": [...]} -> {path: [w, h]}: the canvas lays out big drops without loading every thumbnail
            n = int(self.headers.get("Content-Length", 0))
            try:
                paths = json.loads(self.rfile.read(n) or b"{}").get("paths", [])[:5000]
            except (ValueError, AttributeError):
                return self.send(400, b"bad sizes", "text/plain")
            return self.send(200, json.dumps(image_sizes(paths), ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/live":   # what the owner has selected and sees right now (canvas and library), for the agent: python3 live.py
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}"); src = d.pop("src")
                if src not in ("canvas", "library", "bench"): raise ValueError(src)
            except (ValueError, KeyError, AttributeError):
                return self.send(400, b"bad live state", "text/plain")
            with LOCK:
                p = os.path.join(HERE, "live.json")
                try: cur = json.load(open(p, encoding="utf-8"))
                except (OSError, ValueError): cur = {}
                cur[src] = dict(d, t=time.strftime("%Y-%m-%d %H:%M:%S"))
                _write_json(p, cur)
            return self.send(200, b"{}", "application/json")
        if self.path.startswith("/api/snapshot"):   # body: png bytes; ?name=&folder=<library folder>&meta=<json>: a picture made by a plugin
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_UPLOAD: return self.send(413, tr("The file is over 80 MB", "Файл больше 80 МБ").encode(), "text/plain; charset=utf-8")
            try:
                meta = json.loads(q.get("meta", ["{}"])[0])
                res = save_snapshot(self.rfile.read(n), q.get("name", ["shot"])[0], q.get("folder", ["plugins"])[0], meta)
            except Exception as ex:
                return self.send(400, (tr("snapshot not saved: ", "снимок не сохранен: ") + str(ex)[:160]).encode(), "text/plain; charset=utf-8")
            return self.send(200, json.dumps(res, ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/notifications":   # {"action": "add", title, text, who, page, ids, previews, area} | {"action": "read", "ids": [...] or none for all}
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                if d.get("action") == "read": return self.send(200, json.dumps({"unread": read_notifications(d.get("ids"))}).encode(), "application/json")
                return self.send(200, json.dumps(notify(d), ensure_ascii=False).encode(), "application/json")
            except (ValueError, AttributeError, TypeError) as ex:
                return self.send(400, (tr("not saved: ", "не записано: ") + str(ex)[:120]).encode(), "text/plain; charset=utf-8")
        if self.path == "/api/stat":   # {"paths": [...]} -> {path: mtime_ns or null}: many files in one look (3D cards and their scenes)
            n = int(self.headers.get("Content-Length", 0))
            try: paths = [str(p) for p in json.loads(self.rfile.read(n) or b"{}").get("paths", [])][:5000]
            except (ValueError, AttributeError, TypeError): return self.send(400, b"bad request", "text/plain")
            out = {}
            for rel in paths:
                try: out[rel] = os.stat(safe(rel)).st_mtime_ns
                except (OSError, PermissionError): out[rel] = None
            return self.send(200, json.dumps(out).encode(), "application/json")
        if self.path == "/api/models3d":   # {"paths": [...]} -> [entry | null, ...]: given 3D files, for a card's recent list (no walk of the library)
            n = int(self.headers.get("Content-Length", 0))
            try: paths = [str(p) for p in json.loads(self.rfile.read(n) or b"{}").get("paths", [])]
            except (ValueError, AttributeError, TypeError): return self.send(400, b"bad request", "text/plain")
            return self.send(200, json.dumps(models3d_info(paths), ensure_ascii=False).encode(), "application/json")
        if self.path.startswith("/api/sprite"):   # ?p=<3D file>&n=&cols=&cell=: the png sheet of its turntable, drawn by a page with three.js
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            n = int(self.headers.get("Content-Length", 0))
            if n > SPRITE_MAX: return self.send(413, b"the sheet is over 32 MB", "text/plain")
            try: res = save_sprite(q["p"][0], self.rfile.read(n), int(q["n"][0]), int(q["cols"][0]), int(q["cell"][0]))
            except (KeyError, ValueError, PermissionError, OSError) as ex: return self.send(400, ("not saved: " + str(ex)[:160]).encode(), "text/plain; charset=utf-8")
            return self.send(200, json.dumps(res).encode(), "application/json")
        if self.path == "/api/settings":   # {key: value | null}: settings of the whole app
            n = int(self.headers.get("Content-Length", 0))
            try: change = json.loads(self.rfile.read(n) or b"{}"); assert isinstance(change, dict)
            except (ValueError, AssertionError): return self.send(400, b"bad settings", "text/plain")
            return self.send(200, json.dumps(settings_write(change), ensure_ascii=False).encode(), "application/json")
        if self.path.startswith("/api/htmlstill"):   # ?p=<page.html>&w=&h=: a still of an HTML frame (Hyimg-frames)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try: res = html_still(q["p"][0], q.get("w", ["1440"])[0], q.get("h", ["900"])[0], self.server.server_port)
            except (KeyError, ValueError, PermissionError, FileNotFoundError) as ex: return self.send(400, (tr("no snapshot: ", "нет снимка: ") + str(ex)[:160]).encode(), "text/plain; charset=utf-8")
            return self.send(200, json.dumps(res).encode(), "application/json")
        if self.path.startswith("/api/plugin/"):   # /api/plugin/<plugin>/<route>: a plugin's own server route (plugin_routes above)
            u = urllib.parse.urlparse(self.path); parts = u.path.split("/")
            err = lambda code, t: self.send(code, json.dumps({"error": t}, ensure_ascii=False).encode(), "application/json")
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_UPLOAD: return err(413, "body over 80 MB")
            body = self.rfile.read(n)
            try: fn = plugin_routes(parts[3])[parts[4]] if len(parts) == 5 else None
            except (KeyError, PermissionError, OSError, SyntaxError, ImportError) as ex: return err(404, f"no plugin route: {str(ex)[:160]}")
            if not fn: return err(404, "no plugin route")
            try: res = fn(body, urllib.parse.parse_qs(u.query))
            except Exception as ex: return err(500, f"{type(ex).__name__}: {str(ex)[:300]}")
            code, ctype, data = res if len(res) == 3 else (200, *res)
            return self.send(code, data, ctype)
        if self.path.startswith("/api/file"):   # body: the bytes; ?p=3d/<...>.json|.glb: plugin data (a 3D scene and its geometry)
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            n = int(self.headers.get("Content-Length", 0))
            if n > (FRAME_MAX if q.get("p", [""])[0].startswith("frames/") else MAX_UPLOAD): return self.send(413, tr("The file is too large", "Файл слишком большой").encode(), "text/plain; charset=utf-8")
            try: res = save_plugin_file(q.get("p", [""])[0], self.rfile.read(n))
            except (ValueError, PermissionError) as ex: return self.send(400, (tr("not saved: ", "не записано: ") + str(ex)[:160]).encode(), "text/plain; charset=utf-8")
            return self.send(200, json.dumps(res).encode(), "application/json")
        if self.path.startswith("/api/upload"):   # body: the image bytes (?name=file name), or JSON {"url": ...} for a picture dragged from a web page
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_UPLOAD:
                return self.send(413, tr("The file is over 80 MB", "Файл больше 80 МБ").encode(), "text/plain; charset=utf-8")
            body = self.rfile.read(n)
            try:
                if (self.headers.get("Content-Type") or "").startswith("application/json"):
                    url = json.loads(body or b"{}").get("url", "")
                    res = add_image(fetch_image(url), url=url)
                else:
                    res = add_image(body, name=q.get("name", [""])[0])
            except Exception as ex:
                return self.send(400, (tr("Couldn't add the image: ", "Не получилось добавить картинку: ") + str(ex)[:160]).encode(), "text/plain; charset=utf-8")
            return self.send(200, json.dumps(res, ensure_ascii=False).encode(), "application/json")
        if self.path.startswith("/api/board"):
            n = int(self.headers.get("Content-Length", 0))
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            try:
                nm = q.get("name", ["main"])[0]
                try: old = load_board(nm)
                except Exception: old = {}
                new = json.loads(self.rfile.read(n) or b"{}")
                code, res = save_board(nm, new)
                if code == 200:
                    try: events.record(nm, old, new, (q.get("who") or ["owner"])[0][:20], (q.get("label") or [""])[0], (q.get("agent") or [""])[0])
                    except Exception as ex: res["events_error"] = str(ex)[:160]
                    try:
                        if history.auto(nm, load_board(nm)): res["snapshot"] = True
                    except Exception as ex: res["history_error"] = str(ex)[:160]
                    try: res["notes_synced"] = sync_notes(nm)
                    except Exception as ex: res["notes_error"] = str(ex)[:160]
                    layout_kick()   # folders as on the board, in the auto mode only (2026-10-05)
            except PermissionError:
                return self.send(400, b"bad board name", "text/plain")
            return self.send(code, json.dumps(res, ensure_ascii=False).encode(), "application/json")
        if self.path == "/api/fav":   # {"paths": [...], "fav": true|false} -> {"feedback": {path: feedback}}
            n = int(self.headers.get("Content-Length", 0))
            entry = json.loads(self.rfile.read(n) or b"{}")
            ps = [p for p in entry.get("paths") or [] if isinstance(p, str)]
            if not ps:
                return self.send(400, b"paths required", "text/plain")
            try:
                cur = save_fav(ps, bool(entry.get("fav")))
            except (PermissionError, OSError):
                return self.send(400, b"bad image path", "text/plain")
            return self.send(200, json.dumps(cur, ensure_ascii=False).encode(), "application/json")
        if self.path not in ("/api/feedback", "/api/answer"):
            return self.send(404, b"not found", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        entry = json.loads(self.rfile.read(n) or b"{}")
        if not entry.get("path"):
            return self.send(400, b"path required", "text/plain")
        try:
            cur = save_answer(entry) if self.path == "/api/answer" else save_feedback(entry)
        except PermissionError:
            return self.send(400, b"bad image path", "text/plain")
        self.send(200, json.dumps(cur, ensure_ascii=False).encode(), "application/json")


# One guard for every request (2026-10-06, found by the unit tests): a handler that raised answered nothing, the connection was dropped
# and the page saw a network error instead of a status it could show (/api/events?limit=abc, /thumb?s=big, feedback for a file that is
# gone, an answer for a picture without questions, a body that is not JSON). Now a bad value is a 400, a missing file a 404, anything
# else a 500 with its message and a line in the log; a client that went away is left alone. Nothing is sent twice: once the status
# line is out (send_response marks it), the error only goes to the log.
def _guarded(method):
    def run(self):
        self._answered = False
        try:
            return method(self)
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception as ex:
            code = 400 if isinstance(ex, (ValueError, TypeError, json.JSONDecodeError)) else 404 if isinstance(ex, FileNotFoundError) else 500
            if code == 500 or self._answered:
                sys.stderr.write(f"{self.command} {self.path}: {type(ex).__name__}: {ex}\n")
            if not self._answered:
                self.send(code, f"{type(ex).__name__}: {str(ex)[:200]}".encode(), "text/plain; charset=utf-8")
    run.__name__ = method.__name__
    return run


_send_response = H.send_response
def _marked_send_response(self, *a, **k):
    self._answered = True
    return _send_response(self, *a, **k)
H.send_response = _marked_send_response
for _m in ("do_GET", "do_POST", "do_HEAD"):
    if hasattr(H, _m): setattr(H, _m, _guarded(getattr(H, _m)))


# Live updates (owner 2026-10-01: "when the AI adds pictures, the board and the library should update without a reload").
# A watcher walks the folders every few seconds and only looks at directory times (a new or moved file changes its folder's
# time); the pages ask /api/changes every two seconds and fetch the board or the library only when something moved.
LIB_SIG = {"v": 0, "sig": None}


def library_signature():
    h = hashlib.sha1()
    for base in [W] + [root for root, _t, _m in MOUNTS.values()]:
        for root, dirs, _files in os.walk(base):
            if os.path.realpath(root) == HERE:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
            try:
                h.update(f"{root}:{os.stat(root).st_mtime_ns}".encode())
            except OSError:
                pass
    return h.hexdigest()


def watch_library():
    # The pages refetch the whole library when LIB_SIG["v"] moves. While an agent writes thousands of files the folders change on
    # every look, so the pages hear of it once things are quiet for a look (3 s) and at most every 30 s while the writing goes on
    # (owner 2026-10-02: 2400 new files made every page refetch a 21 s list every 3 s and the canvas stopped loading pictures).
    pending, told = False, 0.0
    while True:
        try:
            sig = library_signature()
            if sig != LIB_SIG["sig"]:
                first = LIB_SIG["sig"] is None
                LIB_SIG["sig"] = sig
                # new or changed files get their sha1 before the pages hear of them, so copies are folded at once; the very
                # first pass reads the whole library (16 s for 8.5 GB), later passes only what changed
                n = dedup.fill(SKIP)
                if not first or n:
                    pending = True
                    if time.time() - told < 30: sig = None   # still changing: wait
            if pending and (sig is not None or time.time() - told >= 30):
                LIB_SIG["v"] += 1; pending, told = False, time.time()
        except Exception:
            pass
        time.sleep(3)


def board_stamp(name):
    """what a page compares to notice another writer: the board file's time and its revision"""
    p = board_path(name)
    try:
        st = os.stat(p)
    except OSError:
        return {"mtime": 0, "revision": 0}
    hit = _STAMPS.get(name)
    if not hit or hit[0] != st.st_mtime_ns:   # the board is parsed only when its file changed
        hit = _STAMPS[name] = (st.st_mtime_ns, load_board(name).get("revision", 0))
    return {"mtime": hit[0], "revision": hit[1]}


_STAMPS = {}


def warm():
    # Pre-build thumbnails so the grid is fast after the first start.
    for it in scan():
        try:
            thumb(it["path"])
            thumb(it["path"], 320)   # library cards (2026-09-29)
        except Exception:
            pass


def main() -> None:
    """Hold one writer lease for the state folder across every listener."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4180
    compat = int(os.environ.get("HYIMG_COMPAT_PORT", "0"))
    lifetime.start(H)   # the app's server lives with the app; any other ends with its parent or after 20 idle minutes (lifetime.py)
    ports = list(dict.fromkeys([port] + ([compat] if compat else [])))
    os.makedirs(HERE, exist_ok=True)
    with open(os.path.join(HERE, ".hyimg-server.lock"), "a+", encoding="utf-8") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(f"Hyimg already owns this state folder: {HERE}") from exc
        with ExitStack() as stack:
            servers = []
            for listener in ports:
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", listener), H)
                except OSError as exc:
                    raise SystemExit(f"Cannot bind Hyimg port {listener}: {exc}") from exc
                stack.callback(server.server_close)
                servers.append(server)
            thumbcache.start()   # the old <state>/_thumbs moved into the cache, its ceiling kept behind
            threading.Thread(target=watch_library, daemon=True).start()   # live updates of the library (/api/changes)
            for server in servers[1:]:
                threading.Thread(target=server.serve_forever, daemon=True).start()
                stack.callback(server.shutdown)
            print(f"Hyimg on http://127.0.0.1:{port}", flush=True)
            servers[0].serve_forever()


if __name__ == "__main__":
    main()
