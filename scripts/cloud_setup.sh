#!/usr/bin/env bash
# Prepares a Claude Code cloud machine (Linux) for Hyimg: the Python server, its tests and the canvas tests in Chromium.
# Runs from the SessionStart hook in .claude/settings.json, only when CLAUDE_CODE_REMOTE=true; safe to run again.
# The Mac app (native/, build.sh, tests/test_native*.sh, tests/test_webkit.sh) needs macOS and is not built here.
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "$(dirname "$0")/.."
python3 -m pip install --quiet --disable-pip-version-check pillow pytest playwright >/dev/null 2>&1 \
  || python3 -m pip install --quiet --disable-pip-version-check --break-system-packages pillow pytest playwright
# Chromium for tests/test_canvas_pages.py; without it those tests skip themselves
python3 -m playwright install --with-deps chromium >/dev/null 2>&1 || python3 -m playwright install chromium >/dev/null 2>&1 || true
echo "Hyimg cloud: python $(python3 -c 'import sys;print(sys.version.split()[0])'), node $(node --version 2>/dev/null || echo none), pillow and pytest ready"
