"""What happened on a canvas page, event by event (owner 2026-10-02: "not snapshots, but when what was added, with the pictures, and a
click takes me there"). Every save of a board is compared with the board it replaces: pictures added or removed, notes and headings
written, groups made, renamed or taken away, things moved. One line per event in <state>/boards/_events/<page>.jsonl, newest last,
the last KEEP kept. Moves of the same author within a couple of minutes fold into one event, so a long drag is one line."""
import json, os, time

from config import BOARDS

# The labels this file writes for the interface in the app's language (owner 2026-10-06: «make 2 versions, Russian and English,
# switchable in settings»): server.py sets tr to its own (the app's setting cv.lang); alone, English.
tr = lambda en, ru: en

KEEP = 3000          # events per page; about a month of busy work
SAMPLE = 24          # pictures remembered per event for the thumbnails
FOLD_S = 150         # moves of one author closer than this fold into one event


def _path(page):
    return os.path.join(BOARDS, "_events", page + ".jsonl")


def _first(t, n=140):
    return " ".join((t or "").strip().split())[:n]


def _is_pic(it):
    return bool(it) and not it.get("type") and bool(it.get("path"))


def diff(old, new):
    """events that turn board old into board new"""
    oi, ni = old.get("items", {}) or {}, new.get("items", {}) or {}
    og, ng = old.get("groups", {}) or {}, new.get("groups", {}) or {}
    out = []
    added = [i for i, it in ni.items() if i not in oi and _is_pic(it)]
    gone = [i for i, it in oi.items() if i not in ni and _is_pic(it)]
    new_groups = [g for g in ng if g not in og]
    in_new_group = {m for g in new_groups for m in ng[g].get("members", [])}
    # a new group with its new pictures is one event ("group made with 12 pictures"); pictures added elsewhere are another
    for g in new_groups:
        mem = ng[g].get("members", [])
        pics = [m for m in mem if _is_pic(ni.get(m))]
        out.append({"kind": "group", "ids": [g], "title": _first(ng[g].get("title"), 80) or tr("Group", "Группа"), "count": len(pics),
                    "paths": [ni[m]["path"] for m in pics[:SAMPLE]], "new": sum(1 for m in pics if m in added)})
    rest = [i for i in added if i not in in_new_group]
    if rest:
        out.append({"kind": "add", "ids": rest[:200], "count": len(rest), "paths": [ni[i]["path"] for i in rest[:SAMPLE]]})
    if gone:
        out.append({"kind": "remove", "ids": gone[:200], "count": len(gone), "paths": [oi[i]["path"] for i in gone[:SAMPLE]]})
    for g in og:
        if g not in ng:
            out.append({"kind": "group-remove", "ids": [g], "title": _first(og[g].get("title"), 80) or tr("Group", "Группа"),
                        "count": sum(1 for m in og[g].get("members", []) if _is_pic(oi.get(m)))})
        elif (og[g].get("title") or "") != (ng[g].get("title") or ""):
            out.append({"kind": "rename", "ids": [g], "title": _first(ng[g].get("title"), 80), "was": _first(og[g].get("title"), 80)})
    for i, it in ni.items():
        t = it.get("type")
        if t not in ("note", "text", "timeline"): continue
        if i not in oi:
            out.append({"kind": t, "ids": [i], "text": _first(it.get("text") or it.get("label")), "color": it.get("color", "")})
        elif t in ("note", "text") and _first(oi[i].get("text"), 400) != _first(it.get("text"), 400) and _first(it.get("text")):
            out.append({"kind": t + "-edit", "ids": [i], "text": _first(it.get("text")), "color": it.get("color", "")})
    for i, it in oi.items():
        if it.get("type") in ("note", "text") and i not in ni:
            out.append({"kind": it["type"] + "-remove", "ids": [i], "text": _first(it.get("text")), "color": it.get("color", "")})
    moved = [i for i, it in ni.items() if i in oi and (round(it.get("x", 0)) != round(oi[i].get("x", 0)) or round(it.get("y", 0)) != round(oi[i].get("y", 0)))]
    moved_groups = [g for g in ng if g in og and (round(ng[g].get("x", 0)) != round(og[g].get("x", 0)) or round(ng[g].get("y", 0)) != round(og[g].get("y", 0)))]
    if moved or moved_groups:
        pics = [i for i in moved if _is_pic(ni[i])]
        out.append({"kind": "move", "ids": (moved_groups + moved)[:200], "count": len(pics), "groups": len(moved_groups),
                    "titles": [_first(ng[g].get("title"), 60) for g in moved_groups[:4]], "paths": [ni[i]["path"] for i in pics[:SAMPLE]]})
    return out


def record(page, old, new, who="owner", label="", agent=""):
    """agent: the name of the agent behind an AI save (hy.py sends HYIMG_AGENT, e.g. Codex): Home names it in a board's news"""
    evs = diff(old, new)
    if not evs: return 0
    p = _path(page); os.makedirs(os.path.dirname(p), exist_ok=True)
    t = time.strftime("%Y-%m-%d %H:%M:%S"); now = time.time()
    try: lines = open(p, encoding="utf-8").read().splitlines()
    except OSError: lines = []
    last = json.loads(lines[-1]) if lines else None
    for e in evs:
        e.update(t=t, ts=now, who=who, rev=new.get("revision"))
        if label: e["label"] = label[:120]
        if agent: e["agent"] = agent[:40]
        if e["kind"] == "move" and last and last.get("kind") == "move" and last.get("who") == who and last.get("agent", "") == e.get("agent", "") and now - last.get("ts", 0) < FOLD_S:
            ids = list(dict.fromkeys(e["ids"] + last["ids"]))[:200]
            paths = list(dict.fromkeys(e["paths"] + last.get("paths", [])))[:SAMPLE]
            titles = list(dict.fromkeys(e.get("titles", []) + last.get("titles", [])))[:4]
            e.update(ids=ids, paths=paths, titles=titles, count=max(e["count"], last.get("count", 0)), groups=max(e.get("groups", 0), last.get("groups", 0)), since=last.get("since", last["t"]))
            lines[-1] = json.dumps(e, ensure_ascii=False)
        else:
            lines.append(json.dumps(e, ensure_ascii=False))
        last = e
    if len(lines) > KEEP + 300: lines = lines[-KEEP:]
    tmp = p + ".tmp"; open(tmp, "w", encoding="utf-8").write("\n".join(lines) + "\n"); os.replace(tmp, p)
    return len(evs)


def read(page, limit=300, before=None):
    try: lines = open(_path(page), encoding="utf-8").read().splitlines()
    except OSError: return []
    out = []
    for l in reversed(lines):
        try: e = json.loads(l)
        except ValueError: continue
        if before and e.get("ts", 0) >= before: continue
        out.append(e)
        if len(out) >= limit: break
    return out
