"""The row-plate rule of scripts/validate.py: the top row is one row (owner 2026-10-07: «breadcrumb area тоже разношерстная», the
group's and the 3D scene's title after the crumb were shorter and another shade). design/contract.json runtime.top_row names the plates.

  a title plate after the crumb (top_row.title_plates: .gst, .m3title) is made with the class hy-plate, and no page but ui/hy/plate.css
  sets its look (height, padding, ground, glass, shadow, edge, corner, font)
  a rule for a plate of the row (top_row.plates) keeps the row's tokens: 38 px or var(--hy-plate-h), blur(14px), var(--plate-sh) or
  another var(), the plate ground at 82 %

Its runtime half is design/audit.js «top-row» (tests/test_design_toprow.py).
"""
import re

RULE = "row-plate"
REASON = ("the top row is one row (owner 2026-10-07: «breadcrumb area тоже разношерстная»): a title plate after the crumb is made with "
          "the class hy-plate and takes its look from ui/hy/plate.css; a rule for a plate of the row keeps its height, glass and shadow tokens "
          "(scripts/validate_row.py)")
LOOK = re.compile(r"(?<![\w-])(height|min-height|padding(?:-top|-bottom|-block)?|background(?:-color)?|(?:-webkit-)?backdrop-filter"
                  r"|box-shadow|border(?:-radius)?|font(?:-size|-weight)?|line-height)\s*:\s*([^;]+)")
CLASS = re.compile(r"(?:className\s*=\s*|class\s*=\s*\\?)([\"'`])([^\"'`<>]*)\1")


def subjects(sel, T):
    """the compounds of a selector that are a plate of the row: (title, plate), a title plate (.gst, .m3title, .hy-plate) or a listed one"""
    title, plate = [], []
    names = "|".join(map(re.escape, T["title_plates"] + ["hy-plate"]))
    listed = [q for q in T["plates"] if not q.startswith(".hy-plate")]
    for x in re.split(r",(?![^()]*\))", sel):
        x = x.strip(); last = re.split(r"\s*[\s>+~]\s*(?![^()]*\))", x)[-1]
        if "::" in last or ":where(" in last: continue
        if re.search(r"\.(" + names + r")(?![\w-])", last): title.append(x)
        elif any(re.search(re.escape(q.split()[-1]) + r"(?![\w-])", last) and all(p in x for p in q.split()[:-1]) for q in listed): plate.append(x)
    return title, plate


def bad_token(k, v):
    return (k == "height" and v not in ("38px", "var(--hy-plate-h)", "auto")
            or k == "box-shadow" and not (v.startswith("var(--") or v == "none")
            or k.endswith("backdrop-filter") and v != "none" and not v.startswith("blur(14px)")
            or k in ("background", "background-color") and "color-mix" in v and "var(--panel) 82%" not in v)


def check(src, report, C, css_rules):
    T = C["runtime"].get("top_row")
    if not T: return
    if not src.rel.endswith(("ui/look.css", "ui/hy/plate.css")):
        for off, txt in src.css_texts():
            for sel, body, boff in css_rules(txt):
                if not sel or sel.startswith("@") or re.search(r":root\[data-(shape|ui)", sel): continue
                title, plate = subjects(sel, T)
                for m in LOOK.finditer(body) if title else ():
                    if m.group(1) == "background" and m.group(2).strip() in ("transparent", "none"): continue
                    report.add(src, off + boff + m.start(), RULE,
                               f"«{title[0][-40:]}» sets its own {m.group(1)}: a title plate of the top row takes the row's look from .hy-plate (ui/hy/plate.css)")
                    break
                for m in LOOK.finditer(body) if plate else ():
                    k, v = m.group(1), m.group(2).replace("!important", "").strip()
                    if bad_token(k, v):
                        report.add(src, off + boff + m.start(), RULE, f"{k}: {v[:50]} on a plate of the top row ({plate[0][-40:]}): "
                                   "the row's tokens (38 px, blur(14px), var(--plate-sh), the plate ground at 82 %)")
    for m in CLASS.finditer(src.decl_text()):   # a title plate made in code or markup carries hy-plate
        toks = m.group(2).split()
        if any(t in T["title_plates"] for t in toks) and "hy-plate" not in toks:
            report.add(src, m.start(), RULE, f"class «{m.group(2)}»: a title plate of the top row is made with the class hy-plate (ui/hy/plate.css)")
