"""Image Studio for agents (owner 2026-10-10: «научить агента пользоваться всеми тулзами в Image Studio: вырезать, рисовать ... не нажимая
кнопки»). An agent works on an image frame with the person's own tools: select, mask, fill, brush, erase, layers, transform, content-aware
fill, save. The commands run inside Image Studio itself (plugin frames, editor/agentops.js, window.hyImage), in headless Chromium, so a
step is the tool's step with the tool's name in History; Save writes a new version of the frame (the pictures and older versions stay)
and the frame's card on the board takes it, one step of the board's history, as the person's Save. Coordinates: the image's own pixels.

  hy.py image look F|PATH [grid=100] [crop=x,y,w,h] [max=1800] [--out P.png]   a PNG to look at, every 100 px a line, labelled in image px
  hy.py image run F OPS.json|'[{"op": …}, …]' [--dry] [--out P.png] [--grid]  the commands, then Save (--dry: no Save); prints the steps
                                       and the picture as the studio shows it (--grid: also gridded, to read the next coordinates)
  hy.py image export F --out P.png      the frame's last saved render (without its master Raw Editor and mask, which the board applies)
  hy.py image ops                       every command and what it takes (from the plugin's agentops.js)

F is an image frame's id or name; make one from a picture with hy.py do 'frame <picture id>'. Also standalone:
python3 review/imageops.py look … --port N --page P. Needs Playwright with Chromium for run (as render_html.py).
"""
import base64
import io
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HELP = __doc__.split("\n\n")[1] + "\n"
OUT = os.path.join(tempfile.gettempdir(), "hyimg-imageops")   # never the library: what an agent looks at is not the person's


def _out(name):
    os.makedirs(OUT, exist_ok=True)
    return os.path.join(OUT, re.sub(r"[^\w.-]+", "_", name)[:80] + time.strftime("-%H%M%S") + ".png")


