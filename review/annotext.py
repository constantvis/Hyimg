"""Drawings and comment areas in words, for agents (owner 2026-10-07: «как аннотации будут работать в json? Мы делали систему,
простую для агентов, чтобы они всё понимали, не смотря на картинки»; and «как в preview сейчас: выделяешь область и пишешь, что к чему»).

A drawing keeps its geometry for the board (points as shares of its object's box); this module says what it is, the way a note's file says
what the note touches: the kind and colour, who drew it, the object it is on, and where in words and numbers, in shares of what the card
shows and in the picture's own pixels (its crop taken into account) or the page's css px for an HTML card:
  «красный овал вокруг области вверху справа: x 62–85 %, y 10–40 % = px 1240–1700 × 140–560 из 2000×1400, на кадре a/sky.png, Ann Lee»
An arrow goes «от <объект> (точка) к <объект> (точка)», a pen stroke is a closed loop (it marks the area inside), a horizontal or a
vertical line (an underline or a cross-out) or a free stroke; a text label is quoted. A comment's area is described the same way. A
drawing and a comment on the same object, close in space or in time, are linked both ways («about» and «marks»).
The library's preview marks («Comment on area N», feedback.notes in a picture's json) read the same way (library_marks).

Pure: the caller gives the board, the people and the files' pixel sizes (size_of)."""
import math
import time

KIND = {"rect": "прямоугольник", "ellipse": "овал", "arrow": "стрелка", "text": "надпись", "pen": "штрих"}
COLOR = {"red": "красный", "orange": "оранжевый", "yellow": "желтый", "green": "зеленый", "blue": "синий", "purple": "фиолетовый",
         "pink": "розовый", "grey": "серый"}
COLOR_F = {"red": "красная", "orange": "оранжевая", "yellow": "желтая", "green": "зеленая", "blue": "синяя", "purple": "фиолетовая",
           "pink": "розовая", "grey": "серая"}
FEMININE = {"arrow", "text"}
OBJ = {"picture": "кадр", "video": "видео", "pdf": "PDF", "html": "HTML", "3d": "3D-сцена", "frame": "фрейм", "card": "карточка",
       "heading": "заголовок", "timeline": "таймлайн"}
CASE = {"на": {"picture": "кадре", "3d": "3D-сцене", "frame": "фрейме", "card": "карточке", "html": "HTML-странице", "heading": "заголовке"},
        "от": {"picture": "кадра", "3d": "3D-сцены", "frame": "фрейма", "card": "карточки", "html": "HTML-страницы", "heading": "заголовка"},
        "к": {"picture": "кадру", "3d": "3D-сцене", "frame": "фрейму", "card": "карточке", "html": "HTML-странице", "heading": "заголовку"}}
AGENT = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "kimi": "Kimi", "opencode": "OpenCode", "agent": "Агент"}
NEAR_S = 600   # a drawing and a comment made within 10 minutes of each other on one object, not far apart, belong together


def pct(v): return int(round(max(0.0, min(1.0, v)) * 100))


def words(u0, u1, v0, v1):
    """where a region is on its object: «вверху справа», «в центре», «почти весь кадр»"""
    if u1 - u0 > .8 and v1 - v0 > .8: return "почти целиком"
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    h = "слева" if cu < .34 else "справа" if cu > .66 else ""
    v = "вверху" if cv < .34 else "внизу" if cv > .66 else ""
    if not h and not v: return "в центре"
    return " ".join(x for x in (v or "посередине", h) if x) if h else v + " по центру"


def who(by, people):
    p = (people or {}).get((by or {}).get("person")) or {}
    name = p.get("name") or "кто-то"
    via = (by or {}).get("via", "app")
    return name if via in ("", "app") else f"{AGENT.get(via, via)} · {name}"


def kind_of(it):
    t = it.get("type")
    if t: return {"htmlframe": "html", "html": "html", "model3d": "3d", "imgframe": "frame", "text": "heading", "timeline": "timeline"}.get(t, "card")
    p = (it.get("path") or "").lower()
    return "video" if p.endswith((".mp4", ".mov", ".m4v", ".webm")) else "pdf" if p.endswith(".pdf") else "picture"


def file_of(it): return next((it[k] for k in ("path", "src", "scene", "doc") if isinstance(it.get(k), str) and it[k]), "")


