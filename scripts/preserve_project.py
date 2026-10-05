from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP = frozenset({"_thumbs", "__pycache__", "node_modules", ".git", "exports", "test-results"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".avif", ".heic", ".tiff"})

@dataclass(frozen=True, slots=True)
class Entry:
    path: str
    bytes: int
    sha256: str

def files(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory, children, names in os.walk(root):
        children[:] = sorted(child for child in children if child not in SKIP)
        found.extend(Path(directory) / name for name in sorted(names) if name != ".DS_Store")
    return found

def capture(root: Path, destination: Path, mounts: list[Path]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    entries: list[Entry] = []
    media: list[tuple[str, int, int]] = []
    with zipfile.ZipFile(destination / "metadata.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for label, source in [("project", root), *[(f"mount-{i}", mount) for i, mount in enumerate(mounts)]]:
            for path in files(source):
                relative = path.relative_to(source)
                archive_path = f"{label}/{relative.as_posix()}"
                if path.suffix.lower() in IMAGE_EXTENSIONS:
                    stat = path.stat()
                    media.append((archive_path, stat.st_size, stat.st_mtime_ns))
                    continue
                is_code = relative.parts[0] == "_review" and path.suffix in {".py", ".html", ".md", ".swift", ".sh"}
                is_metadata = path.suffix in {".json", ".jsonl"} or (relative.parts[0] == "_review" and "boards" in relative.parts and path.suffix == ".gz")
                if not (is_code or is_metadata):
                    continue
                content = path.read_bytes()
                entries.append(Entry(archive_path, len(content), hashlib.sha256(content).hexdigest()))
                archive.writestr(archive_path, content)
    manifest = {"libraryRoot": str(root), "mounts": [str(mount) for mount in mounts], "files": [asdict(entry) for entry in entries], "media": media}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(destination / "metadata.zip") as archive:
        for entry in entries:
            if hashlib.sha256(archive.read(entry.path)).hexdigest() != entry.sha256:
                raise RuntimeError(f"Snapshot checksum mismatch: {entry.path}")
    print(json.dumps({"snapshot": str(destination), "metadataFiles": len(entries), "metadataBytes": sum(entry.bytes for entry in entries), "mediaFilesLeftInPlace": len(media), "archiveVerified": True}, ensure_ascii=False))

def compare(snapshot: Path) -> None:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    roots = {"project": Path(manifest["libraryRoot"]), **{f"mount-{i}": Path(mount) for i, mount in enumerate(manifest["mounts"])}}
    changes: list[str] = []
    for entry in manifest["files"]:
        label, relative = entry["path"].split("/", 1)
        path = roots[label] / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            changes.append(entry["path"])
    media_changes: list[str] = []
    for relative, size, modified in manifest["media"]:
        label, name = relative.split("/", 1)
        path = roots[label] / name
        if not path.is_file() or (path.stat().st_size, path.stat().st_mtime_ns) != (size, modified):
            media_changes.append(relative)
    print(json.dumps({"metadataChanges": changes, "mediaChanges": media_changes, "checkedMetadata": len(manifest["files"]), "checkedMedia": len(manifest["media"])}, ensure_ascii=False))
    if changes or media_changes:
        raise SystemExit(1)

if __name__ == "__main__":
    if sys.argv[1] == "verify":
        compare(Path(sys.argv[2]))
    else:
        capture(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]), [Path(path).resolve(strict=True) for path in sys.argv[3:]])
