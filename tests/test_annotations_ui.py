"""Annotations and comments on the board (owner 2026-10-07: «рисовать и добавлять комменты, как в Figma ... тегать участников»).
A pen stroke drawn over a picture is anchored to it and moves with it; ⌘Z and ⇧⌘Z take it back and bring it again; the eraser; the
eye hides them all. A comment pinned to a picture with an @mention of Claude, a reply, resolve; the bell names another person's
comment that mentions you and his mention of your agent, never your own; hy.py lists the threads and answers in one; History has
every step. Chromium, dark theme, English and Russian, temporary folders. HY_SHOTS=<folder> keeps screenshots."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ME, OTHER = str(uuid.uuid4()), str(uuid.uuid4())


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def get(port, path):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10))


def wait(fn, what, t=10):
    end = time.time() + t
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(0.1)
    raise AssertionError(what)


def board(tmp_path, lang):
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    (tmp_path / "people.json").write_text(json.dumps({OTHER: {"name": "Bob", "color": "orange", "agents": {"codex": time.time() - 60}}}))
    servers = run_server(tmp_path); port = next(servers)
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps({"cv.theme": "dark", "cv.lang": lang}).encode(),
                                                  method="POST", headers={"Content-Type": "application/json"}), timeout=10).read()
    return servers, port


def open_board(p, port):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url); page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('i1') && window.hyAnnot && document.getElementById('bann') && window.hyPeople && hyPeople.me()",
                           timeout=20000)
    page.evaluate("() => { cam.x = -60; cam.y = -120; cam.z = 1; renderCam(); render(); }")
    return browser, page, errors


def box(page, sel):
    return page.evaluate(f"() => {{ const r = document.querySelector({json.dumps(sel)}).getBoundingClientRect(); return {{ x: r.x, y: r.y, w: r.width, h: r.height }}; }}")


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_draw_on_a_picture_it_moves_with_it_undo_eraser_and_the_eye(tmp_path, lang):
    servers, port = board(tmp_path, lang)
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, port)
            page.keyboard.press("p")   # Annotate, the pen
            page.wait_for_selector("#dock .ann-bar [data-tool=pen].on")
            r = box(page, '.it[data-id="i1"]')
            page.mouse.move(r["x"] + 40, r["y"] + 80); page.mouse.down()
            for i in range(16): page.mouse.move(r["x"] + 40 + i * 12, r["y"] + 80 + (i % 4) * 14)
            page.mouse.up()
            items = wait(lambda: get(port, "/api/annotations?name=main")["items"], "the stroke was not saved")
            a = items[0]
            assert a["kind"] == "pen" and a["anchor"]["obj"] == "i1" and a["by"] == {"person": ME, "via": "app"} and 0 < a["pts"][0][0] < 1
            assert not (tmp_path / "lib" / "a" / "1.png.json").exists()   # never written into the picture or its json
            shot(page, f"annot-{lang}-1-pen")
            # the picture moves: the stroke goes with it
            g0 = box(page, f'#annsvg g[data-a="{a["id"]}"]')
            page.evaluate("() => { board.items.i1.x += 300; board.items.i1.y += 40; render(); }")
            g1 = box(page, f'#annsvg g[data-a="{a["id"]}"]')
            assert abs(g1["x"] - g0["x"] - 300) < 1.5 and abs(g1["y"] - g0["y"] - 40) < 1.5, (g0, g1)
            page.evaluate("() => { board.items.i1.x -= 300; board.items.i1.y -= 40; render(); }")
            # ⌘Z takes the stroke back (one step), ⇧⌘Z brings it again
            page.keyboard.press("Meta+z")
            wait(lambda: not get(port, "/api/annotations?name=main")["items"], "undo did not remove the stroke")
            assert page.locator("#annsvg g").count() == 0
            page.keyboard.press("Meta+Shift+z")
            wait(lambda: get(port, "/api/annotations?name=main")["items"], "redo did not bring it back")
            assert not page.locator("#bundo").is_disabled()   # the dock's undo knows the step too
            page.evaluate("() => hyAnnot.exit()"); page.locator("#bundo").click()
            wait(lambda: not get(port, "/api/annotations?name=main")["items"], "the dock's undo did not take it back")
            page.locator("#bredo").click()
            wait(lambda: get(port, "/api/annotations?name=main")["items"], "the dock's redo did not bring it back")
            page.keyboard.press("p")
            # a rectangle on the empty canvas keeps board units
            page.keyboard.press("r")
            page.mouse.move(r["x"] + 60, r["y"] + 520); page.mouse.down(); page.mouse.move(r["x"] + 220, r["y"] + 600, steps=6); page.mouse.up()
            rect = wait(lambda: [x for x in get(port, "/api/annotations?name=main")["items"] if x["kind"] == "rect"], "no rectangle")[0]
            assert rect["anchor"] is None and rect["pts"][1][0] - rect["pts"][0][0] == pytest.approx(160, abs=2)
            # the eraser takes the pen stroke, one step
            page.keyboard.press("e")
            g = box(page, f'#annsvg g[data-a="{a["id"]}"]')
            page.mouse.move(g["x"] - 10, g["y"] + g["h"] / 2); page.mouse.down(); page.mouse.move(g["x"] + g["w"] + 10, g["y"] + g["h"] / 2, steps=12); page.mouse.up()
            wait(lambda: [x["kind"] for x in get(port, "/api/annotations?name=main")["items"]] == ["rect"], "the eraser did not take the stroke")
            # the eye hides them all, for this viewer
            page.locator("#dock .ann-bar [data-ann=eye]").click()
            assert page.locator("#annsvg").evaluate("s => getComputedStyle(s).display") == "none"
            page.locator("#dock .ann-bar [data-ann=eye]").click()
            assert page.locator("#annsvg g").count() == 1
            page.keyboard.press("Escape")
            assert page.locator("#dock .ann-bar").count() == 0 and page.locator("#annsvg g").count() == 1
            # History: each step an event, by this Mac's person in the app
            kinds = [e["kind"] for e in get(port, "/api/events?name=main")][::-1]
            assert kinds == ["annotate", "annotate-remove", "annotate", "annotate-remove", "annotate", "annotate", "annotate-remove"], kinds
            page.click("#bhist"); page.click('#hist [data-tab="ev"]')
            page.wait_for_selector("#evList .ev.kind-annotate .hy-by hy-avatar")
            shot(page, f"annot-{lang}-2-history")
            assert not errors, errors
            browser.close()
    finally:
        servers.close()


def write_thread(tmp_path, tid, by, text, mentions, at=(0.5, 0.5), obj="i3"):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    t = {"id": tid, "page": "main", "anchor": {"obj": obj, "kind": "picture", "file": f"a/{obj[1:]}.png"}, "at": list(at), "by": by, "created": now, "updated": now,
         "resolved": None, "objects": [obj], "messages": [{"id": "m" + tid[1:], "by": by, "text": text, "mentions": mentions, "created": now}]}
    d = tmp_path / "lib" / "comments"; d.mkdir(exist_ok=True)
    (d / f"main__{tid}.json").write_text(json.dumps(t))


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_comment_mentions_reply_resolve_bell_and_hy_py(tmp_path, lang):
    servers, port = board(tmp_path, lang)
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, port)
            r = box(page, '.it[data-id="i2"]')
            page.keyboard.press("Shift+C")   # a comment straight from the board
            page.mouse.click(r["x"] + 200, r["y"] + 90)
            page.wait_for_selector("#cmthread.open textarea")
            page.keyboard.type("@Cl")
            page.wait_for_selector("#cmat button")
            assert "Claude" in page.locator("#cmat button").first.inner_text()
            assert page.locator("#cmat button hy-avatar[agent=claude]").count() == 1
            shot(page, f"comment-{lang}-1-mention")
            page.keyboard.press("Enter"); page.keyboard.type("the sky darker"); page.keyboard.press("Enter")
            t = wait(lambda: get(port, "/api/comments?name=main")["items"], "the comment was not saved")[0]
            assert t["anchor"]["obj"] == "i2" and t["messages"][0]["mentions"] == [{"person": ME, "agent": "claude", "label": "Claude"}]
            page.keyboard.type("and @Bo"); page.wait_for_selector("#cmat button"); page.keyboard.press("Enter"); page.keyboard.type("too?"); page.keyboard.press("Enter")
            wait(lambda: len(get(port, "/api/comments?name=main")["items"][0]["messages"]) == 2, "no reply")
            page.wait_for_selector("#cmthread .cm-m >> nth=1")
            assert page.locator("#cmthread .cm-at").all_inner_texts() == ["@Claude", "@Bob"]
            shot(page, f"comment-{lang}-2-thread")
            # one's own comments never ring one's own bell
            assert not [n for n in get(port, "/api/notifications")["items"] if n["id"].startswith("c:")]
            # the pin moves with its picture
            pin0 = box(page, f'#cmpins [data-c="{t["id"]}"]')
            page.evaluate("() => { board.items.i2.y += 50; render(); }")
            pin1 = box(page, f'#cmpins [data-c="{t["id"]}"]')
            assert abs(pin1["y"] - pin0["y"] - 50) < 1.5
            page.evaluate("() => { board.items.i2.y -= 50; render(); }")
            # the agent answers from hy.py; the server sees who writes (here, no agent in the tree: the header says)
            env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")} | {"HYIMG_PORT": str(port), "HYIMG_AGENT": "Claude Code", "PYTHONDONTWRITEBYTECODE": "1"}
            out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "comments", "--open", "--mentions", "claude"], env=env, capture_output=True, text=True, timeout=60)
            assert out.returncode == 0 and t["id"] in out.stdout and "the sky darker" in out.stdout, out.stdout + out.stderr
            out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "comments", "reply", t["id"], "Done, the sky is a third darker"], env=env,
                                 capture_output=True, text=True, timeout=60)
            assert out.returncode == 0, out.stdout + out.stderr
            last = get(port, "/api/comments?name=main")["items"][0]["messages"][-1]
            assert last["by"] == {"person": ME, "via": "claude"}
            page.evaluate("() => hyComments.load()")
            page.wait_for_selector("#cmthread .cm-m hy-avatar[agent=claude]")
            out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "comments", "add", "i5", "A second crop here? @Ann Lee"], env=env, capture_output=True, text=True,
                                 timeout=60)
            assert out.returncode == 0, out.stdout + out.stderr
            new = next(x for x in get(port, "/api/comments?name=main")["items"] if x["anchor"] and x["anchor"]["obj"] == "i5")
            assert new["by"]["via"] == "claude" and new["messages"][0]["mentions"] == [{"person": ME, "label": "Ann Lee"}]
            # another person's comment that mentions you, and his mention of your Claude
            write_thread(tmp_path, "cbob00001", {"person": OTHER, "via": "app"}, "@Ann Lee have a look", [{"person": ME, "label": "Ann Lee"}])
            write_thread(tmp_path, "cbob00002", {"person": OTHER, "via": "codex"}, "@Claude can you crop it?", [{"person": ME, "agent": "claude", "label": "Claude"}],
                         obj="i4")
            ns = [n for n in get(port, "/api/notifications")["items"] if n["id"].startswith("c:")]
            titles = sorted(n["title"] for n in ns)
            assert any("Ann" in n["text"] for n in ns) and len([n for n in ns if n["thread"].startswith("cbob")]) == 2, ns
            assert {"person": OTHER, "via": "codex"} in [n["by"] for n in ns] and len(titles) >= 3   # Claude's reply too
            page.evaluate("() => pollNtf()")
            page.wait_for_selector("#bntf.dot")
            page.click("#bntf")
            page.wait_for_selector("#ntf.open .nt hy-avatar")
            shot(page, f"comment-{lang}-3-bell")
            page.locator('#ntf .nt[data-n^="c:cbob00002"]').click()
            page.wait_for_selector('#cmthread.open[data-c="cbob00002"]')
            assert page.locator("#cmthread .cm-m hy-avatar[agent=codex]").count() == 1
            # resolve: the pin goes, the list keeps it under Resolved
            page.evaluate(f"() => hyComments.open({json.dumps(t['id'])})")
            page.locator("#cmthread [data-cm=resolve] button").click()
            wait(lambda: next(x for x in get(port, "/api/comments?name=main")["items"] if x["id"] == t["id"])["resolved"], "not resolved")
            page.wait_for_function(f"() => !document.querySelector('#cmpins [data-c=\"{t['id']}\"]')")
            page.evaluate("() => hyComments.list()")
            page.locator('#cmlist [data-cf="done"]').click()
            assert page.locator(f'#cmlist [data-go="{t["id"]}"]').count() == 1
            shot(page, f"comment-{lang}-4-list")
            # ⌘Z: the resolve back
            page.keyboard.press("Escape"); page.mouse.click(700, 760)
            page.keyboard.press("Meta+z")
            wait(lambda: not next(x for x in get(port, "/api/comments?name=main")["items"] if x["id"] == t["id"])["resolved"], "undo did not reopen")
            kinds = [e["kind"] for e in get(port, "/api/events?name=main")][::-1]
            assert kinds[:6] == ["comment", "reply", "reply", "comment", "resolve", "reopen"], kinds
            page.click("#bhist"); page.click('#hist [data-tab="ev"]')
            page.wait_for_selector("#evList .ev.kind-comment .ecm")
            shot(page, f"comment-{lang}-5-history")
            assert not errors, errors
            browser.close()
    finally:
        servers.close()


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_comment_on_an_area_like_the_library_preview(tmp_path, lang):
    """the Comment tool (first in Annotate, its default): a drag draws an area on the picture and opens the box at once; the area is a thin
    outline in the author's colour with the pin at its top right corner, it moves with the picture, the list and hy.py say where it is"""
    servers, port = board(tmp_path, lang)
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = open_board(p, port)
            page.locator("#bann").click()
            page.wait_for_selector("#dock .ann-bar [data-tool=comment].on")
            assert page.locator("#dock .ann-bar > button.ic").first.get_attribute("data-tool") == "comment"
            assert page.evaluate("() => document.querySelector('#dock .ann-bar [data-tool=comment]').nextElementSibling.className") == "sep"
            r = box(page, '.it[data-id="i3"]')
            page.mouse.move(r["x"] + r["w"] * .5, r["y"] + r["h"] * .1); page.mouse.down()
            page.mouse.move(r["x"] + r["w"] * .9, r["y"] + r["h"] * .4, steps=8); page.mouse.up()
            page.wait_for_selector("#cmthread.open textarea")
            want = "Comment on area 1" if lang == "en" else "Комментарий к области 1"
            assert page.locator("#cmthread textarea").get_attribute("placeholder") == want
            page.keyboard.type("too bright here"); page.keyboard.press("Enter")
            t = wait(lambda: get(port, "/api/comments?name=main")["items"], "the area comment was not saved")[0]
            assert t["anchor"]["obj"] == "i3" and [round(v, 2) for v in t["area"]] == [.5, .1, .4, .3], t["area"]
            assert t["describe"].startswith("область вверху справа: x 50–90 %, y 10–40 %")
            area = page.locator(f'#cmpins .cmarea[data-a="{t["id"]}"]')
            ab, pb = area.bounding_box(), box(page, f'#cmpins [data-c="{t["id"]}"]')
            assert abs(ab["x"] - (r["x"] + r["w"] * .5)) < 2 and abs(pb["x"] - (ab["x"] + ab["width"])) < 2 and abs(pb["y"] + pb["h"] - ab["y"]) < 3
            assert area.evaluate("d => getComputedStyle(d).borderTopColor") == "rgb(127, 212, 155)"   # the author's green
            shot(page, f"area-{lang}-1-thread")
            page.evaluate("() => { board.items.i3.y += 30; render(); }")
            assert abs(area.bounding_box()["y"] - ab["y"] - 30) < 1.5
            page.keyboard.press("Escape")
            page.locator("#dock .ann-bar [data-ann=list]").click()
            row = page.locator(f'#cmlist [data-go="{t["id"]}"] .cm-ra')
            assert row.inner_text().endswith("x 50–90 %, y 10–40 %")
            row.hover(); assert "on" in area.get_attribute("class")
            shot(page, f"area-{lang}-2-list")
            env = {k: v for k, v in os.environ.items() if not k.startswith("HYIMG_")} | {"HYIMG_PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"}
            out = subprocess.run([sys.executable, str(ROOT / "review/hy.py"), "comments"], env=env, capture_output=True, text=True, timeout=60).stdout
            assert "область вверху справа: x 50–90 %, y 10–40 %" in out, out
            assert not errors, errors
            browser.close()
    finally:
        servers.close()
