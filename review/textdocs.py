"""Text documents on the board, the agent's side (owner 2026-10-09: «нужно, чтобы мы могли не только title писать, а как в Notes Apple:
когда сверху пишешь — это title, далее обычный текст. И чтобы это была Markdown-структура»). ui/textdoc.js is the same model on the board.

A text item {"type": "text", "text": ..., "fs", "size", "tw"?} holds a small Markdown document in its `text`:
  the first line   the title, at the item's size (a heading with nothing under it is exactly the heading it always was)
  the rest         the body: half the title's size; # ## ### headings, - and 1. lists, - [ ] / - [x] checklists, > quotes, --- rules,
                   **bold**, *italic*, `code`, [links](https://…)
  tw               the width a document wraps at (board units); a title alone has none and is as wide as its words
  tm, th           its box, as Figma's text (owner 2026-10-11, ui/textbox.js): tm "w" Auto width, "h" Auto height (wraps at tw), "f" Fixed
                   size (tw × th, the words wrap and what does not fit shows below); no tm: a title Auto width, a document Auto height

Here: split, the body as Markdown under a heading of hy.py md (body_md), a size estimate before the board measures it, the box (mode,
box, mark), and hy.py's `text` command (\\n in its argument is a new line; w= h= mode= the box) and `set REF text=…` with \\n, w= h= mode=."""
import math
import re

TSIZE = [24, 40, 72, 128, 874]   # canvas.html TSIZE: Small, Regular, Large, Heading, Big heading
BODY = 0.5                       # the body's type, a share of the title's (ui/textdoc.css .tb)
WRAP = 14                        # a new document's width in title letters (ui/textdoc.js autoW)

def split(text):
    s = text or ""
    i = s.find("\n")
    return (s, "") if i < 0 else (s[:i], s[i + 1:])


def is_doc(it): return isinstance(it, dict) and it.get("type") == "text" and bool(split(it.get("text"))[1].strip())
def unescape(s): return str(s).replace("\\n", "\n")


def body_md(text, level):
    """the body's lines for hy.py md under the document's heading of this level: its own headings one level and more below it"""
    body = split(text)[1].rstrip()
    if not body.strip(): return []
    out = []
    for ln in body.split("\n"):
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        out.append(f"{'#' * min(6, level + len(m.group(1)))} {m.group(2)}" if m else ln)
    while out and not out[0].strip(): out.pop(0)
    return [""] + out


def mode(it):
    """its box: tm as set, else what it always was (a title Auto width, a document Auto height); Fixed needs its height (ui/textdoc.js)"""
    m = it.get("tm")
    if m == "f": return "f" if (it.get("th") or 0) > 0 else "h"
    return m if m in ("w", "h") else "h" if is_doc(it) else "w"


def mark(it):
    """hy.py md's mark after a text's [id]: ▭W×H a Fixed box, ▭W a title that wraps (mdapply.py MARKS reads past it)"""
    m = mode(it)
    if m == "f": return f" ▭{round(it.get('tw') or 0)}×{round(it['th'])}"
    return f" ▭{round(it.get('tw') or 0)}" if m == "h" and it.get("tm") == "h" and not is_doc(it) else ""


def box(it, w=None, h=None, m=None):
    """a text's box from hy.py (w=, h=, mode=): mode w Auto width, h Auto height at w, f Fixed w × h; w alone on a title Auto height, h
    Fixed; nothing: a document wraps at its width and a title is as wide as its words, as before"""
    if m not in (None, "w", "h", "f"): raise SystemExit("mode=w (auto width), h (auto height) или f (fixed size)")
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None
    w, h, fs = num(w), num(h), it.get("fs") or 40
    if m is None: m = "f" if h else "h" if w and not is_doc(it) else None
    if m == "w":
        it.pop("tw", None); it.pop("th", None)
        if is_doc(it): it["tm"] = "w"
        else: it.pop("tm", None)
    elif m in ("h", "f"):
        it["tm"] = m; it["tw"] = round(w or it.get("tw") or fs * WRAP)
        if m == "f": it["th"] = round(h or it.get("th") or estimate({**it, "tm": "h"})[1])
        else: it.pop("th", None)
    elif w and mode(it) != "w": it["tw"] = round(w)
    elif not it.get("tm"):   # never sized by hand: a document wraps at its width, a title loses it
        if is_doc(it): it["tw"] = round(it.get("tw") or fs * WRAP)
        else: it.pop("tw", None)
    it["w"], it["h"] = estimate(it)


