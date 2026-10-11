"""pattern table and the column cap through hy.py on a running server (owner 2026-10-11 on «Workflows» › «Batch 2 · макеты для генерации»:
«Я ожидаю, что тут может быть табличная расстановка, чтобы related объекты можно было сравнивать ... чтобы были в одном column. Также
можно убрать ограничение ... если у нас из-за этого всё переносится на другую строку»). Two series laid out as an agent had them (rows of
7 that wrap, v1 and v2 of a step in different rows, a card left under the block) become one table: a row per series with its note, a
column per step, ten columns (no cap of 8), the variants of a step stacked in its cell, the ids kept, the old grids gone, the frame
grown; --dry changes nothing; a second run lays out the same. block keeps a row per argument on one row however long."""
import json
import urllib.request

from test_agent_tools import hyimg, png  # noqa: F401  (the fixture: a library with old/ and new/, a group «Старые»)

COLS = ("Оригинал=^added/;Поза=pose;Рендер=render;SAM=sam;Стереть=erase;Чистый фон=clean|lama;Макет=mockup;Маска макета=mockup.*mask;"
        "Кропы=crops;Фото-рендер=photoreal")
S1 = ["added/s1.png", "wf/S1/S1-02-pose.png", "wf/S1/S1-03-render.png", "wf/S1/S1-03-sam.png", "wf/S1/S1-03b-erase-mask.png",
      "wf/S1/S1-04-clean.png", "wf/S1/S1-05-mockup.png", "wf/S1/S1-05-mockup-mask.png", "wf/S1/S1-06-crops.png",
      "wf/S1/S1-07a-photoreal.png", "wf/S1/S1-04a-clean-lama.png", "wf/S1/S1-06-crops-v2.png"]
S2 = ["added/s2.png", "wf/S2/S2-02-pose.png", "wf/S2/S2-04-clean.png", "wf/S2/S2-05-mockup.png", "wf/S2/S2-06-crops.png",
      "wf/S2/S2-06-crops-v2.png", "wf/S2/S2-05-mockup-v2.png"]


def post(port, page, b):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/board?name={page}", data=json.dumps(b).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req).status