def grid(im, step=100, crop=None, maxside=1800):
    """the picture with a line every `step` px of its own, labelled in its own px at the top and the left; crop (x, y, w, h) shows a part
    of it with its own coordinates; the result fits maxside (the labels stay the picture's pixels)"""
    from PIL import Image, ImageDraw, ImageFont
    x0 = y0 = 0
    if crop:
        x0, y0, w, h = (int(round(v)) for v in crop)
        im = im.crop((x0, y0, x0 + w, y0 + h))
    s = min(1.0, maxside / max(im.size))
    base = im.convert("RGBA")
    if s < 1: base = base.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", base.size, (128, 128, 128, 255)); out.alpha_composite(base)   # transparency reads as grey
    d = ImageDraw.Draw(out, "RGBA")
    try: font = ImageFont.load_default(size=13)
    except TypeError: font = ImageFont.load_default()
    k = next((k for k in (1, 2, 5, 10, 20, 50, 100) if step * k * s >= 36), 100)   # labels never closer than 36 px
    for axis, lo, n in (("x", x0, im.width), ("y", y0, im.height)):
        v = math.ceil(lo / step) * step
        while v <= lo + n:
            p = round((v - lo) * s); big = (v // step) % k == 0
            seg = [(p, 0), (p, out.height)] if axis == "x" else [(0, p), (out.width, p)]
            if big: d.line([(a + 1, b + 1) for a, b in seg], fill=(0, 0, 0, 120))
            d.line(seg, fill=(255, 255, 255, 170 if big else 55))
            if big and not (axis == "y" and p < 16):   # the corner is the top row's label
                t = str(v); tw = d.textlength(t, font=font)
                at = (p + 3, 2) if axis == "x" else (2, p + 2)
                d.rectangle([at[0] - 2, at[1] - 1, at[0] + tw + 2, at[1] + 14], fill=(0, 0, 0, 160)); d.text(at, t, fill=(255, 255, 255, 255), font=font)
            v += step
    return out.convert("RGB"), s


def _bytes(g, path):
    with urllib.request.urlopen(g["BASE"] + path, timeout=120) as r: return r.read()


def _frame(g, page, ref):
    _, b = g["api"](f"/api/board?name={urllib.parse.quote(page)}")
    fid = g["frame_ref"](b, ref)
    return fid, b["items"][fid]


def look(g, page, ref, step=100, crop=None, maxside=1800, out=None):
    from PIL import Image
    if ref in ("-", "") or re.search(r"\.(png|jpe?g|webp|heic|tiff?)$", ref, re.I) and "/" in ref:   # a picture of the library
        im, name = Image.open(io.BytesIO(_bytes(g, "/img?p=" + urllib.parse.quote(ref)))), os.path.basename(ref)
    else:
        fid, card = _frame(g, page, ref)
        im, name = Image.open(io.BytesIO(_bytes(g, "/file?p=" + urllib.parse.quote(card["render"])))), f"{card.get('name') or fid}-v{card.get('v', 1)}"
    full = im.size
    pic, s = grid(im, step, crop, maxside)
    path = out or _out(name + "-look"); pic.save(path)
    print(f"{path}\n{full[0]}×{full[1]} px" + (f", crop {','.join(str(int(v)) for v in crop)}" if crop else "") +
          f"; a line every {step} px, the labels are the picture's own px" + (f"; shown at {s:.3f}" if s < 1 else ""))
    return path


def ops_list(g):
    src = _bytes(g, "/plugins/frames/editor/agentops.js").decode("utf-8")
    return [(n, a.replace("\\'", "'")) for n, a in re.findall(r"^\s*'?([\w.]+)'?: \{ args: '((?:[^'\\]|\\.)*)'", src, re.M)]


def apply_saved(card, res):
    """the card takes the new version as the board does when the studio saves (imgframe.js saved)"""
    card.update(rv=res["rv"], size=res["size"], name=res.get("name") or card.get("name"), pics=res.get("pics") or card.get("pics"))
    if res.get("doc"): card.update(doc=res["doc"], render=res["render"], v=res["v"])
    if res.get("alpha"): card["alpha"] = True
    else: card.pop("alpha", None)
    for k in ("grade", "mask"):
        if k in res:
            if res[k]: card[k] = res[k]
            else: card.pop(k, None)
    nh = round(card["w"] * res["size"][1] / res["size"][0])
    if abs(nh - card["h"]) > 1: card["h"] = nh


def save_board(g, page, label, fn):
    """fn(board) on the fresh board, saved as hy.py do saves: the board's history before and after (who: ai), again when the person saved
    in between"""
    api = g["api"]
    for attempt in range(4):
        _, b = api(f"/api/board?name={urllib.parse.quote(page)}")
        log = fn(b)
        if attempt == 0: _, e = api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"до: {label}"})
        code, res = api(f"/api/board?name={urllib.parse.quote(page)}", b)
        if code == 200: break
        if code != 409: raise SystemExit(f"сервер не сохранил доску: {code} {res}")
    else:
        raise SystemExit("доску все время сохраняют, не смог записать карточку; версия фрейма записана, повтори run без команд")
    _, e2 = api("/api/history", {"action": "save", "name": page, "who": "ai", "label": f"после: {label}"})
    vid = lambda x: x.get("id") if isinstance(x, dict) else "нет"
    return log + [f"ревизия {res.get('revision')} · версии {vid(e)} → {vid(e2)}"]


def run(g, page, ref, ops, dry=False, out=None, gridded=False, timeout=240):
    from playwright.sync_api import sync_playwright
    fid, card = _frame(g, page, ref)
    if not dry and not any(o.get("op") == "save" for o in ops): ops = ops + [{"op": "save"}]
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            pg = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(f"{g['BASE']}/plugins/frames/editor/agenthost.html?page={urllib.parse.quote(page)}&id={urllib.parse.quote(fid)}")
            fr, t0 = None, time.time()
            while not fr:
                bad = pg.evaluate("() => window.__hyHostError || null")
                if bad: raise SystemExit(f"Image Studio не открылся: {bad}")
                fr = next((f for f in pg.frames if "/editor/index.html" in f.url), None)
                if time.time() - t0 > 30: raise SystemExit("Image Studio не открылся: нет плагина frames на этом сервере?")
                if not fr: time.sleep(0.1)
            fr.wait_for_function("() => window.hyImage && window.__ed && __ed.ready", timeout=60000)
            res = fr.evaluate("ops => hyImage.run(ops)", ops)
            shot = fr.evaluate("() => hyImage.png(1)")
            saved = pg.evaluate("() => window.__hySaved || null")
        finally:
            browser.close()
    for i, r in enumerate(res.get("results", [])):
        bits = [f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in r.items() if k not in ("op", "layers", "history", "res") and v is not None]
        print(f"{i + 1}. {r['op']}  " + "  ".join(bits))
    if not res.get("ok"):
        print(f"ОШИБКА в команде {res.get('at', 0) + 1} ({res.get('op')}): {res.get('error')}" + (f"\nстраница: {errors[-1]}" if errors else ""))
    print("шаги History: " + (", ".join(res.get("steps") or []) or "нет"))
    data = base64.b64decode(shot["png"].split(",", 1)[1])
    path = out or _out(f"{card.get('name') or fid}-{'dry' if dry or not saved else 'v' + str(saved.get('v'))}")
    with open(path, "wb") as f: f.write(data)
    print(f"картинка: {path} ({shot['w']}×{shot['h']} px, как в студии)")
    if gridded:
        from PIL import Image
        gp = path[:-4] + "-grid.png"; grid(Image.open(io.BytesIO(data)))[0].save(gp); print(f"с сеткой: {gp}")
    if saved and res.get("ok"):
        def put(b):
            c = b["items"].get(fid)
            if not c: raise SystemExit(f"фрейма {fid} уже нет на странице")
            apply_saved(c, saved); return [f"frame {fid} «{c.get('name')}»: версия {saved.get('v')}, {saved['doc']}"]
        label = g.get("LABEL") or f"Image Studio: {', '.join(res.get('steps') or ['Save'])}"[:120]
        g["LABEL"] = label; print("\n".join(save_board(g, page, label, put)))
    elif not dry and res.get("ok"):
        print("НЕ СОХРАНЕНО: студия не вернула новую версию")
    if not res.get("ok"): raise SystemExit(1)
    return res


