import Foundation

// Home's news on a board (owner 2026-10-06: «show how many new events happened on each board without him»): BoardNews reads the
// board's event logs straight from its state root, BoardSeen keeps when the owner last saw each board. Temporary folders only.
@main struct NewsTests {
    static func main() throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("hyimg-news-test-\(UUID())")
        defer { try? fm.removeItem(at: root) }
        func require(_ value: Bool, _ name: String) throws {
            guard value else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        let state = root.appendingPathComponent("lib/_review"), logs = state.appendingPathComponent("boards/_events")
        try fm.createDirectory(at: logs, withIntermediateDirectories: true)
        func line(_ e: [String: Any]) throws -> String { String(data: try JSONSerialization.data(withJSONObject: e), encoding: .utf8)! }
        func log(_ page: String, _ evs: [[String: Any]], mtime: Double? = nil) throws {
            let f = logs.appendingPathComponent(page + ".jsonl")
            try (try evs.map(line).joined(separator: "\n") + "\n").write(to: f, atomically: true, encoding: .utf8)
            if let mtime { try fm.setAttributes([.modificationDate: Date(timeIntervalSince1970: mtime)], ofItemAtPath: f.path) }
        }
        let pages: [String: Any] = ["pages": [["id": "main", "title": "Main"], ["id": "p2", "title": "Renderings"]]]
        try JSONSerialization.data(withJSONObject: pages).write(to: state.appendingPathComponent("boards/pages.json"))

        // no logs at all: nothing new, and nothing is created
        try fm.removeItem(at: logs)
        try require(BoardNews.summary(stateRoot: state.path, since: 0) == nil && !fm.fileExists(atPath: logs.path), "a board without logs has no news")
        try fm.createDirectory(at: logs, withIntermediateDirectories: true)

        try log("main", [
            ["kind": "add", "who": "ai", "ts": 100, "count": 5],          // before the owner last saw it
            ["kind": "note", "who": "owner", "ts": 210],                 // the owner's own
            ["kind": "add", "who": "ai", "agent": "Codex", "ts": 220, "count": 24],
            ["kind": "note", "who": "ai", "agent": "Codex", "ts": 230],
            ["kind": "note", "who": "ai", "agent": "Codex", "ts": 231],
            ["kind": "move", "who": "owner", "ts": 240, "count": 3],
        ])
        try log("p2", [["kind": "group", "who": "ai", "ts": 250, "count": 6, "new": 4], ["kind": "remove", "who": "claude", "ts": 260, "count": 2]])
        try log("gone", [["kind": "add", "who": "ai", "ts": 270, "count": 9]])   // a page no longer listed in pages.json
        let s = BoardNews.summary(stateRoot: state.path, since: 200)
        let rows = (s?["rows"] as? [[String: Any]]) ?? []
        func row(_ p: String, _ k: String, _ w: String) -> [String: Any]? { rows.first { $0["pid"] as? String == p && $0["k"] as? String == k && $0["w"] as? String == w } }
        try require(s?["n"] as? Int == 5, "counts only events after the last look and not the owner's (5 of 9)")
        try require(row("main", "add", "Codex")?["c"] as? Int == 24 && row("main", "add", "Codex")?["n"] as? Int == 1, "pictures added are counted per author, the agent's name from the event")
        try require(row("main", "note", "Codex")?["n"] as? Int == 2 && row("main", "note", "Codex")?["p"] as? String == "Main", "notes per page, with the page's name")
        try require(row("p2", "group", "ai")?["c"] as? Int == 4 && row("p2", "remove", "claude")?["c"] as? Int == 2, "a new group counts the pictures added with it; another author is its own row")
        try require(!rows.contains { $0["pid"] as? String == "gone" }, "a deleted page's log is not news")
        try require(rows.first?["pid"] as? String == "main" && rows.last?["pid"] as? String == "p2", "rows in the board's page order")
        try require((s?["t"] as? Double) == 260, "the newest news' time")
        try require(BoardNews.summary(stateRoot: state.path, since: 300) == nil, "nothing after the last look: nil")

        // a log not written since the last look is not even opened (its lines would count, its time says no)
        try log("main", [["kind": "add", "who": "ai", "ts": 500, "count": 1]], mtime: 400)
        try log("p2", [], mtime: 400)
        try require(BoardNews.summary(stateRoot: state.path, since: 450) == nil, "a log older than the last look is skipped by its time")

        // a long log is read from its end, across chunks, back to its first older line
        var long: [[String: Any]] = (0..<3000).map { ["kind": "move", "who": "ai", "ts": Double($0), "count": 1, "paths": Array(repeating: "folder/picture-with-a-long-name.png", count: 4)] }
        long.append(["kind": "add", "who": "ai", "ts": 5000.0, "count": 7])
        try log("main", long)
        let l = BoardNews.summary(stateRoot: state.path, since: 2899.5)
        try require(l?["n"] as? Int == 101, "a long log: the 101 newest lines across 64 KB chunks")
        try require(BoardNews.summary(stateRoot: state.path, since: -1)?["n"] as? Int == 3001, "read whole, back to its first line")
        let one = BoardNews.newer(logs.appendingPathComponent("main.jsonl"), since: 4999)
        try require(one.count == 1 && one[0]["kind"] as? String == "add", "newer reads only the lines after since, newest first")

        // a board with no pages.json has its first page «main»
        let bare = root.appendingPathComponent("bare/_review/boards/_events")
        try fm.createDirectory(at: bare, withIntermediateDirectories: true)
        try (try line(["kind": "text", "who": "ai", "ts": 10]) + "\n").write(to: bare.appendingPathComponent("main.jsonl"), atomically: true, encoding: .utf8)
        let b = BoardNews.summary(stateRoot: root.appendingPathComponent("bare/_review").path, since: 0)
        try require(b?["n"] as? Int == 1 && ((b?["rows"] as? [[String: Any]])?.first?["p"] as? String) == "", "no pages.json: the main page, unnamed")

        // seen.json: when the owner last saw each board; marking it clears the news
        let seenFile = root.appendingPathComponent("config/seen.json"), a = UUID(), z = UUID()
        try require(BoardSeen.read(seenFile).isEmpty, "no seen.json reads empty")
        BoardSeen.mark(seenFile, [a], at: 1000); BoardSeen.mark(seenFile, [z], at: 2000)
        let seen = BoardSeen.read(seenFile)
        try require(seen[a.uuidString] == 1000 && seen[z.uuidString] == 2000, "marks are kept per board, others untouched")
        try log("main", [["kind": "add", "who": "ai", "ts": Date().timeIntervalSince1970 - 5, "count": 3]])
        try require(BoardNews.summary(stateRoot: state.path, since: BoardSeen.read(seenFile)[a.uuidString]!) != nil, "news before the board is opened")
        BoardSeen.mark(seenFile, [a])
        try require(BoardNews.summary(stateRoot: state.path, since: BoardSeen.read(seenFile)[a.uuidString]!) == nil, "opening the board clears its news")
    }
}
