# Settings › Plugins (owner 2026-10-07: «Хочу, чтобы в настройках было видно, какие плагины подключены, добавить новый плагин ...
# в процессе работы отключить какой-то плагин, и он отключался ... В настройках включить, выключить и посмотреть»).
#
# Where plugins come from: the folders in HYIMG_PLUGINS (paths split by ":") and the plugins folder the person manages, normally
# ~/Library/Application Support/Hyimg/plugins (HYIMG_PLUGIN_DIR names another; a test that sets HY_TEST_ONLY_PLUGINS has none unless it
# names one). A plugin there is a link to its repository; «Add plugin…» checks a folder's manifest.json and makes that link, «Remove»
# takes the link away and never touches the folder it points to.
#
# On and off: the app's setting cv.plugoff in the settings file every board's server reads (a comma list of names, all on when it is
# missing). The server asks active() on every request, so a plugin turned off stops being served at once, without a restart: its files,
# its routes (they answer «plugin off»), its kinds of library files, its page script. A board's page that is inside the plugin's editor
# holds it (hold(), a lease the page renews) until the person leaves the editor; then the page reloads without it.
#
#   python3 plugins_admin.py list | add <folder> | remove <name>    (the Mac app, for Home; JSON on stdout)
import json, os, re, sys, threading, time

NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
DEFAULT = os.path.expanduser("~/Library/Application Support/Hyimg/plugins")
FILES = ("canvas", "server", "sprites", "pageScript")   # the manifest's files, each must lie inside the plugin's folder
HOLD_S = 90   # a page renews its hold every 30 s while it is in a plugin's editor; a page that went away lets go by itself
_HOLDS, _LOCK = {}, threading.Lock()


def managed():
    """the plugins folder the person manages; "" in a test that names its plugins and no folder"""
    d = os.environ.get("HYIMG_PLUGIN_DIR")
    if d: return d
    return "" if os.environ.get("HY_TEST_ONLY_PLUGINS") == "1" else DEFAULT


def roots():
    m = managed()
    return [r for r in os.environ.get("HYIMG_PLUGINS", "").split(os.pathsep) if r] + ([m] if m else [])


def entries():
    """every name in every root, the first root wins a name: (name, entry path, real folder, manifest or None, why not)"""
    out, seen = [], set()
    for root in roots():
        if not os.path.isdir(root): continue
        for n in sorted(os.listdir(root)):
            if n in seen or not NAME.fullmatch(n): continue
            e = os.path.join(root, n); d = os.path.realpath(e); m = os.path.join(d, "manifest.json")
            man = None
            if os.path.isfile(m):
                try: man = json.load(open(m, encoding="utf-8"))
                except (OSError, ValueError): man = None
            if isinstance(man, dict): seen.add(n); out.append((n, e, d, man, ""))
            elif os.path.islink(e) or os.path.isdir(d): out.append((n, e, d, None, "manifest.json is broken" if os.path.isfile(m) else "no manifest.json"))
    return [r for r in out if r[3] is not None or r[0] not in seen]   # a broken entry, unless a later root has that name working


def scan():
    """{name: (folder, manifest)} of every plugin found, on or off (server.plugins)"""
    return {n: (d, man) for n, _e, d, man, _w in entries() if man is not None}


def off_names(settings):
    """the names cv.plugoff turns off"""
    return {n.strip() for n in str((settings or {}).get("cv.plugoff") or "").split(",") if NAME.fullmatch(n.strip())}


def held():
    now = time.time()
    with _LOCK:
        for n in [n for n, t in _HOLDS.items() if t < now]: _HOLDS.pop(n)
        return set(_HOLDS)


def hold(name, on):
    """a board's page is inside this plugin's editor (on), or left it: while held the plugin is served even when it was turned off"""
    if not NAME.fullmatch(str(name or "")): return sorted(held())
    with _LOCK:
        if on: _HOLDS[name] = time.time() + HOLD_S
        else: _HOLDS.pop(name, None)
    return sorted(held())


