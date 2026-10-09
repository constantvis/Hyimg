#!/bin/bash
# Every check of Hyimg's four repositories in one command (owner 2026-10-06: «делай юнит тесты, тесты ui, валидаторы, консистентный
# design валидатор»), with a short table at the end.
#
#   scripts/check.sh                 --fast on the four repositories
#   scripts/check.sh --fast [repo…]  the static validator (scripts/validate.py) and the unit tests (tests/unit: pytest and node --test): seconds
#   scripts/check.sh --full [repo…]  and every Playwright suite of the repositories (tests/*.py, the design audit among them): minutes
#   scripts/check.sh --staged        the pre-commit hook's check: the validator on the staged files of this repository, its unit tests
# repo: hyimg, hyimg-frames, hyimg-3d-studio, hyimg-dev-studio (a name or a path). The core's tests run with HY_TEST_ONLY_PLUGINS=1
# (tests/conftest.py), so the plugins installed on this Mac never take part; a plugin's suite mounts its own working copy itself.
# Exit status: 0 everything passed, 1 something failed.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HYIMG="$(dirname "$HERE")"
REPOS_DIR="$(dirname "$HYIMG")"
ALL=(hyimg hyimg-frames hyimg-3d-studio hyimg-dev-studio)
MODE=fast; REPOS=(); LABEL=""
for a in "$@"; do
  case "$a" in
    --fast) MODE=fast ;; --full) MODE=full ;; --staged) MODE=staged ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) n="$(basename "$a")"; [ -d "$REPOS_DIR/$n" ] || { echo "check: no repository $a" >&2; exit 2; }; REPOS+=("$n") ;;
  esac
done
[ ${#REPOS[@]} -eq 0 ] && REPOS=("${ALL[@]}")
PY="${PYTHON:-python3}"
export HY_TEST_ONLY_PLUGINS=1 PYTHONDONTWRITEBYTECODE=1 HYIMG_REPO="$HYIMG"
LOG="$(mktemp -d "${TMPDIR:-/tmp}/hycheck.XXXXXX")"
ROWS=(); FAIL=0

secs() { "$PY" -c "import time; print(f'{time.time() - $1:.1f}')"; }
now() { "$PY" -c "import time; print(time.time())"; }
# run <label> <cmd…>: its output in a log, a row in the table; the tail of a failing log is printed
run() {
  local label="$1"; shift
  local t0; t0="$(now)"; local f="$LOG/$(echo "$label" | tr ' /' '__').log"
  "$@" >"$f" 2>&1; local rc=$?
  local summary; summary="$(grep -vE "^[[:space:]]*(not )?ok " "$f" | grep -E "passed|failed|no tests ran|validate:|^# (pass|fail) " | tail -3 | tr '\n' ' ' | sed 's/  */ /g' | cut -c1-90)"
  if [ $rc -eq 5 ]; then rc=0; summary="no tests"; fi   # pytest: nothing collected
  if [ $rc -ne 0 ]; then FAIL=1; echo "---- $label failed ($f)"; tail -25 "$f"; fi
  ROWS+=("$(printf '%-34s %-5s %6ss  %s' "$label" "$([ $rc -eq 0 ] && echo ok || echo FAIL)" "$(secs "$t0")" "$summary")")
}

T0="$(now)"
if [ "$MODE" = staged ]; then
  # the hook: the files about to be committed in this repository (added, copied, modified, renamed), what the validator reads
  REPO="$(git rev-parse --show-toplevel)"; NAME="$(basename "$REPO")"
  FILES=(); while IFS= read -r f; do
    case "$f" in *.html|*.htm|*.js|*.mjs|*.cjs|*.ts|*.css|*.py|*.swift|*.m|*.mm|*.h|*.sh) FILES+=("$REPO/$f") ;; esac
  done < <(git diff --cached --name-only --diff-filter=ACMR)
  if [ ${#FILES[@]} -gt 0 ]; then run "validate (staged, $NAME)" "$PY" "$HYIMG/scripts/validate.py" -q "${FILES[@]}"; fi
  REPOS=("$NAME"); MODE=units; LABEL=staged
fi

if [ "$MODE" = fast ] || [ "$MODE" = full ]; then
  paths=(); for r in "${REPOS[@]}"; do paths+=("$REPOS_DIR/$r"); done
  run "validate (${#REPOS[@]} repos)" "$PY" "$HYIMG/scripts/validate.py" -q "${paths[@]}"
fi

for r in "${REPOS[@]}"; do
  d="$REPOS_DIR/$r"
  [ -d "$d/tests/unit" ] && run "$r unit (pytest)" "$PY" -m pytest -q -p no:cacheprovider "$d/tests/unit"
  # pytest takes its cache folder from tests/procguard.py; node gets one of the run's own, never ~/Library/Caches/Hyimg
  [ -d "$d/tests/unit/js" ] && command -v node >/dev/null && run "$r unit (node)" env HYIMG_CACHE_ROOT="$LOG/cache" node --test "$d/tests/unit/js/"
  [ "$r" = hyimg ] && [ -f "$d/tests/test_validate.py" ] && run "hyimg validator tests" "$PY" -m pytest -q -p no:cacheprovider "$d/tests/test_validate.py" "$d/tests/test_validate_icons.py"
  [ "$r" = hyimg ] && [ -f "$d/tests/test_validate_size.py" ] && run "hyimg file-size tests" "$PY" -m pytest -q -p no:cacheprovider "$d/tests/test_validate_size.py"
  # the primitives' types (review/ui/hy, JSDoc checked by tsc --noEmit --checkJs): the TypeScript on this Mac, nothing is downloaded
  if [ "$r" = hyimg ] && [ -f "$d/jsconfig.json" ]; then
    TSC="${TSC:-$(command -v tsc || ls "$HOME"/.nvm/versions/node/*/bin/tsc 2>/dev/null | tail -1)}"
    if [ -n "$TSC" ]; then run "hyimg types (tsc)" "$TSC" -p "$d/jsconfig.json"; else ROWS+=("$(printf '%-34s %-5s %6s   %s' "hyimg types (tsc)" skip "" "no tsc on this machine")"); fi
  fi
done

if [ "$MODE" = full ]; then
  for r in "${REPOS[@]}"; do
    d="$REPOS_DIR/$r"
    suites=(); for f in "$d"/tests/test_*.py; do [ -f "$f" ] && [ "$(basename "$f")" != test_validate.py ] && [ "$(basename "$f")" != test_validate_icons.py ] && suites+=("$f"); done
    [ ${#suites[@]} -eq 0 ] && continue
    # each repository's suites from its own folder (the core's tests/conftest.py isolates the plugins; a plugin's suite mounts its copy)
    run "$r playwright" bash -c 'cd "$1" && shift && exec "$@"' _ "$d" "$PY" -m pytest -q -p no:cacheprovider "${suites[@]}"
  done
fi

echo
printf '%-34s %-5s %7s  %s\n' "check" "" "time" "result"
for row in "${ROWS[@]}"; do echo "$row"; done
echo "check --${LABEL:-$MODE}: $([ $FAIL -eq 0 ] && echo passed || echo FAILED) in $(secs "$T0") s (logs: $LOG)"
exit $FAIL
