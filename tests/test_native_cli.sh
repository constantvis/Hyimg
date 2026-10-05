#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
BIN="$ROOT/dist/Hyimg.app/Contents/MacOS/Hyimg"
TMP="$(mktemp -d /private/tmp/hyimg-cli-test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir "$TMP/library"
"$BIN" --catalog "$TMP/projects.json" --register-project "$TMP/library" --name "CLI test" > "$TMP/registered.json"
"$BIN" --catalog "$TMP/projects.json" --register-project "$TMP/library" --name "Duplicate" > "$TMP/duplicate.json"
python3 - "$TMP" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
first = json.loads((root / 'registered.json').read_text())
second = json.loads((root / 'duplicate.json').read_text())
projects = json.loads((root / 'projects.json').read_text())
assert first == second == projects[0] and len(projects) == 1
assert first['libraryRoot'] == str((root / 'library').resolve())
assert first['name'] == 'CLI test'
print('PASS: compiled app CLI registers and deduplicates a project in explicit catalog')
PY
if "$BIN" --catalog relative.json --register-project "$TMP/library" > "$TMP/invalid.log" 2>&1; then
  cat "$TMP/invalid.log"
  exit 1
fi
rg -q 'должен быть абсолютным' "$TMP/invalid.log"
printf 'PASS: compiled app CLI rejects relative catalog path\nNATIVE_CLI_TESTS_PASSED\n'
