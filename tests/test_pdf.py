"""PDFs and empty files (owner 2026-10-06).

Empty files (0 bytes, a Dropbox folder where 105 of 111 files had not been brought down) are listed in the library with the mark
«Empty file · 0 bytes» and a note with their count, not folded into one another by the sha1 and not placed on the board. A PDF is in
the library with its first page as the picture; its board card has the video's grey pill with ‹ 2 / 5 › (the card remembers `page`),
⤢ opens the library's own viewer on that page when the board sits inside the library (alone it keeps a large preview over the dimmed board, where the keys step pages and Esc closes), the library viewer steps pages, and «Split into
pages» turns the card into one card per page in a group. The pages are images drawn by the server (PDFKit, poppler as the second way),
so this works in the app's Chromium without a PDF plugin and in WebKit. Test PDFs are written here by hand: nothing is downloaded."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ["chromium", "webkit"]
COLORS = [(220, 40, 40), (40, 180, 70), (50, 80, 230)]   # page 1 red, 2 green, 3 blue
MAC = sys.platform == "darwin"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_pdf(colors, size=(300, 400)):
    """a PDF with one full-page colour per page (Helvetica number on it), written by hand with a correct xref"""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    kids = []
    for k, c in enumerate(colors):
        page_id = 3 + k * 2
        kids.append(f"{page_id} 0 R")
        stream = f"{c[0] / 255:.3f} {c[1] / 255:.3f} {c[2] / 255:.3f} rg 0 0 {size[0]} {size[1]} re f 1 1 1 rg BT /F1 40 Tf 20 20 Td (p{k + 1}) Tj ET".encode()
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] /Contents {page_id + 1} 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Font1 /BaseFont /Helvetica >> >> >> >>".encode()
                    .replace(b"/Subtype /Font1", b"/Subtype /Type1"))
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(colors)} >>".encode()
    out = b"%PDF-1.4\n"; offs = []
    for n, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return out


def png(color=(120, 120, 120)):
    from PIL import Image
    import io
    b = io.BytesIO(); Image.new("RGB", (60, 40), color).save(b, "PNG"); return b.getvalue()


def run_server(tmp_path, board_items=None, **extra):
    lib, state = tmp_path / "lib", tmp_path / "state"
    (lib / "a").mkdir(parents=True); (state / "boards").mkdir(parents=True)
    (lib / "a/doc.pdf").write_bytes(make_pdf(COLORS))
    (lib / "a/one.pdf").write_bytes(make_pdf(COLORS[:1]))
    (lib / "a/ok.png").write_bytes(png())
    for n in ("zero1.png", "zero2.png", "zero3.jpg", "zero.pdf"):
        (lib / "a" / n).write_bytes(b"")   # four files with no bytes: all alike to a sha1
    items = board_items if board_items is not None else {"p0": {"path": "a/doc.pdf", "x": 0, "y": 0, "w": 260, "ar": 0.75, "crop": None}}
    (state / "boards/main.json").write_text(json.dumps({"schema": 1, "revision": 1, "items": items, "groups": {}, "removed": {}}))
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HYIMG_", "REVIEW_"))}
    (tmp_path / "settings.json").write_text(json.dumps({"cv.lang": "en"}))
    env.update(HYIMG_LIBRARY_ROOT=str(lib), HYIMG_STATE_ROOT=str(state), HYIMG_PROJECT_ID=str(uuid.uuid4()), HYIMG_SETTINGS=str(tmp_path / "settings.json"),
               PYTHONDONTWRITEBYTECODE="1", **extra)
    log = open(tmp_path / "server.log", "w+")
    process = subprocess.Popen([sys.executable, str(ROOT / "review/server.py"), str(port)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        yield port
    finally:
        process.terminate(); process.wait(5); log.close()


@pytest.fixture
def server(tmp_path):
    yield from run_server(tmp_path)


def get(port, path):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60).read()


def centre_color(data):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data)).convert("RGB"); return im.getpixel((im.width // 2, im.height // 3))


def near(a, b, tol=40):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


needs_renderer = pytest.mark.skipif(not (MAC or shutil.which("pdftoppm")), reason="no PDF renderer on this machine")


def launch(p, engine):
    try:
        return getattr(p, engine).launch()
    except Exception as error:
        pytest.skip(f"no {engine} for Playwright: {error}")


# ---------------------------------------------------------------- the server

def test_empty_files_are_listed_not_folded(server):
    items = json.loads(get(server, "/api/items"))
    zero = {i["path"]: i for i in items if i["path"].startswith("a/zero")}
    assert set(zero) == {"a/zero1.png", "a/zero2.png", "a/zero3.jpg", "a/zero.pdf"}, "empty files must not be folded into one copy"
    assert all(i.get("empty") and i["size"] == 0 for i in zero.values())
    assert zero["a/zero.pdf"]["kind"] == "pdf"
    ok = next(i for i in items if i["path"] == "a/ok.png")
    assert not ok.get("empty")
    assert get(server, "/thumb?p=a/zero1.png&s=320")[:3] == b"\xff\xd8\xff", "an empty picture gets a grey card, not an error"
    assert json.loads(get(server, "/api/pdf?p=a/zero.pdf"))["pages"] == 0


@needs_renderer
def test_pdf_pages_are_images(server):
    d = json.loads(get(server, "/api/pdf?p=a/doc.pdf"))
    assert d["pages"] == 3 and len(d["ars"]) == 3 and abs(d["ars"][0] - 0.75) < 0.01
    for pg, c in enumerate(COLORS, 1):
        assert near(centre_color(get(server, f"/thumb?p=a/doc.pdf&s=640&pg={pg}")), c), pg
    assert near(centre_color(get(server, "/thumb?p=a/doc.pdf&s=320")), COLORS[0]), "no page = the first"
    assert near(centre_color(get(server, "/thumb?p=a/doc.pdf&s=640&pg=99")), COLORS[2]), "a page past the end is the last"
    assert near(centre_color(get(server, "/img?p=a/doc.pdf")), COLORS[0])
    big = get(server, "/thumb?p=a/doc.pdf&s=2048&pg=2")
    from PIL import Image
    import io
    assert max(Image.open(io.BytesIO(big)).size) == 2048 and near(centre_color(big), COLORS[1])
    time.sleep(0.5)
    it = next(i for i in json.loads(get(server, "/api/items")) if i["path"] == "a/doc.pdf")
    assert it["kind"] == "pdf" and it["ext"] == "PDF" and it["pages"] == 3, "the page count is kept once it is known"


@pytest.mark.skipif(not shutil.which("pdftoppm") and not os.path.exists("/opt/homebrew/bin/pdftoppm"), reason="no poppler")
def test_poppler_is_the_second_way(tmp_path):
    for port in run_server(tmp_path, HYIMG_PDF_ENGINE="poppler"):
        assert json.loads(get(port, "/api/pdf?p=a/doc.pdf"))["pages"] == 3
        assert near(centre_color(get(port, "/thumb?p=a/doc.pdf&s=640&pg=2")), COLORS[1])


# ---------------------------------------------------------------- the library

@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_library_empty_cards_and_pdf_viewer(server, engine):
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1300, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/?view=lib"); page.evaluate("() => localStorage.clear()")
        page.goto(f"http://127.0.0.1:{server}/?view=lib"); page.wait_for_selector("#list .card")
        # empty files: four cards with the mark, the name, the extension, nothing to drag; the note says how many
        empties = page.locator("#list .card.empty")
        assert empties.count() == 4
        assert "Empty file · 0 bytes" in empties.first.inner_text() and empties.first.get_attribute("draggable") == "false"
        assert {t.strip() for t in page.locator("#list .card.empty .pill.kd").all_inner_texts()} == {"PNG", "JPG", "PDF"}
        assert page.locator("#list .emptynote").inner_text() == "4 files in all folders are empty"
        page.select_option("#coll", "a")
        assert page.locator("#list .emptynote").inner_text() == "4 files here are empty"
        empties.first.click(); page.wait_for_timeout(300)
        assert not page.evaluate("() => document.getElementById('viewer').classList.contains('open')"), "an empty file opens nothing"
        # the PDF's first page is its picture
        card = page.locator("#list .card", has_text="doc").first
        card.locator("img").wait_for(); page.wait_for_function("() => [...document.querySelectorAll('#list .card img')].some(i => /doc\\.pdf/.test(decodeURIComponent(i.src)) && i.naturalWidth > 0)")
        card.click(); page.wait_for_selector("#viewer.open")
        page.wait_for_function("() => document.getElementById('pgN').textContent === '1 / 3'")
        assert "pg=1" in page.evaluate("() => document.getElementById('big').src")
        page.keyboard.press("PageDown"); page.wait_for_function("() => document.getElementById('pgN').textContent === '2 / 3' && /pg=2/.test(document.getElementById('big').src)")
        page.wait_for_function("() => { const i = document.getElementById('big'); return i.complete && i.naturalWidth > 0; }")
        px = page.evaluate("""() => { const i = document.getElementById('big'), c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight;
          const g = c.getContext('2d'); g.drawImage(i, 0, 0); return [...g.getImageData(i.naturalWidth >> 1, i.naturalHeight / 3 | 0, 1, 1).data]; }""")
        assert near(tuple(px[:3]), COLORS[1]), px
        page.click("#pgNext"); page.wait_for_function("() => document.getElementById('pgN').textContent === '3 / 3'")
        assert page.locator("#pgNext").is_disabled()
        page.keyboard.press("PageUp"); page.wait_for_function("() => document.getElementById('pgN').textContent === '2 / 3'")
        page.keyboard.press("Escape"); page.wait_for_function("() => !document.getElementById('viewer').classList.contains('open')")
        assert not errors, errors
        browser.close()


# ---------------------------------------------------------------- the board

def open_board(p, engine, port, count=1):
    browser = launch(p, engine)
    page = browser.new_page(viewport={"width": 1200, "height": 800}); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    url = f"http://127.0.0.1:{port}/canvas.html?board=main"
    page.goto(url)
    page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); localStorage.setItem('cv.lod', '0'); localStorage.setItem('cv.cam.main', JSON.stringify({x: -60, y: -60, z: 1})); }")
    page.goto(url)
    page.wait_for_function(f"() => typeof BOARD !== 'undefined' && Object.keys(board.items).length === {count} && byPath.size >= 4")
    return browser, page, errors


def pill(page, id="p0"):
    return page.evaluate("id => { const k = EL.get(id).querySelector('.kd .kt'); return k ? k.textContent : null; }", id)


def card_color(page, id="p0"):
    page.wait_for_function("id => { const i = EL.get(id).querySelector('img'); return i.complete && i.naturalWidth > 0; }", arg=id)
    return page.evaluate("""id => { const i = EL.get(id).querySelector('img'), c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight;
      const g = c.getContext('2d'); g.drawImage(i, 0, 0); return [i.src, ...g.getImageData(i.naturalWidth >> 1, i.naturalHeight / 3 | 0, 1, 1).data]; }""", id)


def press(page, selector):
    r = page.evaluate("s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", selector)
    page.mouse.click(*r)


@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_board_pill_steps_pages_and_previews(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.wait_for_function("() => EL.get('p0') && EL.get('p0').classList.contains('pdf') && EL.get('p0').querySelector('.kd .kt') && EL.get('p0').querySelector('.kd .kt').textContent === '1 / 3'")
        src, *rgb = card_color(page); assert near(tuple(rgb[:3]), COLORS[0]) and "pg=" not in src
        c = page.evaluate("() => { const r = EL.get('p0').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        page.mouse.move(*c)
        page.wait_for_function("() => { const f = EL.get('p0').querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 11; }")   # the pill has grown to its hover width: the buttons stand still
        # › twice, then past the end does nothing; the card remembers the page
        sel = "#items .it.pdf .kd .kb[data-d='1']"
        press(page, sel); page.wait_for_function("() => board.items.p0.page === 2 && EL.get('p0').querySelector('.kd .kt').textContent === '2 / 3'")
        page.wait_for_function("() => { const i = EL.get('p0').querySelector('img'); return /pg=2/.test(i.src) && i.complete && i.naturalWidth > 0; }")
        assert near(tuple(card_color(page)[1:4]), COLORS[1])
        press(page, sel); page.wait_for_function("() => board.items.p0.page === 3")
        press(page, sel); page.wait_for_timeout(250)
        assert page.evaluate("() => board.items.p0.page") == 3
        press(page, "#items .it.pdf .kd .kb[data-d='-1']"); page.wait_for_function("() => board.items.p0.page === 2")
        press(page, "#items .it.pdf .kd .kb[data-d='-1']"); page.wait_for_function("() => board.items.p0.page === undefined"); assert pill(page) == "1 / 3"
        press(page, sel); page.wait_for_function("() => board.items.p0.page === 2")
        # the page is saved on the card, in the board's file
        page.wait_for_timeout(1500)
        saved = json.loads(get(server, "/api/board?name=main"))
        assert saved["items"]["p0"]["page"] == 2, saved["items"]["p0"]
        # ⤢ grows in under the pointer and opens the large preview, the board dimmed to 70 %
        page.mouse.move(*c)
        page.wait_for_function("() => { const f = EL.get('p0').querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 8; }")
        press(page, "#items .it.pdf .kd .kf")
        page.wait_for_selector("#vbig.open.pdf")
        assert page.evaluate("() => getComputedStyle(document.getElementById('vbig')).backgroundColor") == "rgba(0, 0, 0, 0.7)"
        page.wait_for_function("() => document.getElementById('vbPg').textContent === '2 / 3' && document.getElementById('vbI').naturalWidth > 0")
        assert page.evaluate("() => /pg=2/.test(document.getElementById('vbI').src)")
        page.keyboard.press("ArrowRight"); page.wait_for_function("() => document.getElementById('vbPg').textContent === '3 / 3' && /pg=3/.test(document.getElementById('vbI').src) && document.getElementById('vbI').complete")
        page.keyboard.press("ArrowRight"); page.wait_for_timeout(200)
        assert page.evaluate("() => document.getElementById('vbPg').textContent") == "3 / 3"
        page.keyboard.press("ArrowLeft"); page.keyboard.press("Home"); page.wait_for_function("() => document.getElementById('vbPg').textContent === '1 / 3'")
        assert page.evaluate("() => board.items.p0.page") == 2, "reading in the preview leaves the card's page alone"
        page.keyboard.press("Escape"); page.wait_for_function("() => !document.getElementById('vbig').classList.contains('open')")
        assert not errors, errors
        browser.close()


@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_pill_expand_opens_the_librarys_viewer_when_embedded(server, engine):
    """Owner 2026-10-06 (two screenshots): «the full-screen preview we have is THIS, the library's viewer with the rating panel, not the
    board's own window with the name and the page arrows». ⤢ on a PDF card inside the library opens that viewer on the card's page, where
    ‹ n / N › and PageDown step; the board's #vbig stays shut. (Alone, the board keeps its own window: the test above.)"""
    with playwright.sync_playwright() as p:
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1300, "height": 900}); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server}/?view=canvas")
        page.evaluate("() => { localStorage.clear(); localStorage.setItem('view', 'canvas'); }")
        page.goto(f"http://127.0.0.1:{server}/?view=canvas")
        page.wait_for_selector("#cvFrame")
        cv = next(f for f in page.frames if "/canvas" in f.url)
        cv.wait_for_function("() => typeof BOARD !== 'undefined' && EL.get('p0') && EL.get('p0').classList.contains('pdf') && EL.get('p0').querySelector('.kd .kt')", timeout=20000)
        cv.evaluate("() => { board.items.p0.page = 2; render(); }")
        off = page.evaluate("() => { const r = document.getElementById('cvFrame').getBoundingClientRect(); return [r.left, r.top]; }")
        c = cv.evaluate("() => { const r = EL.get('p0').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        page.mouse.move(off[0] + c[0], off[1] + c[1])
        cv.wait_for_function("() => { const f = EL.get('p0').querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 8; }")
        k = cv.evaluate("() => { const r = EL.get('p0').querySelector('.kd .kf').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        page.mouse.click(off[0] + k[0], off[1] + k[1])
        page.wait_for_function("() => document.getElementById('viewer').classList.contains('open')", timeout=15000)
        page.wait_for_function("() => document.getElementById('pgN').textContent === '2 / 3' && /pg=2/.test(document.getElementById('big').src)")
        assert page.locator("#viewer #verdicts").count() == 1, "the viewer with the rating panel"
        assert cv.evaluate("() => !VBIG && !document.querySelector('#vbig').classList.contains('open')")
        page.keyboard.press("PageDown"); page.wait_for_function("() => document.getElementById('pgN').textContent === '3 / 3' && /pg=3/.test(document.getElementById('big').src)")
        assert cv.evaluate("() => board.items.p0.page") == 2, "reading in the viewer leaves the card's page alone"
        page.keyboard.press("Escape"); page.wait_for_function("() => !document.getElementById('viewer').classList.contains('open')")
        assert not errors, errors
        browser.close()


@pytest.fixture
def server_one(tmp_path):
    yield from run_server(tmp_path, board_items={"p1": {"path": "a/one.pdf", "x": 0, "y": 0, "w": 260, "ar": 0.75, "crop": None}})


@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_one_page_pdf_has_no_arrows_on_the_card_or_in_the_viewer(server_one, engine):
    """Owner 2026-10-06 (screenshot): a 1-page PDF showed «‹ 1 / 1 ›», but there is nothing to step. The card's pill has only the kind
    mark «PDF» and ⤢ on hover; the library's viewer has no page bar over the picture (the 3-page one keeps both)."""
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server_one)
        page.wait_for_function("() => EL.get('p1') && EL.get('p1').classList.contains('pdf') && EL.get('p1').querySelector('.kd .kt') && EL.get('p1').querySelector('.kd .kt').textContent === 'PDF'")
        assert page.evaluate("() => EL.get('p1').querySelectorAll('.kd .kb').length") == 0, "no arrows"
        assert page.evaluate("() => !!EL.get('p1').querySelector('.kd .kf')"), "⤢ stays"
        browser.close()
        browser = launch(p, engine)
        page = browser.new_page(viewport={"width": 1300, "height": 900})
        page.goto(f"http://127.0.0.1:{server_one}/?view=lib"); page.evaluate("() => localStorage.clear()")
        page.goto(f"http://127.0.0.1:{server_one}/?view=lib"); page.wait_for_selector("#list .card")
        page.locator("#list .card", has_text="one").first.click(); page.wait_for_selector("#viewer.open")
        page.wait_for_function("() => document.getElementById('pgN').textContent === '1 / 1'")
        assert not page.evaluate("() => document.getElementById('pgbar').classList.contains('on')")
        page.wait_for_function("() => getComputedStyle(document.getElementById('pgbar')).opacity === '0'")   # the bar is faded out, not drawn
        assert not errors, errors
        browser.close()


@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_board_pill_folds_on_a_narrow_card(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.wait_for_function("() => EL.get('p0') && EL.get('p0').classList.contains('pdf')")
        assert not page.evaluate("() => EL.get('p0').classList.contains('vnarrow')")
        page.evaluate("() => { cam.z = 0.3; render(); }"); page.wait_for_timeout(500)
        assert page.evaluate("() => EL.get('p0').classList.contains('vnarrow')"), "under 104 px the pill is a circle, like the video's"
        assert not errors, errors
        browser.close()


@needs_renderer
@pytest.mark.parametrize("engine", ENGINES)
def test_split_into_pages(server, engine):
    with playwright.sync_playwright() as p:
        browser, page, errors = open_board(p, engine, server)
        page.wait_for_function("() => EL.get('p0') && EL.get('p0').querySelector('.kd .kt') && EL.get('p0').querySelector('.kd .kt').textContent === '1 / 3'")
        c = page.evaluate("() => { const r = EL.get('p0').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        page.mouse.click(*c); page.wait_for_function("() => sel.has('p0')")
        page.wait_for_selector(".tidy [data-split]")
        label = page.locator(".tidy [data-split]").inner_text()
        assert "Split into pages (3)" in label and page.evaluate("() => !!document.querySelector('.tidy [data-split] > kbd')")
        page.click(".tidy [data-split]")
        page.wait_for_function("() => Object.keys(board.items).length === 3")
        d = page.evaluate("() => ({ items: Object.values(board.items), groups: Object.values(board.groups), sel: [...sel] })")
        assert [i["page"] for i in d["items"]] == [1, 2, 3] and all(i["pageFixed"] and i["path"] == "a/doc.pdf" for i in d["items"])
        assert len(d["groups"]) == 1 and d["groups"][0]["title"] == "doc" and len(d["groups"][0]["members"]) == 3
        xs = [i["x"] for i in d["items"]]; assert xs == sorted(xs) and len({i["y"] for i in d["items"]}) == 1 and all(i["w"] == 260 for i in d["items"]), "one tidy row, the card's width"
        assert page.evaluate("() => sel.size === 1 && !!board.groups[[...sel][0]]"), "the new group is selected"
        ids = page.evaluate("() => Object.keys(board.items)")
        for n, id in enumerate(ids, 1):
            page.wait_for_function("id => EL.get(id) && EL.get(id).querySelector('.kd .kt') && /^p\\. /.test(EL.get(id).querySelector('.kd .kt').textContent)", arg=id)
            assert pill(page, id) == f"p. {n}" and page.evaluate("id => EL.get(id).querySelectorAll('.kd .kb').length", id) == 0, "no stepping on a fixed page"
            if n > 1: page.wait_for_function("([id, n]) => { const i = EL.get(id).querySelector('img'); return i.src.includes('pg=' + n) && i.complete && i.naturalWidth > 0; }", arg=[id, n])
            src, *rgb = card_color(page, id); assert near(tuple(rgb[:3]), COLORS[n - 1]), (n, rgb)
        # ⤢ on a fixed card opens the preview on its page; stepping there does not touch the card
        page.evaluate("id => { sel = new Set([id]); render(); }", ids[1])
        page.mouse.move(*page.evaluate("id => { const r = EL.get(id).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", ids[1]))
        page.wait_for_function("id => { const f = EL.get(id).querySelector('.kd .kf'); return f && f.getBoundingClientRect().width > 8; }", arg=ids[1])
        page.mouse.click(*page.evaluate("id => { const r = EL.get(id).querySelector('.kd .kf').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", ids[1]))
        page.wait_for_function("() => document.getElementById('vbPg').textContent === '2 / 3'")
        page.keyboard.press("ArrowRight"); page.keyboard.press("Escape")
        assert page.evaluate("id => board.items[id].page", ids[1]) == 2
        # one undo brings the single card back
        page.mouse.click(5, 790)
        page.keyboard.press("Control+z")
        page.wait_for_function("() => Object.keys(board.items).length === 1 && !!board.items.p0 && Object.keys(board.groups).length === 0")
        assert not errors, errors
        browser.close()


@pytest.mark.parametrize("engine", ENGINES)
def test_empty_files_are_not_dropped_on_the_board(tmp_path, engine):
    for port in run_server(tmp_path, board_items={}):
        with playwright.sync_playwright() as p:
            browser = launch(p, engine)
            page = browser.new_page(viewport={"width": 1200, "height": 800}); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            url = f"http://127.0.0.1:{port}/canvas.html?board=main"
            page.goto(url); page.evaluate("() => { localStorage.clear(); localStorage.setItem('cv.nolib', '1'); }"); page.goto(url)
            page.wait_for_function("() => typeof BOARD !== 'undefined' && byPath.size >= 6")
            assert page.evaluate("() => byPath.get('a/zero1.png').empty === true")
            page.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text/x-frame', 'a/zero1.png'); dt.setData('text/x-frames', JSON.stringify(['a/zero1.png', 'a/zero2.png']));
              stage.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, clientX: 400, clientY: 300, bubbles: true, cancelable: true })); }""")
            page.wait_for_timeout(500)
            assert page.evaluate("() => Object.keys(board.items).length") == 0, "empty files are not pictures to place"
            assert "2 empty files stay in the library" in page.evaluate("() => document.body.innerText")
            # a real picture is still placed
            page.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text/x-frame', 'a/ok.png'); dt.setData('text/x-frames', JSON.stringify(['a/ok.png', 'a/zero2.png']));
              stage.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, clientX: 400, clientY: 300, bubbles: true, cancelable: true })); }""")
            page.wait_for_function("() => Object.values(board.items).filter(i => i.path === 'a/ok.png').length === 1")
            assert page.evaluate("() => Object.keys(board.items).length") == 1
            assert not errors, errors
            browser.close()
