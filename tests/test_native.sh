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
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/tests/test_native_news.swift" -o "$TMP/news-test"
"$TMP/news-test"
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/Storage.swift" "$ROOT/tests/test_native_storage.swift" -o "$TMP/storage-test"
"$TMP/storage-test"
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/Links.swift" "$ROOT/tests/test_native_links.swift" -o "$TMP/links-test"
"$TMP/links-test"
# two Macs on one Dropbox account (owner 2026-10-08): board.json, links by the folder id or the folder, boards in Dropbox
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 "$ROOT/native/ProjectRegistry.swift" "$ROOT/native/Links.swift" \
  "$ROOT/native/BoardIdentity.swift" "$ROOT/tests/test_native_boards.swift" -o "$TMP/boards-test"
"$TMP/boards-test"
# macOS notifications for the bell (owner 2026-10-08): the policy alone, no AppKit
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 -D HYIMG_POLICY_ONLY "$ROOT/native/MacNotifications.swift" "$ROOT/tests/test_native_macnotif.swift" -o "$TMP/macnotif-test"
"$TMP/macnotif-test"
# sleeping boards and ⌃Tab's order (owner 2026-10-08): the policy alone, no AppKit
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 -D HYIMG_POLICY_ONLY "$ROOT/native/BoardSleep.swift" "$ROOT/tests/test_native_sleep.swift" -o "$TMP/sleep-test"
"$TMP/sleep-test"
# Home's standard Archive (owner 2026-10-08): its boards from home.json, ⌃Tab without them; the policy alone, no AppKit
xcrun swiftc -module-cache-path "$TMP/modules" -swift-version 5 -D HYIMG_POLICY_ONLY "$ROOT/native/HomeArchive.swift" "$ROOT/native/BoardSleep.swift" \
  "$ROOT/tests/test_native_archive.swift" -o "$TMP/archive-test"
"$TMP/archive-test"
