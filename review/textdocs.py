"""Text documents on the board, the agent's side (owner 2026-10-09: «нужно, чтобы мы могли не только title писать, а как в Notes Apple:
когда сверху пишешь — это title, далее обычный текст. И чтобы это была Markdown-структура»). ui/textdoc.js is the same model on the board.

A text item {"type": "text", "text": ..., "fs", "size", "tw"?} holds a small Markdown document in its `text`:
  the first line   the title, at the item's size (a heading with nothing under it is exactly the heading it always was)
  the rest         the body: half the title's size; # ## ### headings, - and 1. lists, - [ ] / - [x] checklists, > quotes, --- rules,
                   **bold**, *italic*, `code`, [links](https://…)
  tw               the width a document wraps at (board units); a title alone has none and is as wide as its words

Here: split, the body as Markdown under a heading of hy.py md (body_md), a size estimate before the board measures it, and hy.py's
`text` command (\\n in its argument is a new line) and `set REF text=…` with \\n."""
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


def estimate(it):
    """(w, h) in board units before the board measures it: a title by its letters, a document by its lines at its width"""
    fs = it.get("fs") or 40
    title, body = split(it.get("text"))
    if not body.strip(): return round(fs * .6 * len(title)), round(fs * 1.15)
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
    if doc: it["tw"] = round(kv.get("w") or fs * WRAP)
    it["w"], it["h"] = estimate(it)
    b["items"][id] = it
    return f"text {id} «{split(text)[0][:30]}»" + (f" +{len(split(text)[1].strip().splitlines())} строк" if doc else "") + f" x {round(kv['x'])} y {round(kv['y'])}"


def register(ops, uid, resolve):
    """hy.py: `text` makes titles and documents; `set REF text="…"` reads \\n as a new line, `set REF w=N` is a document's width"""
    ops["text"] = lambda b, args, kv: op_text(b, args, kv, uid)
    plain = ops["set"]

    def op_set(b, args, kv):
        k, id, _nm, _r = resolve(b, args[0], {"group", "heading", "note", "timeline"})
        if "text" in kv: kv = {**kv, "text": unescape(kv["text"])}
        out = plain(b, args, kv)
        it = b["items"].get(id) if k == "heading" else None
        if it:   # a text whose body came or went, or whose width was set
            if is_doc(it): it["tw"] = round(kv["w"]) if isinstance(kv.get("w"), (int, float)) else it.get("tw") or round((it.get("fs") or 40) * WRAP)
            else: it.pop("tw", None)
            it["w"], it["h"] = estimate(it)
        return out
    ops["set"] = op_set