def active(found, settings):
    """the plugins the server serves now: all but the ones turned off, unless a page still holds one"""
    off = off_names(settings) - held()
    return {n: v for n, v in found.items() if n not in off}


def why_off(name, settings):
    """the answer of an off plugin's route: (409, "plugin off: <name>"), else None"""
    return (409, f"plugin off: {name}") if name in off_names(settings) - held() else None


# what the settings show -------------------------------------------------------------------------------------------------------------
def pick(man, key, lang):
    """the manifest's words in the app's language: <key>_ru in Russian when it has it, else as it is"""
    v = man.get(f"{key}_{lang}") if lang != "en" else None
    v = v if isinstance(v, str) and v.strip() else man.get(key)
    return v.strip() if isinstance(v, str) else ""


def listing(settings, lang="en"):
    off, hl, m = off_names(settings), held(), managed()
    rows = []
    for n, e, d, man, why in entries():
        own = bool(m) and os.path.dirname(e) == m.rstrip("/")
        r = {"name": n, "folder": d, "link": os.path.islink(e), "own": own, "off": n in off, "held": n in off and n in hl, "error": why}
        if man is not None:
            r.update(title=pick(man, "title", lang) or n, version=str(man.get("version") or ""), canvas=isinstance(man.get("canvas"), str),
                     description=pick(man, "description", lang) or pick(man, "about", lang))
        else: r.update(title=n, version="", description="", canvas=False)
        r["removable"] = own and r["link"]
        rows.append(r)
    return {"plugins": rows, "root": m, "off": sorted(off)}


# add and remove ---------------------------------------------------------------------------------------------------------------------
T_RU = {"Not a folder": "Это не папка", "No manifest.json in the folder": "В папке нет manifest.json", "manifest.json is broken": "manifest.json не читается",
        "manifest.json has no title": "В manifest.json нет title", "manifest.json names no canvas, server or kinds": "manifest.json не называет canvas, server или kinds",
        "The manifest's {k} file is missing: {f}": "Нет файла {k} из манифеста: {f}", "No plugins folder here": "Здесь нет папки плагинов",
        "Already added as «{n}»": "Уже добавлен как «{n}»", "A plugin named «{n}» is already there": "Плагин с именем «{n}» уже есть",
        "No plugin «{n}» in the plugins folder": "Плагина «{n}» нет в папке плагинов",
        "«{n}» is a folder, not a link: Hyimg removes only links, move the folder in Finder": "«{n}» это папка, а не ссылка: Hyimg убирает только ссылки, папку переместите в Finder",
        "A name has lowercase letters, digits, - and _": "В имени только строчные буквы, цифры, - и _"}


def say(lang, en, **v):
    return (T_RU.get(en, en) if lang == "ru" else en).format(**v)


def check(folder, lang="en"):
    """the folder's manifest, or ValueError with the reason in the app's language"""
    d = os.path.realpath(os.path.expanduser(str(folder or "")))
    if not os.path.isdir(d): raise ValueError(say(lang, "Not a folder"))
    m = os.path.join(d, "manifest.json")
    if not os.path.isfile(m): raise ValueError(say(lang, "No manifest.json in the folder"))
    try: man = json.load(open(m, encoding="utf-8"))
    except (OSError, ValueError): man = None
    if not isinstance(man, dict): raise ValueError(say(lang, "manifest.json is broken"))
    if not (isinstance(man.get("title"), str) and man["title"].strip()): raise ValueError(say(lang, "manifest.json has no title"))
    if not any(man.get(k) for k in ("canvas", "server", "kinds")): raise ValueError(say(lang, "manifest.json names no canvas, server or kinds"))
    for k in FILES:
        f = man.get(k)
        if f is None: continue
        full = os.path.realpath(os.path.join(d, str(f)))
        if not isinstance(f, str) or not full.startswith(d + os.sep) or not os.path.isfile(full):
            raise ValueError(say(lang, "The manifest's {k} file is missing: {f}", k=k, f=f))
    return d, man


