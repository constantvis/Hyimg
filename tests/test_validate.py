"""The static validator (scripts/validate.py) finds what it is for and stays quiet on what is fine: one small file per rule, written
here, never the repositories' own files. Fast (well under a second besides node), runs in check.sh --fast."""
import importlib.util, json, shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hyvalidate", ROOT / "scripts/validate.py")
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
C = json.loads((ROOT / "design/contract.json").read_text(encoding="utf-8"))


# the icon and colour rules find something in almost any snippet (an svg, a colour); a test sees them only when it asks (icons_of below);
# hy-primitive (a hand-built control) has its own tests, tests/unit/test_validate_prim.py
APART = {"icon-inline", "icon-registry", "icon-color", "css-color", "hy-primitive"}


def rules_of(tmp_path, name, text, apart=APART):
    p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")
    items, _ = V.run([str(p)], C)
    return sorted(((i["rule"], i["line"]) for i in items if i["rule"] not in apart), key=lambda r: (r[1], r[0] != "cyrillic-code", r[0]))


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="no node")


def test_scanner_tells_code_from_text_comments_and_regexes():
    s = 'const a = "x // y", b = /\\/\\/[a-z]/g; // tail\nconst t = `css ${ok ? `in ${n}` : ""} // not a comment`; /* block */ x = 4 / 2 / 1;'
    kinds = [(t.kind, s[t.a:t.b]) for t in V.scan_js(s)]
    assert ("str", '"x // y"') in kinds and ("regex", "/\\/\\/[a-z]/g") in kinds and ("line", "// tail") in kinds and ("block", "/* block */") in kinds
    tpl = [k for k in kinds if k[0] == "tpl"]
    assert len(tpl) == 2 and tpl[-1][1].startswith("`css") and tpl[-1][1].endswith("comment`")
    assert not any(k == "regex" and "2" in v for k, v in kinds), "a division is not a regex"


@needs_node
def test_js_syntax_in_files_and_inline_scripts_keeps_the_line(tmp_path):
    assert rules_of(tmp_path, "a.js", "const a = 1;\nconst b = ;\nconst c = 2;\n") == [("js-syntax", 2)]
    html = "<!doctype html>\n<p>x</p>\n<script>\nconst ok = 1;\nconst no = );\n</script>\n"
    assert rules_of(tmp_path, "p.html", html) == [("js-syntax", 5)]
    assert rules_of(tmp_path, "m.html", '<script type="module">import x from "./x.js"; export const y = x;</script>') == []
    assert rules_of(tmp_path, "j.html", '<script type="application/json">{"a": </script>') == []


def test_a_comment_that_swallowed_code_is_found_and_prose_is_not(tmp_path):
    bad = "function f() { a(); }\nf(); // run it first   g(); h();\nconst x = 1;   // keep ${x} here\n"
    got = rules_of(tmp_path, "s.js", bad)
    assert ("comment-swallow", 2) in got and ("comment-swallow", 3) in got
    prose = ("let HOME = { folders: [] };   // folders of projects (home.json through the app); the folder being named\n"
             "if (x) {   // a title or a note: the corner scales the font (a note its width too); the opposite corner stays\n}\n"
             "// hyMenuItem('data-act=\"group\"', \"group\", \"Group\", [\"⌘\", \"G\"]);\n")
    assert [r for r in rules_of(tmp_path, "p.js", prose) if r[0] == "comment-swallow"] == []
    # CSS in a template: a `//` there eats the next declaration; a URL and GLSL are fine
    css = 'const st = `.a { color: red; } // note\n.b { top: 0; }`;\nconst u = `<a href="https://x.y/z">x</a>`;\nconst g = `uniform float u; // ok in GLSL\nvoid main() {}`;\n'
    assert [r for r in rules_of(tmp_path, "c.js", css) if r[0] == "comment-swallow"] == [("comment-swallow", 1)]
    assert rules_of(tmp_path, "c.css", ".a { color: red; } // gone\n.b { background: url(//x.y/i.png); }\n") == [("comment-swallow", 1)]