def _ops_arg(a):
    if a == "-": return json.load(sys.stdin)
    if os.path.isfile(a):
        with open(a, encoding="utf-8") as f: return json.load(f)
    return json.loads(a)


def cli(argv, g):
    val = ("--page", "--port", "--label", "--out")
    o, pos = {}, []
    it = iter(argv)
    for x in it:
        if x in val: o[x] = next(it)
        elif x.startswith("--"): o[x] = True
        else: pos.append(x)
    if "--port" in o: g["BASE"] = f"http://localhost:{int(o['--port'])}"
    if "--label" in o: g["LABEL"] = o["--label"]
    kv = dict(a.split("=", 1) for a in pos if re.fullmatch(r"[a-z]+=.*", a)); pos = [a for a in pos if not re.fullmatch(r"[a-z]+=.*", a)]
    if not pos or pos[0] in ("help", "-h"): print(HELP); return
    sub, rest = pos[0], pos[1:]
    if sub == "ops":
        for name, args in ops_list(g): print(f"{name:28} {args}")
        return
    page = o.get("--page")
    if not page:
        try: page = (g["api"]("/api/live")[1].get("canvas") or {}).get("page") or "main"
        except Exception: page = "main"
    if not rest: raise SystemExit(f"hy.py image {sub} ФРЕЙМ …\n\n{HELP}")
    if sub == "look":
        crop = [float(v) for v in kv["crop"].split(",")] if kv.get("crop") else None
        return look(g, page, rest[0], int(kv.get("grid", 100)), crop, int(kv.get("max", 1800)), o.get("--out"))
    if sub == "export":
        fid, card = _frame(g, page, rest[0]); path = o.get("--out") or _out(f"{card.get('name') or fid}-v{card.get('v', 1)}")
        with open(path, "wb") as f: f.write(_bytes(g, "/file?p=" + urllib.parse.quote(card["render"])))
        print(f"{path} (render версии {card.get('v', 1)}: {card['render']})"); return path
    if sub == "run":
        if len(rest) < 2: raise SystemExit("hy.py image run ФРЕЙМ OPS.json|'[{\"op\": …}]'")
        ops = _ops_arg(rest[1]); ops = ops if isinstance(ops, list) else [ops]
        return run(g, page, rest[0], ops, dry=bool(o.get("--dry")), out=o.get("--out"), gridded=bool(o.get("--grid")))
    raise SystemExit(f"не знаю image {sub}: look, run, export, ops")


def register(g):
    """hy.py image …: joins hy.py's main through connectors.hook, as patterns.py"""
    main = g["main"]

    def main_(argv):
        pos = [a for k, a in enumerate(argv) if not a.startswith("--") and not (k and argv[k - 1] in ("--page", "--port", "--label", "--out", "--say", "--text", "--ids", "--to", "--tol"))]
        if pos and pos[0] == "image": return cli(_drop(argv, "image"), g)
        return main(argv)
    g["main"] = main_


def _drop(argv, word):
    a = list(argv); a.remove(word); return a


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hy
    a = sys.argv[1:]
    cli(a[1:] if a and a[0] == "image" else a, vars(hy))
