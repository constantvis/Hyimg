"""A 3D card's view is the truth, scene.json's camera a copy (owner 2026-10-07: «чтобы board был source of truth, и от него мы плясали уже в
Blender»). hy.py: cards3d gives each card its own view; camera3d CARD restore makes the scene's camera of that id again from the card when
it was deleted from scene.json; camera3d CARD original puts the card back to the camera of the picture it came from
(studio.angles[id].camera0), without touching the scene; camera3d SCENE sync writes every card's view into its scene.
"""
import json

from test_agent_tools import hyimg   # noqa: F401  (the fixture: a temporary library and server, hy(...) runs hy.py)

CAM = {"lens": 50, "sensor": 36, "sensor_h": 24, "fit": "AUTO", "shift": [0, 0], "clip": [0.01, 100]}


def test_camera3d_restore_original_and_sync(hyimg):
    port, hy, board, state = hyimg
    lib = state.parent
    scene = lib / "3d/scenes/s/scene.json"; scene.parent.mkdir(parents=True)
    doc = {"format": "hyimg-scene/1", "rev": 3, "objects": [], "lights": [],
           "cameras": [dict(CAM, id="c1", name="01 · v01", loc=[0.1, -0.5, 0.2], rot=[1, 0, 0, 0]), dict(CAM, id="c2", name="02 · v02", loc=[0.3, -0.4, 0.1], rot=[1, 0, 0, 0])],
           "active_camera": "c1", "studio": {"folder": "/nowhere", "angles": {"c1": {"camera0": {"loc": [0.9, -0.9, 0.9], "rot": [0.5, 0.5, 0.5, 0.5], "lens": 185}}}}}
    scene.write_text(json.dumps(doc))
    hy("do", "cards3d 3d/scenes/s/scene.json x=0 y=3000")
    cards = {it["camera"]: (k, it) for k, it in board()["items"].items() if it.get("type") == "model3d"}
    assert set(cards) == {"c1", "c2"}
    assert cards["c2"][1]["view"]["loc"] == [0.3, -0.4, 0.1] and cards["c2"][1]["view"]["name"] == "02 · v02", "each card its own view"

    # the camera deleted from scene.json: the card makes it again
    d = json.loads(scene.read_text()); d["cameras"] = [c for c in d["cameras"] if c["id"] != "c2"]; scene.write_text(json.dumps(d))
    out = hy("do", f"camera3d {cards['c2'][0]} restore")
    d = json.loads(scene.read_text()); c2 = next(c for c in d["cameras"] if c["id"] == "c2")
    assert c2["loc"] == [0.3, -0.4, 0.1] and c2["name"] == "02 · v02" and d["rev"] == 4, (out, c2)
    assert "теперь как на карточке" in out
    assert "уже как на карточке" in hy("do", f"camera3d {cards['c2'][0]} restore")   # nothing to write
    assert json.loads(scene.read_text())["rev"] == 4

    # the picture's camera back on the card; the scene is not touched by it
    raw = scene.read_text()
    hy("do", f"camera3d {cards['c1'][0]} original")
    v = board()["items"][cards["c1"][0]]["view"]
    assert v["loc"] == [0.9, -0.9, 0.9] and v["lens"] == 185 and v["name"] == "01 · v01", v
    assert scene.read_text() == raw

    # the scene follows its cards when asked
    hy("do", "camera3d 3d/scenes/s/scene.json sync")
    c1 = next(c for c in json.loads(scene.read_text())["cameras"] if c["id"] == "c1")
    assert c1["loc"] == [0.9, -0.9, 0.9] and c1["lens"] == 185, c1