def box_of(it):
    """the item's box on the board, as notelinks.rect"""
    x, y, w = float(it["x"]), float(it["y"]), float(it["w"])
    if not it.get("type"):
        c = it.get("crop") or [0, 0, 1, 1]
        return (x, y, w, w * ((c[3] - c[1]) / float(it.get("ar") or 1)) / (c[2] - c[0]))
    return (x, y, w, float(it.get("h") or w))


def object_name(oid, it, prep=""):
    """«кадр a/sky.png»; with a preposition its case: «на кадре a/sky.png», «от кадра …», «к кадру …»"""
    k, f = kind_of(it), file_of(it)
    word = CASE[prep].get(k, OBJ.get(k, "объект")) if prep else OBJ.get(k, "объект")
    return f"{prep + ' ' if prep else ''}{word} {f or it.get('name') or oid}"


def pixels(it, u0, u1, v0, v1, size_of):
    """the region in the object's own pixels: a picture's original (its crop applied), an HTML card's page (css px); None for others"""
    if kind_of(it) in ("picture", "pdf", "video") and it.get("path"):
        wh = size_of(it["path"]) if size_of else None
        if not wh: return None
        c = it.get("crop") or [0, 0, 1, 1]
        X = lambda u: (c[0] + u * (c[2] - c[0])) * wh[0]
        Y = lambda v: (c[1] + v * (c[3] - c[1])) * wh[1]
        return {"px": [round(X(u0)), round(X(u1)), round(Y(v0)), round(Y(v1))], "size": list(wh), "unit": "px"}
    if it.get("type") in ("html", "htmlframe") and it.get("vw"):
        vw = float(it["vw"]); vh = vw * float(it.get("h") or 1) / float(it.get("w") or 1)
        return {"px": [round(u0 * vw), round(u1 * vw), round(v0 * vh), round(v1 * vh)], "size": [round(vw), round(vh)], "unit": "css px страницы"}
    return None


def region(it, oid, u0, u1, v0, v1, size_of):
    """{u, v, words, px?, size?, text}: a region of an object in shares (0..1 of what the card shows) and its pixels"""
    u0, u1, v0, v1 = max(0.0, min(u0, u1)), min(1.0, max(u0, u1)), max(0.0, min(v0, v1)), min(1.0, max(v0, v1))
    out = {"obj": oid, "u": [round(u0, 4), round(u1, 4)], "v": [round(v0, 4), round(v1, 4)], "words": words(u0, u1, v0, v1)}
    t = f"{out['words']}: x {pct(u0)}–{pct(u1)} %, y {pct(v0)}–{pct(v1)} %"
    px = pixels(it, u0, u1, v0, v1, size_of)
    if px:
        out.update(px)
        p = px["px"]; t += f" = {px['unit']} {p[0]}–{p[1]} × {p[2]}–{p[3]} из {px['size'][0]}×{px['size'][1]}"
    out["text"] = t
    return out


def point_text(it, u, v, size_of, page=None):
    """«x 3 %, y 54 % (36, 432 css px страницы)». page: an element's point in an HTML card's page (Dev Studio), the one to print: the pin's
    share u, v of the card's picture (the page's first screen) stops at its edge for an element further down or right (owner 2026-10-08)"""
    t = f"x {pct(u)} %, y {pct(v)} %"
    px = pixels(it, u, u, v, v, size_of)
    if px and isinstance(page, (list, tuple)) and len(page) == 2 and it.get("type") in ("html", "htmlframe"):
        x, y = float(page[0]), float(page[1]); vw, vh = px["size"]
        far = [w for w, out in (("ниже", y > vh), ("правее", x > vw)) if out]
        edge = {"ниже": "нижнего ", "правее": "правого "}.get(far[0], "") if len(far) == 1 else ""
        return t + f" ({round(x)}, {round(y)} {px['unit']}" + (f", {' и '.join(far)} первого экрана: на картинке карточки она у {edge}края" if far else "") + ")"
    return t + (f" ({px['px'][0]}, {px['px'][2]} {px['unit']})" if px else "")


def _abs(a, b):
    """the drawing's points in board units, its object's box, or None when the object is gone and nothing remembers its box"""
    an = a.get("anchor")
    if not an: return [(p[0], p[1]) for p in a["pts"]], None
    it = (b.get("items") or {}).get(an["obj"])
    q = box_of(it) if it else (tuple(an["r"]) if an.get("r") else None)
    if not q: return None, None
    return [(q[0] + p[0] * q[2], q[1] + p[1] * q[3]) for p in a["pts"]], q


