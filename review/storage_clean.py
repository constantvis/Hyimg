"""The two deletions of Settings › Storage (storage.py), each one guarded so it can never reach the person's files.

clear_cache(): «Очистить кэш». Only what Hyimg makes again by itself and keeps in its cache folder (~/Library/Caches/Hyimg): WebM
copies of videos (video/), CAD conversions (cad/), Blender's work files (blender/), and the folders of boards that are no longer in
the catalog (a test's or a removed board's list snapshot and engine profile). Not the engine's cache of open boards (Chromium caps
it itself), not the LaMa model, not the browser profiles agents sign in with, not the CEF SDK.
Every path is checked before it goes: a direct child of one of those folders, resolving inside the cache folder, the cache folder
itself not inside any board's folder and not the home folder; a link is removed as a link, what it points at stays; nothing touched
in the last 10 minutes (something may be writing it).

trash_backups(keep): the app's older copies (Hyimg.backup.<date>-<time>.app, made by scripts/install.sh) beyond the newest `keep`
go to the macOS Trash with /usr/bin/trash (HYIMG_TRASH names another command, for the tests), never rm: they can be put back.
"""
import os, re, shutil, subprocess, time

import storage

RECENT = 10 * 60
CLEAR_DIRS = ("video", "cad", "blender")
BACKUP_RE = re.compile(r"Hyimg\.backup\.\d{8}-\d{6}\.app")


class Refused(Exception):
    pass


def _inside(path, root):
    return path == root or path.startswith(root + os.sep)


def _check_root(root, boards):
    """the cache folder must be a real folder of its own: not / or the home folder, not inside or around a board's folder"""
    real = os.path.realpath(root)
    if not os.path.isdir(real) or os.path.islink(root):
        raise Refused(f"no cache folder: {root}")
    if real in ("/", os.path.realpath(storage.HOME)) or real.count(os.sep) < 3:
        raise Refused(f"refusing a cache folder this wide: {real}")
    for b in boards:
        for p in (b["lib"], b["state"]):
            if _inside(real, p) or _inside(p, real):
                raise Refused(f"the cache folder and a board's folder overlap: {real} and {p}")
    return real


def _guarded(path, root, boards, now):
    """True when path may be removed by clear_cache (see the module's note)"""
    parent = os.path.realpath(os.path.dirname(path))
    name = os.path.basename(path)
    if not name or name in (".", "..") or not _inside(parent, root) or parent == os.path.realpath(path):
        return False
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if not os.path.islink(path):
        real = os.path.realpath(path)
        if not _inside(real, root) or real == root or any(_inside(real, b["lib"]) or _inside(real, b["state"]) for b in boards):
            return False
    return now - st.st_mtime >= RECENT


def clear_targets(boards=None):
    """the paths «Clear cache» would remove, each already guarded"""
    boards = storage.catalog() if boards is None else boards
    root = _check_root(storage.cache_root(), boards)
    ids = {b["id"].upper() for b in boards}; now = time.time(); out = []
    for d in CLEAR_DIRS:
        top = os.path.join(root, d)
        if os.path.isdir(top) and not os.path.islink(top):
            out += [os.path.join(top, n) for n in sorted(os.listdir(top))]
    for n in sorted(os.listdir(root)):   # list snapshots of boards no longer in the catalog (tests left 10 000 of them)
        if storage.UUID_RE.fullmatch(n) and n.upper() not in ids:
            out.append(os.path.join(root, n))
    engine = os.path.join(root, "Chromium")
    if os.path.isdir(engine) and not os.path.islink(engine):   # engine profiles of boards no longer in the catalog
        out += [os.path.join(engine, n) for n in sorted(os.listdir(engine)) if storage.UUID_RE.fullmatch(n) and n.upper() not in ids]
    return [p for p in out if _guarded(p, root, boards, now)]


def clear_cache(dry_run=False, boards=None):
    """{"freed": bytes on disk, "removed": n, "paths": [...]}; dry_run only counts"""
    targets = clear_targets(boards); freed = 0; done = []
    for p in targets:
        size = storage.dir_size(p)["disk"]
        if not dry_run:
            try:
                if os.path.islink(p) or not os.path.isdir(p):
                    os.unlink(p)
                else:
                    shutil.rmtree(p)   # never follows a link inside (shutil.rmtree.avoids_symlink_attacks on macOS)
            except OSError:
                continue
        freed += size; done.append(p)
    return {"freed": freed, "removed": len(done), "paths": done[:50], "dryRun": dry_run}


def trash_backups(keep=2, dry_run=False):
    """the app's copies beyond the newest `keep` to the Trash; {"freed", "trashed": [names], "kept": [names]}"""
    if str(keep) == "all":
        return {"freed": 0, "trashed": [], "kept": [], "dryRun": dry_run}
    keep = int(keep)
    if keep < 1:
        raise Refused("keep at least one copy")
    d = storage.apps_dir()
    names = sorted(n for n in os.listdir(d) if BACKUP_RE.fullmatch(n) and not os.path.islink(os.path.join(d, n))) if os.path.isdir(d) else []
    old, kept = names[:-keep] if len(names) > keep else [], names[-keep:]
    freed = 0; trashed = []
    trash = os.environ.get("HYIMG_TRASH") or "/usr/bin/trash"
    for n in old:
        p = os.path.join(d, n)
        if os.path.islink(p) or not os.path.isdir(p) or os.path.realpath(os.path.dirname(p)) != os.path.realpath(d):
            continue
        size = storage.dir_size(p)["disk"]
        if not dry_run:
            if not os.access(trash, os.X_OK):
                raise Refused("no trash command: nothing was moved")
            if subprocess.run([trash, p], capture_output=True, timeout=120).returncode != 0 or os.path.exists(p):
                continue
        freed += size; trashed.append(n)
    return {"freed": freed, "trashed": trashed, "kept": kept, "dryRun": dry_run}
