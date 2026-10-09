# Sticky notes from the canvas, for agents (2026-09-30). The notes live once in notes/<board>__<id>.json; a picture's sidecar holds only
# "related_notes" references. Usage:
#   python3 _review/notes.py                 all notes: id, scope, group, how many pictures, first line; replies under their note
#   python3 _review/notes.py <thing>         the notes that touch a picture or a card: a part of its path or file (a card's .html, a 3D
#                                            scene), or its id on the board (2026-10-07: "objects" in a note file, every kind)
#   python3 _review/notes.py --show <id>     one note in full with everything it touches, id as main/abc123
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
            if d.get("reply_to") or d.get("replies"): print(f"   ответ на {d.get('reply_to') or '-'}, ответы: {', '.join(d.get('replies') or []) or '-'}\n")
            for p in d.get("objects") or [{"kind": "picture", "file": p["path"], **p} for p in d["pictures"]]:
                print("  ", ",".join(p["via"]).ljust(14), p["kind"].ljust(8), p.get("file") or p.get("name") or "", f"[{p['id']}]" if p.get("id") else "")
elif a:
    for d in docs:
        hit = [p for p in d.get("objects") or d["pictures"] if a[0] in (p.get("file") or p.get("path") or "") or a[0] == p.get("id")]
        if hit: print(f"{d['id']}  [{','.join(hit[0]['via'])}]" + (f"  группа «{d['group']}»" if d.get("group") else "") + f"\n{d['text']}\n")
else:   # a reply (reply_to, 2026-10-08) stands under the note it answers, indented
    ids = {d["id"] for d in docs}

    def line(d, depth=0, seen=()):
        print(f"{'   ' * depth + ('↳ ' if depth else '') + d['id']:<22} {d['scope']:<9} {len(d.get('objects') or d['pictures']):>3} объект.  "
              f"{(d.get('group') or '-')[:22]:<22} {d['text'].splitlines()[0][:60]}")
        for r in docs:
            if r.get("reply_to") == d["id"] and r["id"] not in seen: line(r, depth + 1, (*seen, d["id"]))
    for d in docs:
        if d.get("reply_to") not in ids: line(d)
