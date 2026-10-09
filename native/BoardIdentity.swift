import Foundation

// Boards shared through one Dropbox account on two Macs (owner 2026-10-08: he and his partner use two Macs signed into the same Dropbox
// account: every board folder syncs to both, each Mac's catalog has its own UUIDs). A board's id lives in its folder (BoardFolder,
// ProjectRegistry.swift); here is how a Mac finds a board by that id, and the boards in Dropbox it has not added yet.
//   Dropbox      this Mac's Dropbox roots (~/.dropbox/info.json, ~/Dropbox, ~/Library/CloudStorage/Dropbox*) and a folder's path relative
//                to them, the same on both Macs
//   BoardLookup  what a hyimg:// link names here: a board of the catalog (by its catalog id, its folder id, its folder in Dropbox), a
//                board in Dropbox to offer on Home (found by the scan or at the link's dir), or nothing
//   DropboxScan  the scan's result (review/boardid.py scan, run by the app in the background) kept beside the catalog, read by Home
//                without waiting, the boards of the catalog left out
// Foundation only: tests/test_native_boards.swift compiles it with ProjectRegistry.swift and Links.swift.
enum Dropbox {
    // HYIMG_DROPBOX_ROOT (folders split by «:») names them instead (tests); real paths without repeats
    static func roots(environment: [String: String] = ProcessInfo.processInfo.environment,
                      home: URL = FileManager.default.homeDirectoryForCurrentUser) -> [String] {
        var found: [String] = []
        if let env = environment["HYIMG_DROPBOX_ROOT"] { found = env.split(separator: ":").map(String.init) }
        else {
            if let d = try? Data(contentsOf: home.appendingPathComponent(".dropbox/info.json")),
               let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                found += j.values.compactMap { ($0 as? [String: Any])?["path"] as? String }
            }
            found.append(home.appendingPathComponent("Dropbox").path)
            let cloud = home.appendingPathComponent("Library/CloudStorage")
            found += ((try? FileManager.default.contentsOfDirectory(atPath: cloud.path)) ?? []).filter { $0.hasPrefix("Dropbox") }.sorted()
                .map { cloud.appendingPathComponent($0).path }
        }
        var out: [String] = []
        for p in found where p.hasPrefix("/") {
            var dir: ObjCBool = false
            let r = ProjectRegistry.canonical(p)
            if FileManager.default.fileExists(atPath: r, isDirectory: &dir), dir.boolValue, !out.contains(r) { out.append(r) }
        }
        return out
    }
    // «Studio/Brand/Board» for a folder inside one of the roots, else nil
    static func relative(_ path: String, roots: [String]) -> String? {
        let p = ProjectRegistry.canonical(path)
        for r in roots {
            let base = r.hasSuffix("/") ? r : r + "/"
            if p.hasPrefix(base), p.count > base.count { return String(p.dropFirst(base.count)) }
        }
        return nil
    }
}

// a board folder in Dropbox: its id when it has board.json (an old board opened on neither Mac since has none), its name, where it is
struct DropboxBoard: Equatable {
    var id: UUID?
    var name: String
    var path: String
    var rel: String
    var json: [String: Any] { ["id": id?.uuidString.lowercased() ?? "", "name": name, "path": path, "rel": rel] }
    init(id: UUID?, name: String, path: String, rel: String) { self.id = id; self.name = name; self.path = path; self.rel = rel }
    init?(_ j: [String: Any]) {
        guard let path = j["path"] as? String, path.hasPrefix("/") else { return nil }
        self.init(id: (j["id"] as? String).flatMap(UUID.init), name: (j["name"] as? String) ?? "", path: path, rel: (j["rel"] as? String) ?? "")
        if name.isEmpty { name = URL(fileURLWithPath: path).lastPathComponent }
    }
    // the board at a folder (its _review has board.json or saved pages), as review/boardid.py board_at
    static func at(_ path: String, rel: String) -> DropboxBoard? {
        let state = URL(fileURLWithPath: path).appendingPathComponent("_review"), fm = FileManager.default
        guard fm.fileExists(atPath: state.appendingPathComponent(BoardFolder.file).path) || fm.fileExists(atPath: state.appendingPathComponent("boards").path) else { return nil }
        let f = BoardFolder.read(state.path), real = ProjectRegistry.canonical(path)
        return DropboxBoard(id: f?.id, name: (f?.name).flatMap { $0.isEmpty ? nil : $0 } ?? URL(fileURLWithPath: real).lastPathComponent, path: real, rel: rel)
    }
}

enum BoardLookup: Equatable {
    case open(UUID)            // a board of this Mac's catalog, by its catalog id
    case offer(DropboxBoard)   // a board in Dropbox not in the catalog: Home offers to add it, nothing happens without a click
    case unknown

    // in this order: the catalog id (links made on this Mac before 2026-10-08), the folder id (the catalog's copy, then board.json and its
    // conflicted copies, read now), the link's folder in Dropbox among the catalog's boards, a board the scan found with that id, a
    // board at the link's folder in this Mac's Dropbox
    static func resolve(_ t: AppLink.Target, projects: [Project], found: [DropboxBoard], roots: [String]) -> BoardLookup {
        if let p = projects.first(where: { $0.id == t.project }) { return .open(p.id) }
        if let p = projects.first(where: { $0.folderId == t.project }) { return .open(p.id) }
        if let p = projects.first(where: { BoardFolder.ids($0.stateRoot).contains(t.project) }) { return .open(p.id) }
        if let dir = t.dir, let p = projects.first(where: { Dropbox.relative($0.libraryRoot, roots: roots) == dir }) { return .open(p.id) }
        if let b = found.first(where: { $0.id == t.project }) { return .offer(b) }
        if let dir = t.dir {
            for r in roots {
                let path = URL(fileURLWithPath: r).appendingPathComponent(dir).path
                guard Dropbox.relative(path, roots: [r]) == dir else { continue }   // a link inside the folder stays inside the root
                if let b = DropboxBoard.at(path, rel: dir) { return .offer(b) }
            }
        }
        return .unknown
    }
}

// the scan's result beside the catalog (dropbox-boards.json {t, roots, boards}); Home reads it as it is and the app refreshes it behind
enum DropboxScan {
    static let maxAge: TimeInterval = 600
    static func file(_ catalog: URL) -> URL { catalog.deletingLastPathComponent().appendingPathComponent("dropbox-boards.json") }
    static func read(_ catalog: URL) -> (t: Double, boards: [DropboxBoard]) {
        guard let d = try? Data(contentsOf: file(catalog)), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return (0, []) }
        return ((j["t"] as? NSNumber)?.doubleValue ?? 0, ((j["boards"] as? [[String: Any]]) ?? []).compactMap(DropboxBoard.init))
    }
    static func write(_ catalog: URL, _ result: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]) else { return }
        try? FileManager.default.createDirectory(at: catalog.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: file(catalog), options: .atomic)
    }
    // the boards not on this Mac: none whose folder or id the catalog has (a board added since the scan goes at once)
    static func notHere(_ boards: [DropboxBoard], projects: [Project]) -> [DropboxBoard] {
        let paths = Set(projects.map { ProjectRegistry.canonical($0.libraryRoot) })
        let ids = Set(projects.flatMap { [$0.id] + ($0.folderId.map { [$0] } ?? []) })
        return boards.filter { !paths.contains(ProjectRegistry.canonical($0.path)) && !($0.id.map(ids.contains) ?? false) }
    }
    static func stale(_ t: Double, now: Double = Date().timeIntervalSince1970) -> Bool { now - t > maxAge }
}
