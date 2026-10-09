"""POST /api/arrange: the board's right click › Arrange runs the agents' layout patterns and the table on what is selected (owner
2026-10-09: «Что у нас с нашим Arrange? Почему у меня нет кнопок для Arrange новых, которые мы разработали ... сетка, таблица, вот это
вот все. Где это все? Почему я не вижу этого?»).

One logic for both: the board sends its page and its selection, the selection becomes a pattern's arguments (patterns.selection) and
the same hy.py do command an agent would type runs on that page here, through hy.py's own commands (patterns.py, grids.py op_table).
Nothing is saved here: the board takes the page back as one undo step and saves it as after any edit. The answer names the command, so
an agent (and the test) can make the same thing with `hy.py do '…'`.

  body {"board": {items, groups, grids?, links?, removed?}, "op": "ab" | "variants" | … | "table", "sel": [ids], "opt": {title, …}}
  200  {"board": {...}, "sel": [ids laid out and made], "log": "…", "cmd": "hy.py do '…'"}
  422  {"error": "…"} when the pattern cannot run (no timeline on the page, too few things)"""
import json
import shlex
import threading

import favread
import grids
import patterns

OPS = tuple(k for k in patterns.RUN if k not in ("mark", "unmark")) + ("table",)
OPT = {"title": str, "phase": str, "tl": str, "color": str, "before": str, "after": str, "a": str, "b": str, "labels": str,
       "picked": str, "decide": str, "rejected": str, "cols": int, "w": int, "x": float, "y": float}
ANCHOR = {"variants", "moodboard", "ab", "before-after", "directions", "docs", "glossary"}   # laid out where the selection began
_lock = threading.Lock()
_hy = []


def _load(port):
    """hy.py as a module, its commands registered (connectors.hook), its server address this one: never the app's 4180"""
    if not _hy:
        import hy
        _hy.append(hy)
    _hy[0].BASE = f"http://localhost:{port}"
    return _hy[0]


def _favs(srv):
    def read(ps):
        out = set()
        for k in range(0, len(ps), favread.MAX):
            out |= {p for p, fb in favread.read(ps[k:k + favread.MAX], srv).items() if fb.get("fav")}
        return out
    return read


def plan(b, op, sel, opt):
    """(the command's words, its key=values): the selection as the pattern's arguments, where it goes"""
    kv = {}
    for k, cast in OPT.items():
        v = (opt or {}).get(k)
        if v is None or v == "": continue
        try: kv[k] = cast(v)
        except (TypeError, ValueError): raise SystemExit(f"{k}: {v!r}")
    if op == "table":
        return ["table", ",".join(sel)], kv
    args = patterns.selection(b, op, sel)
    if not args: raise SystemExit("нечего раскладывать: выдели картинки или карточки")
    if op in ANCHOR or op == "review":
        x, y = grids.origin(b, patterns.on_page(b, ",".join(args)) or [])
        kv.setdefault("x", round(x)); kv.setdefault("y", round(y))
        if op in ANCHOR: kv["at"] = "grid"
    return ["pattern", op, *args], kv


def command(words, kv):
    """the same thing as an agent's hy.py command"""
    num = lambda v: str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    return "hy.py do " + shlex.quote(" ".join([shlex.quote(w) for w in words] + [shlex.quote(f"{k}={num(v)}") for k, v in kv.items()]))


def run(b, op, sel, opt, port, srv=None):
    if op not in OPS: raise SystemExit(f"op: {', '.join(OPS)}")
    for k in ("items", "groups"):
        if not isinstance(b.get(k), dict): b[k] = {}
    sel = [i for i in dict.fromkeys(sel or []) if isinstance(i, str) and (i in b["items"] or i in b["groups"])]
    hy = _load(port)
    words, kv = plan(b, op, sel, opt)
    before = set(b["items"]) | set(b["groups"])
    with _lock:
        if srv is not None: patterns._hy["favs"] = _favs(srv)
        log = hy.OPS[words[0]](b, words[1:], kv)
    made = [k for k in list(b["items"]) + list(b["groups"]) if k not in before]
    page = {k: b[k] for k in ("items", "groups", "grids", "links", "removed") if k in b}
    return {"board": page, "sel": [i for i in sel if i in b["items"] or i in b["groups"]] + made, "log": log, "cmd": command(words, kv)}


def http(h, srv):
    n = int(h.headers.get("Content-Length", 0))
    try:
        d = json.loads(h.rfile.read(n) or b"{}")
        if not isinstance(d, dict) or not isinstance(d.get("board"), dict): raise ValueError("board")
        out = run(d["board"], str(d.get("op") or ""), d.get("sel") or [], d.get("opt") or {}, h.server.server_port, srv)
    except (ValueError, TypeError, KeyError) as e:
        return h.send(400, json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False).encode(), "application/json")
    except SystemExit as e:
        return h.send(422, json.dumps({"error": str(e)[:300]}, ensure_ascii=False).encode(), "application/json")
    return h.send(200, json.dumps(out, ensure_ascii=False).encode(), "application/json")
