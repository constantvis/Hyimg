"""GET /api/fav?p=<path>&p=...: the feedback (♥ and the rest) of files by their path, from the same json POST /api/fav writes.

The board asks it for an HTML card's page outside the library (html/, a project's concept rounds): the list the board loads
(/api/items) never brings those, so the card's ♥ had nothing to show after a reload (owner 2026-10-08: «И почему пропали лайки справа в
углу на HTML?», review/ui/cardfav.js). A path outside the library, or one without a json or without feedback, is left out of the answer.
"""
import json

MAX = 200   # paths in one request (the board asks 40 at a time)


def read(paths, srv):
    """{path: feedback} for the paths whose json holds some; srv is the server module (resolve, safe, sidecar)"""
    out = {}
    for p in paths[:MAX]:
        try:
            rel = srv.resolve(p); srv.safe(rel)
            with open(srv.sidecar(rel), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError, PermissionError):
            continue
        fb = meta.get("feedback") if isinstance(meta, dict) else None
        if isinstance(fb, dict) and fb:
            out[p] = fb
    return out


def http(h, q, srv):
    body = json.dumps({"feedback": read([p for p in q.get("p", []) if p], srv)}, ensure_ascii=False).encode()
    return h.send(200, body, "application/json")
