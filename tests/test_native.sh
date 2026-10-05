#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
TMP="$(mktemp -d /private/tmp/hyimg-native-test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/ServerSession.swift" "$ROOT/tests/test_native_registry.swift" -o "$TMP/test"
"$TMP/test"
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/ServerSession.swift" "$ROOT/tests/test_native_server.swift" -o "$TMP/server-test"
"$TMP/server-test" "$ROOT"
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/SaveBarrier.swift" "$ROOT/tests/test_native_flush.swift" -o "$TMP/flush-test"
"$TMP/flush-test"
