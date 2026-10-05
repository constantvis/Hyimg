# Sticky notes from the canvas, for agents (2026-09-30). The notes live once in notes/<board>__<id>.json; a picture's sidecar holds only
# "related_notes" references. Usage:
#   python3 _review/notes.py                 all notes: id, scope, group, how many pictures, first line
#   python3 _review/notes.py <picture>       the notes that touch a picture (path or file name, part of it is enough)
#   python3 _review/notes.py --show <id>     one note in full with its pictures, id as main/abc123
import glob, json, os, sys
from config import HERE, W, BOARDS, NOTES
docs = []
for f in sorted(glob.glob(os.path.join(NOTES, "*.json"))):
    try: docs.append(json.load(open(f, encoding="utf-8")))
    except (OSError, ValueError): pass
a = sys.argv[1:]
if a[:1] == ["--show"]:
    for d in docs:
        if d["id"] == a[1]:
            print(f"{d['id']}  {d['color']}  {d['scope']}" + (f"  группа «{d['group']}»" if d.get("group") else "") + f"\n\n{d['text']}\n")
            for p in d["pictures"]: print("  ", ",".join(p["via"]).ljust(14), p["path"])
elif a:
    for d in docs:
        hit = [p for p in d["pictures"] if a[0] in p["path"]]
        if hit: print(f"{d['id']}  [{','.join(hit[0]['via'])}]" + (f"  группа «{d['group']}»" if d.get("group") else "") + f"\n{d['text']}\n")
else:
    for d in docs: print(f"{d['id']:<22} {d['scope']:<9} {len(d['pictures']):>3} кадров  {(d.get('group') or '-')[:22]:<22} {d['text'].splitlines()[0][:60]}")
