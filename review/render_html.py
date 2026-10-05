"""A still of an HTML page at a given viewport, for an HTML frame on the canvas (owner 2026-10-04: «HTML frames we can open, with
interactive buttons, and freeze as a picture»). Run by server.py in its own process: python3 render_html.py <url> <w> <h> <out.png>.
Chromium from Playwright runs the page's scripts, unlike Quick Look, which draws HTML without them."""
import sys

from playwright.sync_api import sync_playwright

url, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": w, "height": h})
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(400)   # fonts and a first animation frame
    page.screenshot(path=out)
    browser.close()
