"""One shell for the three Studios (owner 2026-10-11 on round 20, r20/studio-a.html «Одна оболочка» ♥ «беру», r20/esc-a.html «Одна
лестница» ♥ «отлично, го»; studios audit S-05…S-08, S-10, S-12, S-14, S-18). What a person sees, the same in Image Studio, 3D Studio and
Dev Studio, read from one table per part, the real plugins beside this repository. Chromium, the dark theme, our own temporary server.

  NAME    the crumb gains one step: the Studio's dot and the thing's name, the path in its tooltip; the leave question says the same name

  nice -n 10 python3 -m pytest -q tests/test_studio_shell.py
"""
import pytest

from test_p4_studio_keys import board, blur, serve, studios

playwright = pytest.importorskip("playwright.sync_api")

#        studio,  the name in the crumb and the question, the path in the step's tooltip
NAME = [("image", "a", "pics/a.png"), ("3d", "3D scene", "3d/scenes/a/scene.json"), ("dev", "Keys", "site/keys.html")]
ASKS = {"image", "3d"}   # Dev Studio writes every edit at once and never asks (owner decision 2026-10-10)

STEP = """() => { const s = document.getElementById('cStudio'); if (!s || !s.classList.contains('in') || !s.getClientRects().length) return null;
  const c = document.getElementById('crumb'), d = s.querySelector('.hyd'), r = s.getBoundingClientRect(), cr = c.getBoundingClientRect();
  return { name: s.innerText.trim(), path: s.title, dot: getComputedStyle(d).backgroundColor, last: c.lastElementChild === s,
           inside: r.left >= cr.left - 1 && r.right <= cr.right + 1,
           studio: getComputedStyle(document.documentElement).getPropertyValue('--hy-studio').trim() } }"""
COLOUR = "c => { const e = document.createElement('i'); e.style.color = c; document.body.appendChild(e); const v = getComputedStyle(e).color; e.remove(); return v; }"


def browser_of(pw):
    return pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])


def test_the_open_thing_has_one_name(tmp_path):
    with serve(tmp_path) as (port, lib), playwright.sync_playwright() as pw:
        browser = browser_of(pw); page, errors = board(browser, port); S = studios(page, lib); bad = []
        for k, name, path in NAME:
            s = S[k].open()
            try: page.wait_for_function(STEP, timeout=8000)
            except Exception: bad.append(f"{k}: no step of the open thing in the crumb"); s.close(); continue
            st = page.evaluate(STEP)
            if st["name"] != name: bad.append(f"{k}: the crumb's step says {st['name']!r}, want {name!r}")
            if st["path"] != path: bad.append(f"{k}: the step's tooltip is {st['path']!r}, want {path!r}")
            if not st["last"] or not st["inside"]: bad.append(f"{k}: the step is not the crumb's last part: {st}")
            if st["dot"] != page.evaluate(COLOUR, st["studio"]): bad.append(f"{k}: the step's dot {st['dot']} is not the Studio's colour {st['studio']}")
            if page.evaluate("() => [...document.querySelectorAll('.m3title')].some(e => e.getClientRects().length)"):
                bad.append(f"{k}: a plate with the path still stands beside the crumb")
            if k in ASKS:
                s.change("Renamed in the test"); blur(page); s.leave("cancel"); q = s.question()
                if q[0] != f"Save changes to “{name}”?": bad.append(f"{k}: the question names another thing: {q[0]!r}")
                page.keyboard.press("Escape"); page.wait_for_timeout(400)
            s.close()
            page.wait_for_function("() => !document.getElementById('cStudio')", timeout=5000)
        assert not bad, "\n".join(bad)
        assert not errors, errors
        browser.close()
