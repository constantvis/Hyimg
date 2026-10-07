"""A PDF's page count and pages as pictures (pdfpages.py, server.pdf_info / pdf_master / pdf_pages_known). The renderers (osascript
PDFKit, poppler) are never run: subprocess.run is replaced by a recorder that answers as the tool would."""
import json
import os
import subprocess

import pytest
from PIL import Image

import pdfpages
import server


class Run:
    """a stand-in for subprocess.run: answers[tool name] -> (stdout, stderr) or an exception; writes `out` files when told"""
    def __init__(self, answers, writes=()):
        self.answers, self.writes, self.calls = answers, writes, []

    def __call__(self, args, **kw):
        self.calls.append(args)
        tool = os.path.basename(args[0])
        a = self.answers.get(tool, ("", ""))
        if isinstance(a, BaseException): raise a
        for path in self.writes: open(path, "wb").write(b"png")
        return subprocess.CompletedProcess(args, 0, a[0], a[1])


@pytest.fixture
def tools(monkeypatch):
    def use(answers, writes=(), have=("osascript", "pdfinfo", "pdftoppm")):
        r = Run(answers, writes)
        monkeypatch.setattr(pdfpages.subprocess, "run", r)
        monkeypatch.setattr(pdfpages.shutil, "which", lambda n: f"/fake/{n}" if n in have else None)
        real_exists = os.path.exists
        monkeypatch.setattr(pdfpages.os.path, "exists", lambda p: p.startswith("/fake/") and os.path.basename(p) in have or (not p.startswith(("/fake/", "/opt/homebrew", "/usr/local/bin", "/usr/bin/osascript")) and real_exists(p)))
        return r
    monkeypatch.delenv("HYIMG_PDF_ENGINE", raising=False)
    return use


def test_pdfkit_is_asked_first_for_the_page_count_and_shapes(tools):
    r = tools({"osascript": ('{"pages": "3", "ars": [0.7071, 1.4142, 1]}\n', "")})
    assert pdfpages.read("/x.pdf") == {"pages": 3, "ars": [0.7071, 1.4142, 1]}
    assert r.calls[0][:3] == ["/fake/osascript", "-l", "JavaScript"] and r.calls[0][-4:] == ["/x.pdf", "0", "", "1600"]


def test_only_the_last_line_of_pdfkits_answer_counts(tools):
    tools({"osascript": ("warning: something\n{\"pages\": 2, \"ars\": []}", "")})
    assert pdfpages.read("/x.pdf")["pages"] == 2


@pytest.mark.parametrize("err", ["locked", "unreadable"])
def test_a_locked_or_unreadable_pdf_is_a_pdf_error(tools, err):
    tools({"osascript": (json.dumps({"error": err}), "")})
    with pytest.raises(pdfpages.PdfError, match=err):
        pdfpages.read("/x.pdf")


INFO = "Title: x\nPages:          2\nPage    1 size: 595.276 x 841.89 pts (A4)\nPage    2 size: 842 x 595 pts\n"


@pytest.mark.parametrize("osa", [("", ""), ("not json", ""), ('{"error": "TypeError: x"}', ""), subprocess.TimeoutExpired("osascript", 90), OSError("no")])
def test_poppler_follows_when_pdfkit_gives_nothing_usable(tools, osa):
    tools({"osascript": osa, "pdfinfo": (INFO, "")})
    assert pdfpages.read("/x.pdf") == {"pages": 2, "ars": [round(595.276 / 841.89, 4), round(842 / 595, 4)]}


def test_the_engine_variable_skips_pdfkit(tools, monkeypatch):
    r = tools({"osascript": ('{"pages": 9}', ""), "pdfinfo": (INFO, "")})
    monkeypatch.setenv("HYIMG_PDF_ENGINE", "poppler")
    assert pdfpages.read("/x.pdf")["pages"] == 2
    assert all(os.path.basename(c[0]) != "osascript" for c in r.calls)


def test_poppler_saying_no_pages_is_an_unreadable_pdf(tools):
    tools({"osascript": ("", ""), "pdfinfo": ("Syntax Error\n", "")})
    with pytest.raises(pdfpages.PdfError, match="unreadable"):
        pdfpages.read("/x.pdf")


def test_with_no_renderer_on_the_machine_read_says_so(tools):
    tools({}, have=())
    with pytest.raises(pdfpages.PdfError, match="no renderer"):
        pdfpages.read("/x.pdf")


