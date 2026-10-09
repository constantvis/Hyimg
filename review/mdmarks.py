"""hy.py md: the comments and drawings on a page, in its Markdown (owner 2026-10-09, note nu6e6cs2 on «grid is a table»: «Эта механика же
и к Annotations (comments) применяется, верно?»). A thing with open comment threads gets «💬N» after its [id], with drawings «✎N», in a
table's cell as on any line, and the page ends with a section that lists them: which thread, on what, where in its grid, who wrote what.
The section is read only: `hy.py md apply` stops at its header and skips the marks (mdapply.MARKS). Threads and drawings themselves are
`hy.py comments` and `hy.py annotations`; a reply goes in the thread only by the rules of the skill hyimg-board."""
import re
import urllib.parse

import grids

HEADER = "## 💬 Комментарии и пометки"
QUOTE = 90


def _people(api):
    try:
        code, res = api("/api/profile")   # who is who, as hy.py comments names them (hycomments.py)
        return (res.get("people") or {}) if code == 200 and isinstance(res, dict) else {}
    except Exception:
        return {}


def _who(by, people):
    p = people.get((by or {}).get("person")) or {}
    via = (by or {}).get("via", "app")
    return (p.get("name") or "?") if via == "app" else f"{via.capitalize()} · {p.get('name') or '?'}"


def where(b, oid):
    """an object in words for the list: its name and id, and its cell when it is in a grid"""
    if oid not in (b.get("items") or {}): return f"[{oid}] (его уже нет на странице)"
    g = grids.of(b, oid); out = grids.cell(b, oid)
    if g:
        rws, cols = grids.grid_rows(b, g); k = [m for r in rws for m in r].index(oid)
        out += f", сетка {g}: ряд {k // cols + 1}, колонка {k % cols + 1}"
    return out


def add(text, b, page, api):
    """text with the marks: counts after the [id]s, the list at the end; the text as it was when the server has no comments for it"""
    try:
        code, res = api("/api/annotations?" + urllib.parse.urlencode({"name": page, "describe": "1"}))
    except Exception:
        return text
    if code != 200 or not isinstance(res, dict): return text
    threads = [t for t in res.get("threads") or [] if not t.get("resolved")]
    drawings = res.get("items") or []
    obj = lambda x: (x.get("anchor") or {}).get("obj")
    n_t, n_d = {}, {}
    for t in threads:
        if obj(t): n_t[obj(t)] = n_t.get(obj(t), 0) + 1
    for d in drawings:
        if obj(d): n_d[obj(d)] = n_d.get(obj(d), 0) + 1
    if not threads and not drawings: return text

    def mark(m):
        i = m.group(1)
        tail = (f" 💬{n_t[i]}" if i in n_t else "") + (f" ✎{n_d[i]}" if i in n_d else "")
        return m.group(0) + tail

    out = re.sub(r"\[([A-Za-z0-9_-]+)\]", mark, text)
    people = _people(api)
    lines = ["", HEADER, ""]
    for t in threads:
        ms = t.get("messages") or [{}]
        m0 = ms[0]; words = " ".join((m0.get("text") or "").split())
        on = where(b, obj(t)) if obj(t) else "на доске x {} y {}".format(*[round(v) for v in (t.get("at") or [0, 0])[:2]])
        more = f" · ответов {len(ms) - 1}" if len(ms) > 1 else ""
        area = " · область" if t.get("area") else ""
        lines.append(f"- 💬 [{t['id']}] {on}{area}: {_who(m0.get('by'), people)}: «{words[:QUOTE]}{'…' if len(words) > QUOTE else ''}»{more}")
    for d in drawings:
        words = " ".join((d.get("describe") or d.get("kind") or "").split())
        lines.append(f"- ✎ [{d['id']}] " + (where(b, obj(d)) + ": " if obj(d) else "") + words[:QUOTE + 30])
    return out.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
