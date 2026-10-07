"""Thumbnails out of Dropbox, with a ceiling (owner 2026-10-07, docs/storage-plan.md, decision 1: «мне гораздо важнее, чтобы было
свободнее на диске»). Everything the server draws again by itself from the originals (thumbnails 96 to 1280 px, the 2048 px previews
of PSD, video and other files, PDF pages, 3D turntables) lived in <state>/_thumbs, inside the board's Dropbox folder: 4.28 GB and 77 234
files for Studio North, synced to the cloud and to every machine. It now lives in ~/Library/Caches/Hyimg/<board id>/thumbs
(HYIMG_CACHE_ROOT moves the whole cache), on this Mac only.

Moving in (migrate, at every start, idempotent and resumable; every step is a line in thumbs-migration.log beside the folder):
1. no new folder yet: the old folder is renamed into place, one rename, instant for any number of files (the same volume);
2. both exist (a start in the middle of a move, or a machine that wrote old thumbnails again): each old file the new folder lacks is
   moved in, file by file; what is left over (the new folder has it already) goes to the Trash with its folder, once;
3. another volume: each file is copied to a temporary name, its size checked, renamed into place; the old folder then goes to the Trash.
A request in the meantime takes its thumbnail from the old folder (adopt) instead of drawing it again. Then a sweep puts the thumbnails
of files that are gone (the path and time in the name match no file of the board or its outside folders) into the Trash, in one folder.
Turntables are kept: their version is not the file's time. Nothing outside the two thumbnail folders is ever touched: not the originals,
the boards, the history or the notes.

The ceiling: the oldest used go first once a board's folder passes its cap (2 GB) or all boards' folders together pass the total (8 GB).
«Used» is the file's time, set again when the server hands a thumbnail out (at most once an hour per file). The caps live in
storage-settings.json beside the catalog (storage.py caps, Settings › Storage). Evicting deletes: these are the app's own regenerable
files in its cache, never a person's file.
"""
import hashlib
import os
import shutil
import subprocess
import threading
import time

from config import CACHE_ROOT, HERE, PROJECT_ID, W

BOARD_DIR = os.path.join(CACHE_ROOT, PROJECT_ID or hashlib.sha1(W.encode()).hexdigest()[:16])
THUMBS = os.path.join(BOARD_DIR, "thumbs")
OLD = os.path.join(HERE, "_thumbs")
LOG = os.path.join(BOARD_DIR, "thumbs-migration.log")
GB = 10 ** 9
TOUCH_EVERY = 3600
EVICT_EVERY = 600
_LOCK = threading.Lock()


