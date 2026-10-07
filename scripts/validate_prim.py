"""The hy-primitive rule of scripts/validate.py: a control that has a primitive in review/ui/hy is not built by hand again (owner
2026-10-07, step 0 of docs/ui-inventory.md: «one switch, one checkbox, one key cap, one badge ...», «Свои ползунки не рисовать» said for
every control). The copies written before the primitives are in design/baseline.json (static, rule hy-primitive), so their count can only
go down: each one migrated leaves the count (`validate.py --update-baseline --rule hy-primitive`), a new one fails. Warn mode: the known
copies are listed as warnings in the summary (`validate.py --list hy-primitive`); the rule turns strict, no baseline, when the migration
is done (docs/ui-inventory.md §5, step 8).

What counts as a hand-built copy, read from a CSS rule's last compound and its declarations (review/ui/hy itself is the primitives' home):
  hy-kbd          a rule for kbd (or .kc) that sets its ground, edge, corner or size
  hy-switch       a pill wider than tall, at most 24 px high, on a switch-like class (.sw .tg .toggle .switch [role=switch])
  hy-check        a native checkbox restyled (accent-color, appearance) or a 12 to 18 px box on a check-like class (.ck .fck .chk)
  hy-swatch       a circle of 7 to 28 px with a colour ground on a swatch-like class (sw, swatch, pjc, msw)
  hy-badge        a pill at most 18 px high with a min-width, a ground and words of 11 px or less (a count on a corner)
  hy-icon-button  a 38 px square that is round: a round key of the top row
  hy-plate        a 38 px plate of glass (blur 14) outside the shared plate rule
  hy-segmented    tabs or a choice track of its own: a class ending in tabs or seg (not the shared .seg) with a ground
  hy-hint         a footnote restated: 11 px at line 1.35 in the hint's colour
"""
import re

RULE = "hy-primitive"
REASON = ("a control that has a primitive (review/ui/hy: hy-button, hy-icon-button, hy-switch, hy-check, hy-kbd, hy-badge, hy-chip, hy-swatch, "
          "hy-segmented, hy-plate, hy-hint, hy-info) is not built by hand again; the copies before 2026-10-07 are known and may only go down "
          "(scripts/validate_prim.py)")
HOME = ("ui/hy/", "ui/look.css", "ui/tokens.css")   # the primitives and the shared rules they took over

PX = re.compile(r"(-?[\d.]+)px")


def decls(body):
    """{property: value} of a rule's body, !important dropped"""
    out = {}
    for m in re.finditer(r"(?<![\w-])([a-z-]+)\s*:\s*([^;]+)", body):
        out[m.group(1)] = m.group(2).replace("!important", "").strip()
    return out


def px(v):
    m = PX.match((v or "").strip())
    return float(m.group(1)) if m else None


def font_px(d):
    v = d.get("font-size") or d.get("font") or ""
    m = re.search(r"([\d.]+)px", v)
    return float(m.group(1)) if m else None


def pill(d):
    r = d.get("border-radius", "")
    return bool(re.match(r"^(\d{3,}px|50%|var\(--hy-row-r|var\(--hy-pill)", r))


def classify(last, d):
    """the primitive a rule's subject (its last compound) and declarations copy, or None"""
    h, w, mw = px(d.get("height")), px(d.get("width")), px(d.get("min-width"))
    ground = any(k in d for k in ("background", "background-color"))
    if re.search(r"(^|[\s>+~(,])kbd\b|\.kc\b", last) and any(k in d for k in ("background", "border", "border-radius", "height", "min-width")):
        return "hy-kbd"
    if re.search(r"input\[type=[\"']?checkbox", last) and ("accent-color" in d or "appearance" in d or "-webkit-appearance" in d):
        return "hy-check"
    if re.search(r"\.(ck|fck|chk|hcg-ck)(?![\w-])", last) and h and w and h == w and 12 <= h <= 18 and "border" in " ".join(d):
        return "hy-check"
    if re.search(r"\.(sw|tg|toggle|switch)(?![\w-])|\[role=[\"']?switch", last) and h and w and w > h * 1.3 and h <= 24 and pill(d) and ground:
        return "hy-switch"
    if re.search(r"\.[\w-]*(sw|swatch|pjc)(?![\w-])|\.msw\b", last) and h and w and h == w and 7 <= h <= 28 and pill(d):
        return "hy-swatch"
    if h and h <= 18 and mw and pill(d) and ground and (font_px(d) or 99) <= 11:
        return "hy-badge"
    if h == 38 and w == 38 and pill(d):
        return "hy-icon-button"
    if h == 38 and re.search(r"blur\(14px\)", d.get("backdrop-filter", "") + d.get("-webkit-backdrop-filter", "")):
        return "hy-plate"
    if re.search(r"\.[\w-]*(tabs|-seg|seg)(?![\w-])|\[role=[\"']?tablist", last) and not re.search(r"\.seg(?![\w-])", last) and ground:
        return "hy-segmented"
    if re.search(r"11px/1\.35", d.get("font", "")) and re.search(r"var\(--(hy-hint|muted|sub)\b", d.get("color", "")):
        return "hy-hint"
    return None


def check(src, report, C, css_rules):
    if any(h in src.rel for h in HOME): return
    for off, txt in src.css_texts():
        for sel, body, boff in css_rules(txt):
            if not sel or sel.startswith("@") or ":root[data-" in sel: continue
            d = decls(body)
            if not d: continue
            for part in re.split(r",(?![^()]*\))", sel):
                last = re.split(r"\s*[\s>+~]\s*(?![^()]*\))", part.strip())[-1]
                if "::" in last or ":hover" in last or ":focus" in last: continue
                prim = classify(last, d)
                if prim:
                    report.add(src, off + boff, RULE, f"«{part.strip()[-50:]}» builds a {prim} by hand: use <{prim}> (review/ui/hy), or add the variant there")
                    break
