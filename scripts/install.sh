#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESTINATION="${HYIMG_INSTALL_DIR:-$HOME/Applications}"
APP="$ROOT/dist/Hyimg.app"
if [[ ! -d "$APP" ]]; then
  printf 'Сначала выполните ./build.sh\n' >&2
  exit 1
fi
mkdir -p "$DESTINATION"
if [[ -e "$DESTINATION/Hyimg.app" ]]; then
  EXPECTED=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$DESTINATION/Hyimg.app/Contents/Info.plist")
  ACTUAL=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")
  if [[ "$EXPECTED" != "$ACTUAL" ]]; then
    printf 'В месте установки уже существует другое приложение.\n' >&2
    exit 1
  fi
  mv "$DESTINATION/Hyimg.app" "$DESTINATION/Hyimg.backup.$(date +%Y%m%d-%H%M%S).app"
fi
ditto "$APP" "$DESTINATION/Hyimg.app"
codesign --verify --deep --strict "$DESTINATION/Hyimg.app"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DESTINATION/Hyimg.app"
printf 'Установлено: %s/Hyimg.app\n' "$DESTINATION"
# Each install leaves the previous app beside it as Hyimg.backup.<date>-<time>.app, about 300 MB each (2026-10-07: 59 of them, 17 GB).
# The newest HYIMG_KEEP_BACKUPS (2) stay, older ones go to the macOS Trash, never rm (review/storage_clean.py trash_backups).
# HYIMG_KEEP_BACKUPS=all keeps every copy.
if [[ "${HYIMG_KEEP_BACKUPS:-2}" != "all" ]]; then
  if OUT=$(HYIMG_INSTALL_DIR="$DESTINATION" python3 "$ROOT/review/storage.py" backups --keep "${HYIMG_KEEP_BACKUPS:-2}" 2>&1); then
    printf 'Старые копии приложения: %s\n' "$OUT"
  else
    printf 'Старые копии не тронуты: %s\n' "$OUT" >&2
  fi
fi
