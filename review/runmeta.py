"""How long a picture took to make, what it cost and where it ran, read from its json however an agent spelled it (owner 2026-10-11 on the
Info card of a LaMa clean-up: «вот тут нужно ещё обязательно затраченное время на генерацию или рендеринг, обязательный параметр, и
количество токенов или кредитов потраченных при возможности, либо compute power какой-то условный»; and «ну это для 3д генераций в том
числе»). One reading for every place that shows or checks it: the server's /api/items ("run" of each frame), /api/meta ("run" with the
chain), the Info card (ui/infobody.js only formats), `hy.py undocumented` (generated files without a time).

What new files write (docs/data.md «Время, стоимость, где считалось»):
  "seconds": 892.7                     required for anything generated or rendered: the wall time of the run that made this file
  "cost": {"tokens": {"in", "out", "total"}, "credits": {"n", "service"}, "usd"}   whatever of it is known
  "compute": "local · M3 Max GPU"      where it ran: «ChatGPT web», «Codex CLI», «Blender Cycles · GPU · 128 samples»

Old files keep what they have; nothing here guesses a time from file dates. The spellings below are the ones found in the owner's
libraries on 2026-10-11 (seconds, time_s, render_seconds, elapsed_seconds, wall_s, ms, params.seconds, metrics.time_s, render.times;
usage of OpenAI and Gemini, credits, cost as words; engine, device, samples). "duration" and "duration_s" are not read: there they are
the length of a video, not the time it took.
"""
import math
import os

SECONDS = ("seconds", "time_s", "elapsed_s", "elapsed_seconds", "elapsed", "render_seconds", "render_s", "took", "took_s", "wall_s",
           "generation_seconds", "gen_seconds", "times")
MS = ("ms", "elapsed_ms", "time_ms", "took_ms", "duration_ms")
NESTS = ("params", "metrics", "run", "render", "stats", "timing", "result")   # where agents put them besides the top
TOK_IN = ("in", "input", "input_tokens", "prompt_tokens", "promptTokenCount", "inputTokens")
TOK_OUT = ("out", "output", "output_tokens", "completion_tokens", "candidatesTokenCount", "outputTokens")
TOK_ALL = ("total", "total_tokens", "totalTokenCount", "totalTokens")
MADE = ("model", "tool", "generator", "engine", "render_engine", "route")   # a file made by something, not taken from somewhere
TAKEN = ("source_url", "image_url", "post_url")                            # a downloaded reference: nobody here made it
SOURCES = ("inputs", "sources", "original")


def num(v):
    """a finite number not below 0, from a number or a numeric string («12.5», «12.5 s»); else None"""
    if isinstance(v, bool): return None
    if isinstance(v, str):
        try: v = float(v.strip().split()[0].rstrip("s")) if v.strip() else None
        except ValueError: return None
    if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0: return v
    return None


def _secs(v):
    """a seconds value: a number, or a dict of stages ({"render": 8.37, "comp": 1.65} or with its own "total")"""
    if isinstance(v, dict):
        if num(v.get("total")) is not None: return num(v["total"])
        parts = [num(x) for x in v.values() if num(x) is not None]
        return round(sum(parts), 3) if parts else None
    return num(v)


def seconds(d):
    """(seconds, the key it came from) of a file's json, or (None, None)"""
    if not isinstance(d, dict): return None, None
    for where, src in [("", d)] + [(n + ".", d[n]) for n in NESTS if isinstance(d.get(n), dict)]:
        for k in SECONDS:
            if k in src and _secs(src[k]) is not None: return _secs(src[k]), where + k
        for k in MS:
            if k in src and num(src[k]) is not None: return round(num(src[k]) / 1000, 3), where + k
    return None, None


def _first(d, keys):
    for k in keys:
        if isinstance(d, dict) and num(d.get(k)) is not None: return num(d[k])
    return None


def cost(d):
    """{"tokens": {"in", "out", "total"}, "credits": {"n", "service"}, "usd", "note"} with only what the json says; {} when nothing"""
    if not isinstance(d, dict): return {}
    c, out = d.get("cost"), {}
    c = c if isinstance(c, dict) else ({"note": c.strip()} if isinstance(c, str) and c.strip() else {"usd": c} if num(c) is not None else {})
    tok = c.get("tokens") if c.get("tokens") is not None else d.get("usage") if isinstance(d.get("usage"), dict) else d.get("tokens", d)
    if isinstance(tok, dict):
        top = (lambda ks: [k for k in ks if "_" in k or k[-5:] == "Count"]) if tok is d else (lambda ks: ks)   # at the top only token words
        t = {k: v for k, v in (("in", _first(tok, top(TOK_IN))), ("out", _first(tok, top(TOK_OUT))), ("total", _first(tok, top(TOK_ALL)))) if v is not None}
        if t: out["tokens"] = t
    elif num(tok) is not None: out["tokens"] = {"total": num(tok)}
    cr = c.get("credits", d.get("credits"))
    n = num(cr.get("n", cr.get("count"))) if isinstance(cr, dict) else num(cr)
    if n is not None:
        service = (cr.get("service") if isinstance(cr, dict) else None) or d.get("credits_service") or d.get("service") or d.get("provider")
        out["credits"] = {"n": n, **({"service": str(service)} if isinstance(service, str) and service else {})}
    usd = num(c.get("usd")) if num(c.get("usd")) is not None else _first(d, ("cost_usd", "usd", "price"))
    if usd is not None: out["usd"] = usd
    if isinstance(c.get("note"), str): out["note"] = c["note"]
    return out


