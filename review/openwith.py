"""«Open with ›» on a card's right-click menu and in the Info card's Open ▾ (round 20, owner 2026-10-11 on open-b.html: «да вот так лучше»):
the apps of this Mac that open a library file, its default app first, as Finder's «Open With ›» lists them; a click opens the file in one
of them, «Other…» asks macOS to choose an app. Before this the menus had only «Open in <default app>» (owner 2026-10-06), and the Info
card's Open ▾ put it next to Hyimg's own viewer, both called Preview (panels audit P-12).

LaunchServices answers through osascript (JXA, NSWorkspace), once per file extension. HYIMG_OPEN_APPS='[{"name": ..., "path": ...}]'
answers for every file instead (tests: nothing depends on what this Mac has installed); the first one is the default then.
An app is opened only when it was listed for that kind of file: a page cannot make the server run any path it likes."""
import json
import os
import subprocess

APPS = {}   # extension -> [{name, path, default}]
JXA_APPS = """ObjC.import('AppKit');
function run(argv) {
  const ws = $.NSWorkspace.sharedWorkspace, u = $.NSURL.fileURLWithPath(argv[0]), fm = $.NSFileManager.defaultManager, out = [], seen = {};
  const d = ws.URLForApplicationToOpenURL(u), dp = d && !d.isNil() ? ObjC.unwrap(d.path) : "";
  const add = p => { if (!p || seen[p]) return; seen[p] = 1; out.push({ name: String(ObjC.unwrap(fm.displayNameAtPath(p))).replace(/[.]app$/, ""), path: p, default: p === dp }); };
  add(dp);
  const all = ws.URLsForApplicationsToOpenURL ? ws.URLsForApplicationsToOpenURL(u) : null;
  if (all && !all.isNil()) for (let i = 0; i < all.count; i++) add(ObjC.unwrap(all.objectAtIndex(i).path));
  return JSON.stringify(out);
}"""
JXA_CHOOSE = """const app = Application.currentApplication(); app.includeStandardAdditions = true;
function run(argv) { try { return app.chooseApplication({ withPrompt: argv[0], as: "alias" }).toString(); } catch (e) { return ""; } }"""
MOST = 16   # a submenu, not a list of every app that claims PNG


def _clean(found):
    """the default first, then by name; one row per name (two versions of one app read the same in a menu), at most MOST"""
    out, names = [], set()
    rows = [a for a in found if isinstance(a, dict) and isinstance(a.get("name"), str) and isinstance(a.get("path"), str) and a["name"] and a["path"]]
    rows.sort(key=lambda a: (not a.get("default"), a["name"].lower()))
    for a in rows:
        if a["name"].lower() in names: continue
        names.add(a["name"].lower()); out.append({"name": a["name"], "path": a["path"], "default": bool(a.get("default"))})
    return out[:MOST]


def apps(full):
    """the apps that open this file: [{"name": "Preview", "path": "/System/Applications/Preview.app", "default": true}, ...]"""
    fake = os.environ.get("HYIMG_OPEN_APPS")
    if fake:
        try: found = json.loads(fake)
        except ValueError: found = []
        if found and isinstance(found[0], dict) and not any(isinstance(a, dict) and a.get("default") for a in found): found[0]["default"] = True
        return _clean(found)
    ext = os.path.splitext(full)[1].lower()
    if ext in APPS: return APPS[ext]
    try:
        out = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", JXA_APPS, full], capture_output=True, text=True, timeout=10).stdout.strip()
        found = json.loads(out) if out else []
    except (OSError, ValueError, subprocess.SubprocessError):
        found = []
    APPS[ext] = _clean(found if isinstance(found, list) else [])
    return APPS[ext]


def known(app_path):
    """an app some file's list named (the icons are drawn for these only)"""
    return any(a["path"] == app_path for rows in APPS.values() for a in rows)


def open_with(full, app_path, cmd):
    """the file in one of its listed apps (`open -a`); PermissionError for an app not on its list"""
    hit = next((a for a in apps(full) if a["path"] == app_path), None)
    if not hit: raise PermissionError(app_path)
    subprocess.run([cmd, "-a", hit["path"], full], capture_output=True, timeout=20)   # an argument list, no shell
    return {"opened": full, "app": hit["name"]}


def choose(full, cmd, prompt="Open with"):
    """«Other…»: macOS's own chooser of apps, then `open -a`; {"cancelled": true} when the person closed it"""
    try:
        got = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", JXA_CHOOSE, prompt], capture_output=True, text=True, timeout=300).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        got = ""
    path = got.rstrip("/")
    if not path.endswith(".app") or not os.path.isdir(path): return {"cancelled": True}
    subprocess.run([cmd, "-a", path, full], capture_output=True, timeout=20)
    return {"opened": full, "app": os.path.basename(path)[:-4]}