def name_for(folder, man):
    """the manifest's name, else the folder's: hyimg-dev-studio → dev, hyimg-image-studio → frames"""
    n = man.get("name")
    if isinstance(n, str) and NAME.fullmatch(n): return n
    b = re.sub(r"[^a-z0-9_-]+", "-", os.path.basename(folder).lower())
    b = re.sub(r"^hyimg-", "", b); b = re.sub(r"-(studio|plugin)$", "", b)
    return b.strip("-_") or "plugin"


def add(folder, lang="en"):
    """links the folder into the plugins folder under its name; {"added": name} or ValueError"""
    d, man = check(folder, lang)
    root = managed()
    if not root: raise ValueError(say(lang, "No plugins folder here"))
    for n, _e, real, _m, _w in entries():
        if real == d: raise ValueError(say(lang, "Already added as «{n}»", n=n))
    n = name_for(d, man)
    if not NAME.fullmatch(n): raise ValueError(say(lang, "A name has lowercase letters, digits, - and _"))
    e = os.path.join(root, n)
    if os.path.lexists(e) or n in scan(): raise ValueError(say(lang, "A plugin named «{n}» is already there", n=n))
    os.makedirs(root, exist_ok=True)
    os.symlink(d, e)
    return {"added": n, "title": pick(man, "title", lang)}


def remove(name, lang="en"):
    """takes the link away; the folder it points to stays as it is"""
    root = managed(); e = os.path.join(root, str(name or "")) if root else ""
    if not root or not NAME.fullmatch(str(name or "")) or not os.path.lexists(e): raise ValueError(say(lang, "No plugin «{n}» in the plugins folder", n=name))
    if not os.path.islink(e): raise ValueError(say(lang, "«{n}» is a folder, not a link: Hyimg removes only links, move the folder in Finder", n=name))
    os.unlink(e)
    return {"removed": name}


# the server's routes: GET /api/plugins/all, POST /api/plugins/hold {name, on}, POST /api/plugins/remove {name} --------------------
def http(method, path, body, settings, lang):
    """(status, bytes, content type)"""
    ok = lambda d, code=200: (code, json.dumps(d, ensure_ascii=False).encode(), "application/json")
    path = path.split("?")[0]
    if method == "GET" and path == "/api/plugins/all": return ok({**listing(settings, lang), "held": sorted(held())})
    if method != "POST": return ok({"error": "no such route"}, 404)
    try: q = json.loads(body or b"{}"); assert isinstance(q, dict)
    except (ValueError, AssertionError): return ok({"error": "bad body"}, 400)
    if path == "/api/plugins/hold": return ok({"held": hold(q.get("name"), bool(q.get("on")))})
    if path == "/api/plugins/remove":
        try: res = remove(q.get("name"), lang)
        except (ValueError, OSError) as ex: return ok({"error": str(ex)}, 400)
        return ok({**res, **listing(settings, lang)})
    return ok({"error": "no such route"}, 404)


def main(argv):
    sf = os.environ.get("HYIMG_SETTINGS") or os.path.join(os.environ.get("HYIMG_PROFILE_DIR") or os.path.dirname(DEFAULT), "settings.json")
    try: settings = json.load(open(sf, encoding="utf-8")); settings = settings if isinstance(settings, dict) else {}
    except (OSError, ValueError): settings = {}
    lang = "ru" if settings.get("cv.lang") == "ru" else "en"
    op = argv[1] if len(argv) > 1 else "list"
    try:
        res = add(argv[2], lang) if op == "add" and len(argv) > 2 else remove(argv[2], lang) if op == "remove" and len(argv) > 2 else {}
    except (ValueError, OSError) as ex:
        res = {"error": str(ex)}
    print(json.dumps({**res, **listing(settings, lang)}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)
