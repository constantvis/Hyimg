# Theme tags for the review page filter (owner 2026-09-29: "tags like crash test, old or young; include or exclude").
# Tags are derived from the frame's prompt, name and folder by word rules, so every new batch gets them for free.
# Negated phrases ("no people", "never plastic", "not old hands") are cut out first, so they never trigger a tag.
# A frame without a prompt only gets the engine tag and the tags its name codes give.
# The rules are the board's own data (config.py RULES: "tags" [[group, tag, regex]], "tagCodes" {name part: tag}, "pinnedTags"
# [[group, tag]]); the server hands them over with configure(). To add or fix a tag: edit the rules file and restart the server
# (⇧⌘R); nothing is written to the sidecars.
import re

RULES = []
_NEG = re.compile(r"\b(?:no|never|not|without|avoid|nothing like)\b[^,.;:\n]*", re.I)
_COMPILED = []
_CODES = {}   # codes in frame names: a name part that gives a tag
PINNED = []   # [group, tag] pairs listed first in the filter


def configure(rules):
    """the board's tag rules (config.RULES); bad entries are left out, one wrong regex does not take the library down"""
    RULES[:] = []; _COMPILED[:] = []; _CODES.clear(); PINNED[:] = []; _MEMO.clear()
    for r in rules.get("tags") or []:
        if not (isinstance(r, (list, tuple)) and len(r) == 3 and all(isinstance(x, str) for x in r)): continue
        try: _COMPILED.append((r[0], r[1], re.compile(r[2], re.I)))
        except re.error: continue
        RULES.append(tuple(r))
    _CODES.update({k: v for k, v in (rules.get("tagCodes") or {}).items() if isinstance(k, str) and isinstance(v, str)})
    PINNED.extend([g, t] for g, t in (p for p in rules.get("pinnedTags") or [] if isinstance(p, (list, tuple)) and len(p) == 2))


def engine(model, folder):
    m = (model or "").lower()
    if "higgsfield" in m: return "Nano Banana Pro · Higgsfield"
    if "magnific" in m: return "Nano Banana Pro · Magnific"
    if "midjourney" in m or (not m and "-mj-" in folder): return "Midjourney"   # the folder only when no model is written (2026-10-03: GPT strips in a "-mj-" batch were tagged Midjourney)
    if "flash-image" in m: return "Nano Banana 2"
    if "gemini" in m or "nano banana" in m: return "Nano Banana Pro · Gemini"
    if "gpt" in m or "codex" in m: return "GPT Image"
    if "blender" in m or "recolor" in m or "recolour" in m: return "3D и перекраска"
    return "Движок не указан"


_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n+")
BOILER = set()   # sentences that repeat across many prompts: the style block of a batch, not the scene


def learn(items, times=8):
    # a sentence met in `times` or more prompts is batch boilerplate ("a campaign style block...", "keep everything else identical")
    from collections import Counter
    c = Counter(x.strip().lower() for i in items for x in set(_SPLIT.split(i.get("prompt") or "")) if len(x.strip()) > 25)
    BOILER.clear(); BOILER.update(k for k, v in c.items() if v >= times)


def scene(prompt):
    return " ".join(x for x in _SPLIT.split(prompt or "") if x.strip().lower() not in BOILER)


_MEMO = {}   # the same scene, name, folder, model and owner tags give the same tags: a library of 21 000 frames re-tagged in 7 s each scan


def tags(item):
    key = (scene(item.get("prompt")), item.get("name") or "", item.get("folder") or "", item.get("model") or "", tuple(item.get("owner_tags") or ()))
    hit = _MEMO.get(key)
    if hit is None:
        if len(_MEMO) > 200000: _MEMO.clear()
        hit = _MEMO[key] = _tags(item, key[0])
    return list(hit)


def _tags(item, sc):
    text = " ".join([sc, item.get("name") or "", item.get("folder") or ""])
    text = _NEG.sub(" ", text.replace("_", " "))
    out = [t for g, t, rx in _COMPILED if rx.search(text)]
    for part in re.split(r"[-_]", item.get("name") or ""):
        if part in _CODES and _CODES[part] not in out:
            out.append(_CODES[part])
    out.append(engine(item.get("model"), item.get("folder") or ""))
    out += [t for t in item.get("owner_tags") or [] if t not in out]
    return out


def groups():
    seen, out = set(), [list(p) for p in PINNED]
    for g, t, _ in RULES:
        if (g, t) not in seen:
            seen.add((g, t)); out.append([g, t])
    return out