def estimate(it):
    """(w, h) in board units before the board measures it: a title by its letters, a document by its lines at its width, a Fixed box its own"""
    fs = it.get("fs") or 40
    title, body = split(it.get("text"))
    m = mode(it)
    if m == "f": return round(it.get("tw") or fs * WRAP), round(it["th"])
    if m == "w" and body.strip():   # a document on one line each: as wide as its longest
        L = [title, *body.rstrip().split("\n")]
        return round(max(fs * .6 * len(title), *(fs * BODY * .55 * len(x) for x in L[1:]))), round(fs * 1.15 + fs * BODY * (.4 + 1.45 * (len(L) - 1)))
    if not body.strip():
        if m != "h": return round(fs * .6 * len(title)), round(fs * 1.15)
        w = it.get("tw") or round(fs * WRAP)
        return round(w), round(math.ceil(max(1, len(title)) * fs * .6 / w) * fs * 1.15)
    w = it.get("tw") or round(fs * WRAP)
    h = math.ceil(max(1, len(title)) * fs * .6 / w) * fs * 1.15 + fs * BODY * .4
    bf = fs * BODY
    for ln in body.rstrip().split("\n"):
        m = re.match(r"^(#{1,3})\s+", ln); k = (1.6, 1.3, 1.1)[len(m.group(1)) - 1] if m else 1
        h += (math.ceil(max(1, len(ln)) * bf * k * .55 / w) * bf * k * 1.45) if ln.strip() else bf * .7
    return w, round(h)


def op_text(b, args, kv, uid):
    text = unescape(args[0]).replace("\r\n", "\n").rstrip()
    doc = bool(split(text)[1].strip())
    if "size" in kv: size = max(0, min(4, int(kv["size"]))); fs = kv.get("fs", TSIZE[size])
    elif doc and "fs" not in kv: size, fs = 1, TSIZE[1]
    else: size, fs = 4, kv.get("fs", 874)   # a heading as hy.py always made it: Big heading's weight, any fs
    id = uid("t")
    it = {"type": "text", "text": text, "x": kv["x"], "y": kv["y"], "fs": fs, "size": size}
    box(it, kv.get("w"), kv.get("h"), kv.get("mode"))
    b["items"][id] = it
    return f"text {id} «{split(text)[0][:30]}»" + (f" +{len(split(text)[1].strip().splitlines())} строк" if doc else "") + f" x {round(kv['x'])} y {round(kv['y'])}"


def register(ops, uid, resolve):
    """hy.py: `text` makes titles and documents; `set REF text="…"` reads \\n as a new line, `set REF w=N h=N mode=w|h|f` its box"""
    ops["text"] = lambda b, args, kv: op_text(b, args, kv, uid)
    plain = ops["set"]

    def op_set(b, args, kv):
        k, id, _nm, _r = resolve(b, args[0], {"group", "heading", "note", "timeline"})
        if "text" in kv: kv = {**kv, "text": unescape(kv["text"])}
        m = kv.get("mode") if k == "heading" else None
        if k == "heading": kv = {x: v for x, v in kv.items() if x != "mode"}
        out = plain(b, args, kv)
        it = b["items"].get(id) if k == "heading" else None
        if it: box(it, kv.get("w"), kv.get("h"), m)   # a text whose body came or went, or whose box was set
        return out + (f" mode={m}" if m else "")
    ops["set"] = op_set
