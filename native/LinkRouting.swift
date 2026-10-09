import AppKit

// What the app does with a hyimg:// link (Links.swift parses and validates it). macOS hands the link to application(_:open:), on a running
// app or on one it launches for it (then before applicationDidFinishLaunching: the link waits for the window). The app comes to the front:
//   hyimg://home                  Home
//   hyimg://board/<id>?…          that board opens or its tab comes forward, on the link's page, its objects selected and centred as the
//                                 board's own ?obj= does (canvas.html openLink): a board not loaded yet gets them in its first address, a
//                                 drawn one through window.hyimgGo (ui/applink.js), a board still loading once it is drawn
//   a board not in the catalog    found in this Mac's Dropbox (by its folder id, or at the link's dir): Home offers «Add this board from
//                                 Dropbox», one click adds and opens it (owner 2026-10-08, two Macs on one Dropbox account); not found:
//                                 Home, with a note saying so; an invalid link: Home, with a note too
var pendingLinks: [UUID: AppLink.Target] = [:]   // a board opening for a link: load() puts these into its first address (main.swift)

extension App {
    @objc(application:openURLs:) func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls.prefix(4) { openLink(url) }
    }
    func openLink(_ url: URL, attempt: Int = 0) {
        guard window != nil else {   // launched for the link: the window comes a moment later
            if attempt < 100 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in self?.openLink(url, attempt: attempt + 1) } }
            return
        }
        let link = AppLink.parse(url)
        appLog("link \(AppLink.describe(link))")
        NSApp.activate(ignoringOtherApps: true); window?.makeKeyAndOrderFront(nil)
        switch link {
        case .home: showProjects()
        case .board(let t): lookUpLink(t)   // by the catalog id, the folder id, the folder in Dropbox (DropboxBoards.swift)
        case nil: showProjects(); homeNote("This link can't be opened in Hyimg")
        }
    }
    func go(_ project: Project, _ t: AppLink.Target) {
        guard let session = sessions[project.id], session.loaded || session.loading else {
            pendingLinks[project.id] = t   // its first address carries the link: the page applies it before it is drawn
            openProject(project); return
        }
        pendingLinks.removeValue(forKey: project.id)
        openProject(project)
        deliver(project.id, t)
    }
    // to a board whose page is there: once it is drawn (a board still loading takes up to 2 minutes, as Home waits for it)
    func deliver(_ id: UUID, _ t: AppLink.Target, attempt: Int = 0) {
        guard let session = sessions[id] else { return }
        if session.drawn { evaluate(session, "window.hyimgGo && window.hyimgGo(\(t.json))"); return }
        if attempt < 480 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in self?.deliver(id, t, attempt: attempt + 1) } }
    }
    // a note on Home (ui/toasts.js) in the owner's language (ui/lang-home.js); Home may still be loading when the app was launched for the link
    func homeNote(_ text: String, attempt: Int = 0) {
        let js = "typeof hyToast === 'function' && typeof T === 'function' ? (hyToast(T(\(jsString(text))), 'error', { sticky: true }), true) : false"
        homeWeb?.evaluateJavaScript(js) { [weak self] result, _ in
            if (result as? Bool) != true, attempt < 50 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self?.homeNote(text, attempt: attempt + 1) } }
        }
    }
    // the board's first address with the link's page, objects and camera (load() in main.swift); taken once
    func linkQuery(_ id: UUID) -> [URLQueryItem] { pendingLinks.removeValue(forKey: id)?.query ?? [] }
}