def compute(d):
    """where it ran, as words: the json's own "compute", else made of its provider, engine, device and samples; "" when nothing"""
    if not isinstance(d, dict): return ""
    if isinstance(d.get("compute"), str) and d["compute"].strip(): return d["compute"].strip()
    nests = [d] + [d[n] for n in ("render", "params", "request") if isinstance(d.get(n), dict)]
    nests += [x["info"] for x in nests if isinstance(x.get("info"), dict)]
    pick = lambda *ks: next((str(x[k]) for x in nests for k in ks if isinstance(x.get(k), (str, int)) and not isinstance(x[k], bool) and str(x[k]).strip()), "")
    engine = pick("engine", "render_engine").replace("BLENDER_", "")
    samples = next((num(x[k]) for x in nests for k in ("samples",) if num(x.get(k)) is not None), None) if engine else None
    parts = [pick("provider"), engine, pick("device", "gpu"), f"{int(samples)} samples" if samples else ""]
    return " · ".join(p for p in parts if p)


def made(d):
    """the json says something made this file (a model, a tool, a render), and it is not a downloaded reference"""
    return isinstance(d, dict) and (any(d.get(k) for k in MADE) or seconds(d)[0] is not None) and not any(d.get(k) for k in TAKEN)


def of(d):
    """the one normalized view of a file's json: {"seconds", "cost", "compute", "made"}, only the keys that are known"""
    s, c, w = seconds(d)[0], cost(d), compute(d)
    return {**({"seconds": s} if s is not None else {}), **({"cost": c} if c else {}), **({"compute": w} if w else {}),
            **({"made": True} if made(d) else {})}


def sources(d):
    """the files this one was made from, as the json names them: inputs, sources, original; a 3D scene's model files"""
    out = []
    def add(v):
        if isinstance(v, str) and v: out.append(v)
        elif isinstance(v, dict): add(v.get("path")) if isinstance(v.get("path"), str) else [add(x) for x in v.values() if isinstance(x, str)]
        elif isinstance(v, list): [add(x) for x in v]
    for k in SOURCES: add(d.get(k))
    for o in (d["objects"] if isinstance(d.get("objects"), list) else []):   # a 3D scene (hyimg-3d-studio scene.json)
        s = o.get("src") if isinstance(o, dict) else None
        if isinstance(s, dict): add(s.get("path")) if s.get("path") else add("3d/models/" + s["model"]) if isinstance(s.get("model"), str) else None
    return list(dict.fromkeys(out))


def sidecar_of(full):
    """the json beside a file: <name>.json of a picture, <file>.<ext>.json of a video, PDF or 3D file (either is read)"""
    for p in (full + ".json", os.path.splitext(full)[0] + ".json"):
        if p != full and os.path.isfile(p): return p
    return None


def chain(d, folder, root, read, limit=200):
    """the time of the whole chain behind a file: its own seconds and those of every file it was made from, each once, following their
    jsons back (inputs, sources, original). folder: the file's folder; root: the library (sources outside it are not read); read(path) ->
    dict. {"seconds", "steps", "untimed", "parts": [{"path", "run"}] of the direct sources} or {} when no source has a time"""
    root = os.path.realpath(root)
    def find(src, at):
        for p in ([src] if os.path.isabs(src) else [os.path.join(at, src), os.path.join(root, src)]):
            p = os.path.realpath(p)
            if p.startswith(root + os.sep) and os.path.isfile(p): return p
        return None
    seen, total, steps, untimed, parts, timed = set(), 0.0, 0, 0, [], False
    own = seconds(d)[0]
    if own is not None: total, steps = own, 1
    elif made(d): steps, untimed = 1, 1
    todo = [(s, folder, 1) for s in sources(d)]
    while todo and len(seen) < limit:
        src, at, depth = todo.pop(0); p = find(src, at)
        if not p or p in seen: continue
        seen.add(p); side = sidecar_of(p); m = read(side) if side else {}
        m = m if isinstance(m, dict) else {}; r = of(m)
        if depth == 1 and r: parts.append({"path": os.path.relpath(p, root), "run": r})
        if "seconds" in r: total += r["seconds"]; steps += 1; timed = True
        elif r.get("made"): steps += 1; untimed += 1
        todo += [(s, os.path.dirname(p), depth + 1) for s in sources(m)]
    if not timed and not parts: return {}
    return {**({"seconds": round(total, 3)} if timed else {}), "steps": steps, "untimed": untimed, "parts": parts}


def view(d, full, root, read):
    """what /api/meta adds for the Info card: {"run": the file's own view and, when its sources have times, the chain's}, or {} when the
    json says nothing of it (a downloaded reference keeps its answer as it was)"""
    c = chain(d, os.path.dirname(full), root, read) if isinstance(d, dict) else {}
    run = {**of(d), **({"chain": c} if c else {})}
    return {"run": run} if run else {}


def untimed(items):
    """frames of /api/items that something made and whose json has no time: what `hy.py undocumented` lists"""
    return [i for i in items if (i.get("run") or {}).get("made") and "seconds" not in i["run"]]


def record(path, secs, comp, **extra):
    """the json beside a file Hyimg itself just made (a still, a render): its seconds and where it ran, with what else is known; returns
    {"seconds", "compute"} for the answer of the route that made it"""
    import json
    run = {"seconds": round(secs, 2), "compute": comp}
    side = os.path.splitext(path)[0] + ".json"
    with open(side + ".tmp", "w", encoding="utf-8") as f: json.dump({**extra, **run}, f, ensure_ascii=False, indent=1)
    os.replace(side + ".tmp", side)
    return run
