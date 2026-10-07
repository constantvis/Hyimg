"""«Свет и материалы» for agents (owner 2026-10-07: «было бы шикарно, если можно как-то свет тестировать и материалы»): hy.py do variant3d
keeps a Blender studio scene's named variants of light and material overrides in scene.json (variants) and has a card show one
(item.variant) or compare two (item.compare). The 3D plugin's studio and its Blender bridge read the same fields (hyimg-3d-studio
variants.js, variants.py)."""
import json

import pytest

from test_agent_tools import hyimg   # noqa: F401  (the fixture: a temporary library and server, hy(...) runs hy.py)

CAM = {"lens": 50, "sensor": 36, "sensor_h": 24, "fit": "AUTO", "shift": [0, 0], "clip": [0.01, 100]}


def test_variant3d_new_set_apply_compare_list_delete(hyimg):
    port, hy, board, state = hyimg
    lib = state.parent
    scene = lib / "3d/scenes/s/scene.json"; scene.parent.mkdir(parents=True)
    doc = {"format": "hyimg-scene/1", "rev": 3, "objects": [], "lights": [], "cameras": [dict(CAM, id="c1", name="01 · v01", loc=[0.1, -0.5, 0.2], rot=[1, 0, 0, 0])],
           "active_camera": "c1", "studio": {"folder": "/nowhere", "angles": {"c1": {"source": "renderings/x.json", "view": "v01", "look": "M07"}}}}
    scene.write_text(json.dumps(doc))
    hy("do", "cards3d 3d/scenes/s/scene.json x=0 y=3000")
    card = next(k for k, it in board()["items"].items() if it.get("type") == "model3d")

    out = hy("do", "variant3d 3d/scenes/s/scene.json new 'M26 · свет ракурса' light=angle")
    d = json.loads(scene.read_text()); v = d["variants"][0]
    assert v["name"] == "M26 · свет ракурса" and v["light"] == "angle" and v["id"].startswith("v") and d["rev"] == 4, out

    hy("do", "variant3d 3d/scenes/s/scene.json new 'M26 · металл темнее' from='M26 · свет ракурса' env=0.8")
    hy("do", "variant3d 3d/scenes/s/scene.json set 'M26 · металл темнее' mat='Phone | anodized aluminum' metallic=1 roughness=x0.8 tint=808080 color='#a0b0c0' light=studio")
    w = json.loads(scene.read_text())["variants"][1]
    assert w["light"] == "studio" and w["env"] == 0.8 and w["id"] != v["id"]
    assert w["materials"] == {"Phone | anodized aluminum": {"metallic": 1.0, "roughness": {"mul": 0.8}, "base_color": [0.3515, 0.4342, 0.5271]}}, w
    hy("do", "variant3d 3d/scenes/s/scene.json set 'M26 · металл темнее' mat='Phone | anodized aluminum' roughness=-")
    assert "roughness" not in json.loads(scene.read_text())["variants"][1]["materials"]["Phone | anodized aluminum"]

    hy("do", f"variant3d {card} apply 'M26 · металл темнее'; variant3d {card} compare 'M26 · свет ракурса'")
    it = board()["items"][card]
    assert it["variant"] == w["id"] and it["compare"] == v["id"]
    listed = hy("do", f"variant3d {card} list")
    assert "M26 · свет ракурса" in listed and f"карточки {card}" in listed and "окружение ×0.8" in listed, listed

    hy("do", f"variant3d {card} compare off; variant3d {card} apply base")
    it = board()["items"][card]
    assert "variant" not in it and "compare" not in it

    hy("do", f"variant3d {card} apply 'M26 · свет ракурса'")
    hy("do", "variant3d 3d/scenes/s/scene.json delete 'M26 · свет ракурса'")
    assert [x["name"] for x in json.loads(scene.read_text())["variants"]] == ["M26 · металл темнее"]
    assert "variant" not in board()["items"][card], "a card of a deleted variant shows the look as it is"

    with pytest.raises(Exception):
        hy("do", "variant3d 3d/scenes/s/scene.json set 'нет такого' light=own")
