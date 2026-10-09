# Version history of the canvas boards (owner 2026-09-30, like Figma's version history).
# A snapshot is the whole board file, gzipped, in boards/_history/<page>/<time>-<who>.json.gz, listed in index.jsonl with
# time, who (owner | ai | auto), label and counts. Restoring first snapshots the current state, so a restore can be undone too.
# Who: saves from the canvas page are the owner; agents that change a board call this script with --who ai before and after.
#   python3 _review/history.py list [page]
#   python3 _review/history.py snapshot [page] --who ai --label "до перестройки разделов"
#   python3 _review/history.py restore [page] <id>
import gzip, json, os, sys, time

from config import HERE, W, BOARDS

# The labels this file writes for the interface in the app's language (owner 2026-10-06: «make 2 versions, Russian and English,
# switchable in settings»): server.py sets tr to its own (the app's setting cv.lang); alone, English.
tr = lambda en, ru: en

AUTO_EVERY = 10 * 60   # an automatic snapshot at the first save after 10 minutes without one


def _dir(page):
    d = os.path.join(BOARDS, "_history", page); os.makedirs(d, exist_ok=True); return d


def entries(page):
    try:
        return [json.loads(l) for l in open(os.path.join(_dir(page), "index.jsonl"), encoding="utf-8") if l.strip()]
    except OSError:
        return []


def counts(board):
    it = board.get("items", {})
    return {"pictures": sum(1 for v in it.values() if v.get("path")), "notes": sum(1 for v in it.values() if v.get("type") == "note"),
            "titles": sum(1 for v in it.values() if v.get("type") == "text"), "groups": len(board.get("groups", {}))}


def snapshot(page, who="owner", label="", board=None, by=None, extra=None):
    """extra: more fields of the entry (merge.py: how many conflicts a merged save lost, which Dropbox copy)"""
    if board is None:
        board = json.load(open(os.path.join(BOARDS, page + ".json"), encoding="utf-8"))
    t = time.time(); sid = time.strftime("%y%m%d-%H%M%S", time.localtime(t)) + "-" + who
    n = 2
    while os.path.exists(os.path.join(_dir(page), sid + ".json.gz")): sid = sid.rsplit("~", 1)[0] + f"~{n}"; n += 1
    with gzip.open(os.path.join(_dir(page), sid + ".json.gz"), "wt", encoding="utf-8") as f:
        json.dump(board, f, ensure_ascii=False)
    e = {"id": sid, "t": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)), "who": who, "label": label, "revision": board.get("revision"), **counts(board)}
    if by: e["by"] = by   # who: {"person": profile id, "via": "app" | agent} (people.py, owner 2026-10-07)
    if extra: e.update({k: v for k, v in extra.items() if k not in e})
    with open(os.path.join(_dir(page), "index.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


def load(page, sid):
    if not all(c.isalnum() or c in "-~" for c in sid): raise PermissionError(sid)
    with gzip.open(os.path.join(_dir(page), sid + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


def auto(page, board, by=None):
    """called by the server after a save from the canvas: one snapshot per 10 minutes of work"""
    last = [e for e in entries(page)]
    if last and time.time() - time.mktime(time.strptime(last[-1]["t"], "%Y-%m-%d %H:%M:%S")) < AUTO_EVERY:
        return None
    return snapshot(page, "auto", tr("auto snapshot", "автоснимок"), board, by)


_MISS = {}


def missing(page, sid, exists):
    """pictures of a snapshot whose file is gone from disk (moved, renamed or deleted since); snapshots never change, so it is cached"""
    if (page, sid) not in _MISS:
        b = load(page, sid)
        _MISS[(page, sid)] = sorted({v["path"] for v in b.get("items", {}).values() if v.get("path") and not exists(v["path"])})
    return _MISS[(page, sid)]


def restore(page, sid, write, by=None):
    """snapshot the current board, then put the old one back as the newest revision; write(board) saves it"""
    cur = json.load(open(os.path.join(BOARDS, page + ".json"), encoding="utf-8"))
    old = load(page, sid)
    when = next((e["t"] for e in entries(page) if e["id"] == sid), sid)
    snapshot(page, "auto", tr("before restoring the version {}", "до возврата к версии {}").format(f"{when[8:10]}.{when[5:7]} {when[11:16]}"), cur, by)
    old["revision"] = cur.get("revision", 0)   # the save below bumps it, so open pages see the change
    return write(old)


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k, d="": a[a.index(k) + 1] if k in a else d
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    cmd, page = (pos + ["list"])[0], (pos[1] if len(pos) > 1 else "main")
    if cmd == "list":
        for e in reversed(entries(page)):
            print(f"{e['id']:<24} {e['t']}  {e['who']:<5} {e['pictures']:>5} кадров  {e['label']}")
    elif cmd == "snapshot":
        print(snapshot(page, opt("--who", "ai"), opt("--label")))
    elif cmd == "restore":
        def write(b):
            b["revision"] = b.get("revision", 0) + 1; b["saved"] = time.strftime("%Y-%m-%d %H:%M:%S"); b.pop("vid", None)   # not the old one's
            p = os.path.join(BOARDS, page + ".json"); json.dump(b, open(p + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p)
            return b["revision"]
        print("restored, revision", restore(page, pos[2], write))
