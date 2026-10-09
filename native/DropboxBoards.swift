import AppKit

// The app's side of boards shared through one Dropbox account on two Macs (owner 2026-10-08; BoardIdentity.swift says what and why):
//   ensureFolderID     a board's first open on this Mac gives its folder an id (board.json) or reads the one there; the catalog keeps it
//   dropboxHome        Home's «Boards in Dropbox not on this Mac» from the scan beside the catalog, as it is; a scan older than 10
//                      minutes is redone behind (review/boardid.py scan), Home gets the new list when it is done; Home never waits
//   offerBoard         a link to a board this Mac has not added: Home shows «Add this board from Dropbox» (ui/dropbox.js)
//   dropboxAdd         Home's «Add» on either: the folder joins the catalog with its folder id (one click, never on its own), a link's
//                      board then opens where the link points
var dropboxOffers: [String: AppLink.Target] = [:]   // the boards offered for a link, by folder: «Add» opens them at the link
var dropboxScanning = false
var dropboxTried = 0.0   // when the last scan started: a scan that fails (no Python) is not retried on every Home list
var dropboxWaiting: [() -> Void] = []

extension App {
    func ensureFolderID(_ project: Project) {
        guard let id = BoardFolder.ensure(stateRoot: project.stateRoot, id: project.id, name: project.name), id != project.folderId else { return }
        do { try registry.setFolderID(id: project.id, folderId: id) } catch { appLog("folder id of \(project.name): \(error.localizedDescription)") }
    }
    func dropboxHome(_ projects: [Project]) -> [String: Any] {
        let scan = DropboxScan.read(registry.file)
        if DropboxScan.stale(scan.t), DropboxScan.stale(dropboxTried) { refreshDropbox() }
        return ["dropbox": ["t": scan.t, "boards": DropboxScan.notHere(scan.boards, projects: projects).map(\.json)]]
    }
    // the scan in the background, one at a time; then Home's list again and whoever waited for it
    func refreshDropbox(then: (() -> Void)? = nil) {
        if let then { dropboxWaiting.append(then) }
        guard !dropboxScanning, !quitting else { return }
        dropboxScanning = true; dropboxTried = Date().timeIntervalSince1970
        let catalog = registry.file, root = sourceRoot
        DispatchQueue.global(qos: .utility).async {
            let res = Self.runReview("boardid.py", ["scan", "--catalog", catalog.path], dir: catalog.deletingLastPathComponent(), root: root)
            if var res, res["boards"] is [[String: Any]] { res["t"] = Date().timeIntervalSince1970; DropboxScan.write(catalog, res) }
            DispatchQueue.main.async {
                dropboxScanning = false
                let waiting = dropboxWaiting; dropboxWaiting = []
                if res != nil { self.pushHome() }
                waiting.forEach { $0() }
            }
        }
    }
    // a link's board is in this Mac's Dropbox but not in its catalog: Home offers it (Home may still be loading after a launch for the link)
    func offerBoard(_ b: DropboxBoard, _ t: AppLink.Target, attempt: Int = 0) {
        dropboxOffers[ProjectRegistry.canonical(b.path)] = t
        guard let data = try? JSONSerialization.data(withJSONObject: b.json), let json = String(data: data, encoding: .utf8) else { return }
        homeWeb?.evaluateJavaScript("typeof window.hyimgOffer === 'function' ? (window.hyimgOffer(\(json)), true) : false") { [weak self] result, _ in
            if (result as? Bool) != true, attempt < 50 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self?.offerBoard(b, t, attempt: attempt + 1) } }
        }
    }
    // a link whose board is not in the catalog: the scan's list, the link's folder, then a fresh scan; still nothing: the note as before
    func lookUpLink(_ t: AppLink.Target, rescanned: Bool = false) {
        switch BoardLookup.resolve(t, projects: registry.projects, found: DropboxScan.read(registry.file).boards, roots: Dropbox.roots()) {
        case .open(let id): if let p = registry.projects.first(where: { $0.id == id }) { go(p, t) }
        case .offer(let b): showProjects(); offerBoard(b, t)
        case .unknown:
            showProjects()
            if rescanned { homeNote("The board of this link is not in Hyimg on this Mac"); return }
            refreshDropbox { [weak self] in self?.lookUpLink(t, rescanned: true) }
        }
    }
    // Home's messages that are not the board list's own: Settings › Plugins (Plugins.swift), › Profile (People.swift), Dropbox here
    func otherMessage(_ action: String, _ body: [String: Any], _ project: Project?) {
        if action == "plugins" { pluginsMessage(body, project) } else if action == "dropboxAdd" { dropboxAdd(body["path"] as? String ?? "") }
        else if action == "browsers" { browsersMessage(body, project) }   // «Open in <Browser>»: the browsers, one opening a page (Browsers.swift)
        else if switchMessage(action, body) { return }   // ⌃Tab's cards, the crumb's list of boards, a page's sleep answer (Switcher.swift)
        else { profileMessage(body, project) }
    }
    // only a folder the app offered (a link's) or the scan found: a page cannot make the app add any other folder
    func dropboxAdd(_ path: String) {
        let key = ProjectRegistry.canonical(path), found = DropboxScan.read(registry.file).boards.first { ProjectRegistry.canonical($0.path) == key }
        guard !path.isEmpty, dropboxOffers[key] != nil || found != nil else { return }
        let name = found?.name ?? DropboxBoard.at(key, rel: "")?.name
        do {
            let project = try registry.register(path: key, name: name, styleRefs: nil)
            pushHome(); writeActive()
            if let t = dropboxOffers.removeValue(forKey: key) { go(project, t) }
        } catch { alert(L("Couldn't add the board"), detail: error.localizedDescription) }
    }
}
