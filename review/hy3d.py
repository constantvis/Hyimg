"""hy.py's commands for 3D cards that keep their own view (owner 2026-10-07: «чтобы board был source of truth, и от него мы плясали уже
в Blender»). A 3D card carries its camera as "view" (name, loc, rot, lens, sensor, sensor_h, fit, shift, clip): the board's undo, history
and copy carry it. scene.json's camera of the same id is a copy, written only when something reads it: these commands, the studio's «Sync
with the scene» and the Blender bridge right before it renders the card. hy.py registers them: hy3d.register(OPS, api, resolve).
"""
import random
import re
import string
import urllib.parse

HELP = """
  camera3d CARD restore | CARD original | SCENE sync   a 3D card's own view ("view", the truth for what the card shows): restore writes
                                      it into its scene's camera of that id (made again if it was deleted), original puts back the camera
                                      of the picture it came from (studio.angles[id].camera0), sync writes every card's view of SCENE
                                      (3d/scenes/<имя>/scene.json) into that scene. cards3d gives each new card its view
  variant3d SCENE|CARD list | materials | new NAME [light=studio|angle|own] [env=0.8] [from=NAME] | set NAME [light=] [env=] [name=NEW]
            [mat="<материал>" color=rrggbb|tint=rrggbb metallic=0.8 roughness=x0.7 coat= coatrough= specular= ior= transmission= emission=
            emitcolor=rrggbb, «-» снимает] | delete NAME | CARD apply NAME|base | CARD compare NAME|base|off
                                      «Свет и материалы» Blender-студии (scene.studio): варианты света и правок материалов в scene.json
                                      (variants), карточка показывает один (поле variant), A/B (compare) рядом в карточке; materials
                                      спрашивает у Blender материалы студии с параметрами (запускает Blender, несколько секунд)
"""
VIEWF = ("name", "loc", "rot", "lens", "sensor", "sensor_h", "fit", "shift", "clip")
api = resolve = None


def view_of(cam):
    return {k: cam[k] for k in VIEWF if k in cam}


def scene_doc(path):
    st, doc = api("/file?p=" + urllib.parse.quote(path))
    if st != 200 or not isinstance(doc, dict): raise SystemExit(f"нет сцены {path}")
    return doc


def views_into(path, cards):
    """the cards' views into their scene's cameras of the same ids (made again when missing); the file written once, only on a change"""
    doc = scene_doc(path); cams = doc.setdefault("cameras", []); changed = []
    for it in cards:
        cid, v = it.get("camera") or doc.get("active_camera"), it.get("view")
        if not cid or not v: continue
        cur = next((c for c in cams if c.get("id") == cid), None)
        if cur is None: cur = {"id": cid}; cams.append(cur)
        want = {k: v[k] for k in VIEWF if k in v and not (k == "name" and cur.get("name"))}
        if any(cur.get(k) != x for k, x in want.items()): cur.update(want); changed.append(cur.get("name") or cid)
    if changed:
        doc["rev"] = int(doc.get("rev") or 0) + 1; doc["by"] = "hy.py"
        st, r = api("/api/file?p=" + urllib.parse.quote(path), doc)
        if st != 200: raise SystemExit(f"сцена не записана: {r}")
    return changed


def op_camera3d(b, args, kv):
    if len(args) < 2 or args[1] not in ("restore", "original", "sync"): raise SystemExit("camera3d CARD restore | CARD original | SCENE sync")
    ref, act = args[0], args[1]
    if act == "sync" and ref.endswith(".json"):
        cards = [it for it in b["items"].values() if it.get("type") == "model3d" and it.get("scene") == ref]
        if not cards: raise SystemExit(f"на этой странице нет карточек сцены {ref}")
        ch = views_into(ref, cards)
        return f"camera3d {ref}: " + (f"камеры {', '.join(ch)} теперь как на карточках" if ch else "все камеры уже как на карточках")
    cid = ref if ref in b["items"] else resolve(b, ref)[1]
    it = b["items"].get(cid)
    if not it or it.get("type") != "model3d" or not it.get("scene"): raise SystemExit(f"«{ref}» не 3D-карточка")
    if act in ("restore", "sync"):
        if not it.get("view"): raise SystemExit(f"у карточки {cid} нет своего вида: она покажет камеру сцены, писать нечего")
        ch = views_into(it["scene"], [it])
        return f"camera3d {cid}: " + ("камера сцены теперь как на карточке" if ch else "камера сцены уже как на карточке")
    doc = scene_doc(it["scene"]); cam = it.get("camera") or doc.get("active_camera")
    a = ((doc.get("studio") or {}).get("angles") or {}).get(cam) or {}
    if not a.get("camera0"): raise SystemExit(f"камера {cam} не из картинки: у нее нет studio.angles[{cam}].camera0")
    v = dict(it.get("view") or view_of(next((c for c in doc.get("cameras", []) if c.get("id") == cam), {})))
    v.update(view_of(a["camera0"]))
    it["view"] = v
    return f"camera3d {cid}: вид как на картинке {a.get('source') or ''}".rstrip()


