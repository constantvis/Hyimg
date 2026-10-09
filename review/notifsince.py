"""What came to the bell since a time (owner 2026-10-08, a screenshot of macOS banners: «очень крутая тема, чтобы я видел, что
что-то произошло, что-то новое появилось»). The Mac app asks every open board for its new bell items every few
seconds (native/MacNotifications.swift) and shows each as a macOS notification:

  GET /api/notifications?since=<unix seconds>&limit=<n>   the rows whose time is after since, newest first, and "now", the server's time

Every row of /api/notifications gets three fields here, with or without since:
  ts     its time in unix seconds (an agent's news has it; a comment's and a note reply's come from comments.feed; old news: its "t")
  type   agent (an agent's news, hy.py notify), comment (a new thread, or a reply in a thread this person never wrote in), reply (a reply
         in a thread he or his agent wrote in), mention (he or his agent is @mentioned), note (a reply arrow to his note); the app's
         Settings › Notifications turn each on or off
  from   who it is from, as the banner's title says it: «Claude» for this Mac's person's agent, «Codex · Bob» for another person's,
         «Bob» for a person
A since that is not a finite number is ignored: the whole list, as without it."""
import math
import time

import agents


def when(n):
    """a row's time in unix seconds: its ts, else its t («YYYY-MM-DD HH:MM:SS», local time), else 0"""
    try:
        v = float(n["ts"])
        if math.isfinite(v) and v > 0: return v
    except (KeyError, TypeError, ValueError): pass
    try: return time.mktime(time.strptime(str(n.get("t") or "")[:19], "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OverflowError): return 0.0


def sender(n, view):
    """who a row is from (see above); view: people.view(), {me, people}"""
    by = n.get("by") if isinstance(n.get("by"), dict) else {}
    me = ((view or {}).get("me") or {}).get("id")
    name = (((view or {}).get("people") or {}).get(by.get("person")) or {}).get("name") or ""
    via = by.get("via") or ""
    ag = agents.label(via) if via and via != "app" else ""
    if n.get("type") == "agent" and not ag: ag = agents.label(n.get("who"))
    if ag: return ag if not by.get("person") or by.get("person") == me or not name else f"{ag} · {name}"
    return name or str(n.get("who") or "")


def typed(L, view=None):
    """the rows with ts, type and from (copies; the stored notifications are not changed)"""
    out = []
    for n in L:
        n = dict(n)
        n["ts"] = when(n)
        if not n.get("type"): n["type"] = "note" if n.get("kind") == "note" else "comment" if n.get("kind") == "comment" else "agent"
        n["from"] = sender(n, view)
        out.append(n)
    return out


def since(L, q):
    """the rows after ?since= (q: the parsed query), or all of them"""
    try: s = float((q.get("since") or [""])[0])
    except (TypeError, ValueError): return L
    return [n for n in L if n.get("ts", 0) > s] if math.isfinite(s) else L