def test_a_page_past_the_end_is_drawn_as_the_last_page_by_poppler(tools, tmp_path):
    out = tmp_path / "p.png"
    r = tools({"osascript": ("", ""), "pdfinfo": (INFO, "")}, writes=[str(out)])
    assert pdfpages.read("/x.pdf", 7, str(out), 900)["pages"] == 2
    ppm = r.calls[-1]
    assert os.path.basename(ppm[0]) == "pdftoppm" and ppm[1:5] == ["-f", "2", "-l", "2"] and "900" in ppm and ppm[-1] == str(tmp_path / "p")


def test_a_page_pdfkit_said_it_drew_but_did_not_write_falls_through(tools, tmp_path):
    out = tmp_path / "p.png"
    tools({"osascript": ('{"pages": 1, "ars": [1]}', ""), "pdfinfo": ("", "")}, have=("osascript", "pdfinfo"))
    with pytest.raises(pdfpages.PdfError):
        pdfpages.read("/x.pdf", 1, str(out))


def test_remembered_page_counts_are_read_back_and_bad_ones_ignored(tmp_path):
    base = str(tmp_path / "doc")
    assert pdfpages.cached(base) is None
    pdfpages.remember(base, {"pages": 4, "ars": [1, 2], "extra": 1})
    assert pdfpages.cached(base) == {"pages": 4, "ars": [1, 2]}
    for text in ('{"pages": 0}', "[4]", "{nope"):
        open(base + ".pdfinfo.json", "w").write(text)
        assert pdfpages.cached(base) is None


def test_remember_into_a_missing_folder_is_quietly_skipped(tmp_path):
    pdfpages.remember(str(tmp_path / "none" / "doc"), {"pages": 1})


class TestServerPdf:
    def test_an_empty_pdf_has_no_pages_and_no_renderer_runs(self, lib, monkeypatch):
        (lib / "e.pdf").write_bytes(b"")
        monkeypatch.setattr(server.pdfpages, "read", lambda *a, **k: pytest.fail("no renderer for an empty file"))
        assert server.pdf_info("e.pdf") == {"pages": 0, "ars": [], "error": "empty"}

    def test_a_pdfs_page_count_is_read_once_per_version_of_the_file(self, lib, monkeypatch):
        (lib / "d.pdf").write_bytes(b"%PDF")
        calls = []
        monkeypatch.setattr(server.pdfpages, "read", lambda full, *a: calls.append(full) or {"pages": 5, "ars": [1] * 5})
        assert server.pdf_pages_known("d.pdf") == 0
        assert server.pdf_info("d.pdf") == {"pages": 5, "ars": [1] * 5}
        assert server.pdf_info("d.pdf")["pages"] == 5 and len(calls) == 1
        assert server.pdf_pages_known("d.pdf") == 5
        os.utime(lib / "d.pdf", (10, 10))
        server.pdf_info("d.pdf")
        assert len(calls) == 2

    def test_a_locked_pdf_reports_its_error(self, lib, monkeypatch):
        (lib / "l.pdf").write_bytes(b"%PDF")
        def locked(*a): raise pdfpages.PdfError("locked")
        monkeypatch.setattr(server.pdfpages, "read", locked)
        assert server.pdf_info("l.pdf") == {"pages": 0, "ars": [], "error": "locked"}

    def test_a_page_that_cannot_be_drawn_is_a_grey_card(self, lib, monkeypatch):
        (lib / "l.pdf").write_bytes(b"%PDF")
        def locked(*a): raise pdfpages.PdfError("locked")
        monkeypatch.setattr(server.pdfpages, "read", locked)
        out = server.pdf_master("l.pdf", 3)
        assert out.endswith(".pdf1.jpg")
        with Image.open(out) as im:
            assert im.size == (640, 640) and all(abs(a - b) <= 2 for a, b in zip(im.getpixel((5, 5)), (58, 58, 62)))

    def test_a_drawn_page_is_put_on_white_as_a_jpeg_and_clamped_to_the_last_page(self, lib, monkeypatch):
        (lib / "d.pdf").write_bytes(b"%PDF")
        def draw(full, page=0, out="", side=1600):
            if page: Image.new("RGBA", (40, 20), (0, 0, 0, 0)).save(out)
            return {"pages": 2, "ars": [2, 2]}
        monkeypatch.setattr(server.pdfpages, "read", draw)
        out = server.pdf_master("d.pdf", 9)
        assert out.endswith(".pdf2.jpg")
        with Image.open(out) as im:
            assert im.size == (40, 20) and im.getpixel((3, 3))[0] > 250
        assert server.pdf_master("d.pdf", 9) == out
