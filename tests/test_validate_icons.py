"""The icon and colour rules of the static validator (owner 2026-10-07, the image studio's Adjustments tab wore the opacity's half circle:
«Нужно, чтобы это было систематизировано ... консистентные иконки, консистентные стили, консистентные цвета»): one meaning, one icon, only
from ui/icons.js; colours only by tokens. Small files written here, never the repositories' own; the registry itself is the real one."""
import importlib.util, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hyvalidate_icons", ROOT / "scripts/validate.py")
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
C = json.loads((ROOT / "design/contract.json").read_text(encoding="utf-8"))
MINE = {"icon-inline", "icon-registry", "icon-color", "icon-stroke", "css-color"}


def found(tmp_path, name, text, contract=C):
    p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
    items, _ = V.run([str(p)], contract)
    return sorted((i["rule"], i["line"]) for i in items if i["rule"] in MINE)


def test_an_icon_drawn_outside_the_registry_is_found_and_a_lookup_is_not(tmp_path):
    js = ('const a = `<svg viewBox="0 0 24 24"><path d="M5 12h14"/></svg>`;\n'
          'const b = hyIcon("plus", 15, 1.9);\n'
          "const c = '<circle cx=\"12\" cy=\"12\" r=\"3\"/>';\n"
          'const d = `<svg data-ic="close" width="12" height="12"></svg>`;\n')
    assert found(tmp_path, "a.js", js) == [("icon-inline", 1), ("icon-inline", 3)]
    css = ".x { background: url(\"data:image/svg+xml,%3Csvg%3E%3Cpath d='M0 0'/%3E%3C/svg%3E\"); }\n.y { mask: var(--hy-ic-info); }\n"
    assert found(tmp_path, "a.css", css) == [("icon-inline", 1)]
    html = '<button><svg data-ic="home" width="16" height="16" stroke-width="1.9"></svg></button>\n<svg viewBox="0 0 24 24"><rect x="1" y="1" width="2" height="2"/></svg>\n'
    assert found(tmp_path, "p.html", html) == [("icon-inline", 2)]


def test_a_drawing_that_is_not_an_icon_says_so(tmp_path):
    one = '// hy-allow: icon-inline the board\'s arrow, drawn at the board\'s scale\nconst a = `<line x1="0" y1="0" x2="${x}" y2="${y}"/>`;\n'
    assert found(tmp_path, "one.js", one) == []
    block = ("// hy-allow-begin: icon-inline the marks a person draws on a frame\nfunction shape() {\n  return `<rect x=\"${x}\"/>`\n"
             "    + `<circle r=\"${r}\"/>`;\n}\n// hy-allow-end\nconst after = `<path d=\"M0 0\"/>`;\n")
    assert found(tmp_path, "block.js", block) == [("icon-inline", 7)]


def test_a_name_asked_for_is_in_the_registry(tmp_path):
    js = ('const a = hyIcon("plus", 15, 1.9), b = hyIcon("nope", 15, 1.9);\n'
          'const c = `<svg data-ic="settings"></svg><svg data-ic="gearwheel"></svg>`;\n'
          'const T = {   // hy-icon-names\n  x: "close", y: "nothere"\n};\n'
          'const m = hyMarkIcon("scene3d"), n = hyMarkIcon("cube");\n')
    assert found(tmp_path, "n.js", js) == [("icon-registry", 1), ("icon-registry", 2), ("icon-registry", 4), ("icon-registry", 6)]


def test_an_icon_takes_the_contracts_line_and_currentcolor(tmp_path):
    js = 'const a = hyIcon("plus", 15, 2.6), b = hyIcon("plus", 0, 0, "", { fill: true }), c = hyIcon("plus", 15, 2.4);\n'
    assert found(tmp_path, "w.js", js) == [("icon-stroke", 1)]
    html = '<svg data-ic="home" stroke="#ff0000"></svg>\n<svg data-ic="home" stroke="currentColor"></svg>\n'
    assert found(tmp_path, "c.html", html) == [("icon-color", 1)]


def test_a_colour_in_css_is_a_token(tmp_path):
    css = (":root { --ink: #fafafa; --sel: rgb(59 130 246); }\n"
           ".a { color: var(--ink); border-color: var(--line, #27272a); }\n"
           ".b { color: #fff; }\n"
           ".c { box-shadow: 0 4px 12px rgba(0,0,0,.3); }\n"
           ".d { -webkit-mask: linear-gradient(#000 0 0); mask-image: linear-gradient(#000, transparent); }\n"
           ".e { background: color-mix(in srgb, var(--sel) 20%, transparent); }\n")
    assert found(tmp_path, "k.css", css) == [("css-color", 3), ("css-color", 4)]
    js = "const st = `.x { background: #123456; } .y { --tok: #abcdef; }`;\n"
    assert found(tmp_path, "k.js", js) == [("css-color", 1)]


def test_the_registry_is_one_glyph_per_name_and_one_name_per_glyph():
    names, twice, path = V.registry_of(C)
    assert names and not twice, twice
    keys = {}
    for n, (g, ln, meant) in names.items():
        assert meant, f"{n} (line {ln}) has no meaning"
        k = V.glyph_key(g)
        assert k not in keys, f"{n} draws the same glyph as {keys.get(k)}"
        keys[k] = n
        for m in V.GLYPH_PAINT.finditer(g):
            assert m.group(2) in ("none", "currentColor"), f"{n}: {m.group(0)}"


def test_the_half_circle_is_only_the_opacity():
    """the owner's case: Adjustments (Raw Editor's layers) wore the opacity's half-filled circle; the half circle means opacity alone"""
    names = V.registry_of(C)[0]
    half = [n for n, (g, _, _) in names.items() if re.search(r'd="M12 [34](?:\.\d+)?a[89](?:\.\d+)? [89](?:\.\d+)? 0 0 1 0 1[68]z"', g)]
    assert half == ["opacity"], half
    assert "rawEditor" in names and "rawGrading" in names


def test_the_registry_and_the_repositories_pass(tmp_path):
    """the four repositories have no icon of their own left and ask only for names the registry has"""
    items, _ = V.run([], C)
    bad = [i for i in items if i["rule"] in ("icon-inline", "icon-registry", "icon-color")]
    assert not bad, "\n".join(f"{i['file']}:{i['line']} {i['rule']} {i['msg'][:80]}" for i in bad[:20])