def register(ops, api_, resolve_):
    """camera3d, and cards3d's new cards with their own view"""
    global api, resolve
    api, resolve = api_, resolve_
    ops["camera3d"] = op_camera3d
    ops["variant3d"] = op_variant3d
    cards3d = ops.get("cards3d")
    if cards3d:
        def with_views(b, args, kv):
            before = set(b["items"])
            msg = cards3d(b, args, kv)
            new = [it for k, it in b["items"].items() if k not in before and it.get("type") == "model3d" and not it.get("view")]
            if new:
                cams = {c.get("id"): c for c in scene_doc(args[0]).get("cameras", [])}
                for it in new:
                    if it.get("camera") in cams: it["view"] = view_of(cams[it["camera"]])
            return msg
        ops["cards3d"] = with_views


# ---- «Свет и материалы» (owner 2026-10-07: «было бы шикарно, если можно как-то свет тестировать и материалы»): a Blender studio's scene
# keeps named variants of light and material overrides, a card shows one; the 3D plugin's FEATURES.md says how the studio and Blender use them
LIGHTS = ("studio", "angle", "own")
NUM = {"metallic": ("metallic", 0, 1), "roughness": ("roughness", 0, 1), "coat": ("coat", 0, 1), "coatrough": ("coat_roughness", 0, 1),
       "specular": ("specular", 0, 1), "ior": ("ior", 1, 3), "transmission": ("transmission", 0, 1), "emission": ("emission", 0, 100)}
COL = {"color": ("base_color", False), "tint": ("base_color", True), "emitcolor": ("emission_color", False), "emittint": ("emission_color", True)}


