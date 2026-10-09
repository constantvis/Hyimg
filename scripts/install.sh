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
LSREG=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
# hyimg:// links (native/Links.swift, owner 2026-10-07) belong to this copy only: the copies kept beside it (Hyimg.backup.*.app) and the
# build in dist/ carry the scheme too, and macOS could hand a link to any of them. A backup loses CFBundleURLTypes from its Info.plist
# (signed again, so it still opens) and is unregistered, before the oldest go to the Trash below; the build in dist/ is unregistered.
for b in "$DESTINATION"/Hyimg.backup.*.app; do
  [[ -d "$b" ]] || continue
  if /usr/libexec/PlistBuddy -c 'Print :CFBundleURLTypes' "$b/Contents/Info.plist" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c 'Delete :CFBundleURLTypes' "$b/Contents/Info.plist"
    codesign --force --sign - "$b" >/dev/null 2>&1 || printf 'Копия %s не подписана заново\n' "$b" >&2
  fi
  "$LSREG" -u "$b" >/dev/null 2>&1 || true
done
"$LSREG" -u "$APP" >/dev/null 2>&1 || true
"$LSREG" -f "$DESTINATION/Hyimg.app"
printf 'Установлено: %s/Hyimg.app\n' "$DESTINATION"
# who answers hyimg:// now: only this copy is expected (the LaunchServices database, its bundles' «claimed schemes»)
OWNERS=$("$LSREG" -dump 2>/dev/null | awk '/^path:/ { sub(/^path: */, ""); sub(/ \(0x[0-9a-f]+\)$/, ""); p = $0 } /^claimed schemes:.*hyimg:/ { print p }' | sort -u || true)
# builds made in temporary worktrees (/private/tmp, …/dist/) get registered by macOS too (2026-10-08: two of them claimed hyimg://):
# any other Hyimg.app that claims the scheme is unregistered, and the owners are read again
while IFS= read -r o; do
  [[ -n "$o" && "$o" != "$DESTINATION/Hyimg.app" && "$o" == */Hyimg.app ]] && { "$LSREG" -u "$o" >/dev/null 2>&1 || true; }
done <<< "$OWNERS"
OWNERS=$("$LSREG" -dump 2>/dev/null | awk '/^path:/ { sub(/^path: */, ""); sub(/ \(0x[0-9a-f]+\)$/, ""); p = $0 } /^claimed schemes:.*hyimg:/ { print p }' | sort -u || true)
if [[ "$OWNERS" == "$DESTINATION/Hyimg.app" ]]; then printf 'hyimg:// открывает %s\n' "$OWNERS"
else printf 'hyimg:// заявлен не только этой копией:\n%s\n' "$OWNERS" >&2; fi
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