def messy(port, board, state):
    """the page as the agent left it: a note per series, its cards 7 a row wrapping, the series' grids, one card under the block"""
    lib = state.parent
    for k, p in enumerate(S1 + S2):
        (lib / p).parent.mkdir(parents=True, exist_ok=True); (lib / p).write_bytes(png(c=(10 + k * 9, 200 - k * 7, 60)))
    b = board(); I, ids = b["items"], {}
    for s, (paths, y0) in enumerate(((S1, 2000), (S2, 3600))):
        n = f"n{s + 1}"; I[n] = {"type": "note", "text": f"# S{s + 1} · серия", "x": 0, "y": y0, "w": 320, "fs": 17.8, "size": 2, "h": 0,
                                  "color": "blue", "to": [], "reach": {"l": 160, "t": 160, "r": 7 * 344 + 48 - 24 + 160, "b": 2 * 344 + 160}}
        for k, p in enumerate(paths):
            i = f"c{s + 1}_{k}"; ids[p] = i
            I[i] = {"path": p, "x": 368 + (k % 7) * 344, "y": y0 + (k // 7) * 344, "w": 320, "ar": 1}
    I[ids["wf/S1/S1-06-crops-v2.png"]]["y"] = 2000 + 3 * 344 + 200   # left under its block, out of the note's zone
    b["grids"] = {"gra": {"members": [ids[p] for p in S1[:7]], "cols": 7, "rows": 1, "gap": 24, "cell": "fit"},
                  "grb": {"members": [ids[p] for p in S2[:7]], "cols": 7, "rows": 1, "gap": 24, "cell": "fit"}}
    b["groups"]["gs"] = {"title": "Серии", "x": -480, "y": 1520, "w": 368 + 7 * 344 + 480, "h": 3600 - 1520 + 1200,
                         "members": ["n1", "n2", *ids.values()]}
    assert post(port, "main", b) == 200
    return ids


def test_table_by_series_and_steps_keeps_ids_stacks_variants_and_has_no_column_cap(hyimg):
    port, hy, board, state = hyimg
    ids = messy(port, board, state)
    was = board(); rev = was["revision"]
    out = hy("do", f'pattern table gs rows=note cols="{COLS}"', "--dry")
    assert "pattern table: 2 рядов × 10 колонок, 19 кадров" in out and "проба" in out, out
    assert board()["revision"] == rev and board()["items"] == was["items"]   # a dry run saves nothing

    out = hy("do", f'pattern table gs rows=note cols="{COLS}"', "--quiet")
    assert "pattern table: 2 рядов × 10 колонок" in out and "версии" in out, out
    b = board(); I = b["items"]; G = b["groups"]["gs"]
    assert set(ids.values()) | {"n1", "n2"} <= set(I) and set(ids.values()) | {"n1", "n2"} <= set(G["members"])   # ids and group kept
    heads = sorted((it["x"], it["text"]) for it in I.values() if it.get("pattern_col"))
    assert [t for _x, t in heads] == ["Оригинал", "Поза", "Рендер", "SAM", "Стереть", "Чистый фон", "Макет", "Маска макета", "Кропы",
                                      "Фото-рендер"]   # ten columns in the given order: no wrap at 8
    xs = [x for x, _t in heads]; assert len({b - a for a, b in zip(xs, xs[1:])}) == 1   # one width, one gap
    col = {t: x for x, t in heads}
    c = lambda p: I[ids[p]]
    for s in ("S1", "S2"):   # v1 and v2 of the crops share their column, v2 stacked under v1
        v1, v2 = c(f"wf/{s}/{s}-06-crops.png"), c(f"wf/{s}/{s}-06-crops-v2.png")
        assert v1["x"] == v2["x"] == col["Кропы"] and abs(v2["y"] - (v1["y"] + 320 + 24)) < 1, (v1, v2)
    assert c("wf/S1/S1-04a-clean-lama.png")["x"] == c("wf/S2/S2-04-clean.png")["x"] == col["Чистый фон"]
    assert c("wf/S2/S2-05-mockup-v2.png")["x"] == col["Макет"] and c("wf/S1/S1-05-mockup-mask.png")["x"] == col["Маска макета"]
    assert c("added/s1.png")["y"] == I["n1"]["y"] and c("added/s2.png")["y"] == I["n2"]["y"] > c("wf/S1/S1-06-crops-v2.png")["y"]
    assert I["n1"]["x"] == I["n2"]["x"] == 0 and I["n1"]["type"] == "note" and I["n1"]["text"] == "# S1 · серия"   # the notes moved, kept
    assert not b.get("grids")   # the series' old grids are gone: a grid has no stacks
    assert G["x"] + G["w"] > col["Фото-рендер"] + 320 and G["w"] > 368 + 7 * 344 + 480   # the frame grew to hold ten columns
    chk = hy("check", "--pattern"); assert "✓ table «Оригинал»" in chk and "10 колонок, 19 кадров" in chk and "⚠" not in chk, chk
    assert "проблем не нашел" in hy("check"), hy("check")

    out = hy("do", "pattern table gs", "--quiet")   # again (a batch goes on): the same keys, the same places, no new headings
    b2 = board()
    assert {k: (it["x"], it["y"]) for k, it in b2["items"].items()} == {k: (it["x"], it["y"]) for k, it in I.items()}, out


def test_block_keeps_each_argument_on_one_row(hyimg):
    port, hy, board, state = hyimg
    lib = state.parent
    for d, k0 in (("ra", 0), ("rb", 50)):
        (lib / d).mkdir()
        for n in range(11): (lib / d / f"{n}.png").write_bytes(png(c=(k0 + n * 4, 90, 200 - n * 5)))
    out = hy("do", 'block "ra/*" "rb/*" x=0 y=4000', "--quiet")   # two series: a row each, eleven long, not 8 + 3
    b = board(); I = b["items"]
    ys = lambda d: {it["y"] for it in I.values() if (it.get("path") or "").startswith(d + "/")}
    assert len(ys("ra")) == 1 and len(ys("rb")) == 1 and ys("ra") != ys("rb"), out
    assert "больше 8" not in out and "шире 8" not in out, out   # a single row of related things is no wide pile
    hy("do", 'remove "ra/*"; remove "rb/*"', "--quiet")
    out = hy("do", 'block "ra/*" x=0 y=4000 cols=all', "--quiet")   # one argument, cols=all: no wrap either
    assert len(ys_now(board, "ra")) == 1, out
    hy("do", 'remove "ra/*"', "--quiet")
    hy("do", 'block "rb/*" x=0 y=4000', "--quiet")   # a pile still wraps at 8
    assert len(ys_now(board, "rb")) == 2


def ys_now(board, d):
    return {it["y"] for it in board()["items"].values() if (it.get("path") or "").startswith(d + "/")}