def _lin(h):
    """rrggbb or "#rrggbb" (sRGB, as the panels show it; # starts a comment in do unless quoted) to linear RGB, as scene.json keeps colours"""
    if isinstance(h, float): h = f"{int(h):06d}"   # do reads 808080 as a number
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(h).strip())
    if not m: raise SystemExit(f"цвет {h}: нужен rrggbb или \"#rrggbb\" в кавычках")
    c = [int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [round(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4, 4) for v in c]


def _num(v, lo, hi, what):
    try: x = float(v)
    except (TypeError, ValueError): raise SystemExit(f"{what}: нужно число, а не {v}")
    return round(min(hi, max(lo, x)), 4)


def _find(doc, name):
    v = next((x for x in doc.get("variants") or [] if x.get("id") == name or x.get("name") == name), None)
    if v is None: raise SystemExit(f"в сцене нет варианта «{name}»: " + (", ".join(f"«{x.get('name')}»" for x in doc.get("variants") or []) or "вариантов нет"))
    return v


def _write(path, doc):
    doc["rev"] = int(doc.get("rev") or 0) + 1; doc["by"] = "hy.py"
    st, r = api("/api/file?p=" + urllib.parse.quote(path), doc)
    if st != 200: raise SystemExit(f"сцена не записана: {r}")


def _describe(v):
    mats = v.get("materials") or {}
    m = "; ".join(f"{k}: " + ", ".join(f"{p}={x}" for p, x in ps.items()) for k, ps in mats.items())
    return f"«{v.get('name')}» ({v.get('id')}) свет {v.get('light', 'studio')}" + (f", окружение ×{v['env']}" if v.get("env") is not None else "") + (f", материалы: {m}" if m else "")


def op_variant3d(b, args, kv):
    if len(args) < 2: raise SystemExit("variant3d SCENE|CARD list | materials | new NAME | set NAME … | delete NAME | CARD apply NAME|base | CARD compare NAME|base|off")
    ref, act = args[0], args[1]
    card = None
    if ref.endswith(".json"): path = ref
    else:
        cid = ref if ref in b["items"] else resolve(b, ref)[1]; card = b["items"].get(cid)
        if not card or card.get("type") != "model3d" or not card.get("scene"): raise SystemExit(f"«{ref}» не 3D-карточка")
        path = card["scene"]
    doc = scene_doc(path)
    if not (doc.get("studio") or {}).get("angles"): raise SystemExit(f"{path}: не сцена Blender-студии (нет studio.angles), варианты света и материалов ей не нужны")
    name = args[2] if len(args) > 2 else None
    if act == "list":
        shows = {}
        for k, it in b["items"].items():
            if it.get("type") == "model3d" and it.get("scene") == path: shows.setdefault(it.get("variant") or "", []).append(k)
        lines = [_describe(v) + (f"; карточки {', '.join(shows.get(v.get('id'), []))}" if shows.get(v.get("id")) else "") for v in doc.get("variants") or []]
        return f"variant3d {path}: " + ("\n  " + "\n  ".join(lines) if lines else "вариантов нет") + (f"\n  без изменений: {', '.join(shows[''])}" if shows.get("") else "")
    if act == "materials":
        _, pl = api("/api/plugins")
        plug = next((p.get("name") for p in pl if p.get("name") in ("3d", "hyimg-3d-studio", "hyimg-3d")), None) if isinstance(pl, list) else None
        if not plug: raise SystemExit("плагин «3D-объекты» не установлен")
        st, r = api(f"/api/plugin/{plug}/blender", {"action": "materials", "scene": path, "camera": (card or {}).get("camera"), "look": (card or {}).get("look", "current")})
        if st != 200: raise SystemExit(f"Blender: {r.get('error') if isinstance(r, dict) else r}")
        par = lambda m: ", ".join(f"{k}={'узлы' if p['linked'] else p['value']}" for k, p in m["params"].items()) if m.get("principled") else "нет Principled BSDF"
        rows = [f"«{m['name']}» частей {m['users']}: " + par(m) for m in r["list"]]
        return f"variant3d {path}: материалы {r['list'][0]['look'] if r['list'] else ''}\n  " + "\n  ".join(rows)
    if act in ("apply", "compare"):
        if card is None: raise SystemExit(f"variant3d КАРТОЧКА {act} …: нужна карточка, а не сцена")
        field = "variant" if act == "apply" else "compare"
        if name in (None, "off") or (act == "apply" and name == "base"): card.pop(field, None)
        else: card[field] = "base" if name == "base" else _find(doc, name)["id"]
        return f"variant3d {ref}: {field} = {card.get(field, 'нет')}"
    if not name: raise SystemExit(f"variant3d … {act} ИМЯ")
    variants = doc.setdefault("variants", [])
    if act == "new":
        if any(v.get("name") == name for v in variants): raise SystemExit(f"вариант «{name}» уже есть")
        v = dict(_find(doc, kv["from"])) if kv.get("from") else {}
        v.update(id="v" + "".join(random.choice(string.hexdigits.lower()[:16]) for _ in range(6)), name=name)
        v.setdefault("light", "studio"); variants.append(v)
    elif act == "delete":
        v = _find(doc, name); variants.remove(v)
        if not variants: doc.pop("variants")
        for it in b["items"].values():
            if it.get("scene") == path and it.get("variant") == v["id"]: it.pop("variant")
        _write(path, doc)
        return f"variant3d {path}: вариант «{name}» удален"
    elif act == "set": v = _find(doc, name)
    else: raise SystemExit(f"variant3d: не знаю {act}")
    if "light" in kv:
        if kv["light"] not in LIGHTS: raise SystemExit(f"light=: {', '.join(LIGHTS)}")
        v["light"] = kv["light"]
    if "env" in kv:
        if kv["env"] == "-" or float(kv["env"]) == 1: v.pop("env", None)
        else: v["env"] = _num(kv["env"], 0, 10, "env")
    if act == "set" and kv.get("name"): v["name"] = str(kv["name"])
    if "mat" in kv:
        mats = v.setdefault("materials", {}); ps = mats.setdefault(str(kv["mat"]), {})
        for k, x in kv.items():
            if k in NUM:
                key, lo, hi = NUM[k]; sx = str(x)
                if sx == "-": ps.pop(key, None)
                elif sx[:1] in ("x", "×"): ps[key] = {"mul": _num(sx[1:], 0, 20, k)}
                else: ps[key] = _num(x, lo, hi, k)
            elif k in COL:
                key, tint = COL[k]
                if str(x) == "-": ps.pop(key, None)
                else: ps[key] = {"tint": _lin(x)} if tint else _lin(x)
        if not ps: mats.pop(str(kv["mat"]))
        if not mats: v.pop("materials")
    _write(path, doc)
    return f"variant3d {path}: " + _describe(v)
