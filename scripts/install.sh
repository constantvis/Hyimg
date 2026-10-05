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
