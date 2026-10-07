"""The hy-primitive rule (scripts/validate_prim.py): a control that has a primitive in review/ui/hy is not built by hand again. One small file
per case, written here; the primitives' own files and the shared rules they took over are their home and never count."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("hyvalidate_prim", ROOT / "scripts/validate.py")
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
C = json.loads((ROOT / "design/contract.json").read_text(encoding="utf-8"))


def found(tmp_path, name, css):
    p = tmp_path / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(css, encoding="utf-8")
    items, _ = V.run([str(p)], C)
    return sorted(i["msg"].split("builds a ")[1].split(" ")[0] for i in items if i["rule"] == "hy-primitive")


def test_each_hand_built_control_names_its_primitive(tmp_path):
    css = "\n".join([
        ".bar kbd { height: 18px; min-width: 18px; background: var(--panel); }",
        ".ntog .sw { width: 34px; height: 22px; border-radius: 999px; background: var(--raise); }",
        ".frow .fck { width: 16px; height: 16px; border: 1.5px solid var(--line); border-radius: 5px; }",
        "#x input[type=checkbox] { accent-color: var(--sel); }",
        ".tidy .sw { width: 18px; height: 18px; border-radius: 50%; background: var(--c); }",
        ".nb { min-width: 18px; height: 18px; border-radius: 999px; background: var(--hy-red); font: 600 10px var(--sans); }",
        "#bset { width: 38px; height: 38px; border-radius: 50%; }",
        "#crumb { height: 38px; backdrop-filter: blur(14px); }",
        "#hist .htabs { display: flex; background: var(--raise); }",
        ".emptynote { font: 400 11px/1.35 var(--sans); color: var(--muted); }",
    ])
    assert found(tmp_path, "a.css", css) == sorted(["hy-kbd", "hy-switch", "hy-check", "hy-check", "hy-swatch", "hy-badge",
                                                    "hy-icon-button", "hy-plate", "hy-segmented", "hy-hint"])


def test_what_is_not_a_control_stays_quiet(tmp_path):
    css = "\n".join([
        ".card { width: 38px; height: 38px; border-radius: 12px; }",                     # a square card, not round
        ".tfbtn hy-badge { position: absolute; top: -5px; right: -5px; }",                # placing a primitive is fine
        ".seg { background: var(--raise); }",                                             # the shared choice track (look.css)
        ".big { font: 600 15px/1.2 var(--sans); color: var(--muted); }",                   # a title, not a footnote
        ".bar kbd:hover { color: var(--ink); }",                                          # a state of a known copy is not a second copy
    ])
    assert found(tmp_path, "b.css", css) == []


def test_the_primitives_home_never_counts(tmp_path):
    css = "kbd, hy-kbd { height: 20px; background: var(--raise); border: 1px solid var(--line); }\n"
    assert found(tmp_path, "review/ui/hy/kbd.css", css) == []
    assert found(tmp_path, "review/ui/other.css", css) == ["hy-kbd"]


def test_a_line_is_let_through_with_its_reason(tmp_path):
    css = "/* hy-allow: hy-primitive the Photoshop colour squares are a tool, not a swatch */\n.fg .sw { width: 17px; height: 17px; border-radius: 50%; }\n"
    assert found(tmp_path, "c.css", css) == []
