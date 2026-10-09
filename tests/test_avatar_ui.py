"""Changing faces (owner 2026-10-08: «Сделай так, чтобы аватар можно было менять, и для агентов возьми логотип Claude и логотип Codex»).
Settings › Profile on a board, through its server alone (no app): a picture placed and zoomed in a round window (ui/crop.js), kept as a
256 px square, taken off again; an agent kind's own badge on this Mac (agent-badges.json beside the profile) and back to the default;
Home sends the same to the app. The default badges are the companies' marks (ui/agents) at 16, 24 and 32 px; without the files (the
public repositories) every badge keeps our glyph. Chromium, dark theme, temporary folders. HY_SHOTS=<folder> keeps screenshots."""
import base64
import io
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from PIL import Image

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "review/home.html").as_uri()
ME = str(uuid.uuid4())
MARKS = (ROOT / "review/ui/agents/claude.svg").is_file()   # the public repositories leave the companies' marks out


def shot(page, name, **kw):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"), **kw)


def halves(w=600, h=300):
    """a picture red on the left half, blue on the right: where the crop's window lies shows in the kept colour"""
    im = Image.new("RGB", (w, h), (220, 40, 40)); im.paste((40, 80, 230), (w // 2, 0, w, h))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def decoded(url):
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")


def mean(im):
    px = list(im.getdata()); return tuple(sum(p[i] for p in px) // len(px) for i in range(3))


def launch(p, **kw):
    try: browser = p.chromium.launch()
    except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
    page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark", **kw)
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
    return browser, page, errors


def open_board(page, port):
    url = f"http://127.0.0.1:{port}/canvas.html"
    page.goto(url); page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
    page.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyPeople && hyPeople.me()", timeout=20000)
    page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "team")   # this Mac's agents: Team & agents in the settings window
    page.locator("#hyPeopleSet .hp-mine").first.wait_for()
    return page.locator("#hyPeopleSet")


def saved(page):
    """waits for the server's answer to a profile write (the page shows the change before it)"""
    return page.expect_response(lambda r: r.url.endswith("/api/profile") and r.request.method == "POST")


def after_bg(page, sel):
    return page.locator(sel).first.evaluate("b => getComputedStyle(b, '::after').backgroundImage")


def test_board_picture_crop_remove_and_agent_badges(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    servers = run_server(tmp_path); port = next(servers)
    pic = tmp_path / "halves.png"; pic.write_bytes(halves())
    try:
        import urllib.request
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps({"cv.theme": "dark"}).encode(),
                                                      method="POST", headers={"Content-Type": "application/json"}), timeout=10).read()
        with playwright.sync_playwright() as p:
            browser, page, errors = launch(p)
            sec = open_board(page, port)
            # every kind of the catalog under Agents, each with its badge and a button for its picture; none acted yet
            assert sec.locator(".hp-mine").evaluate_all("rs => rs.map(r => r.dataset.agent)") == ["claude", "codex", "gemini", "kimi", "opencode", "agent"]
            assert sec.locator(".hp-mine button.hp-badge .hya-b").evaluate_all("bs => bs.map(b => b.dataset.k)") == ["claude", "codex", "gemini", "kimi", "opencode", "agent"]
            assert sec.locator(".hp-mine hy-icon-button[data-hp-badge]").count() == 6 and sec.locator("[data-hp-badge-reset]").count() == 0
            # the picture: a file, then the round window; Esc leaves everything as it was and the settings stay open
            sec.locator("[data-hp-file]").set_input_files(str(pic))
            page.wait_for_selector("#hyCrop.on")
            page.keyboard.press("Escape")
            page.wait_for_selector("#hyCrop", state="detached")
            assert "avatar" not in json.loads((tmp_path / "profile.json").read_text()) and sec.locator(".hp-team").is_visible()
            # again: dragged left by half the window, the blue half fills it; zoomed in with the wheel, then Save
            sec.locator("[data-hp-file]").set_input_files(str(pic))
            page.wait_for_selector("#hyCrop.on")
            st = page.locator("#hyCrop .hcr-stage").bounding_box()
            cx, cy = st["x"] + st["width"] / 2, st["y"] + st["height"] / 2
            page.mouse.move(cx, cy); page.mouse.down(); page.mouse.move(cx - 60, cy, steps=4); page.mouse.move(cx - 200, cy, steps=6); page.mouse.up()
            page.mouse.move(cx + 60, cy); page.mouse.wheel(0, -200)
            zoom = page.locator("#hyCrop .hy-slider input").input_value()
            assert int(zoom) > 100, zoom
            page.wait_for_timeout(300); shot(page, "avatar-1-crop")
            with saved(page): page.locator("#hyCrop [data-a=ok]").click()
            page.wait_for_function("() => (hyPeople.me() || {}).avatar")
            prof = json.loads((tmp_path / "profile.json").read_text())
            assert prof["avatar"].startswith("data:image/jpeg;base64,") and len(prof["avatar"]) <= 80000
            im = decoded(prof["avatar"]); r, g, b = mean(im)
            assert im.size == (256, 256) and b > 180 and r < 90, (im.size, (r, g, b))
            card = json.loads((tmp_path / "state" / "people" / f"{ME}.json").read_text())
            assert card["avatar"] == prof["avatar"]   # the other Mac learns it from the board's card
            page.evaluate("s => hySetPanel.go(s)", "profile"); page.wait_for_selector("#hyPeopleSet .hp-pic hy-avatar img"); shot(page, "avatar-2-picture")
            # Remove: back to the initials on his colour
            with saved(page): sec.locator('[data-hp="nopic"] button').click()
            page.wait_for_function("() => !(hyPeople.me() || {}).avatar")
            assert "avatar" not in json.loads((tmp_path / "profile.json").read_text())
            assert sec.locator(".hp-pic hy-avatar .hya-p").get_attribute("data-i") == "AL"
            # Claude's default is its mark (ui/agents/claude.svg); this Mac's own picture over it, kept beside the profile only
            if MARKS:
                page.wait_for_function("() => HY_AGENTS.logo('claude')")
                assert "agents/claude.svg" in after_bg(page, '#hyPeopleSet .hp-mine[data-agent=claude] .hya-b')
            page.evaluate("s => hySetPanel.go(s)", "team"); sec.locator('[data-hp-badge="claude"] button').click()
            sec.locator("[data-hp-bfile]").set_input_files(str(pic))
            page.wait_for_selector("#hyCrop.on"); page.wait_for_timeout(250); shot(page, "avatar-3-badge-crop")
            with saved(page): page.keyboard.press("Enter")
            page.wait_for_function("() => (JSON.parse(JSON.stringify(hyPeople.badges())).claude || '').startsWith('data:image/png')")
            page.wait_for_function("() => !document.querySelector('#hyCrop')")
            kept = json.loads((tmp_path / "agent-badges.json").read_text())
            assert list(kept) == ["claude"] and decoded(kept["claude"]).size == (96, 96)
            assert not (tmp_path / "state" / "people" / f"{ME}.json").read_text().count("badge")   # never on the board
            assert after_bg(page, '#hyPeopleSet .hp-mine[data-agent=claude] .hya-b').startswith('url("data:image/png')
            assert sec.locator('[data-hp-badge-reset="claude"]').count() == 1
            shot(page, "avatar-4-badge-own")
            # a reload reads it back from the server
            page.reload(); page.wait_for_function("() => window.hyPeople && hyPeople.badges().claude")
            # back to the default: the file forgets the kind, the mark again
            sec = open_board(page, port)
            with saved(page): sec.locator('[data-hp-badge-reset="claude"] button').click()
            page.wait_for_function("() => !hyPeople.badges().claude")
            assert json.loads((tmp_path / "agent-badges.json").read_text()) == {}
            assert ("agents/claude.svg" in after_bg(page, '#hyPeopleSet .hp-mine[data-agent=claude] .hya-b')) == MARKS
            assert not errors, errors
            browser.close()
    finally:
        servers.close()


STRIP = """() => {
  const sizes = [16, 24, 32], kinds = ['claude', 'codex', 'gemini', 'kimi'];
  const d = document.createElement('div'); d.id = 'strip';
  d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999;padding:14px;display:grid;gap:12px;background:var(--panel);border:1px solid var(--line);border-radius:12px';
  d.innerHTML = kinds.map(k => '<div style="display:flex;gap:14px;align-items:center">' + sizes.map(s => hyAvatarHTML({ name: 'Ann Lee', color: 'green', agent: k, size: s })).join('')
    + sizes.map(s => hyAgentBadgeHTML(k, s)).join('') + '</div>').join('');
  document.body.appendChild(d);
}"""


def test_default_logos_at_16_24_32(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    servers = run_server(tmp_path); port = next(servers)
    try:
        with playwright.sync_playwright() as p:
            if not MARKS: pytest.skip("no marks in this copy (a public repository): test_glyphs_without_the_marks")
            browser, page, errors = launch(p, device_scale_factor=3)
            open_board(page, port)
            page.wait_for_function("() => HY_AGENTS.logo('claude') && HY_AGENTS.logo('codex') && HY_AGENTS.logo('gemini')")
            page.evaluate(STRIP)
            for k in ("claude", "codex", "gemini"):
                for el in page.locator(f"#strip .hya-b[data-k={k}]").all():
                    g = el.evaluate("b => { const a = getComputedStyle(b, '::after'), r = b.getBoundingClientRect();"
                                    " return { bg: a.backgroundImage, glyph: getComputedStyle(b.querySelector('svg')).visibility, w: r.width, h: r.height }; }")
                    assert f"agents/{k}.svg" in g["bg"] and g["glyph"] == "hidden" and abs(g["w"] - g["h"]) < .01, (k, g)
            sizes = page.locator("#strip hy-avatar[agent=claude] .hya-b").evaluate_all("bs => bs.map(b => Math.round(b.getBoundingClientRect().width * 10) / 10)")
            assert sizes == [7.2, 10.8, 14.4], sizes   # 45 % of 16, 24, 32
            k = page.locator("#strip .hya-b[data-k=kimi]").first.evaluate("b => [getComputedStyle(b, '::after').content, getComputedStyle(b.querySelector('svg')).visibility]")
            assert k == ["none", "visible"], k   # no official mark: our glyph
            box = page.locator("#strip").bounding_box()
            shot(page, "avatar-5-logos-16-24-32", clip=box)
            assert not errors, errors
            browser.close()
    finally:
        servers.close()


def test_glyphs_without_the_marks(tmp_path):
    """the public repositories have no ui/agents: every badge keeps its glyph, nothing breaks"""
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    servers = run_server(tmp_path); port = next(servers)
    try:
        with playwright.sync_playwright() as p:
            browser, page, errors = launch(p, device_scale_factor=3)
            page.route("**/ui/agents/**", lambda r: r.fulfill(status=404, body="no such ui file"))
            open_board(page, port)
            page.wait_for_timeout(400)
            page.evaluate(STRIP)
            assert page.evaluate("() => document.getElementById('hyAgentLogos').textContent") == ""
            vis = page.locator("#strip .hya-b").evaluate_all("bs => bs.map(b => getComputedStyle(b.querySelector('svg')).visibility)")
            assert set(vis) == {"visible"}, vis
            shot(page, "avatar-6-glyphs-public", clip=page.locator("#strip").bounding_box())
            assert not errors, errors
            browser.close()
    finally:
        servers.close()


def test_home_sends_the_picture_and_the_badge_to_the_app():
    with playwright.sync_playwright() as p:
        browser, page, errors = launch(p)
        sent = []
        page.expose_function("__post", lambda m: sent.append(m))
        page.add_init_script("window.webkit = { messageHandlers: { hyimg: { postMessage: m => window.__post(m) } } };")
        page.goto(HOME)
        me = {"id": ME, "name": "Ann Lee", "color": "green"}
        data = {"projects": [], "settings": {"cv.theme": "dark"}, "home": {"folders": []}, "profile": me,
                "people": {ME: {"name": "Ann Lee", "own": "Ann Lee", "color": "green", "me": True}}, "places": {"shared": "", "private": ""}, "vis": {}}
        page.evaluate(f"hyimgHome({json.dumps(data)})")
        page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "team")
        sec = page.locator("#hyPeopleSet"); sec.locator(".hp-mine").first.wait_for()
        ops = lambda op: [m for m in sent if m.get("action") == "profile" and m.get("op") == op]
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.png"; f.write_bytes(halves())
            sec.locator("[data-hp-file]").set_input_files(str(f))
            page.wait_for_selector("#hyCrop.on"); page.locator("#hyCrop [data-a=ok]").click()
            page.wait_for_function("() => !document.querySelector('#hyCrop')")
            page.wait_for_timeout(100)
            assert len(ops("avatar")) == 1 and decoded(ops("avatar")[0]["avatar"]).size == (256, 256)
            sec.locator('[data-hp-badge="codex"] button').click()
            sec.locator("[data-hp-bfile]").set_input_files(str(f))
            page.wait_for_selector("#hyCrop.on"); page.locator("#hyCrop [data-a=ok]").click()
            page.wait_for_timeout(300)
        b = ops("badge")
        assert len(b) == 1 and b[0]["kind"] == "codex" and decoded(b[0]["picture"]).size == (96, 96)
        # the app answers with this Mac's badges: they show at once; Home's logos load from the files beside it
        page.evaluate(f"hyimgProfile({json.dumps({'badges': {'codex': b[0]['picture']}})})")
        assert after_bg(page, '#hyPeopleSet .hp-mine[data-agent=codex] .hya-b').startswith('url("data:image/png')
        if MARKS:
            page.wait_for_function("() => HY_AGENTS.logo('claude')")
            assert "agents/claude.svg" in after_bg(page, '#hyPeopleSet .hp-mine[data-agent=claude] .hya-b')
        sec.locator('[data-hp-badge-reset="codex"] button').click()
        assert ops("badge")[-1] == {"action": "profile", "op": "badge", "kind": "codex", "picture": ""}
        shot(page, "avatar-7-home")
        assert not errors, errors
        browser.close()


def test_public_export_leaves_the_marks_out(tmp_path):
    """the committed tree as the public repository gets it: no ui/agents, avatar.js asks for no mark"""
    out = tmp_path / "pub"
    if not (ROOT / "scripts/public_export.py").is_file(): pytest.skip("a public copy has no export tool")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/public_export.py"), str(ROOT), str(out), "--name", "hyimg", "--report", str(tmp_path / "r.json")],
                       capture_output=True, text=True)
    if not (tmp_path / "r.json").exists(): pytest.fail(r.stderr[-2000:])
    rep = json.loads((tmp_path / "r.json").read_text())
    if not (ROOT / "review/ui/agents").is_dir() or "review/ui/agents" not in [e["path"] for e in rep["excluded"]]:
        pytest.skip("the marks are not committed yet")
    assert not (out / "review/ui/agents").exists()
    js = (out / "review/ui/avatar.js").read_text()
    assert "const LOGOS = {};" in js and "agents/claude.svg" not in js
    mine = [h for h in rep["hits"] if h["file"].startswith(("review/ui/agents", "review/ui/avatar.js", "review/ui/crop.js", "tests/test_avatar_ui.py"))]
    assert not mine, mine
