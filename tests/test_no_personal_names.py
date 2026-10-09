"""Nothing personal in the repository (owner 2026-10-07: the repositories are public; names live only in the person's own settings,
~/Library/Application Support/Hyimg). The two people who use Hyimg now type their names into the app themselves: no code, test or doc
names them, pre-fills them or shows them as an example. The names are written here as code points, so this file does not name them
either. The public export's scrub list (scripts/public_scrub.json) names what to remove and is the one file allowed to."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEMS = ["".join(map(chr, c)) for c in ((0x413, 0x435, 0x43E, 0x440, 0x433, 0x438),                  # the partner's first name, its stem
                                         (0x41A, 0x43E, 0x43D, 0x441, 0x442, 0x430, 0x43D, 0x442, 0x438, 0x43D),   # the owner's, in Russian
                                         (0x4B, 0x6F, 0x6E, 0x73, 0x74, 0x61, 0x6E, 0x74, 0x69, 0x6E))]   # and in Latin letters
NAMES = re.compile("|".join(STEMS), re.IGNORECASE)
ALLOWED = {"scripts/public_scrub.json"}


def test_no_personal_names_in_the_repository():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    hits = []
    for rel in filter(None, files):
        p = ROOT / rel
        if rel in ALLOWED or not p.is_file() or p.stat().st_size > 5_000_000: continue
        try: text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue   # pictures, fonts and other binaries
        hits += [f"{rel}:{n}" for n, line in enumerate(text.splitlines(), 1) if NAMES.search(line)]
    assert not hits, "personal names in the repository: " + ", ".join(hits[:20])
