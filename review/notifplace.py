"""Every notification has a place on the board (owner 2026-10-08: one notification in the bell moved him nowhere; the agent had written
«put 21 references next to the storyboard» without ids, so the click had nowhere to go). A notification that names nothing gets the
things its author put on the page around it, from the page's events (events.py: every board save is an event with ids and `by`):
what was added or changed (pictures, notes, headings, groups) gives ids, their box the area, the first pictures the previews.

  window   from the author's previous notification on the page (2 hours back at most) to the notification itself; at a click, also
           up to the author's next notification there, 15 minutes at most (an agent that wrote first and placed after)
  author   by.person and by.via, case aside (a board without profiles stamps by.via alone); without by: who against the agent
  only what is still on the page; a move counts only when nothing was added or changed

server.py: notify() fills a notification that names nothing; POST /api/notifications {"action": "place", "id"} is where the bell goes
for one without a place ("fill": true writes it in); {"action": "place", "page"} is what hy.py notify would get now.
server.py notify() also writes the bell's pictures of what a notification names (tiles(), feedthumbs.py).
hy.py: notify without --ids asks the server (an older server: reads the events itself), notify --place ID repairs an old one."""
import os, time

import feedthumbs
import notelinks

BEFORE_S, AFTER_S = 2 * 3600, 15 * 60
PLACE = ("group", "add", "note", "text", "timeline", "note-edit", "text-edit", "rename")
PREVIEWS = 6


def ts(n):
    if isinstance(n.get("ts"), (int, float)): return float(n["ts"])
    try: return time.mktime(time.strptime(str(n.get("t") or "")[:19], "%Y-%m-%d %H:%M:%S"))
    except ValueError: return 0.0


def _low(s): return str(s or "").strip().lower()


def by_author(x, n):
    """x (an event or another notification) was written by n's author"""
    nb, xb = n.get("by") or {}, x.get("by") or {}
    if nb and xb:   # a board without profiles stamps the kind alone
        return nb.get("person") == xb.get("person") and _low(nb.get("via") or "app") == _low(xb.get("via") or "app")
    who = _low(n.get("who"))
    return bool(who) and who in (_low(x.get("agent")), _low(x.get("who")), _low(xb.get("via")))


def window(n, notes, after=False):
    """(from, to) in seconds: since the author's previous notification on the page, to it (after: to the next one, 15 min at most)"""
    t = ts(n)
    others = [ts(m) for m in notes if m.get("id") != n.get("id") and m.get("page") == n.get("page") and by_author(m, n)]
    lo = max([t - BEFORE_S] + [x for x in others if x < t])
    hi = min([t + AFTER_S] + [x for x in others if x > t]) if after else t
    return lo, hi + 1   # a notification's t has whole seconds; its own events were written in the second before it


def rect(b, i):
    if i in (b.get("groups") or {}):
        g = b["groups"][i]
        return tuple(float(g[k]) for k in "xywh") if all(isinstance(g.get(k), (int, float)) for k in "xywh") else None
    try: return notelinks.rect(b["items"][i])
    except (KeyError, TypeError, ValueError, ZeroDivisionError): return None


def of_ids(b, ids):
    """{"ids", "area", "previews"} of things on board b, or None when none of them is there"""
    items, groups = b.get("items") or {}, b.get("groups") or {}
    ids = [i for i in dict.fromkeys(ids) if i in items or i in groups][:500]
    rs = [r for r in (rect(b, i) for i in ids) if r]
    if not ids or not rs: return None
    x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
    area = {"x": x0, "y": y0, "w": max(r[0] + r[2] for r in rs) - x0, "h": max(r[1] + r[3] for r in rs) - y0}
    pics = [m for i in ids for m in ([i] if i in items else groups.get(i, {}).get("members") or [])]
    previews = [items[m]["path"] for m in dict.fromkeys(pics) if m in items and not items[m].get("type") and items[m].get("path")]
    return {"ids": ids, "area": area, "previews": previews[:PREVIEWS]}