def test_easing_focus_range_radius_z_and_fonts(tmp_path):
    css = (".a { transition: transform .3s cubic-bezier(.32, .72, 0, 1), opacity .2s ease; }\n"
           ".b { transition: left .3s ease-in-out; }\n"
           ".c:focus-visible { outline: 2px solid blue; }\n"
           ".d:focus { outline: none; box-shadow: none; }\n"
           ".panel select { border-radius: 9px; }\n"
           ".panel select.ok { border-radius: var(--hy-row-r); }\n"
           ":root[data-shape=pro] .panel select { border-radius: 8px; }\n"
           ".hy-slider.sm::before { border-radius: 999px; }\n"
           ".e { z-index: 31; }\n.f { z-index: 500; }\n"
           ".g { font-family: \"Geist\", -apple-system, sans-serif; }\n.h { font-family: Comic Sans MS, sans-serif; }\n")
    got = rules_of(tmp_path, "x.css", css)
    assert got == [("easing", 2), ("focus-ring", 3), ("row-radius", 5), ("z-layer", 10), ("font-family", 12)], got
    html = ('<div class="hy-slider"><input type="range" min="0" max="1"></div>\n<label>Size <input type=range min=1 max=9></label>\n'
            '<svg viewBox="0 0 24 24" stroke-width="1.85"><path d="M0 0"/></svg>\n<svg viewBox="0 0 24 24" stroke-width="3.3"><path d="M0 0"/></svg>\n'
            '<svg viewBox="0 0 400 300" stroke-width="52"><path d="M0 0"/></svg>\n')
    assert rules_of(tmp_path, "r.html", html) == [("range-input", 2), ("icon-stroke", 4)]


def test_russian_words_live_in_the_lang_files_in_the_owners_style(tmp_path):
    code = 'const a = T("Show in Finder");\nconst b = "Показать";\nconst k = { "я": "z" };\n// комментарий по-русски\n'
    assert rules_of(tmp_path, "ui/c.js", code) == [("cyrillic-code", 2)]
    assert rules_of(tmp_path, "p.html", "<p>Hello</p>\n<!-- заметка -->\n<p>Привет — мир</p>\n") == [("cyrillic-code", 3), ("ru-style", 3)]
    lang = 'hyLang({ ru: {\n  "Save": "Сохранить",\n  "Saved.": "Сохранено.",\n  "Hide interface · ⌘.": "Скрыть интерфейс · ⌘.",\n  "{n} cams": "{n} кам.",\n  "Done": "Ещё — нет",\n} });\n'
    got = rules_of(tmp_path, "ui/lang-x.js", lang)
    assert got == [("lang-period", 3), ("lang-period", 3), ("ru-style", 6), ("ru-style", 6)], got


def test_one_line_is_let_through_with_its_reason(tmp_path):
    css = ".f { z-index: 500; }   /* hy-allow: z-layer above the native overlay */\n/* hy-allow: easing the spring of the old look */\n.b { transition: left .3s ease-in-out; }\n"
    assert rules_of(tmp_path, "y.css", css) == []
    assert rules_of(tmp_path, "y2.css", ".f { z-index: 500; }   /* hy-allow: easing wrong rule named */\n") == [("z-layer", 1)]


def test_the_baseline_is_a_ratchet(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "BASELINE", tmp_path / "baseline.json")
    p = tmp_path / "z.css"; p.write_text(".a { z-index: 500; }\n.b { z-index: 600; }\n")
    items, files = V.run([str(p)], C)
    V.write_baseline(items)
    items, files = V.run([str(p)], C)
    new, known, fixed = V.compare(items, files)
    assert new == [] and known["z-layer"] == 2 and fixed["z-layer"] == 0
    p.write_text("\n\n.b { z-index: 600; }\n.c { z-index: 700; }\n")   # one fixed, one moved two lines down, one new
    items, files = V.run([str(p)], C)
    new, known, fixed = V.compare(items, files)
    assert [(i["rule"], i["line"]) for i in new] == [("z-layer", 4)] and fixed["z-layer"] == 1