def log(msg):
    try:
        os.makedirs(BOARD_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def to_trash(path):
    """the macOS Trash (HYIMG_TRASH names another command, for the tests): True when the path is gone"""
    trash = os.environ.get("HYIMG_TRASH") or "/usr/bin/trash"
    try:
        ok = subprocess.run([trash, path], capture_output=True, timeout=600).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return ok and not os.path.lexists(path)


def _same_volume(a, b):
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _move_files(src, dst, copy):
    """each file of src that dst lacks into dst (rename, or copy, check, rename); returns (moved, left)"""
    moved = left = 0
    with os.scandir(src) as it:
        for e in it:
            if not e.is_file(follow_symlinks=False) or e.name.endswith(".tmp"):
                continue
            to = os.path.join(dst, e.name)
            if os.path.exists(to):
                left += 1
                continue
            try:
                if copy:
                    tmp = to + ".mig.tmp"
                    shutil.copyfile(e.path, tmp)
                    if os.path.getsize(tmp) != e.stat().st_size:
                        os.remove(tmp); left += 1; continue
                    os.replace(tmp, to); os.remove(e.path)
                else:
                    os.rename(e.path, to)
                moved += 1
            except OSError:
                left += 1
    return moved, left


def migrate():
    """the old thumbnails into the cache folder (see the module's note); returns what was done"""
    with _LOCK:
        if not os.path.isdir(OLD) or os.path.islink(OLD):
            os.makedirs(THUMBS, exist_ok=True)
            return {"step": "nothing to move"}
        os.makedirs(BOARD_DIR, exist_ok=True)
        if not os.path.exists(THUMBS) and _same_volume(OLD, BOARD_DIR):
            os.rename(OLD, THUMBS)
            log(f"moved {OLD} -> {THUMBS} (one rename)")
            return {"step": "renamed"}
        os.makedirs(THUMBS, exist_ok=True)
        copy = not _same_volume(OLD, THUMBS)
        log(f"merging {OLD} into {THUMBS} ({'copy' if copy else 'rename'} file by file)")
        moved, left = _move_files(OLD, THUMBS, copy)
        log(f"moved {moved} files, {left} already there")
        rest = [n for n in os.listdir(OLD) if n not in (".DS_Store",)]
        if all(os.path.exists(os.path.join(THUMBS, n)) or n.endswith(".tmp") or os.path.isdir(os.path.join(OLD, n)) for n in rest):
            gone = to_trash(OLD)
            log(f"old folder with {len(rest)} leftovers to the Trash: {'done' if gone else 'FAILED, kept'}")
        return {"step": "merged", "moved": moved, "left": left}


def adopt(name):
    """a thumbnail still in the old folder, moved into the new one (a request during the move); True when it is in place"""
    src, dst = os.path.join(OLD, name), os.path.join(THUMBS, name)
    try:
        if os.path.isfile(src) and not os.path.exists(dst):
            os.makedirs(THUMBS, exist_ok=True)
            os.rename(src, dst) if _same_volume(OLD, THUMBS) else shutil.copyfile(src, dst)
    except OSError:
        return False
    return os.path.exists(dst)


def used(path):
    """the file was handed out: its time moves to now (at most once an hour), so the ceiling keeps it; returns the path"""
    try:
        if time.time() - os.stat(path).st_mtime > TOUCH_EVERY:
            os.utime(path)
    except OSError:
        pass
    return path


def caps():
    """{"board", "total"} in bytes: storage-settings.json beside the catalog (storage.py caps_read), else 2 GB and 8 GB"""
    import storage
    c = storage.caps_read()
    return {"board": int(c["board"] * GB), "total": int(c["total"] * GB)}


def _files(d):
    out = []
    try:
        with os.scandir(d) as it:
            for e in it:
                if e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    out.append((st.st_mtime, st.st_blocks * 512, e.path))
    except OSError:
        pass
    return out


def evict(limits=None, root=None, mine=None):
    """the oldest used thumbnails of this board go while its folder passes the board's cap or all boards' folders pass the total;
    returns {"removed", "freed"}. Only regular files right inside this board's thumbnail folder are removed."""
    limits = limits or caps(); root = root or CACHE_ROOT; mine = mine or THUMBS
    own = sorted(_files(mine))
    size = sum(b for _t, b, _p in own)
    others = 0
    try:
        for n in os.listdir(root):
            d = os.path.join(root, n, "thumbs")
            if os.path.realpath(d) != os.path.realpath(mine) and os.path.isdir(d):
                others += sum(b for _t, b, _p in _files(d))
    except OSError:
        pass
    # the total over the cap: this board gives up its share, in proportion to its size
    over_total = max(0, size + others - limits["total"])
    share = over_total * size // max(1, size + others)
    need = max(size - limits["board"], share)
    freed = removed = 0
    for _t, b, p in own:
        if freed >= need:
            break
        try:
            os.remove(p); freed += b; removed += 1
        except OSError:
            pass
    if removed:
        log(f"ceiling: removed {removed} thumbnails, {freed} bytes (board {size} of {limits['board']}, total {size + others} of {limits['total']})")
    return {"removed": removed, "freed": freed}


def sweep_orphans(board=None):
    """thumbnails of files that are gone, into the Trash in one folder; returns how many"""
    import storage
    board = board or {"id": PROJECT_ID, "lib": W, "state": HERE, "refs": os.environ.get("HYIMG_STYLE_REFS", "")}
    stems = set()
    for path, st in storage._walk(W, skip={HERE}):
        stems.add(storage._thumb_stem(os.path.relpath(path, W).replace(os.sep, "/"), st.st_mtime))
    for prefix, folder in storage._mounts(board).items():
        for path, st in storage._walk(folder):
            stems.add(storage._thumb_stem(prefix + "/" + os.path.relpath(path, folder).replace(os.sep, "/"), st.st_mtime))
    lost, total = [], 0
    for e in os.scandir(THUMBS):
        n = e.name
        if not e.is_file(follow_symlinks=False) or ".sprite" in n or n.endswith(".tmp"):
            continue
        total += 1
        if not any(n[:i] in stems for i, c in enumerate(n) if c == "."):
            lost.append(e.path)
    if not lost:
        return 0
    if not stems or len(lost) > total // 2:   # the board's folder unreadable or half its files gone at once: not a moment to judge
        log(f"sweep skipped: {len(lost)} of {total} thumbnails match no file, the folder may be unavailable")
        return 0
    bin_ = os.path.join(BOARD_DIR, time.strftime("thumbs-of-gone-files-%y%m%d-%H%M%S"))
    os.makedirs(bin_, exist_ok=True)
    for p in lost:
        try:
            os.rename(p, os.path.join(bin_, os.path.basename(p)))
        except OSError:
            pass
    gone = to_trash(bin_)
    log(f"{len(lost)} thumbnails of files that are gone to the Trash: {'done' if gone else 'FAILED, kept in ' + bin_}")
    return len(lost)


def _behind():
    try:
        migrate()
        sweep_orphans()
    except Exception as ex:   # the board works without the sweep; the log says why
        log(f"sweep stopped: {ex!r}")
    while True:
        try:
            evict()
        except Exception as ex:
            log(f"ceiling stopped: {ex!r}")
        time.sleep(EVICT_EVERY)


def start():
    """at the server's start: the fast part of the move now (a rename), the rest, the sweep and the ceiling behind"""
    try:
        os.makedirs(BOARD_DIR, exist_ok=True)
        if not os.path.exists(THUMBS) and os.path.isdir(OLD) and _same_volume(OLD, BOARD_DIR):
            migrate()
    except OSError as ex:
        log(f"move at start failed: {ex!r}")
    os.makedirs(THUMBS, exist_ok=True)
    threading.Thread(target=_behind, daemon=True, name="hyimg-thumbcache").start()
