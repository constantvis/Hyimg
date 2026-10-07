"""scripts/validate.py «capsule-pad» (owner 2026-10-06: «Presets ⌄» flush against its capsule, «посмотри, где еще вот такие проблемы
есть, где нет пэддинга по сторонам»): a pill control with words closer than the contract to its round ends fails, and so does a panel's
reset `.panel button { padding: 0 }` that outweighs the panel's own `.panel-btn { padding: … }` (one class against a class and a type:
the bug behind «Presets ⌄»). An icon button (a set width), a plate of buttons, a reset under :where() and a roomy pill pass."""
import importlib.util, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hyvalidate_cap", ROOT / "scripts/validate.py")
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
C = json.loads((ROOT / "design/contract.json").read_text(encoding="utf-8"))


def caps(tmp_path, name, text):
    p = tmp_path / name; p.write_text(text, encoding="utf-8")
    items, _ = V.run([str(p)], C)
    return sorted(i["line"] for i in items if i["rule"] == "capsule-pad")


def test_a_pill_with_words_at_its_ends_fails(tmp_path):
    css = (".a-btn { height: 28px; padding: 0 2px; border-radius: 999px; }\n"          # words 2 px from the round end
           ".b-chip { height: 18px; padding: 0 4px; border-radius: 999px; }\n"          # a small chip: 6 px at least
           ".c-btn { height: 28px; padding: 0 10px; border-radius: 999px; }\n"          # roomy: passes
           ".d-btn { width: 28px; height: 28px; padding: 0; border-radius: 50%; }\n"    # an icon button: passes
           ".bar { height: 38px; padding: 4px; border-radius: 999px; }\n"               # a plate of buttons: measured by its buttons
           ".e-sel { height: 28px; padding: 0 9px 0 12px; border-radius: var(--hy-row-r); }\n")
    assert caps(tmp_path, "p.css", css) == [1, 2]


def test_a_reset_that_outweighs_a_buttons_padding_fails_and_where_passes(tmp_path):
    bad = ".hcg button { font: inherit; border: 0; padding: 0; margin: 0; }\n.hcg-pbtn { height: 28px; padding: 0 8px 0 10px; border-radius: 8px; }\n"
    assert caps(tmp_path, "r.css", bad) == [1]
    good = ":where(.hcg) button { font: inherit; border: 0; padding: 0; margin: 0; }\n.hcg-pbtn { height: 28px; padding: 0 8px 0 10px; border-radius: 8px; }\n"
    assert caps(tmp_path, "w.css", good) == []
    # the same in a JS template (a plugin's injected styles), as colorgrade.js had it
    js = "const CSS = `\n.hcg button{padding:0;margin:0}\n.hcg-pbtn{height:28px;padding:0 8px 0 10px}\n`;\n"
    assert caps(tmp_path, "s.js", js) == [2]


def test_the_repositories_have_no_new_capsule_pad():
    items, files = V.run([str(ROOT.parent / r) for r in ("hyimg", "hyimg-frames", "hyimg-3d-studio") if (ROOT.parent / r).is_dir()], C)
    bad = [f"{i['file']}:{i['line']} {i['msg']}" for i in items if i["rule"] == "capsule-pad"]
    assert not bad, "\n".join(bad)
