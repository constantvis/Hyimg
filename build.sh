#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
if [[ $# -gt 0 && ( $# -ne 2 || "$1" != "--icon-only" ) ]]; then
  printf 'Usage: %s [--icon-only output-directory]\n' "$0" >&2
  exit 1
fi
SOURCE_ROOT="${HYIMG_SOURCE_ROOT:-$ROOT}"
APP="$ROOT/dist/Hyimg.app"
TMP="$(mktemp -d /private/tmp/hyimg-build.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
SWIFTC="$(xcrun --find swiftc)"
SDK="$(xcrun --show-sdk-path)"; TARGET="$(uname -m)-apple-macosx14.0"
"$SWIFTC" -module-cache-path "$TMP/modules" -sdk "$SDK" -target "$TARGET" "$ROOT/native/icon.swift" -framework AppKit -o "$TMP/icon"
if [[ "${1:-}" == "--icon-only" ]]; then
  "$TMP/icon" "$ROOT/native/assets/hyimg.svg" "$2"
  cp "$ROOT/native/assets/hyimg.svg" "$2/hyimg.svg"
  printf 'Built icons in %s\n' "$2"
  exit 0
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$TMP/png"
# Chromium (CEF) engine, optional (owner 2026-10-01): with the SDK found the app carries Chromium (~330 MB) and draws the
# projects with it; without it the stub keeps the same interface and Hyimg stays on WebKit. HYIMG_NO_CEF=1 forces that.
# The SDK: the "minimal" macOS build from https://cef-builds.spotifycdn.com unpacked in ~/Library/Caches/Hyimg, with
# libcef_dll_wrapper built by its CMake (see README); HYIMG_CEF points elsewhere.
CEF="${HYIMG_CEF:-$(ls -d "$HOME"/Library/Caches/Hyimg/cef_binary_*_macos$( [[ $(uname -m) == arm64 ]] && echo arm64 || echo x64 )_minimal 2>/dev/null | tail -1)}"
CEF_WRAPPER="$CEF/build/libcef_dll_wrapper/libcef_dll_wrapper.a"
CEF_LINK=()
if [[ -z "${HYIMG_NO_CEF:-}" && -n "$CEF" && -f "$CEF_WRAPPER" ]]; then
  CEF_FLAGS=(-std=c++20 -fno-exceptions -fno-rtti -fobjc-arc -O2 -isysroot "$SDK" -target "$TARGET" -I "$CEF" -I "$ROOT/native/cef")
  clang++ "${CEF_FLAGS[@]}" -c "$ROOT/native/cef/HyimgCEF.mm" -o "$TMP/cef.o"
  clang++ "${CEF_FLAGS[@]}" "$ROOT/native/cef/helper.mm" "$CEF_WRAPPER" -framework AppKit -o "$TMP/helper"
  CEF_LINK=("$CEF_WRAPPER" -lc++)
else
  CEF=""
  clang -fobjc-arc -O2 -isysroot "$SDK" -target "$TARGET" -I "$ROOT/native/cef" -c "$ROOT/native/cef/HyimgCEFStub.m" -o "$TMP/cef.o"
fi
"$SWIFTC" -module-cache-path "$TMP/modules" -swift-version 5 -sdk "$SDK" -target "$TARGET" -O \
  -import-objc-header "$ROOT/native/cef/HyimgCEF.h" \
  "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/ServerSession.swift" "$ROOT/native/SaveBarrier.swift" "$ROOT/native/Chrome.swift" "$ROOT/native/main.swift" \
  "$ROOT/native/Storage.swift" "$ROOT/native/StorageBridge.swift" \
  "$TMP/cef.o" ${CEF_LINK[@]+"${CEF_LINK[@]}"} -framework AppKit -framework WebKit -o "$APP/Contents/MacOS/Hyimg"
"$TMP/icon" "$ROOT/native/assets/hyimg.svg" "$TMP/png"
cp "$TMP/png/Hyimg.icns" "$APP/Contents/Resources/Hyimg.icns"
cp "$ROOT/native/assets/hyimg.svg" "$APP/Contents/Resources/hyimg.svg"
/usr/bin/plutil -create xml1 "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleExecutable -string Hyimg "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleIdentifier -string app.hyimg.desktop "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleName -string Hyimg "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleDisplayName -string Hyimg "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundlePackageType -string APPL "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleShortVersionString -string 1.0 "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleVersion -string 1 "$APP/Contents/Info.plist"
/usr/bin/plutil -insert CFBundleIconFile -string Hyimg "$APP/Contents/Info.plist"
/usr/bin/plutil -insert LSMinimumSystemVersion -string 14.0 "$APP/Contents/Info.plist"
/usr/bin/plutil -insert NSHighResolutionCapable -bool YES "$APP/Contents/Info.plist"
/usr/bin/plutil -insert NSPrincipalClass -string HyimgApplication "$APP/Contents/Info.plist"
/usr/bin/plutil -insert HYIMGSourceRoot -string "$SOURCE_ROOT" "$APP/Contents/Info.plist"
/usr/bin/plutil -insert NSAppTransportSecurity -dictionary "$APP/Contents/Info.plist"
/usr/bin/plutil -insert NSAppTransportSecurity.NSAllowsLocalNetworking -bool YES "$APP/Contents/Info.plist"
mkdir -p "$APP/Contents/Resources/review"
for source in "$ROOT"/review/*.py "$ROOT"/review/*.html; do
  cp "$source" "$APP/Contents/Resources/review/"
done
rm -rf "$APP/Contents/Frameworks"
if [[ -n "$CEF" ]]; then
  mkdir -p "$APP/Contents/Frameworks"
  ditto "$CEF/Release/Chromium Embedded Framework.framework" "$APP/Contents/Frameworks/Chromium Embedded Framework.framework"
  for kind in "" " (GPU)" " (Renderer)" " (Plugin)" " (Alerts)"; do
    H="$APP/Contents/Frameworks/Hyimg Helper$kind.app"; mkdir -p "$H/Contents/MacOS"
    cp "$TMP/helper" "$H/Contents/MacOS/Hyimg Helper$kind"
    suffix=$(printf '%s' "$kind" | tr -d ' ()' | tr '[:upper:]' '[:lower:]')
    /usr/bin/plutil -create xml1 "$H/Contents/Info.plist"
    /usr/bin/plutil -insert CFBundleExecutable -string "Hyimg Helper$kind" "$H/Contents/Info.plist"
    /usr/bin/plutil -insert CFBundleIdentifier -string "app.hyimg.desktop.helper${suffix:+.$suffix}" "$H/Contents/Info.plist"
    /usr/bin/plutil -insert CFBundleName -string "Hyimg Helper$kind" "$H/Contents/Info.plist"
    /usr/bin/plutil -insert CFBundlePackageType -string APPL "$H/Contents/Info.plist"
    /usr/bin/plutil -insert LSUIElement -bool YES "$H/Contents/Info.plist"
    /usr/bin/plutil -insert LSMinimumSystemVersion -string 14.0 "$H/Contents/Info.plist"
    /usr/bin/plutil -insert NSHighResolutionCapable -bool YES "$H/Contents/Info.plist"
  done
fi
# the built app (with Chromium about 330 MB) is not for Dropbox to upload on every build
xattr -w com.dropbox.ignored 1 "$ROOT/dist" 2>/dev/null || true
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
printf 'Built %s\n' "$APP"
