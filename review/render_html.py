"""A still of an HTML page at a given viewport, for an HTML frame on the canvas (owner 2026-10-04: «HTML frames we can open, with
interactive buttons, and freeze as a picture»). Run by server.py in its own process: python3 render_html.py <url> <w> <h> <out.png> [scale].
Chromium from Playwright runs the page's scripts, unlike Quick Look, which draws HTML without them. scale is the device pixel ratio: 2 draws
the w × h css px page twice as wide, as a Retina screen shows it (⇧⌘C copies a card's page so, copyimg.py)."""
import sys

from playwright.sync_api import sync_playwright

url, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
scale = float(sys.argv[5]) if len(sys.argv) > 5 else 1
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": w, "height": h}, **({"device_scale_factor": scale} if scale != 1 else {}))
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(400)   # fonts and a first animation frame
    page.screenshot(path=out)
    browser.close()