def find(n, evs, b, notes=(), after=False):
    """what n's author put on n's page in its window and is still there: {"ids", "area", "previews"}, or None"""
    lo, hi = window(n, notes, after)
    mine = sorted((e for e in evs if lo < ts(e) <= hi and by_author(e, n)), key=ts)
    for kinds in (PLACE, ("move",)):
        got = of_ids(b, [i for e in mine if e.get("kind") in kinds for i in e.get("ids") or []])
        if got: return got
    return None


def place(n, evs, b, notes=()):
    """where a click on n goes: its own things or area while there, else its author's around its time (find, after=True)"""
    own = of_ids(b, n.get("ids") or [])
    if own: return {**own, "area": n.get("area") or own["area"], "previews": n.get("previews") or own["previews"]}
    if isinstance(n.get("area"), dict): return {"ids": [], "area": n["area"], "previews": n.get("previews") or []}
    return find(n, evs, b, notes, after=True)


def tiles(n, load):
    """n with the bell's pictures of what it names (feedthumbs.py: "pv", "pvn"), written when it is made; old ones get them on read.
    load(page) gives the page's board"""
    if "pv" in n or not n.get("page") or not (n.get("ids") or n.get("area") or n.get("previews")): return n
    try: b = load(n["page"])
    except (OSError, ValueError, PermissionError): return n
    n["pv"], n["pvn"] = feedthumbs.of_notification(n, b)
    return n


# ---- hy.py's side
def _plural(n, one, few, many):
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def parts(b, ids):
    """«6 кадров, 1 заметка, 1 группа»: what ids are, counted as the bell says it"""
    items, kinds = b.get("items") or {}, {}
    for i in ids:
        it = items.get(i)
        t = "group" if it is None else "pic" if not it.get("type") else it["type"] if it["type"] in ("note", "model3d", "text") else "other"
        kinds[t] = kinds.get(t, 0) + 1
    words = [("pic", "кадр", "кадра", "кадров"), ("note", "заметка", "заметки", "заметок"), ("model3d", "3D-карточка", "3D-карточки", "3D-карточек"),
             ("text", "заголовок", "заголовка", "заголовков"), ("other", "объект", "объекта", "объектов"), ("group", "группа", "группы", "групп")]
    return ", ".join(f"{kinds[k]} {_plural(kinds[k], *w)}" for k, *w in words if kinds.get(k))


def ask(api, page, b):
    """ids of what this agent put on the page since its last notification there: the server's answer, or (an older server without
    {"action": "place"}) the page's events read here, the author known by HYIMG_AGENT"""
    code, res = api("/api/notifications", {"action": "place", "page": page})
    if code == 200 and isinstance(res, dict): return res.get("ids") or []
    who = os.environ.get("HYIMG_AGENT") or ""
    if not who: return []
    _, evs = api(f"/api/events?name={page}&limit=3000")
    _, notes = api("/api/notifications?limit=500")
    notes = notes.get("items") or [] if isinstance(notes, dict) else []
    got = find({"id": "", "ts": time.time(), "page": page, "who": who}, evs if isinstance(evs, list) else [], b, notes)
    return got["ids"] if got else []


def repair(api, nid):
    """hy.py notify --place ID: an old notification that names nothing gets its author's things around its time, written by the server"""
    if not nid: raise SystemExit("hy.py notify --place ID")
    code, res = api("/api/notifications", {"action": "place", "id": nid, "fill": True})
    if code != 200: raise SystemExit(f"место не записано: {code} {res} (сервер без notifplace: перезапусти его: Вид › Перезапустить сервер)")
    if not res.get("found"): print(f"{nid}: событий автора рядом по времени не нашлось, уведомление осталось без места"); return
    print(f"{nid}: {len(res['ids'])} вещей на странице {res.get('page')}, область {res['area']}, превью {len(res['previews'])}"
          + (" (уже было место)" if res.get("had") else ""))
