"""3D files as files of their folders (owner 2026-10-07, project «Field Kit»: STEP files in «modeling C4D», «я не могу их смотреть через
наш 3D просмотрщик»). Until then the library listed 3D files only under its «3D» filter (server.py scan3d, /api/models3d): the folder view
showed a folder's PNG pictures and not the STEP beside them, and a folder holding only a .stp was not there at all. Now /api/items lists
every 3D file the 3D filter lists (the same walk, the same rules), as a card of its folder like a PSD or a PDF: kind "model", its
extension, its version and turntable (the plugin's sprites.js draws it, the STEP converted by FreeCAD first), its ratings in its own json
(<file>.step.json, as <file>.psd.json: a picture of the same name beside it keeps its own).

The library draws the tile from the turntable (v2.html card3d), its viewer shows the model in 3D (ui/lib3d.js and the plugin's viewer.js),
the board makes a 3D card of it (the plugin's place.js). Nothing here reads or writes the 3D file itself.
"""
import json
import os

FRAME = {"model": "", "aspect": "1:1", "prompt": "", "refs": [], "refpaths": [], "owner_tags": [], "gate": None, "grid": "", "grid_feedback": {},
         "board_notes": [], "tags": []}   # what scan() gives a frame and a 3D entry has not: the pages read them without asking


def as_frames(models, real):
    """the entries of server.scan3d as items of the library list; real(rel) is the file's path on disk"""
    out = []
    for m in models:
        i = {**FRAME, **m}
        try: meta = json.load(open(real(i["path"]) + ".json", encoding="utf-8"))
        except (OSError, ValueError): meta = {}
        if isinstance(meta, dict):
            if isinstance(meta.get("feedback"), dict): i["feedback"] = meta["feedback"]
            if isinstance(meta.get("questions"), list): i["questions"] = meta["questions"]
        out.append(i)
    return out


def fresh(items, sprite_info):
    """the turntables drawn since the list was made (the list is kept for a minute, a sheet is drawn in seconds)"""
    for i in items:
        if i.get("kind") == "model" and not i.get("sprite"): i["sprite"] = sprite_info(i["path"], i.get("ver") or 0)
    return items


def preview(rel, sprite_file):
    """a picture of a 3D file for /thumb and /img: its turntable's first view; none yet is a FileNotFoundError (404), never Quick Look on a
    STEP (seconds per file, and a grey card kept for the file's version after the turntable is there)"""
    still = sprite_file(rel, 512)
    if not still: raise FileNotFoundError(f"{rel}: no turntable yet")
    out = still[:-5] + ".jpg"   # on the library's light grey: a thumbnail is a jpeg, the sheet's see-through corners would be black
    if not os.path.exists(out):
        from PIL import Image
        with Image.open(still) as im:
            bg = Image.new("RGBA", im.size, (236, 236, 234, 255)); bg.alpha_composite(im.convert("RGBA")); bg.convert("RGB").save(out + ".tmp.jpg", quality=88)
        os.replace(out + ".tmp.jpg", out)
    return out
