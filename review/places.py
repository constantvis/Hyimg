"""Where a board lives decides who sees it (owner 2026-10-07): «Общая» (shared) or «Только для меня» (private). There is no other
security: a shared board is a folder in the folder both Macs sync (Dropbox), a private one is a folder elsewhere. The two places are this
Mac's settings, places.json beside the profile: {"shared": absolute folder, "private": absolute folder}, empty until chosen.

Switching moves the board's Finder folder from one place to the other (the app asks first and stops the board's server before):
- the same volume: one rename, nothing is copied;
- another volume: the folder is copied under a temporary name beside the target, every file's size checked, renamed into place, and only
  then the old folder goes to the Trash (never removed).
A folder of that name already in the target, a target inside the board, a link: refused, nothing moves.
  python3 places.py get | set [--shared P] [--private P] | move SRC shared|private   (HYIMG_PROFILE_DIR: the profile's folder)
"""
import json
import os
import shutil
import subprocess
import sys

KINDS = ("shared", "private")


def read(root):
    try:
        with open(os.path.join(root, "places.json"), encoding="utf-8") as fh: d = json.load(fh)
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return {k: d[k] if isinstance(d.get(k), str) and os.path.isabs(d[k]) else "" for k in KINDS}


def _inside(a, b):
    a, b = os.path.realpath(a), os.path.realpath(b)
    return a == b or a.startswith(b.rstrip(os.sep) + os.sep)


def write(root, **change):
    """{shared, private}: an existing absolute folder, or "" to forget it; the two may not be one folder or inside each other"""
    cur = read(root)
    for k, v in change.items():
        if k not in KINDS: raise ValueError("unknown place " + k)
        v = str(v or "").strip()
        if v and (not os.path.isabs(v) or not os.path.isdir(v)): raise ValueError("not a folder: " + v)
        cur[k] = os.path.realpath(v) if v else ""
    if cur["shared"] and cur["private"] and (_inside(cur["shared"], cur["private"]) or _inside(cur["private"], cur["shared"])):
        raise ValueError("the shared and the private folder must be apart")
    os.makedirs(root, exist_ok=True)
    tmp = os.path.join(root, "places.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh: json.dump(cur, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(root, "places.json"))
    return cur


def visibility(folder, pl):
    """"shared" | "private" | "" (somewhere else) for a board's folder"""
    for k in KINDS:
        if pl.get(k) and _inside(folder, pl[k]) and os.path.realpath(folder) != os.path.realpath(pl[k]): return k
    return ""


def of_board(root, state_root):
    """the visibility of the board whose state folder this is (its library is the state folder's parent by default)"""
    return {"vis": visibility(os.path.dirname(os.path.realpath(state_root)), read(root))}


def to_trash(path):
    """the macOS Trash (HYIMG_TRASH names another command, for the tests): True when the path is gone"""
    trash = os.environ.get("HYIMG_TRASH") or "/usr/bin/trash"
    try: ok = subprocess.run([trash, path], capture_output=True, timeout=600).returncode == 0
    except (OSError, subprocess.SubprocessError): ok = False
    return ok and not os.path.lexists(path)


def _same_volume(a, b):
    return os.stat(a).st_dev == os.stat(b).st_dev


def _files(top):
    out = {}
    for d, _dirs, names in os.walk(top):
        for n in names:
            p = os.path.join(d, n)
            out[os.path.relpath(p, top)] = os.lstat(p).st_size
    return out


def move(src, dest_root, state_root=""):
    """the board's folder src into dest_root; returns {libraryRoot, stateRoot, how}. stateRoot follows when it lies inside src."""
    src = os.path.realpath(src) if not os.path.islink(src) else src
    if os.path.islink(src) or not os.path.isdir(src): raise ValueError("not a folder: " + src)
    if not dest_root or not os.path.isdir(dest_root): raise ValueError("the target folder is not set or not available")
    dest_root = os.path.realpath(dest_root)
    if _inside(dest_root, src): raise ValueError("the target is inside the board's folder")
    dest = os.path.join(dest_root, os.path.basename(src))
    if os.path.dirname(src) == dest_root: raise ValueError("the board is already there")
    if os.path.lexists(dest): raise ValueError("a folder of that name is already there: " + dest)
    state = os.path.realpath(state_root) if state_root else ""
    new_state = os.path.join(dest, os.path.relpath(state, src)) if state and _inside(state, src) else state
    if _same_volume(src, dest_root):
        os.rename(src, dest)
        return {"libraryRoot": dest, "stateRoot": new_state, "how": "rename"}
    tmp = dest + ".hyimg-moving"
    if os.path.lexists(tmp): raise ValueError("an unfinished move is there: " + tmp)
    shutil.copytree(src, tmp, symlinks=True, copy_function=shutil.copy2)
    want, got = _files(src), _files(tmp)
    if want != got:
        bad = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))[:5]
        raise ValueError("the copy differs, the board stays where it was (the copy is kept at " + tmp + "): " + ", ".join(bad))
    os.rename(tmp, dest)
    gone = to_trash(src)
    return {"libraryRoot": dest, "stateRoot": new_state, "how": "copy", "trashed": gone, **({} if gone else {"kept": src})}


if __name__ == "__main__":
    a = sys.argv[1:]
    root = os.path.realpath(os.environ.get("HYIMG_PROFILE_DIR") or os.path.expanduser("~/Library/Application Support/Hyimg"))
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None
    cmd = a[0] if a else "get"
    try:
        if cmd == "set": out = {"places": write(root, **{k: opt("--" + k) for k in KINDS if opt("--" + k) is not None})}
        elif cmd == "move":
            to = read(root).get(a[2]) if len(a) > 2 and a[2] in KINDS else None
            if not to: raise ValueError("choose the " + (a[2] if len(a) > 2 else "") + " folder in Settings › Profile first")
            out = move(a[1], to, opt("--state") or "")
        else: out = {"places": read(root)}
    except (ValueError, OSError, IndexError) as ex:
        out = {"error": str(ex)[:300]}
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(1 if "error" in out else 0)