def object_at(b, x, y, skip=None):
    """the topmost picture or card holding the board point (x, y), else a heading there (a table's title cell, ui/annotate.js headingAt):
    (id, item) or (None, None)"""
    hit, head = (None, None), (None, None)
    for oid, it in (b.get("items") or {}).items():
        if oid == skip or not isinstance(it, dict) or it.get("type") in ("note", "timeline") or not (it.get("type") or it.get("path")): continue
        try: q = box_of(it)
        except (KeyError, TypeError, ValueError, ZeroDivisionError): continue
        if q[0] <= x <= q[0] + q[2] and q[1] <= y <= q[1] + q[3]:
            if it.get("type") == "text": head = (oid, it)
            else: hit = (oid, it)
    return hit if hit[0] else head


def stroke_shape(pts):
    """a pen stroke's shape from its points in board units: loop, hline, vline or free"""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    big = max(w, h, 1e-9)
    gap = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1])
    if len(pts) > 4 and gap < .25 * big and min(w, h) > .25 * big: return "loop"
    if h < .25 * big: return "hline"
    if w < .25 * big: return "vline"
    return "free"


def _ts(iso):
    try: return time.mktime(time.strptime(str(iso)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError): return 0.0


def thread_point(t):
    """a comment's place in its object's shares: its area's box, else its pin"""
    if t.get("area"): u, v, w, h = t["area"]; return u, u + w, v, v + h
    u, v = (t.get("at") or [0, 0])[:2]
    return u, u, v, v


def related(a_obj, a_box, a_when, threads):
    """the comments that are about a drawing: on the same object and near it in space (their area or pin within the drawing's region
    grown by 5 % of the object), or made within NEAR_S of it and not far (grown by 25 %)"""
    out = []
    for t in threads:
        if not t.get("anchor") or t["anchor"].get("obj") != a_obj: continue
        u0, u1, v0, v1 = thread_point(t)
        near = lambda g: u1 >= a_box[0] - g and u0 <= a_box[1] + g and v1 >= a_box[2] - g and v0 <= a_box[3] + g
        if near(.05) or (abs(_ts(t.get("created")) - a_when) < NEAR_S and near(.25)): out.append(t)
    return out


def describe(a, b, people, size_of=None, threads=()):
    """{text, region?, shape?, object?, to?, about: [thread ids]} of one drawing"""
    pts, q = _abs(a, b)
    color = a.get("color") or "red"
    adj = (COLOR_F if a.get("kind") in FEMININE else COLOR).get(color, color)
    author = who(a.get("by"), people)
    an = a.get("anchor") or {}
    it = (b.get("items") or {}).get(an.get("obj")) if an else None
    out = {"about": []}
    if pts is None:
        out["text"] = f"{adj} {KIND.get(a.get('kind'), 'рисунок')} на объекте, которого больше нет ({an.get('file') or an.get('obj')}), {author}"
        return out
    if an:
        us = [(x - q[0]) / q[2] for x, _ in pts]; vs = [(y - q[1]) / q[3] for _, y in pts]
    on = object_name(an['obj'], it, "на") if it else (f"на объекте {an.get('file') or an['obj']}, его уже нет на странице" if an else "на пустом месте доски")
    k = a.get("kind")
    if k == "arrow" and len(pts) >= 2:
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        hid, hit = object_at(b, x1, y1)
        tail = f"{object_name(an['obj'], it, 'от')} ({point_text(it, us[0], vs[0], size_of)})" if it else f"от точки доски ({round(x0)}, {round(y0)})"
        if hit:
            hq = box_of(hit); head = f"{object_name(hid, hit, 'к')} ({point_text(hit, (x1 - hq[0]) / hq[2], (y1 - hq[1]) / hq[3], size_of)})"
            out["to"] = hid
        else: head = f"к пустому месту доски ({round(x1)}, {round(y1)})"
        out["text"] = f"{adj} стрелка {tail} {head}, {author}"
        # what it is about on its object: where it points when the head is on it too, else where it starts
        box = ((us[-1], us[-1], vs[-1], vs[-1]) if hid == an["obj"] else (us[0], us[0], vs[0], vs[0])) if an else None
    else:
        if an:
            box = (min(us), max(us), min(vs), max(vs))
            r = region(it or {}, an["obj"], *box, size_of) if it else None
            if r: out["region"] = r
            where = r["text"] if r else f"x {pct(box[0])}–{pct(box[1])} %, y {pct(box[2])}–{pct(box[3])} %"
        else:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]; box = None
            where = f"доска x {round(min(xs))}–{round(max(xs))}, y {round(min(ys))}–{round(max(ys))}"
        if k == "pen":
            sh = stroke_shape(pts); out["shape"] = sh
            f = COLOR_F.get(color, color)
            what = {"loop": f"{f} обводка: выделяет область", "hline": f"{f} горизонтальная черта (подчеркивание или зачеркивание)",
                    "vline": f"{f} вертикальная черта", "free": f"{adj} штрих от руки"}[sh]
        elif k == "text": what = f"{adj} надпись «{a.get('text', '')}»"
        elif k == "ellipse": what = f"{adj} овал вокруг области"
        else: what = f"{adj} {KIND.get(k, 'рисунок')} вокруг области"
        out["text"] = f"{what} {where}, {on}, {author}"
    if an and box:
        out["about"] = [t["id"] for t in related(an["obj"], box, _ts(a.get("created")), threads)]
        if out["about"]:
            first = next(t for t in threads if t["id"] == out["about"][0])
            out["text"] += f" → комментарий {first['id']}: «{first['messages'][0]['text'][:80]}»" + (f" и еще {len(out['about']) - 1}" if len(out["about"]) > 1 else "")
    return out


