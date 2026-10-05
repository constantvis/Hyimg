# What the owner is looking at right now (2026-09-30): the canvas and the library report their selection to the server (_review/live.json),
# so "do X with these" can be answered without asking which ones.
#   python3 _review/live.py            selection and what is on screen, readable
#   python3 _review/live.py --paths    only the picture paths of the selection (canvas selection, else library picks), one per line
#   python3 _review/live.py --json     the raw state plus resolved pictures
#   python3 _review/live.py --link URL what a canvas link points at (right-click › Копировать ссылку): ?page=..&obj=id,id or &at=x,y,z
import json, os, sys, time, urllib.parse

from config import HERE, BOARDS, W



def rect(it):
    if it.get("type"):
        return it["x"], it["y"], it.get("w") or 1, it.get("h") or it.get("fs", 40) * 1.2
    c = it.get("crop") or [0, 0, 1, 1]
    return it["x"], it["y"], it["w"], it["w"] * ((c[3] - c[1]) / it.get("ar", .75)) / (c[2] - c[0])


def ago(t):
    s = int(time.time() - time.mktime(time.strptime(t, "%Y-%m-%d %H:%M:%S")))
    return f"{s} с назад" if s < 120 else f"{s // 60} мин назад" if s < 7200 else f"{s // 3600} ч назад"


def resolve():
    live = json.load(open(os.path.join(HERE, "live.json"), encoding="utf-8"))
    out = {"live": live}
    cv = live.get("canvas")
    if cv:
        try:
            b = json.load(open(os.path.join(BOARDS, cv["page"] + ".json"), encoding="utf-8"))
        except (OSError, ValueError):   # a new project: the page has no saved board yet
            b = {}
        items, groups = b.get("items", {}), b.get("groups", {})
        owner = {m: g.get("title", "") for g in groups.values() for m in g.get("members", [])}
        sel, pics = [], []
        for i in cv.get("sel", []):
            if i in groups:
                g = groups[i]; mp = [items[m]["path"] for m in g.get("members", []) if items.get(m, {}).get("path")]
                sel.append({"id": i, "kind": "group", "title": g.get("title", ""), "pictures": len(mp)}); pics += mp
            elif i in items:
                it = items[i]
                if it.get("path"): sel.append({"id": i, "kind": "picture", "path": it["path"], "group": owner.get(i, "")}); pics.append(it["path"])
                else: sel.append({"id": i, "kind": it.get("type"), "text": it.get("text", ""), "group": owner.get(i, "")})
        v = cv.get("view") or {}
        inview = [k for k, it in items.items() if v and (lambda r: r[0] < v["x"] + v["w"] and r[0] + r[2] > v["x"] and r[1] < v["y"] + v["h"] and r[1] + r[3] > v["y"])(rect(it))]
        out["canvas"] = {"page": cv["page"], "selected": sel, "selected_pictures": list(dict.fromkeys(pics)),
                         "on_screen": {"pictures": [items[k]["path"] for k in inview if items[k].get("path")],
                                       "groups": sorted({g.get("title", "") for g in groups.values() if v and g["x"] < v["x"] + v["w"] and g["x"] + g["w"] > v["x"] and g["y"] < v["y"] + v["h"] and g["y"] + g["h"] > v["y"]}),
                                       "texts": [items[k].get("text", "") for k in inview if items[k].get("type") == "text"]}}
    return out


