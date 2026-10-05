# My questions to the owner about what his comments meant (2026-09-29). They sit in the frame's sidecar under "questions"
# (outside "feedback", so saves from the page never drop them) and show on the review page with an orange "?" and the «Вопросы» filter.
#   python3 _review/ask.py add <frame path> "question" [pick]   add a question (pick = answered by a heart or verdict on the frame)
#   python3 _review/ask.py load questions.json                  add many: [{"path", "q", "kind"?}]
#   python3 _review/ask.py answers [--open]                     print every question with its answer (--open: unanswered only)
import json, os, sys, time

from config import HERE, W


def side(path):
    return os.path.splitext(os.path.join(W, path))[0] + ".json"


def add(path, q, kind=""):
    sp = side(path)
    meta = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    qs = meta.setdefault("questions", [])
    if any(x["q"] == q for x in qs):
        return False
    item = {"id": f"q{len(qs) + 1}", "q": q, "a": "", "asked": time.strftime("%Y-%m-%d %H:%M"), "answered": ""}
    if kind:
        item["kind"] = kind
    qs.append(item)
    tmp = sp + ".tmp"
    json.dump(meta, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, sp)
    return True


def answers(only_open=False):
    for root, dirs, files in os.walk(W):
        dirs[:] = [d for d in dirs if d not in ("_thumbs", "refs", "__pycache__")]
        for f in sorted(files):
            if not f.endswith(".json") or f.startswith(("_raw-", "jobs")):
                continue
            p = os.path.join(root, f)
            try:
                meta = json.load(open(p, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(meta, dict) or not meta.get("questions"):
                continue
            fb = meta.get("feedback") or {}
            for q in meta["questions"]:
                if only_open and q.get("a", "").strip():
                    continue
                print(f"{os.path.relpath(p, W)[:-5]}  [{q['id']}]  fav={bool(fb.get('fav'))} verdict={fb.get('verdict', '')}")
                print("  Q:", q["q"])
                print("  A:", q.get("a", "") or "—")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "add":
        print(add(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ""))
    elif cmd == "load":
        n = sum(add(x["path"], x["q"], x.get("kind", "")) for x in json.load(open(sys.argv[2], encoding="utf-8")))
        print(n, "questions added")
    elif cmd == "answers":
        answers("--open" in sys.argv)