def test_panel_prose_is_a_footnote_or_a_tooltip(tmp_path):
    """owner 2026-10-06, the 3D studio's Scene panel in white body text: «Вот эти комментарии никто не читает ... микро шрифтом»"""
    long = "Dragging in the frame turns the camera of the card, the right button pans, the scroll wheel zooms and more"
    html = (f'<div class="empty">{long}</div>\n'                                   # body text: fails
            f'<p class="hy-hint">{long}</p>\n'                                     # a footnote of 20 words: two short lines, fine
            '<div class="hy-hint">' + " ".join(["word"] * 25) + '</div>\n'         # a footnote of 25: too long
            '<div>Short text</div>\n'
            f'<div title="{long}">x</div>\n'                                       # a tooltip is where a long text may live
            '<div>Crop: <kbd>X</kbd> turn the ratio <kbd>↵</kbd> apply <kbd>Esc</kbd> cancel <kbd>R</kbd> the whole frame, the keys are no words</div>\n'
            f'<div class="agentnote">{long}</div>\n')                              # the hidden note for an AI agent
    assert rules_of(tmp_path, "p.html", html) == [("panel-prose", 1), ("panel-prose", 3)]
    js = ('const a = `<div class="empty">${esc(t("' + long + '"))}</div>`;\n'      # a template's T("…") hole is read as its key
          'const b = `<p class="hy-hint">${t("' + long + '")}</p>`;\n'
          "const T = { note: '" + long + "' };\n"
          "const c = div('note', T.note);\n"                                      # a frame editor's table: T.note is its text
          'const d = el("div", "ifoot", T("' + long + '"));\n'
          'const e = `<!doctype html><p>${t("' + long + '")}</p>`;\n'             # a whole document is a file the app writes, not its interface
          'const f = `<div>${esc(n.text)} ${n.who}</div>`;\n')                    # the person's own words are one unknown word each
    assert [r for r in rules_of(tmp_path, "c.js", js) if r[0] == "panel-prose"] == [("panel-prose", 1), ("panel-prose", 4), ("panel-prose", 5)]
    allowed = '<div>' + long + '</div><!-- hy-allow: panel-prose a warning before files move: every word is key -->\n'
    assert rules_of(tmp_path, "w.html", allowed) == []


def test_the_top_rows_plates_take_the_rows_look(tmp_path):
    """row-plate (owner 2026-10-07: «breadcrumb area тоже разношерстная»): the group's and the 3D scene's title after the crumb had a look of
    their own, 26 px tall with a shadow and a ground of their own; a title plate is made with .hy-plate and sets none of its look"""
    old = ("<style>\n#gsticky .gst { position: absolute; padding: 4px 10px; box-shadow: 0 4px 14px rgba(0,0,0,.25); }\n"
           "#bset { height: 36px; box-shadow: 0 2px 4px #000; }\n</style>\n"
           "<script>\nconst b = document.createElement('div'); b.className = \"gst\";\nconst t = `<div class=\"m3title\" data-hyui></div>`;\n</script>\n")
    assert rules_of(tmp_path, "old.html", old) == [("row-plate", 2), ("row-plate", 3), ("row-plate", 3), ("row-plate", 6), ("row-plate", 7)]
    new = ("<style>\n#gsticky .gst { position: absolute; top: 0; display: block; }\n#gsticky .gst.sel { color: var(--sel); }\n"
           "#bset { height: 38px; box-shadow: var(--plate-sh); backdrop-filter: blur(14px); background: color-mix(in srgb, var(--panel) 82%, transparent); }\n"
           ":root[data-shape=pro] #crumb { border-radius: 11px; }\n.m3title code { font: 400 12px ui-monospace, monospace; }\n</style>\n"
           "<script>\nconst b = document.createElement('div'); b.className = \"gst hy-plate\";\nconst t = `<div class=\"m3title hy-plate\" data-hyui></div>`;\n</script>\n")
    assert rules_of(tmp_path, "new.html", new) == []