def describe_link(link):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    page = q.get("page", ["main"])[0]
    try:
        b = json.load(open(os.path.join(BOARDS, os.path.basename(page) + ".json"), encoding="utf-8"))
    except (OSError, ValueError):
        sys.exit(f"страницы «{page}» нет в {BOARDS}")
    items, groups = b.get("items", {}), b.get("groups", {})
    owner = {m: g.get("title", "") for g in groups.values() for m in g.get("members", [])}
    def show(i, pad="  "):
        it = items.get(i)
        if i in groups:
            g = groups[i]; ms = g.get("members", [])
            print(f"{pad}группа «{g.get('title', '')}» ({i}): {len(ms)} объектов")
            for m in ms: show(m, pad + "  ")
        elif it and it.get("path"):
            print(f"{pad}кадр {it['path']}" + (f"  (группа «{owner[i]}»)" if owner.get(i) else "") + f"\n{pad}  файл: {os.path.join(W, it['path'])}")
        elif it:
            print(f"{pad}{'заметка' if it.get('type') == 'note' else 'текст'} ({i}): {it.get('text', '')[:300]!r}" + (f"  (группа «{owner[i]}»)" if owner.get(i) else ""))
        else:
            print(f"{pad}{i}: нет на странице (удален)")
    print(f"Страница «{page}»")
    for i in ",".join(q.get("obj", [])).split(","):
        if i: show(i)
    if q.get("at"):   # a view: what is inside a 1440 x 900 window at that camera
        x, y, z = map(float, q["at"][0].split(",")); v = {"x": x, "y": y, "w": 1440 / z, "h": 900 / z}
        inview = [k for k, it in items.items() if (lambda r: r[0] < v["x"] + v["w"] and r[0] + r[2] > v["x"] and r[1] < v["y"] + v["h"] and r[1] + r[3] > v["y"])(rect(it))]
        print(f"  вид: зум {round(z * 100, 1)}%, на экране {sum(1 for k in inview if items[k].get('path'))} кадров")
        for g in groups.values():
            if g["x"] < v["x"] + v["w"] and g["x"] + g["w"] > v["x"] and g["y"] < v["y"] + v["h"] and g["y"] + g["h"] > v["y"]: print(f"    группа «{g.get('title', '')}»")


if __name__ == "__main__":
    if "--link" in sys.argv:
        describe_link(sys.argv[sys.argv.index("--link") + 1]); sys.exit()
    try:
        r = resolve()
    except OSError:
        sys.exit("live.json нет: страница разбора еще ничего не сообщала (открыть проект в Hyimg и выделить что-нибудь)")
    live, cv, lib = r["live"], r.get("canvas"), r["live"].get("library") or {}
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1)); sys.exit()
    if "--paths" in sys.argv:
        print("\n".join((cv or {}).get("selected_pictures") or lib.get("picked") or [])); sys.exit()
    if cv:
        c = live["canvas"]; print(f"Холст, страница «{cv['page']}», {ago(c['t'])}, зум {round(c.get('zoom', 0) * 100)}%")
        if not cv["selected"]: print("  выделено: ничего")
        for s in cv["selected"]:
            if s["kind"] == "group": print(f"  группа «{s['title']}»: {s['pictures']} кадров")
            elif s["kind"] == "picture": print(f"  кадр {s['path']}" + (f"  (группа «{s['group']}»)" if s["group"] else ""))
            else: print(f"  {'заметка' if s['kind'] == 'note' else 'текст'}: {s['text'][:120]!r}" + (f"  (группа «{s['group']}»)" if s["group"] else ""))
        for g in c.get("perf") or []:   # frame timing of the last wheel/pinch gestures in the real window (canvas.html perfStop)
            print(f"  жест {g['at']}: {g['frames']} кадров, медиана {g['med']} мс, 90% {g['p90']} мс, худший {g['max']} мс, >50 мс: {g['over50']}, зум {g['zoom'][0]}→{g['zoom'][1]}, на экране {g['shown']}, окно {g['px']}, худшие кадр/JS мс: {' '.join(g.get('worst') or [])}")
        o = cv["on_screen"]; print(f"  на экране: {len(o['pictures'])} кадров" + (f", группы: {', '.join(o['groups'])}" if o["groups"] else "") + (f", надписи: {', '.join(t for t in o['texts'] if t)}" if o["texts"] else ""))
    if lib:
        print(f"Библиотека, {ago(lib['t'])}: коллекция «{lib.get('coll') or 'все'}», отмечено кружком {len(lib.get('picked', []))}" + (f", открыт {lib['open']}" if lib.get("open") else ""))
        for p in lib.get("picked", [])[:40]: print("  " + p)
