"""PDF pages as pictures (owner 2026-10-06: «PDFs appear in the library and can be put on the board with the first page as their picture;
the card steps through the pages»).

The app's Chromium (CEF) has no PDF plugin, so a page is served as an image, one page at a time, on demand. Measured on this Mac
(8 pages of A4, a 12 MB 8-page cover, a 4 MB presentation page, a label; 1600 px on the long side, one page per call):
  PDFKit through osascript (JXA)   0.23 to 0.46 s, any page, page count and every page's shape in the same call, always on a Mac
  poppler pdftoppm                 0.04 to 1.78 s (the 4 MB presentation page took 1.78 s), only if Homebrew has it
  qlmanage / sips                  0.12 to 0.32 s, the first page only
PDFKit is Apple's own renderer (what Preview draws with), always there and the steadiest on heavy pages, so it is the first choice;
poppler follows when osascript cannot run (a server without a window session); the caller draws a grey card when both fail.
Nothing is installed or downloaded. A page is drawn once per version of its file and kept like a thumbnail (server.py pdf_master).
"""
import json
import os
import shutil
import subprocess

# page: 1-based; 0 only reads the page count and the shape of every page. Prints one line of JSON.
_JXA = r"""
ObjC.import('PDFKit'); ObjC.import('AppKit'); ObjC.import('Foundation');
function run(a) {
  try {
    var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(a[0]));
    if (!doc || !doc.pageCount) return JSON.stringify({ error: "unreadable" });
    if (doc.isLocked) return JSON.stringify({ error: "locked" });
    var n = Number(doc.pageCount), page = parseInt(a[1], 10), side = parseFloat(a[3] || "1600"), ars = [], k, p, b, r;
    for (k = 0; k < Math.min(n, 2000); k++) {   // a shape per page: pages of a document may differ
      p = doc.pageAtIndex(k); b = p.boundsForBox($.kPDFDisplayBoxCropBox); r = p.rotation;
      ars.push(b.size.height ? Math.round((r % 180 ? b.size.height / b.size.width : b.size.width / b.size.height) * 10000) / 10000 : 1);
    }
    if (page > 0) {
      p = doc.pageAtIndex(Math.min(n, page) - 1); b = p.boundsForBox($.kPDFDisplayBoxCropBox);
      var w = b.size.width, h = b.size.height; if (p.rotation % 180) { w = b.size.height; h = b.size.width; }
      var s = side / Math.max(w, h), img = p.thumbnailOfSizeForBox($.NSMakeSize(Math.max(1, Math.round(w * s)), Math.max(1, Math.round(h * s))), $.kPDFDisplayBoxCropBox);
      var rep = $.NSBitmapImageRep.imageRepWithData(img.TIFFRepresentation);
      rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $({})).writeToFileAtomically(a[2], true);
    }
    return JSON.stringify({ pages: n, ars: ars });
  } catch (e) { return JSON.stringify({ error: String(e).slice(0, 120) }); }
}
"""


class PdfError(Exception):
    pass


def _tool(name):
    # the app starts the server without the shell's PATH: Homebrew's tools are looked for where they live
    return shutil.which(name) or next((p for p in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}") if os.path.exists(p)), None)


def _jxa(full, page, out="", side=1600):
    osa = shutil.which("osascript") or "/usr/bin/osascript"
    if not os.path.exists(osa):
        return None
    try:
        r = subprocess.run([osa, "-l", "JavaScript", "-e", _JXA, "--", full, str(page), out, str(side)], capture_output=True, text=True, timeout=90)
        line = (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else ""
        d = json.loads(line)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None
    if d.get("error") in ("locked", "unreadable"):
        raise PdfError(d["error"])
    if "pages" in d:
        d["pages"] = int(d["pages"])
    return d if "pages" in d and (page == 0 or os.path.exists(out)) else None


def _poppler(full, page, out="", side=1600):
    info = _tool("pdfinfo"); ppm = _tool("pdftoppm")
    if not info:
        return None
    try:
        t = subprocess.run([info, "-f", "1", "-l", "2000", full], capture_output=True, text=True, timeout=60).stdout
        n = next((int(x.split(":")[1]) for x in t.splitlines() if x.startswith("Pages:")), 0)
        if not n:
            raise PdfError("unreadable")
        ars = []
        for x in t.splitlines():
            if x.startswith("Page") and "size:" in x:
                w, h = [float(v) for v in x.split("size:")[1].split("pts")[0].replace("x", " ").split()[:2]]
                ars.append(round(w / h, 4) if h else 1)
        if page > 0:
            if not ppm:
                return None
            stem = out[:-4]
            subprocess.run([ppm, "-f", str(min(n, page)), "-l", str(min(n, page)), "-scale-to", str(side), "-png", "-singlefile", full, stem], capture_output=True, timeout=90)
            if not os.path.exists(out):
                return None
        return {"pages": n, "ars": ars}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def read(full, page=0, out="", side=1600):
    """{"pages": n, "ars": [width / height of each page]}; page > 0 also draws that page (1-based) as a PNG into `out`, side px on its
    long side. PdfError for a PDF that is locked or cannot be read, and when no way of drawing it exists on this machine"""
    for way in ((_poppler,) if os.environ.get("HYIMG_PDF_ENGINE") == "poppler" else (_jxa, _poppler)):   # the variable: a test of the second way
        d = way(full, page, out, side)
        if d:
            return d
    raise PdfError("no renderer")


def cached(base):
    """the page count and shapes saved by an earlier read (<base>.pdfinfo.json), else None; a few bytes, read at every scan"""
    try:
        d = json.load(open(base + ".pdfinfo.json", encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("pages") else None
    except (OSError, ValueError):
        return None


def remember(base, d):
    try:
        tmp = base + ".pdfinfo.json.tmp"
        json.dump({"pages": d["pages"], "ars": d.get("ars", [])}, open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, base + ".pdfinfo.json")
    except OSError:
        pass
