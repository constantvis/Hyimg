"""Settings › Profile › Team (owner 2026-10-07: «чтобы я видел своих "сотрудников" в настройках и их аватары»): this Mac's agents under
«Agents», every person this Mac knows with his face and, under him, the agents seen acting for him; hide and show a person; a picture
of one's own. An agent's face is its person's avatar with a smaller round badge on the bottom right. Chromium, dark theme, English and
Russian, temporary folders. HY_SHOTS=<folder> keeps screenshots."""
import base64
import io
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

import pytest
from PIL import Image

from test_shortcuts import run_server

playwright = pytest.importorskip("playwright.sync_api")
ME, OTHER = str(uuid.uuid4()), str(uuid.uuid4())


def png(color, size=64):
    b = io.BytesIO(); Image.new("RGB", (size, size), color).save(b, "PNG"); return b.getvalue()


def shot(page, name):
    if os.environ.get("HY_SHOTS"): page.screenshot(path=str(Path(os.environ["HY_SHOTS"]) / f"{name}.png"))


def setting(port, **kv):
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", data=json.dumps(kv).encode(), method="POST",
                                                  headers={"Content-Type": "application/json"}), timeout=10).read()


@pytest.mark.parametrize("lang", ["en", "ru"])
def test_team_agents_avatars_hide_and_picture(tmp_path, lang):
    now = int(time.time())
    (tmp_path / "profile.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "created": ""}))
    (tmp_path / "people.json").write_text(json.dumps({OTHER: {"name": "Bob", "color": "orange", "alias": "Partner"}}))
    pic = "data:image/png;base64," + base64.b64encode(png((40, 120, 200), 32)).decode()
    servers = run_server(tmp_path); port = next(servers)
    cards = tmp_path / "state" / "people"; cards.mkdir(parents=True, exist_ok=True)
    (cards / f"{ME}.json").write_text(json.dumps({"id": ME, "name": "Ann Lee", "color": "green", "agents": {"claude": now - 120, "codex": now - 7200}}))
    (cards / f"{OTHER}.json").write_text(json.dumps({"id": OTHER, "name": "Bob", "color": "orange", "avatar": pic, "agents": {"Codex CLI": now - 600}}))
    try:
        setting(port, **{"cv.theme": "dark", "cv.lang": lang})
        with playwright.sync_playwright() as p:
            try: browser = p.chromium.launch()
            except Exception as error: pytest.skip(f"no Chromium for Playwright: {error}")
            page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
            errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
            url = f"http://127.0.0.1:{port}/canvas.html"
            page.goto(url); page.evaluate("() => { localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); }"); page.goto(url)
            page.wait_for_function("() => typeof BOARD !== 'undefined' && window.hyPeople && hyPeople.me() && hyPeople.people()[%s]" % json.dumps(OTHER), timeout=20000)
            page.click("#bset"); page.evaluate("s => hySetPanel.go(s)", "team")   # its section of the settings window
            sec = page.locator("#hyPeopleSet")
            sec.locator(".hp-agent").first.wait_for()
            # this Mac's agents first, newest first, each with its badge (2026-10-08: alone, a button that changes its picture)
            mine = sec.locator(".hp-agent").evaluate_all("rs => rs.slice(0, 2).map(r => [r.dataset.agent, r.querySelector('.hya-b').dataset.k])")
            assert mine == [["claude", "claude"], ["codex", "codex"]], mine
            # the partner: his picture, this Mac's name for him, his agent folded into the catalog («Codex CLI» -> codex)
            row = sec.locator(f'.hp-person[data-person="{OTHER}"]')
            assert row.locator("hy-avatar img").get_attribute("src") == pic
            assert row.locator("[data-hp-alias]").input_value() == "Partner"
            his = row.locator("xpath=following-sibling::div[1]")
            assert his.get_attribute("data-agent") == "codex" and his.locator("hy-avatar img").count() == 1
            # the badge: about 45 % of the face, on its bottom right, over its edge, ringed in the panel's colour
            g = his.locator("hy-avatar").evaluate("""a => { const f = a.getBoundingClientRect(), b = a.querySelector('.hya-b').getBoundingClientRect();
              return { f: f.width, b: b.width, right: b.right - f.right, bottom: b.bottom - f.bottom, ring: getComputedStyle(a.querySelector('.hya-b')).boxShadow }; }""")
            assert g["f"] == 20 and 8.5 <= g["b"] <= 9.5 and 0 < g["right"] <= 3 and 0 < g["bottom"] <= 3 and "2px" in g["ring"], g
            shot(page, f"team-{lang}-1")
            # hide the partner: out of the team, under «Hidden» with Show; the address book keeps him
            row.locator("[data-hp-hide] button").click()
            page.wait_for_function("() => hyPeople.people()[%s].hidden" % json.dumps(OTHER))
            assert json.loads((tmp_path / "people.json").read_text())[OTHER]["hidden"] is True
            sec.locator(f'.hp-off[data-person="{OTHER}"]').wait_for()
            shot(page, f"team-{lang}-2-hidden")
            sec.locator(f'[data-hp-show="{OTHER}"] button').click()
            page.wait_for_function("() => !hyPeople.people()[%s].hidden" % json.dumps(OTHER))
            # a picture of one's own: any image, placed in the round window (ui/crop.js), cut to a 256 px square, kept in profile.json and
            # on the board's card (tests/test_avatar_ui.py drags and zooms it)
            f = tmp_path / "me.png"; f.write_bytes(png((230, 80, 60), 300))
            sec.locator("[data-hp-file]").set_input_files(str(f))
            page.locator("#hyCrop.on [data-a=ok]").click()
            page.wait_for_function("() => (hyPeople.me() || {}).avatar")
            prof = json.loads((tmp_path / "profile.json").read_text())
            assert prof["avatar"].startswith("data:image/jpeg;base64,")
            assert Image.open(io.BytesIO(base64.b64decode(prof["avatar"].split(",", 1)[1]))).size == (256, 256)
            assert json.loads((cards / f"{ME}.json").read_text())["avatar"] == prof["avatar"]
            page.evaluate("s => hySetPanel.go(s)", "profile"); page.wait_for_selector("#hyPeopleSet .hp-pic hy-avatar img")
            shot(page, f"team-{lang}-3-picture")
            assert not errors, errors
            browser.close()
    finally:
        servers.close()
