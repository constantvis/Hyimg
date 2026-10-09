import Foundation

// Home's standard Archive, the app's side (native/HomeArchive.swift, owner 2026-10-08: «туда будем пихать все, что не должно светиться
// нигде»): which boards home.json puts in it, ⌃Tab's cards without them, the board in front kept, and a write of home.json that never
// drops it (an unreadable file copied aside first). Built with -D HYIMG_POLICY_ONLY beside native/BoardSleep.swift (SwitchOrder):
// no AppKit. The file it reads is written in a temporary folder.
@main struct HomeArchiveTests {
    static func main() {
        var failed = 0
        func require(_ condition: Bool, _ name: String) {
            if condition { print("PASS: \(name)") } else { print("FAIL: \(name)"); failed += 1 }
        }
        let a = UUID(), b = UUID(), c = UUID(), d = UUID()
        let mine: [String: Any] = ["id": "f1", "name": "Brand Studio", "projects": [a.uuidString]]
        let box: [String: Any] = ["id": "archive", "name": "Archive", "icon": "archive", "from": [b.uuidString: "f1"],
                                  "projects": [b.uuidString, c.uuidString.lowercased(), "not a board", 7] as [Any]]
        let home: [String: Any] = ["folders": [mine, box], "favs": [b.uuidString]]
        let archived = HomeArchive.boards(home)
        require(archived == [b, c], "the Archive's boards, an id in any case; what is not a board id is left out")
        require(!archived.contains(a), "a board in another project is not archived")
        require(HomeArchive.boards([:]).isEmpty && HomeArchive.boards(["folders": "x"]).isEmpty, "no home.json, or a broken one: nothing archived")
        let named: [String: Any] = ["id": "f1", "name": "Archive", "projects": [a.uuidString]]
        require(HomeArchive.boards(["folders": [named]]).isEmpty,
                "a project the owner named Archive is not the standard one")
        // the file the app reads
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("hyimg-archive-test-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("home.json")
        require(HomeArchive.boards(file: file).isEmpty, "no file: nothing archived")
        if let data = try? JSONSerialization.data(withJSONObject: home) { try? data.write(to: file) }
        require(HomeArchive.boards(file: file) == [b, c], "read from home.json")
        try? Data("{".utf8).write(to: file)
        require(HomeArchive.boards(file: file).isEmpty, "an unreadable file: nothing archived")
        // ⌃Tab: the open boards without the archived ones, the board in front kept as the first card
        let open = [a, b, c, d]
        require(HomeArchive.switchable(open, archived: [b, c], front: a) == [a, d], "archived boards behind are no cards")
        require(HomeArchive.switchable(open, archived: [b, c], front: b) == [a, b, d], "an archived board in front stays")
        require(HomeArchive.switchable(open, archived: [b, c], front: nil) == [a, d], "Home in front: no archived card")
        require(HomeArchive.switchable(open, archived: [], front: nil) == open, "nothing archived: every open board")
        let t0 = Date(timeIntervalSince1970: 1_000_000), last: [UUID: Date] = [a: t0, b: t0.addingTimeInterval(30), d: t0.addingTimeInterval(10)]
        let cards = SwitchOrder.cards(front: a, open: HomeArchive.switchable(open, archived: [b], front: a), lastFront: last)
        require(cards == [a, d, c], "the cards' order without the archived board that was last in front")
        // a write of home.json without the Archive keeps the file's, without the boards filed elsewhere now
        let older: [String: Any] = ["folders": [["id": "f1", "name": "Brand Studio", "projects": [a.uuidString, b.uuidString]]], "favs": []]
        let kept = HomeArchive.kept(older, old: home)
        require(HomeArchive.boards(kept) == [c], "an older home without the Archive: it stays, b filed in Brand Studio again leaves it")
        let keptBox = (kept["folders"] as? [[String: Any]])?.last
        require(keptBox?["id"] as? String == "archive" && (keptBox?["from"] as? [String: Any])?.isEmpty == true, "and b's «Restore» is forgotten")
        require((kept["favs"] as? [Any])?.isEmpty == true, "the rest of the written home as written")
        let moved: [String: Any] = ["folders": [mine, ["id": "archive", "projects": [a.uuidString]]]]
        require(HomeArchive.boards(HomeArchive.kept(moved, old: home)) == [a], "a home with the Archive is written as it is")
        require(HomeArchive.boards(HomeArchive.kept(older, old: [:])).isEmpty, "no Archive in the file either: nothing to keep")
        if let data = try? JSONSerialization.data(withJSONObject: home) { try? data.write(to: file) }
        require(HomeArchive.boards(HomeArchive.kept(older, file: file)) == [c], "the same against the file")
        // an unreadable file is copied aside before it is written over
        try? Data("{broken".utf8).write(to: file)
        let lone: [String: Any] = ["folders": [["id": "archive", "projects": []]]]
        let t = Date(timeIntervalSince1970: 2_000_000)
        require(HomeArchive.kept(lone, file: file, now: t).count == 1, "an unreadable file: the home as written")
        let aside = dir.appendingPathComponent("home.unreadable-2000000.json")
        require((try? String(contentsOf: aside, encoding: .utf8)) == "{broken", "and the unreadable file kept beside it")
        let gone = dir.appendingPathComponent("none.json")
        require(HomeArchive.kept(lone, file: gone).count == 1, "no file: the home as written, nothing kept aside")
        if failed > 0 { print("\(failed) failed"); exit(1) }
    }
}
