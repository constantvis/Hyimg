"""Owner 2026-10-04: an agent put 3D cards on the board and the bell said «На доске новое:» with nothing after it and no preview.
The notification counts 3D cards and headings too, and a 3D card's preview is its still, named as the 3D plugin names it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "review"))
import hy  # noqa: E402


def test_3d_cards_are_counted_and_shown(monkeypatch):
    sent = []
    monkeypatch.setattr(hy, "send_notification", lambda *a, **k: sent.append(a))
    before = {"items": {}, "groups": {}}
    card = {"type": "model3d", "scene": "3d/scenes/261004/scene.json", "camera": "cam2", "x": 0, "y": 0, "w": 420, "h": 525, "bg": None}
    after = {"items": {"c1": card, "c2": dict(card, x=500, camera="cam3"), "t1": {"type": "text", "text": "Ракурс 2", "x": 0, "y": -100, "w": 200, "h": 40, "fs": 32}},
             "groups": {}}
    monkeypatch.setattr(hy, "rect", lambda b, i: {k: b["items"][i][k] for k in ("x", "y", "w", "h")})
    hy.notify_added(before, after, "main", None, "правка ИИ")
    title, text, page, ids, previews, area = sent[0]
    assert title == "На доске новое: 2 3D-карточки, 1 заголовок", title
    # the same name canvas.js gives the still: fnv of JSON.stringify([camera, bg, ratio]) (checked against node: 33a984a5)
    assert previews[0].startswith("3d/scenes/261004/.posters/c1-") and previews[0].endswith(".jpg")
    assert hy.still_of(dict(card, camera="cam2"), "abc").endswith("abc-33a984a5.jpg")
    assert len(previews) == 2 and ids[:2] == ["c1", "c2"]