# where the pin of an element's comment stands when not on the element's own box (Dev Studio's tree, owner 2026-10-08): on its contents
# (display: contents), on its nearest ancestor with a box (display: none), at the nearest point in sight (a box that clips it)
PINS = {"kids": "булавка на его содержимом, своей рамки нет", "parent": "булавка на ближайшем родителе, сам он не отрисован",
        "edge": "булавка у ближайшего видимого края, сам он скрыт"}


def element_text(el):
    """«, элемент #t» and where its pin stands when not on it"""
    return f", элемент {el.get('css') or el.get('key')}" + (f" ({PINS[el['pin']]})" if el.get("pin") in PINS else "")


def describe_thread(t, b, people, size_of=None, marks=()):
    """{text, region?, marks: [drawing ids]} of a comment: its area or pin on its object, its element, the drawings about it"""
    an = t.get("anchor") or {}
    it = (b.get("items") or {}).get(an.get("obj")) if an else None
    out = {"marks": [m["id"] for m in marks if t["id"] in (m.get("about") or [])]}   # marks: [{id, about}] of the page's drawings
    if it and t.get("area"):
        u, v, w, h = t["area"]
        r = region(it, an["obj"], u, u + w, v, v + h, size_of); out["region"] = r
        where = f"область {r['text']} {object_name(an['obj'], it, 'на')}"
    elif it:
        page = (t.get("element") or {}).get("page")
        where = f"булавка {point_text(it, *(t.get('at') or [0, 0])[:2], size_of, page)} {object_name(an['obj'], it, 'на')}"
    elif an:
        where = f"на объекте {an.get('file') or an.get('obj')}, его уже нет на странице"
    elif t.get("area"):
        x, y, w, h = t["area"]; where = f"область доски x {round(x)}–{round(x + w)}, y {round(y)}–{round(y + h)}"
    else:
        where = "булавка на доске x {}, y {}".format(*[round(v) for v in (t.get("at") or [0, 0])[:2]])
    if t.get("element"): where += element_text(t["element"])
    out["text"] = where + (f"; рисунки: {', '.join(out['marks'])}" if out["marks"] else "")
    return out


def library_marks(path, notes, it, oid, size_of=None):
    """the library preview's marks on a picture (feedback.notes: box, arrow, marker, 0..1 of the image) in the same words; they lie on the
    whole picture, not on its crop on the board"""
    out = []
    whole = {**it, "crop": None} if it else {"path": path}
    for n, m in enumerate(notes or [], 1):
        pts = m.get("pts") or []
        if not pts: continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        r = region(whole, oid, min(xs), max(xs), min(ys), max(ys), size_of)
        kind = {"box": "область", "arrow": "стрелка", "mark": "маркер"}.get(m.get("kind"), "пометка")
        text = f"{kind} {n} из просмотра библиотеки, {r['text']}" + (f": «{m['text']}»" if m.get("text") else "")
        out.append({"n": n, "kind": m.get("kind"), "region": r, "text": text})
    return out
