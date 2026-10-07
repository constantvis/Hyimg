# A liked card far out (owner 2026-10-06: «a double on click»): the far view draws ♥ on liked pictures, but a selected card stays an
# element there with its own ♥, so the drawn one must not be under it as well.
import json, pathlib, sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_shortcuts import run_server


def liked(lib):
    (lib / "a" / "0.json").write_text(json.dumps({"feedback": {"fav": True, "updated": "2099-01-01 00:00"}}))


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path, more=liked)


PINK = """() => { const c = document.getElementById('lodd'), g = c.getContext('2d'), it = board.items.i0, dpr = c.width / c.clientWidth;
  // where the marks' one law puts the ♥ (canvas.html mkFit, the owner's lab 2026-10-06): the top right corner, 8.5 px × k in, 26 px × k
  const pw = it.w * cam.z, f = mkFit(pw, itemH(it) * cam.z, { fav: true }), d = 26 * f.k, off = 8.5 * f.k;
  const cx = ((it.x + it.w - cam.x) * cam.z - off - d / 2) * dpr, cy = ((it.y - cam.y) * cam.z + off + d / 2) * dpr, r = Math.ceil(d / 2 * dpr);
  const px = g.getImageData(Math.round(cx - r), Math.round(cy - r), 2 * r, 2 * r).data; let n = 0;
  for (let i = 0; i < px.length; i += 4) if (px[i] > 200 && px[i + 1] < 150 && px[i + 2] > 90 && px[i + 3] > 200) n++;
  return n; }"""


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_a_selected_liked_card_far_out_has_one_heart(server, engine):
    with sync_playwright() as p:
        b = getattr(p, engine).launch(); page = b.new_page(viewport={"width": 1400, "height": 900})
        errors = []; page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/canvas.html?board=main"); page.wait_for_function("() => typeof board !== 'undefined' && board.items && board.items.i0 && typeof byPath !== 'undefined' && byPath.get('a/0.png')")
        page.wait_for_function("() => ((byPath.get('a/0.png') || {}).feedback || {}).fav")
        page.evaluate("() => { cam.x = -40; cam.y = -200; cam.z = 0.1; renderCam(); render(); }")
        page.wait_for_function("() => LOD.on"); page.wait_for_timeout(300)
        assert page.evaluate(PINK) > 3   # not selected: the drawn ♥ marks it
        page.evaluate("() => { sel.clear(); sel.add('i0'); render(); renderCam(); }"); page.wait_for_timeout(300)
        assert page.evaluate(PINK) == 0   # selected: only the element's own ♥
        assert page.evaluate("() => getComputedStyle(EL.get('i0').querySelector('.lk')).display") != "none"
        assert not errors, errors
        b.close()
