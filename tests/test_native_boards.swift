import Foundation

// Two Macs signed into one Dropbox account (owner 2026-10-08): a board's id lives in its folder (board.json, written once), links carry
// it, and a Mac finds a board it has not added by that id or by the folder relative to the Dropbox root, then offers it on Home.
// Temporary folders only: two «Dropbox roots» stand for the two Macs, a sync is a copy of the board's files.
@main struct BoardTests {
    static func main() throws {
        func require(_ value: Bool, _ name: String) throws {
            guard value else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        let fm = FileManager.default
        let tmp = URL(fileURLWithPath: ProjectRegistry.canonical(NSTemporaryDirectory())).appendingPathComponent("hyimg-boards-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: tmp) }
        let dropA = tmp.appendingPathComponent("A/Dropbox"), dropB = tmp.appendingPathComponent("B/Library/CloudStorage/Dropbox")
        let rel = "WORK/Studio & Co/Board #1 + ёлка"   // a folder name with what a query would split on, and Cyrillic
        let boardA = dropA.appendingPathComponent(rel), boardB = dropB.appendingPathComponent(rel)
        for d in [boardA, boardB, tmp.appendingPathComponent("A/support"), tmp.appendingPathComponent("B/support")] { try fm.createDirectory(at: d, withIntermediateDirectories: true) }
        let rootsA = Dropbox.roots(environment: ["HYIMG_DROPBOX_ROOT": dropA.path]), rootsB = Dropbox.roots(environment: ["HYIMG_DROPBOX_ROOT": dropB.path + ":/nope"])
        try require(rootsA == [ProjectRegistry.canonical(dropA.path)] && rootsB == [ProjectRegistry.canonical(dropB.path)], "roots: the override, real paths, missing ones left out")
        try require(Dropbox.relative(boardA.path, roots: rootsA) == rel && Dropbox.relative(boardB.path, roots: rootsB) == rel, "the same folder relative to either Mac's root")
        try require(Dropbox.relative(tmp.path, roots: rootsA) == nil && Dropbox.relative(dropA.path, roots: rootsA) == nil, "outside the root, the root itself: none")

        // board.json: written on the first open, read after, never rewritten
        let regA = try ProjectRegistry(file: tmp.appendingPathComponent("A/support/projects.json"))
        let pA = try regA.register(path: boardA.path, name: "Board", styleRefs: nil)
        try require(pA.folderId == nil && BoardFolder.read(pA.stateRoot) == nil, "a folder with no board.json: the catalog's own id, nothing written yet")
        try require(BoardFolder.ensure(stateRoot: pA.stateRoot, id: pA.id, name: "Board") == pA.id, "the first open writes the catalog id as the folder id")
        let file = URL(fileURLWithPath: pA.stateRoot).appendingPathComponent("board.json"), first = try Data(contentsOf: file)
        let j = try JSONSerialization.jsonObject(with: first) as? [String: Any] ?? [:]
        try require(j["id"] as? String == pA.id.uuidString.lowercased() && j["name"] as? String == "Board" && (j["created"] as? String ?? "").hasPrefix("20"), "board.json {id, name, created}")
        try require(BoardFolder.ensure(stateRoot: pA.stateRoot, id: UUID(), name: "Other") == pA.id && (try Data(contentsOf: file)) == first, "a second open keeps the file as it was")
        try regA.setFolderID(id: pA.id, folderId: pA.id)
        let reread = try ProjectRegistry(file: regA.file)
        try require(reread.projects.first?.folderId == pA.id, "the catalog keeps the folder id")
        try require(BoardFolder.ensure(stateRoot: tmp.appendingPathComponent("nowhere/x/_review").path, id: UUID(), name: "") == nil, "no parent folder: nothing written")
        // an older catalog without folderId still reads
        let old = tmp.appendingPathComponent("old.json")
        try Data("[{\"id\":\"\(UUID().uuidString)\",\"name\":\"Old\",\"libraryRoot\":\"/x\",\"stateRoot\":\"/x/_review\",\"port\":4180}]".utf8).write(to: old)
        try require((try ProjectRegistry(file: old)).projects.first?.folderId == nil, "a catalog from before 2026-10-08 reads, folderId nil")

        // Dropbox syncs the folder to Mac B: its catalog does not know the board
        try fm.createDirectory(at: boardB.appendingPathComponent("_review"), withIntermediateDirectories: true)
        try fm.copyItem(at: file, to: boardB.appendingPathComponent("_review/board.json"))
        var link = AppLink.Target(project: pA.id, page: "main"); link.dir = rel
        let regB = try ProjectRegistry(file: tmp.appendingPathComponent("B/support/projects.json"))
        let offerB = BoardLookup.resolve(link, projects: regB.projects, found: [], roots: rootsB)
        try require(offerB == .offer(DropboxBoard(id: pA.id, name: "Board", path: ProjectRegistry.canonical(boardB.path), rel: rel)), "Mac B: by the link's folder in Dropbox, an offer")
        var noDir = link; noDir.dir = nil
        try require(BoardLookup.resolve(noDir, projects: regB.projects, found: [], roots: rootsB) == .unknown, "Mac B, no dir, no scan: unknown, Home says so")
        let scanned = [DropboxBoard(id: pA.id, name: "Board", path: boardB.path, rel: rel)]
        try require(BoardLookup.resolve(noDir, projects: regB.projects, found: scanned, roots: rootsB) == .offer(scanned[0]), "Mac B: by the folder id the scan found, an offer")
        try require(DropboxScan.notHere(scanned, projects: regB.projects) == scanned, "Home on Mac B: the board is in «not on this Mac»")
        // «Add»: the catalog takes the folder's id as its own
        let pB = try regB.register(path: boardB.path, name: "Board", styleRefs: nil)
        try require(pB.id == pA.id && pB.folderId == pA.id, "added on Mac B under the folder id")
        try require(BoardLookup.resolve(noDir, projects: regB.projects, found: scanned, roots: rootsB) == .open(pB.id), "Mac B opens the link now")
        try require(DropboxScan.notHere(scanned, projects: regB.projects).isEmpty, "and Home's list drops it")

        // Mac A: links made before (its catalog id) and after (the folder id, the same here) open; a board whose folder Mac B named first
        try require(BoardLookup.resolve(link, projects: regA.projects, found: [], roots: rootsA) == .open(pA.id), "Mac A: its own link opens its board")
        let boardC = dropA.appendingPathComponent("WORK/C"); try fm.createDirectory(at: boardC, withIntermediateDirectories: true)
        let pC = try regA.register(path: boardC.path, name: nil, styleRefs: nil), other = UUID()
        _ = BoardFolder.ensure(stateRoot: pC.stateRoot, id: other, name: "C")   // Mac B opened it first and wrote its own id
        try require(BoardLookup.resolve(AppLink.Target(project: other), projects: regA.projects, found: [], roots: rootsA) == .open(pC.id), "Mac A: by board.json's id read now")
        try require(BoardFolder.ensure(stateRoot: pC.stateRoot, id: pC.id, name: "C") == other, "Mac A's first open takes the id that is there")
        // both Macs wrote before Dropbox synced: the loser's id is in the conflicted copy and still names the board
        let lost = UUID()
        try Data("{\"id\":\"\(lost.uuidString)\",\"name\":\"C\"}".utf8).write(to: URL(fileURLWithPath: pC.stateRoot).appendingPathComponent("board (Mac B's conflicted copy 2026-10-08).json"))
        try require(BoardFolder.ids(pC.stateRoot) == [other, lost], "ids: board.json's, then the conflicted copy's")
        try require(BoardLookup.resolve(AppLink.Target(project: lost), projects: regA.projects, found: [], roots: rootsA) == .open(pC.id), "a link with the conflicted copy's id opens the board")
        // by the folder's place: a board of the catalog at the link's dir, whatever id the link carries
        var byDir = AppLink.Target(project: UUID()); byDir.dir = "WORK/C"
        try require(BoardLookup.resolve(byDir, projects: regA.projects, found: [], roots: rootsA) == .open(pC.id), "by the folder relative to Dropbox among the catalog's boards")
        // a board copied on one Mac carries the same board.json: the copy gets a new catalog id
        let copy = dropA.appendingPathComponent("WORK/C copy/_review"); try fm.createDirectory(at: copy, withIntermediateDirectories: true)
        try fm.copyItem(at: URL(fileURLWithPath: pC.stateRoot).appendingPathComponent("board.json"), to: copy.appendingPathComponent("board.json"))
        let pCopy = try regA.register(path: copy.deletingLastPathComponent().path, name: nil, styleRefs: nil)
        try require(pCopy.id != other && pCopy.id != pC.id && pCopy.folderId == nil, "an id already in the catalog is not taken twice")

        // a link's dir is only a place under the root: an old board with saved pages and no board.json is offered; a folder without a
        // board, a link that leaves the root through a symlink: nothing
        let oldBoard = dropB.appendingPathComponent("WORK/Old"); try fm.createDirectory(at: oldBoard.appendingPathComponent("_review/boards"), withIntermediateDirectories: true)
        var toOld = AppLink.Target(project: UUID()); toOld.dir = "WORK/Old"
        let oldOffer = DropboxBoard(id: nil, name: "Old", path: ProjectRegistry.canonical(oldBoard.path), rel: "WORK/Old")
        try require(BoardLookup.resolve(toOld, projects: regB.projects, found: [], roots: rootsB) == .offer(oldOffer), "an old board without board.json: offered by its folder")
        var notBoard = toOld; notBoard.dir = "WORK"
        try require(BoardLookup.resolve(notBoard, projects: regB.projects, found: [], roots: rootsB) == .unknown, "a folder that is no board: unknown")
        let outside = tmp.appendingPathComponent("outside"); try fm.createDirectory(at: outside.appendingPathComponent("_review/boards"), withIntermediateDirectories: true)
        try fm.createSymbolicLink(at: dropB.appendingPathComponent("WORK/escape"), withDestinationURL: outside)
        var esc = toOld; esc.dir = "WORK/escape"
        try require(BoardLookup.resolve(esc, projects: regB.projects, found: [], roots: rootsB) == .unknown, "a symlink out of Dropbox: unknown")

        // the scan's file beside the catalog
        let catalog = regB.file
        try require(DropboxScan.read(catalog).boards.isEmpty && DropboxScan.stale(DropboxScan.read(catalog).t), "no scan yet: empty and stale")
        DropboxScan.write(catalog, ["t": 1000.0, "boards": [scanned[0].json, ["path": "relative/no"], ["id": "", "name": "", "path": oldBoard.path, "rel": "WORK/Old"]]])
        let read = DropboxScan.read(catalog)
        try require(read.t == 1000 && read.boards.count == 2 && read.boards[1].id == nil && read.boards[1].name == "Old", "read: bad rows dropped, a nameless board takes its folder's name")
        try require(DropboxScan.stale(1000, now: 1000 + 601) && !DropboxScan.stale(1000, now: 1000 + 60), "stale after 10 minutes")

        // the link with dir: written and read back the same, a dir that climbs or is absolute refused
        let url = AppLink.url(link)!
        try require(AppLink.parse(url) == .board(link), "dir round trip: \(url.absoluteString)")
        try require(url.absoluteString.contains("%26") && url.absoluteString.contains("%2B") && url.absoluteString.contains("%23"), "«&», «+», «#» of a folder's name are encoded")
        if case .board(let t) = AppLink.parse(url) { try require(t.query.allSatisfy { $0.name != "dir" }, "dir never goes to the board's page") }
        print("All board identity tests passed")
    }
}
