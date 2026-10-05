# Renders a canvas board (boards/<page>.json) for the agent to look at: an overview map with the owner's groups, and one sheet per group
# that keeps the layout he made (frames at their board coordinates, scaled). 2026-09-30, owner: "you can see which pictures sit in which groups".
# Usage: python3 board_view.py [page=main] [outdir]   -> outdir/map.jpg, outdir/g-<title>.jpg, outdir/ungrouped.jpg, outdir/report.txt
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
from config import HERE, W, BOARDS, real   # real: the file behind a library path, outside folders of the rules included
page = sys.argv[1] if len(sys.argv) > 1 else "main"
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "_view"); os.makedirs(out, exist_ok=True)
B = json.load(open(os.path.join(HERE, "boards", page + ".json"), encoding="utf-8"))
allitems, groups = B["items"], B["groups"]
items = {k: v for k, v in allitems.items() if "path" in v}   # images; text labels are drawn separately
texts = {k: v for k, v in allitems.items() if v.get("type") == "text"}
try: FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22); FS = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
except Exception: FONT = FS = ImageFont.load_default()

_c = {}
def thumb(it, px):
    p = it["path"]
    if (p, px) in _c: return _c[(p, px)]
    try:
        im = Image.open(real(p)).convert("RGB"); im.thumbnail((px, px * 2))
        cr = it.get("crop")
        _c[(p, px)] = im
    except Exception:
        im = Image.new("RGB", (px, int(px * 1.25)), (60, 20, 20))
    _c[(p, px)] = im; return im
def ih(it): return it["w"] / (it.get("ar") or 0.8)   # ar = width / height
def inside(it, g): return g["x"] - 2 <= it["x"] and it["x"] + it["w"] <= g["x"] + g["w"] + 2 and g["y"] - 2 <= it["y"] and it["y"] + ih(it) <= g["y"] + g["h"] + 2

member = {}
for gid, g in groups.items():
    for m in g.get("members", []): member[m] = gid
spatial = {}   # items sitting inside a group frame without being listed as members
for iid, it in items.items():
    if iid in member: continue
    for gid, g in groups.items():
        if inside(it, g): spatial[iid] = gid; break
un = [i for i in items if i not in member and i not in spatial]

# --- overview map
ex = [(g["x"], g["y"], g["x"] + g["w"], g["y"] + g["h"]) for g in groups.values()] + [(t["x"], t["y"], t["x"] + t["w"], t["y"] + t["h"]) for t in texts.values()] + [(i["x"], i["y"], i["x"] + i["w"], i["y"] + ih(i)) for i in items.values()]
xs0 = min(e[0] for e in ex); ys0 = min(e[1] for e in ex); xs1 = max(e[2] for e in ex); ys1 = max(e[3] for e in ex)
S = 1900 / (xs1 - xs0); MW, MH = 1900, int((ys1 - ys0) * S) + 40
mp = Image.new("RGB", (MW + 20, MH + 20), (24, 24, 26)); d = ImageDraw.Draw(mp)
for iid, it in items.items():
    x, y, w, h = (it["x"] - xs0) * S + 10, (it["y"] - ys0) * S + 10, it["w"] * S, ih(it) * S
    if x < -50 or y < -50 or x > MW + 30 or y > MH + 30: continue
    t = thumb(it, 40).resize((max(2, int(w)), max(2, int(h)))); mp.paste(t, (int(x), int(y)))
for tid, t in texts.items():
    d.text(((t["x"] - xs0) * S + 10, (t["y"] - ys0) * S + 10), t["text"], fill=(255, 255, 255), font=FONT)
pal = [(230, 90, 70), (80, 170, 230), (240, 200, 60), (120, 210, 120), (200, 120, 220), (240, 140, 60)]
for n, (gid, g) in enumerate(groups.items()):
    c = pal[n % len(pal)]; x, y, w, h = (g["x"] - xs0) * S + 10, (g["y"] - ys0) * S + 10, g["w"] * S, g["h"] * S
    d.rectangle([x, y, x + w, y + h], outline=c, width=2); d.text((x + 3, y - 15), f"{len(g.get('members', []))}  {g['title'].splitlines()[0][:38]}", fill=c, font=FS)
mp.save(os.path.join(out, "map.jpg"), quality=85)

# --- one sheet per group, layout as on the board
rep = ["text labels: " + "; ".join(f"{t['text']!r} at ({t['x']:.0f},{t['y']:.0f})" for t in texts.values()), f"page {page}: {len(items)} items, {len(groups)} groups, {len(un)} outside every group, {len(spatial)} inside a frame but not listed as members"]
def sheet(name, its, gx, gy, gw, gh, title):
    sc = min(1500 / max(gw, 1), 1.0); sc = min(sc, 1400 / max(gh, 1)) if gh * sc > 1400 else sc
    im = Image.new("RGB", (int(gw * sc) + 20, int(gh * sc) + 50), (24, 24, 26)); dd = ImageDraw.Draw(im)
    dd.text((10, 8), title, fill=(240, 240, 240), font=FONT)
    for it in its:
        x, y, w, h = (it["x"] - gx) * sc + 10, (it["y"] - gy) * sc + 40, it["w"] * sc, ih(it) * sc
        t = thumb(it, 360).resize((max(3, int(w)), max(3, int(h)))); im.paste(t, (int(x), int(y)))
    im.save(os.path.join(out, name), quality=85)
for n, (gid, g) in enumerate(groups.items()):
    mem = [items[m] for m in g.get("members", []) if m in items] + [items[i] for i, gg in spatial.items() if gg == gid]
    fol = {}
    for it in mem: f = it["path"].rsplit("/", 1)[0] if "/" in it["path"] else "."; fol[f] = fol.get(f, 0) + 1
    rep.append(f"\n[{n+1}] {g['title'].strip()!r}  frame x={g['x']:.0f} y={g['y']:.0f} w={g['w']:.0f} h={g['h']:.0f}  members={len(g.get('members', []))} (+{sum(1 for i,gg in spatial.items() if gg==gid)} inside unlisted)")
    rep.append("   folders: " + ", ".join(f"{k} x{v}" for k, v in sorted(fol.items(), key=lambda a: -a[1])[:8]))
    sheet(f"g{n+1:02d}-" + re.sub(r"[^A-Za-z0-9А-Яа-я]+", "_", g["title"].splitlines()[0])[:30] + ".jpg", mem, g["x"], g["y"], g["w"], g["h"], f"{n+1}. {g['title'].splitlines()[0]}  ({len(mem)})")
if un:
    ux0 = min(items[i]["x"] for i in un); uy0 = min(items[i]["y"] for i in un); ux1 = max(items[i]["x"] + items[i]["w"] for i in un); uy1 = max(items[i]["y"] + ih(items[i]) for i in un)
    rep.append(f"\n[outside groups] {len(un)} items, bbox x={ux0:.0f}..{ux1:.0f} y={uy0:.0f}..{uy1:.0f}")
    sheet("ungrouped.jpg", [items[i] for i in un], ux0, uy0, ux1 - ux0, uy1 - uy0, f"outside groups ({len(un)})")
open(os.path.join(out, "report.txt"), "w", encoding="utf-8").write("\n".join(rep))
print("\n".join(rep))
