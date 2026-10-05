#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
OUTPUT="${1:-/private/tmp/hyimg-evidence/native-webkit}"
TMP="$(mktemp -d /private/tmp/hyimg-webkit-test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUTPUT"
xcrun swiftc -sdk "$(xcrun --show-sdk-path)" -target "$(uname -m)-apple-macosx14.0" -module-cache-path "$TMP/modules" -swift-version 5 \
  "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/ServerSession.swift" "$ROOT/tests/test_webkit.swift" \
  -framework AppKit -framework WebKit -o "$TMP/webkit-test"
"$TMP/webkit-test" "$ROOT" "$OUTPUT"
