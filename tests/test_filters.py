"""The library's filter bar (owner 2026-10-06: «one block with a filter where some default filters already are, and they can be pinned in
the filter itself; many of these things should not be pre-programmed but gathered from what is in the json files, so each new project
can have its own set of tags»). One capsule in the dock (the filter button, the project's pinned filters, the active ones that are not
pinned) and a window built from the project's own data, with a pin on every filter. Run in Chromium and in WebKit on disposable libraries."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from test_canvas_pages import png

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
BASE = ["", "none", "take", "idea", "no", "fav", "ask"]   # what a new project pins


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(tmp_path, scores=True, model=False, rules=True, rejected=False):
    """a library of two collections: a/ (4 frames), b/ (2), a Photoshop file; a project of its own with a tag rule «Birds»"""
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (lib / "b").mkdir(); (state / "boards").mkdir(parents=True)
    frames = {   # path: (sidecar)
        "a/0": {"prompt": "a heron over a bridge", "model": "gpt-image", "feedback": {"verdict": "take", "fav": True, "scores": {"real": 3, "case": 3, "idea": 2}, "updated": "2099-01-01 00:00"}},
        "a/1": {"prompt": "a viaduct at night", "model": "gpt-image", "feedback": {"verdict": "idea", "scores": {"real": 1}, "updated": "2099-01-01 00:00"}},
        "a/2": {"prompt": "a bird on a wire", "model": "midjourney", "feedback": {"verdict": "no", "updated": "2099-01-01 00:00"}},
        "a/3": {"prompt": "something plain", "model": "midjourney"},
        "b/0": {"prompt": "a wolf in snow", "model": "gpt-image", "feedback": {"verdict": "take", "fav": True, "updated": "2099-01-01 00:00"}},
        "b/1": {"prompt": "an empty room", "model": "gpt-image"},
    }
    for n, (rel, side) in enumerate(frames.items()):
        (lib / (rel + ".png")).write_bytes(png(40 + n, 60))   # different pictures: the library folds identical ones
        if not scores:
            side = dict(side, feedback={k: v for k, v in side.get("feedback", {}).items() if k != "scores"})
        (lib / (rel + ".json")).write_text(json.dumps(side))
    (lib / "b/design.psd").write_bytes(b"8BPS" + b"x" * 60)   # a file of another kind
    if model:
        (lib / "b/part.glb").write_bytes(b"glTF" + b"\0" * 40)
    if rejected:
        (lib / "_rejected").mkdir()
        for n in range(2): (lib / f"_rejected/r{n}.png").write_bytes(png(90 + n, 60))
    pid = str(uuid.uuid4())
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps({pid: {"tags": [["Theme", "Birds", r"heron|\bbirds?\b"]]}} if rules else {}))
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": {}, "groups": {}, "removed": {}}))
    (tmp_path / "settings.json").write_text("{}")
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=pid, HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               HYIMG_LIBRARY_RULES=str(rules_file), HYIMG_PLUGINS=str(tmp_path / "no-plugins"), PYTHONDONTWRITEBYTECODE="1")
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    return port, process, log, state, rules_file, pid


@pytest.fixture(params=["chromium", "webkit"])
def engine(request):
    with playwright.sync_playwright() as p:
        try:
            b = getattr(p, request.param).launch()
        except Exception as error:
            pytest.skip(f"no {request.param} for Playwright: {error}")
        yield b
        b.close()


def open_lib(browser, port):
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/?view=lib")
    page.wait_for_selector("#list .card"); page.wait_for_selector("#vfChips button")
    return page, errors


def capsule(page):
    return page.evaluate("() => [...document.querySelectorAll('#vfChips button')].map(b => b.dataset.f)")


def names(page):
    return sorted(page.evaluate("() => [...document.querySelectorAll('#list .card')].map(c => c.getAttribute('aria-label'))"))


def open_window(page):
    if page.evaluate("() => document.querySelector('#tfPanel').hidden"):
        page.click("#tfBtn")
    page.wait_for_selector("#tfPanel:not([hidden]) .fchip")


def fi(page, id_):
    return page.locator(f'#tfGroups .fchip[data-id="{id_}"]')


def count(page, id_):
    return int(fi(page, id_).locator(".fl i").text_content().replace(",", ""))


def stop(process, log):
    process.terminate(); process.wait(5); log.close()


def test_capsule_defaults_and_the_window_from_the_data(tmp_path, engine):
    port, process, log, state, _, _ = start(tmp_path)
    try:
        page, errors = open_lib(engine, port)
        # scores.real and scores.case are in the frames: Metal and Exact are pinned by default, no 3D files: no 3D
        assert capsule(page) == BASE + ["score:real:3", "score:case:3"]
        assert page.evaluate("() => document.querySelector('#vfChips [data-f=\"score:real:3\"]').textContent") == "Metal"
        assert page.evaluate("() => document.querySelector('#vfChips [data-f=\"score:case:3\"]').textContent") == "Exact"
        assert page.evaluate("() => document.querySelector('#tfN').hidden")   # nothing active: no number on the button
        open_window(page)
        titles = page.evaluate("() => [...document.querySelectorAll('#tfGroups h4')].map(h => h.textContent)")
        for want in ("Rating", "Kind", "Score: Idea", "Score: Case", "Score: Material", "Theme"):
            assert want in titles, titles
        assert "Score: Light" not in titles and "Score: Phone" not in titles   # scales the frames hold no scores of are not offered
        # only the kinds present, with counts: 6 pictures and the Photoshop file
        assert count(page, "kind:image") == 6 and count(page, "kind:PSD") == 1
        assert fi(page, "kind:video").count() == 0 and fi(page, "3d").count() == 0
        # the scale's levels carry their words from the review panel, and counts
        assert fi(page, "score:real:1").locator(".fl span").text_content() == "Plastic"
        assert fi(page, "score:real:3").locator(".fl span").text_content() == "Metal"
        assert count(page, "score:real:3") == 1 and count(page, "score:real:1") == 1 and count(page, "score:case:3") == 1
        assert count(page, "tag:Birds") == 2 and count(page, "fav") == 2 and count(page, "all") == 7
        assert count(page, "take") == 2 and count(page, "none") == 3   # a/3, b/1 and the PSD are not reviewed yet
        # the pin marks what stands in the capsule
        assert fi(page, "fav").locator(".pn").get_attribute("aria-pressed") == "true"
        assert fi(page, "kind:PSD").locator(".pn").get_attribute("aria-pressed") == "false"
        assert not errors, errors
    finally:
        stop(process, log)


def test_pins_move_into_and_out_of_the_capsule_and_stay_with_the_project(tmp_path, engine):
    port, process, log, state, _, _ = start(tmp_path)
    try:
        page, errors = open_lib(engine, port)
        assert json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/filters")) == {"pins": None}   # not chosen yet
        open_window(page)
        fi(page, "kind:PSD").locator(".pn").click()
        fi(page, "fav").locator(".pn").click()
        page.wait_for_function("() => document.querySelector('#vfChips [data-f=\"kind:PSD\"]') && !document.querySelector('#vfChips [data-f=\"fav\"]')")
        want = ["all", "none", "take", "idea", "no", "ask", "score:real:3", "score:case:3", "kind:PSD"]   # «All» is the id "all", its chip's data-f is ""
        assert capsule(page) == [""] + want[1:]
        for _ in range(50):   # the server has them, in the project's state folder
            if (state / "filters.json").exists() and json.load(open(state / "filters.json"))["pins"] == want: break
            time.sleep(0.1)
        assert json.load(open(state / "filters.json")) == {"pins": want}
        assert json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/filters"))["pins"] == want
        # a reload, in a new page with nothing in its own storage: the project's pins are there
        other = engine.new_page(viewport={"width": 1400, "height": 900})
        other.goto(f"http://127.0.0.1:{port}/?view=lib"); other.wait_for_selector("#vfChips button")
        assert capsule(other) == [""] + want[1:]
        # the pinned chip works as a filter: the Photoshop file alone
        other.click('#vfChips [data-f="kind:PSD"]'); other.wait_for_timeout(100)
        assert names(other) == ["design"]
        assert other.evaluate("() => document.querySelector('#tfN').textContent") == "1"
        assert not errors, errors
    finally:
        stop(process, log)


def test_a_filter_shows_then_excludes_then_clears(tmp_path, engine):
    port, process, log, state, _, _ = start(tmp_path)
    try:
        page, errors = open_lib(engine, port)
        open_window(page)
        fi(page, "tag:Birds").locator(".fl").click()
        assert names(page) == ["0", "2"]
        assert "inc" in fi(page, "tag:Birds").get_attribute("class")
        # not pinned: it stands in the capsule as «+ Birds ×»
        assert "tag:Birds" in capsule(page)
        assert page.evaluate("() => document.querySelector('#vfChips [data-f=\"tag:Birds\"]').textContent").strip().startswith("+ Birds")
        fi(page, "tag:Birds").locator(".fl").click()
        assert "exc" in fi(page, "tag:Birds").get_attribute("class")
        assert names(page) == ["0", "1", "1", "3", "design"]   # everything but a/0 and a/2
        fi(page, "tag:Birds").locator(".fl").click()
        assert "tag:Birds" not in capsule(page) and len(names(page)) == 7
        # Alt excludes at once; the active chip's × takes it off
        fi(page, "tag:Birds").locator(".fl").click(modifiers=["Alt"])
        assert "exc" in fi(page, "tag:Birds").get_attribute("class")
        page.click('#vfChips [data-f="tag:Birds"]'); page.wait_for_timeout(100)
        assert len(names(page)) == 7 and "tag:Birds" not in capsule(page)
        # the same cycle on a pinned filter of the capsule (♥), and a rating is one choice
        page.click('#vfChips [data-f="fav"]'); assert names(page) == ["0", "0"]
        page.click('#vfChips [data-f="take"]'); assert names(page) == ["0", "0"]   # ♥ and take together: a/0 and b/0
        page.click('#vfChips [data-f="idea"]'); assert names(page) == []   # a rating replaces the other rating; ♥ stays
        page.click('#vfChips [data-f="idea"]'); page.click('#vfChips [data-f="fav"]')   # the rating off, ♥ a second time: excluded
        assert len(names(page)) == 5
        page.click('#vfChips [data-f=""]'); assert len(names(page)) == 7   # «All» takes the chips off
        assert not errors, errors
    finally:
        stop(process, log)


def test_hearts_and_scores_look_through_every_collection(tmp_path, engine):
    port, process, log, state, _, _ = start(tmp_path)
    try:
        page, errors = open_lib(engine, port)
        page.select_option("#coll", "b")
        page.wait_for_timeout(100)
        assert len(names(page)) == 3   # b/0, b/1 and the file
        page.click('#vfChips [data-f="fav"]')
        assert len(names(page)) == 2   # ♥ in a/0 as well: not only this collection
        page.click('#vfChips [data-f="fav"]'); page.click('#vfChips [data-f="fav"]')   # exclude, then off
        page.click('#vfChips [data-f="score:real:3"]')
        assert names(page) == ["0"]   # Metal is a/0, found from collection b
        page.click('#vfChips [data-f="score:real:3"]'); page.click('#vfChips [data-f="score:real:3"]')
        assert len(names(page)) == 3
        assert not errors, errors
    finally:
        stop(process, log)


def test_the_defaults_follow_the_data(tmp_path, engine):
    # no scores, no 3D files: a new project's seven
    (tmp_path / "plain").mkdir()
    port, process, log, *_ = start(tmp_path / "plain", scores=False)
    try:
        page, errors = open_lib(engine, port)
        assert capsule(page) == BASE
        open_window(page)
        titles = page.evaluate("() => [...document.querySelectorAll('#tfGroups h4')].map(h => h.textContent)")
        assert not [t for t in titles if t.startswith("Score")], titles
        assert not errors, errors
    finally:
        stop(process, log)
    # scores and a 3D file: Metal, Exact and 3D, as the Atlas boards had them
    (tmp_path / "shell").mkdir()
    port, process, log, *_ = start(tmp_path / "shell", model=True)
    try:
        page, errors = open_lib(engine, port)
        page.wait_for_function("() => document.querySelector('#vfChips [data-f=\"3d\"]')")
        assert capsule(page) == BASE + ["score:real:3", "score:case:3", "3d"]
        page.click('#vfChips [data-f="3d"]'); page.wait_for_selector("#list .card.m3d")
        assert page.locator("#list .card.m3d").count() == 1
        page.click('#vfChips [data-f="3d"]'); page.wait_for_selector("#list .card:not(.m3d)")
        assert not errors, errors
    finally:
        stop(process, log)


def test_a_project_tag_is_added_without_code(tmp_path, engine):
    port, process, log, state, rules_file, pid = start(tmp_path)
    try:
        page, errors = open_lib(engine, port)
        open_window(page)
        assert fi(page, "tag:Bridges").count() == 0
        page.click("#tgOpen")
        page.fill("#tgName", "Bridges"); page.fill("#tgWords", "bridge, viaduct"); page.fill("#tgGroup", "Theme")
        page.click("#tgGo")
        page.wait_for_selector('#tfGroups .fchip[data-id="tag:Bridges"]', timeout=20000)
        # saved into this board's tag rules, the built-in one kept
        rules = json.load(open(rules_file))[pid]["tags"]
        assert [r[1] for r in rules] == ["Birds", "Bridges"] and rules[1][0] == "Theme"
        assert count(page, "tag:Bridges") == 2   # a heron over a bridge, a viaduct at night: found after the rescan
        assert count(page, "tag:Birds") == 2
        fi(page, "tag:Bridges").locator(".fl").click()
        assert names(page) == ["0", "1"]
        # the same name again is refused, a word-less tag too
        page.fill("#tgName", "Bridges"); page.fill("#tgWords", "arch"); page.click("#tgGo"); page.wait_for_timeout(500)
        assert [r[1] for r in json.load(open(rules_file))[pid]["tags"]] == ["Birds", "Bridges"]
        # a reload: the tag is in the library's own data now
        page.reload(); page.wait_for_selector("#list .card")
        open_window(page)
        assert count(page, "tag:Bridges") == 2
        assert not errors, errors
    finally:
        stop(process, log)


def test_the_server_keeps_only_what_it_understands(tmp_path):
    port, process, log, state, rules_file, pid = start(tmp_path)
    try:
        def post(path, body):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", json.dumps(body).encode(), {"Content-Type": "application/json"})
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        assert post("/api/filters", {"pins": "fav"}) == 400 and post("/api/filters", {"pins": [1]}) == 400
        assert not (state / "filters.json").exists()
        assert post("/api/filters", {"pins": ["fav", "fav", "tag:x"]}) == 200
        assert json.load(open(state / "filters.json")) == {"pins": ["fav", "tag:x"]}
        assert post("/api/tagrule", {"group": "G", "tag": "T", "words": ""}) == 400
        assert post("/api/tagrule", {"group": "", "tag": "T", "words": "a"}) == 400
        assert post("/api/tagrule", {"group": "G", "tag": "Birds", "words": "a"}) == 409   # the board has it
        assert post("/api/tagrule", {"group": "G", "tag": "Odd", "words": "a(b, [c"}) == 200   # punctuation is taken literally
        assert [r[1] for r in json.load(open(rules_file))[pid]["tags"]] == ["Birds", "Odd"]
        assert not list(rules_file.parent.glob("rules.json.tmp"))
    finally:
        stop(process, log)



def test_rejected_are_a_filter_and_the_resets_are_one_button(tmp_path, engine):
    """(owner 2026-10-06: «make Show rejects part of the filter»; «why does the filter below look different from the one above»; «the
    reset buttons differ, they must be the same, and with too little room only the reset icon»)"""
    port, process, log, state, _, _ = start(tmp_path, rejected=True)
    try:
        page, errors = open_lib(engine, port)
        assert not page.locator("#showRej").is_visible()   # no separate toggle in the dock
        assert sorted(names(page)) == names(page) and len(names(page)) == 7   # the 2 rejected frames are hidden by default
        open_window(page)
        chip = fi(page, "rej"); assert count(page, "rej") == 2
        chip.locator(".fl").click(); page.wait_for_function("() => document.querySelectorAll('#list .card').length === 9")   # with the rest
        assert "+" in chip.locator(".fl b").text_content()
        chip.locator(".fl").click(); page.wait_for_function("() => document.querySelectorAll('#list .card').length === 2")   # alone
        assert chip.locator(".fl span").text_content() == "Only rejected"
        # the capsule shows it as the window does: the ink plate
        cap = page.locator('#vfChips [data-f="rej"]')
        assert cap.count() == 1 and "inc" in cap.get_attribute("class")
        page.wait_for_timeout(500)   # both chips ease into their colour
        bg = lambda sel: page.evaluate("s => getComputedStyle(document.querySelector(s)).backgroundColor", sel)
        assert bg('#vfChips [data-f="rej"]') == bg('#tfGroups .fchip[data-id="rej"]')
        # the two resets are one button: same classes and look; the window's clears the filters
        for prop in ("backgroundColor", "borderRadius", "height", "color"):
            a, b = page.evaluate("p => [getComputedStyle(document.getElementById('reset'))[p], getComputedStyle(document.getElementById('tfClear'))[p]]", prop)
            assert a == b, (prop, a, b)
        page.click("#tfClear"); page.wait_for_function("() => document.querySelectorAll('#list .card').length === 7")
        assert page.evaluate("() => document.getElementById('tfClear').disabled")
        # narrow: the dock's reset keeps only its icon
        page.set_viewport_size({"width": 500, "height": 900}); page.wait_for_timeout(300)
        assert page.evaluate("() => document.getElementById('reset').classList.contains('ico')")
        assert not errors, errors
    finally:
        stop(process, log)
