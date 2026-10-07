import AppKit
import UniformTypeIdentifiers
import WebKit

final class ProjectView {
    let server: ServerSession
    let web: WKWebView
    var cef: HYCefView?   // CEF: the page in Chromium instead of the WKWebView (Вид › Движок Chromium)
    var surface: NSView { cef ?? web }
    var pageURL: URL? { cef.flatMap { $0.currentURL.flatMap(URL.init(string:)) } ?? web.url }
    var flushWaiters: [String: (Result<Bool, Error>) -> Void] = [:]   // CEF: flush answers arrive as console lines
    var loaded = false
    var loading = false
    var shown = false   // its page has been there at least once: before that there is nothing of it to save
    var drawn = false   // its canvas said the board and its controls are drawn (canvasReady), pictures may still be coming
    var band: DragStrip.Band?   // where its page's plates are in the window's top band (the "dragband" message)
    var operationPending = false
    init(project: Project, sourceRoot: URL) {
        server = ServerSession(project: project, sourceRoot: sourceRoot)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = WKWebsiteDataStore(forIdentifier: project.id)
        configuration.preferences.isElementFullscreenEnabled = true   // a video's ⤢ opens the player in true full screen (owner 2026-10-06)
        web = FirstClickWebView(frame: .zero, configuration: configuration)
        web.allowsBackForwardNavigationGestures = false
        web.isInspectable = true
    }
}

final class App: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate, WKScriptMessageHandler {
    let registry: ProjectRegistry
    let sourceRoot: URL
    let initialProjectID: UUID?
    var window: NSWindow?
    var content: NSView?
    var tabBar: TabBar?
    var homeWeb: WKWebView?
    var homeBand: DragStrip.Band?
    var tabs: [UUID] = []   // open projects in tab order
    let defaults = UserDefaults.standard
    var sessions: [UUID: ProjectView] = [:]
    var selected: UUID?
    var terminationPending = false
    var appearanceWatch: NSKeyValueObservation?
    // CEF: which engine draws the projects; Chromium when this build carries it, unless the owner picked WebKit
    var useChromium: Bool { HYCef.available() && (defaults.string(forKey: key("engine")) ?? "chromium") == "chromium" }
    var cefRoot: URL { registry.file.deletingLastPathComponent().appendingPathComponent("Chromium", isDirectory: true) }
    func startChromium() -> Bool {
        if HYCef.running() { return true }
        try? FileManager.default.createDirectory(at: cefRoot, withIntermediateDirectories: true)
        return HYCef.start(withCachePath: cefRoot.path)
    }
    init(registry: ProjectRegistry, sourceRoot: URL, initialProjectID: UUID? = nil) { self.registry = registry; self.sourceRoot = sourceRoot; self.initialProjectID = initialProjectID }

    func applicationDidFinishLaunching(_ notification: Notification) {
        ServerSession.settingsFile = registry.file.deletingLastPathComponent().appendingPathComponent("settings.json").path
        Lang.current = fileLang()   // the menus, the titles and Home in the owner's language from the start (owner 2026-10-06)
        buildMenu()
        // macOS switching light/dark: the project pages' «Авто» theme follows (the window chrome stays dark)
        appearanceWatch = NSApp.observe(\.effectiveAppearance) { [weak self] app, _ in self?.sessions.values.forEach { $0.web.appearance = app.effectiveAppearance } }
        // ⌃Tab never reaches the menu: the web view takes Tab for focus moves first, so it is caught for the whole app here
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] e in
            guard let self, e.keyCode == 48, e.modifierFlags.contains(.control), !e.modifierFlags.contains(.command) else { return e }
            self.stepTab(e.modifierFlags.contains(.shift) ? -1 : 1); return nil
        }
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 920),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        self.window = window
        window.title = "Hyimg"
        window.minSize = NSSize(width: 780, height: 540)
        window.delegate = self
        window.appearance = NSAppearance(named: .darkAqua)
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.backgroundColor = Palette.bar
        self.window = window; applyGround()
        let container = NSView()
        // Figma-like chrome (owner 2026-09-30): no button row, tabs in the title bar with Home first
        let bar = TabBar(frame: NSRect(x: 0, y: 0, width: 1440, height: TabBar.height))
        bar.onHome = { [weak self] in self?.showProjects() }
        bar.onSelect = { [weak self] id in if let self, let p = self.registry.projects.first(where: { $0.id == id }) { self.openProject(p) } }
        bar.onClose = { [weak self] id in self?.closeTab(id) }
        tabBar = bar
        let body = NSView()
        content = body
        for view in [body, bar] { view.translatesAutoresizingMaskIntoConstraints = false; container.addSubview(view) }   // the bar above the content, it slides over it in full screen
        let barTop = bar.topAnchor.constraint(equalTo: container.topAnchor), bodyTop = body.topAnchor.constraint(equalTo: container.topAnchor, constant: TabBar.height)
        self.barTop = barTop; self.bodyTop = bodyTop
        NSLayoutConstraint.activate([
            barTop, bar.leadingAnchor.constraint(equalTo: container.leadingAnchor), bar.trailingAnchor.constraint(equalTo: container.trailingAnchor), bar.heightAnchor.constraint(equalToConstant: TabBar.height),
            bodyTop, body.leadingAnchor.constraint(equalTo: container.leadingAnchor), body.trailingAnchor.constraint(equalTo: container.trailingAnchor), body.bottomAnchor.constraint(equalTo: container.bottomAnchor)
        ])
        if TabBar.inPage {
            let strip = DragStrip(); strip.translatesAutoresizingMaskIntoConstraints = false; container.addSubview(strip)
            strip.band = { [weak self] in self?.frontBand() }
            NSLayoutConstraint.activate([strip.topAnchor.constraint(equalTo: container.topAnchor), strip.leadingAnchor.constraint(equalTo: container.leadingAnchor),
                                         strip.trailingAnchor.constraint(equalTo: container.trailingAnchor), strip.heightAnchor.constraint(equalToConstant: DragStrip.height)])
        }
        window.contentView = container
        window.setFrameAutosaveName("HyimgMain")
        if !window.setFrameUsingName("HyimgMain") { window.center() }
        // the app always starts on Home (owner 2026-10-04: «the app should always open on the home screen, not on some file»);
        // no board is running yet, so none is marked open. --open-project still opens one straight away (tests, scripts)
        showProjects()
        if let id = initialProjectID, let project = registry.projects.first(where: { $0.id == id }) { openProject(project) }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    func label(_ text: String, size: CGFloat, weight: NSFont.Weight = .regular) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.font = .systemFont(ofSize: size, weight: weight)
        return label
    }
    func button(_ text: String, _ action: Selector, symbol: String? = nil, tag: Int = -1) -> NSButton {
        let result = NSButton(title: text, target: self, action: action)
        result.bezelStyle = .rounded
        result.tag = tag
        if let symbol { result.image = NSImage(systemSymbolName: symbol, accessibilityDescription: text); result.imagePosition = .imageLeading }
        return result
    }
    // Home and the boards' pages stay in the window once they are there, one over the other, and showing one brings it to the top.
    // Taking a page out of the window and putting it back made it paint a black frame first (Chromium's surface, WebKit's layer), seen
    // at every switch between Home and a board (owner 2026-10-04); a page under another one keeps its picture, so the switch is clean.
    func replaceContent(_ view: NSView) {
        guard let content else { return }
        content.subviews.filter { $0 !== view && !isLive($0) }.forEach { $0.removeFromSuperview() }   // pages of closed boards
        place(view)
        bringToTop(view)
    }
    // Full screen (owner 2026-09-30): the tab strip and the system menu bar hide and the canvas takes the whole screen; bringing
    // the pointer to the top edge slides both in, the tabs just below the menu bar, and they leave when the pointer goes down again.
    var barTop: NSLayoutConstraint?, bodyTop: NSLayoutConstraint?, barMonitor: Any?, barShown = true, barHideWork: DispatchWorkItem?
    func window(_ window: NSWindow, willUseFullScreenPresentationOptions proposed: NSApplication.PresentationOptions = []) -> NSApplication.PresentationOptions {
        [.fullScreen, .autoHideMenuBar, .autoHideDock, .autoHideToolbar]
    }
    // the pages hide the window buttons' capsule in full screen, where the system shows its own buttons in the menu bar's overlay
    // the board's page name on Home's loading plate, so that plate is the board's own when the board comes in front (they jumped)
    func homeCrumb(_ page: String) {
        let arg = (try? JSONSerialization.data(withJSONObject: [page])).flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
        homeWeb?.evaluateJavaScript("window.hyimgCrumb && window.hyimgCrumb(\(arg)[0])")
    }
    func pagesFullScreen(_ on: Bool) {
        let js = "window.hyimgFS && window.hyimgFS(\(on))"
        homeWeb?.evaluateJavaScript(js)
        sessions.values.forEach { evaluate($0, js) }
    }
    func windowDidResize(_ notification: Notification) { tabBar?.placeTrafficLights() }
    func windowDidBecomeKey(_ notification: Notification) { tabBar?.placeTrafficLights() }
    // the pages fold the capsule as the system's move starts, not after it (owner 2026-10-05: it stood empty, then vanished at once)
    func windowWillEnterFullScreen(_ notification: Notification) { pagesFullScreen(true) }
    func windowDidExitFullScreen(_ notification: Notification) { tabBar?.placeTrafficLights(); pagesFullScreen(false) }
    func windowDidEnterFullScreen(_ notification: Notification) {
        pagesFullScreen(true)
        bodyTop?.constant = 0
        setBar(shown: false, animated: false)
        // the system menu bar takes the pointer at the very top edge, so the window never sees it arrive; instead the tabs follow
        // the menu bar: it slides in, the tabs slide in under it (next to the window buttons that come with it); it leaves and the
        // tabs leave too, unless the pointer is on them
        let timer = Timer(timeInterval: 0.08, repeats: true) { [weak self] _ in
            guard let self, let w = self.window else { return }
            // the pointer position is known even while the menu bar holds it (NSMenu.menuBarVisible() stays false in full screen)
            let p = NSEvent.mouseLocation, fromTop = w.frame.maxY - p.y, inside = p.x >= w.frame.minX && p.x <= w.frame.maxX
            let want = inside && (fromTop < 4 || (self.barShown && fromTop < self.revealedTop() + TabBar.height + 8))
            if want { self.barHideWork?.cancel(); self.barHideWork = nil; self.setBar(shown: true, animated: true) }
            else if self.barShown && self.barHideWork == nil {
                let work = DispatchWorkItem { [weak self] in self?.barHideWork = nil; self?.setBar(shown: false, animated: true) }
                self.barHideWork = work; DispatchQueue.main.asyncAfter(deadline: .now() + 0.3, execute: work)
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        barMonitor = timer
    }
    func windowWillExitFullScreen(_ notification: Notification) {
        pagesFullScreen(false)
        (barMonitor as? Timer)?.invalidate(); barMonitor = nil
        barHideWork?.cancel(); barHideWork = nil
        bodyTop?.constant = TabBar.height
        setBar(shown: true, animated: false)
        barTop?.constant = 0
    }
    func setBar(shown: Bool, animated: Bool) {
        barShown = shown
        let full = window?.styleMask.contains(.fullScreen) == true
        let target: CGFloat = shown ? (full ? revealedTop() : 0) : -TabBar.height - 2
        guard animated else { barTop?.constant = target; return }
        if barTop?.constant == target { return }
        NSAnimationContext.runAnimationGroup { ctx in ctx.duration = 0.18; ctx.allowsImplicitAnimation = true; barTop?.animator().constant = target }
    }
    // in full screen the menu bar and the window buttons come in as a separate overlay; the tabs go right under it
    func revealedTop() -> CGFloat {
        guard let w = window else { return 0 }
        // the overlay window is taller than the strip you see; the strip is the 28 pt band the window buttons are centred in
        if let b = w.standardWindowButton(.closeButton), let tw = b.window, tw !== w, tw.isVisible {
            let r = tw.convertToScreen(b.convert(b.bounds, to: nil))
            if r.midY < w.frame.maxY + 40 { return max(0, min(120, w.frame.maxY - (r.midY - 14))) }
        }
        return (w.screen?.safeAreaInsets.top ?? 0) > 0 ? (w.screen?.safeAreaInsets.top ?? 0) + 28 : 24 + 28
    }
    // per catalog, so a test catalog (--catalog) never touches the owner's tabs
    func key(_ name: String) -> String { name + ":" + registry.file.path }
    func tabItems() -> [TabBar.Item] { tabs.compactMap { id in registry.projects.first { $0.id == id }.map { TabBar.Item(id: id, name: $0.name) } } }
    func saveTabs() { defaults.set(tabs.map(\.uuidString), forKey: key("openTabs")); defaults.set(selected?.uuidString, forKey: key("selectedTab")) }
    // Home is an HTML page (review/home.html) in its own web view: edits show with ⌘R like the canvas; actions come back through "hyimg"
    @objc func showProjects() {
        markSeen(selected)   // the board leaving the front: what was done on it while it was there is not news
        selected = nil
        tabBar?.selected = nil
        updateTitle()
        saveTabs(); writeActive()
        let web: WKWebView
        if let homeWeb { web = homeWeb }
        else {
            let configuration = WKWebViewConfiguration()
            configuration.userContentController.add(self, name: "hyimg")
            setHomeLang(configuration.userContentController)   // window.HY_LANG before Home's first line (owner 2026-10-06)
            web = FirstClickWebView(frame: .zero, configuration: configuration)
            web.isInspectable = true
            web.uiDelegate = self
            web.setValue(false, forKey: "drawsBackground")
            homeWeb = web
            let page = sourceRoot.appendingPathComponent("review/home.html")
            web.loadFileURL(page, allowingReadAccessTo: URL(fileURLWithPath: "/"))
        }
        replaceContent(web)
        window?.makeFirstResponder(web)
        opening = nil
        web.evaluateJavaScript("window.hyimgBack && window.hyimgBack()")   // Home settles in at once with what it has; fresh data follows
        pushHome()
    }
    // Home's data is read off the main thread; on quit Chromium owns the memory allocator once it stops, so a read still running
    // then crashed while freeing its dictionaries (2026-10-04): the quit waits for it before Chromium stops
    let homeWork = DispatchGroup()
    var homeSeq = 0   // the latest Home list asked for: an older one built more slowly never overwrites it
    var quitting = false
    func pushHome() {
        guard let web = homeWeb, !quitting else { return }
        homeSeq += 1; let seq = homeSeq
        let projects = registry.projects, openIDs = Set(tabs), opened = defaults.dictionary(forKey: key("opened")) as? [String: Double] ?? [:]
        let engine = useChromium ? "chromium" : "webkit", cef = HYCef.available()
        // news since the owner last saw each board (BoardNews, BoardSeen): a board never seen since this came in counts from when it was
        // last opened (or from now), and that start is written down so it holds; the board in front has none
        var seen = BoardSeen.read(seenFile); let now = Date().timeIntervalSince1970, front = selected
        let fresh = projects.filter { seen[$0.id.uuidString] == nil }
        if !fresh.isEmpty { fresh.forEach { seen[$0.id.uuidString] = opened[$0.id.uuidString] ?? now }; BoardSeen.write(seenFile, seen) }
        let since = seen
        DispatchQueue.global(qos: .userInitiated).async(group: homeWork) {
            let list: [[String: Any]] = projects.map { p in
                var d = HomeData.info(for: p); d["open"] = openIDs.contains(p.id); d["opened"] = opened[p.id.uuidString] ?? 0
                if p.id != front, let news = BoardNews.summary(stateRoot: p.stateRoot, since: since[p.id.uuidString] ?? now) { d["news"] = news }
                return d
            }
            guard let data = try? JSONSerialization.data(withJSONObject: ["projects": list, "settings": self.readSettings(), "home": self.readHome(), "engine": engine, "cef": cef]), let json = String(data: data, encoding: .utf8) else { return }
            // (owner 2026-10-06: a removed board stayed on Home: closing its tab asked for the list first, and that list, built in
            // parallel and later, landed after the one without it)
            DispatchQueue.main.async { guard seq == self.homeSeq else { return }; web.evaluateJavaScript("window.hyimgHome && window.hyimgHome(\(json))") }
        }
    }
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        if body["action"] as? String == "dragband" {
            if message.webView === homeWeb { homeBand = DragStrip.band(body) } else { sessions.values.first { $0.web === message.webView }?.band = DragStrip.band(body) }
            return
        }
        if let session = sessions.values.first(where: { $0.web === message.webView }) {
            if body["action"] as? String == "canvasReady" { canvasReady(session, body["text"] as? String); return }
            if body["action"] as? String == "dotspec" { dotSpec(session, body["spec"]); return }
            if body["action"] as? String == "log", let text = body["text"] as? String { appLog("page \(session.server.project.name): \(text)"); return }
            if body["action"] as? String == "step" { if opening == session.server.project.id, let text = body["text"] as? String { homeProgress(opening!, text) }; return }
            if body["action"] as? String == "crumb" { if opening == session.server.project.id, let page = body["page"] as? String { homeCrumb(page) }; return }
            handle(ofBoard(body, session)); return
        }
        handle(body)
    }
    // a message from a board's own page names no board: it is that board's (its crumb's menu: open its folder, rename it)
    func ofBoard(_ body: [String: Any], _ session: ProjectView) -> [String: Any] {
        var b = body; if b["id"] == nil { b["id"] = session.server.project.id.uuidString }; return b
    }
    func handle(_ body: [String: Any]) {
        guard let action = body["action"] as? String else { return }
        let project = (body["id"] as? String).flatMap(UUID.init).flatMap { id in registry.projects.first { $0.id == id } }
        switch action {
        case "ready":
            pushHome()
            if window?.styleMask.contains(.fullScreen) == true { homeWeb?.evaluateJavaScript("window.hyimgFS && window.hyimgFS(true)") }   // Home reloaded in full screen (a language change) keeps the capsule hidden
        // a board's language switch (ui/i18n.js T.set → hyLangChanged → {action:"lang"}): written to the app's file at once, so it is
        // right even if the page's own POST is late, and applied to the menus and Home (owner 2026-10-06)
        case "lang": if let v = body["lang"] as? String { writeSettings(["cv.lang": Lang.pick(v)]) }
        case "home":   // the house on the canvas's plate «⌂ › project › page», or the board's folder on it (Home shows that folder)
            showProjects()
            if let f = body["folder"] as? String { homeWeb?.evaluateJavaScript("window.hyimgShowFolder && window.hyimgShowFolder(\(jsString(f)))") }
        // Home's loading screen: the owner changed their mind (owner 2026-10-04: «while loading I may want to leave»): Home stays, the
        // board goes on loading behind with its steps on its card, and does not come to the front when drawn
        case "cancelOpen":
            if let project { appLog("cancelOpen \(project.name)"); markSeen(project.id); if opening == project.id { opening = nil }; if selected == project.id { selected = nil; saveTabs(); writeActive() } }
        // Home's card menu: a board's server started without opening it, or stopped (its green mark goes)
        case "startServer": if let project { warm(project) }
        case "ground": DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in self?.applyGround() }   // a board changed the paper's colour (its file write lands first)
        case "stopServer": if let project { closeTab(project.id) }
        case "removeBoard": if let project { removeBoard(project) }   // Home's red «Remove board…» (owner 2026-10-06)
        case "homeSave": if let h = body["home"] as? [String: Any] { writeHome(h) }   // Home's folders of projects
        case "handoff": if let id = (body["id"] as? String).flatMap(UUID.init) { handoff(id, stars: body["stars"] as? [String: Any], lines: body["lines"] as? [String]) }
        case "settings": if let change = body["change"] as? [String: Any] { writeSettings(change) }   // Home's gear: the app's settings
        case "open": if let project { openProject(project) }
        case "add": addProject(into: body["folder"] as? String)
        case "create": createProject(into: body["folder"] as? String)
        case "rename": if let project { rename(project) }
        case "renameTo": if let project, let name = body["name"] as? String { renameTo(project, name) }   // the crumb's name edited in place (a double click)
        case "relink": if let project { relink(project) }
        case "reveal": if let project { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: project.libraryRoot)]) }
        case "openFolder": if let project { NSWorkspace.shared.open(URL(fileURLWithPath: project.libraryRoot, isDirectory: true)) }   // Home's list: the board's own folder, opened in Finder
        case "storage": storageMessage(body, project)   // Settings › Storage: sizes, memory, «Clear cache» (StorageBridge.swift)
        case "engine": if let e = body["engine"] as? String, (e == "chromium") != useChromium { toggleEngine() }   // CEF: the canvas gear
        default: break
        }
    }
    // the app's settings (settings.json beside the catalog, owner 2026-10-04): the same file every project's server reads and writes,
    // under the same lock (review/server.py settings_write)
    func readSettings() -> [String: Any] {
        guard let p = ServerSession.settingsFile, let d = try? Data(contentsOf: URL(fileURLWithPath: p)),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [:] }
        return j
    }
    // Home's own arrangement (owner 2026-10-04: «a folder that gathers projects, Studio North, Lookbook FW27; not a Finder folder»):
    // folders of projects by id, beside the catalog; the catalog of projects stays as it is
    var homeFile: URL { registry.file.deletingLastPathComponent().appendingPathComponent("home.json") }
    // when the owner last saw each board (ProjectRegistry.swift BoardSeen): Home's news counts from there
    var seenFile: URL { registry.file.deletingLastPathComponent().appendingPathComponent("seen.json") }
    // a board came to the front or left it: its news is read; Home takes the number off its card at once (owner 2026-10-06: «the
    // number clears as soon as I open that board»), before its next list arrives
    func markSeen(_ id: UUID?) {
        guard let id else { return }
        BoardSeen.mark(seenFile, [id])
        homeWeb?.evaluateJavaScript("window.hyimgSeen && window.hyimgSeen(\"\(id.uuidString)\")")
    }
    // the Home folder a board is in (Home's own grouping, home.json), for the board's crumb «⌂ › folder › board › page»
    func folderOf(_ id: UUID) -> (id: String, name: String, icon: String, color: String)? {
        guard let folders = readHome()["folders"] as? [[String: Any]] else { return nil }
        for f in folders where (f["projects"] as? [String] ?? []).contains(id.uuidString) {
            if let fid = f["id"] as? String { return (fid, f["name"] as? String ?? "", f["icon"] as? String ?? "", f["color"] as? String ?? "") }
        }
        return nil
    }
    func jsString(_ s: String) -> String { (try? JSONSerialization.data(withJSONObject: [s])).flatMap { String(data: $0, encoding: .utf8) }.map { "\($0)[0]" } ?? "\"\"" }
    // a board's server and page started from Home's card menu, without opening it: it loads behind, its steps on its card, its green mark on
    func warm(_ project: Project) {
        guard sessions[project.id] == nil, FileManager.default.fileExists(atPath: project.libraryRoot) else { return }
        if !tabs.contains(project.id) { tabs.append(project.id); saveTabs() }
        let session = makeSession(project)
        homeProgress(project.id, L("Starting “%@”", project.name))
        stage(session); load(session); pushHome()
    }
    func readHome() -> [String: Any] {
        (try? Data(contentsOf: homeFile)).flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
    }
    func writeHome(_ h: [String: Any]) {
        if let data = try? JSONSerialization.data(withJSONObject: h, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: homeFile, options: .atomic) }
    }
    func writeSettings(_ change: [String: Any]) {
        guard let p = ServerSession.settingsFile else { return }
        let fd = open(p + ".lock", O_CREAT | O_RDWR, 0o644); if fd >= 0 { flock(fd, LOCK_EX) }
        defer { if fd >= 0 { flock(fd, LOCK_UN); close(fd) } }
        var cur = readSettings()
        for (k, v) in change { if v is NSNull { cur.removeValue(forKey: k) } else { cur[k] = "\(v)" } }
        if let data = try? JSONSerialization.data(withJSONObject: cur, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: URL(fileURLWithPath: p), options: .atomic) }
        applyGround()
        sessions.values.forEach { pullSettings($0) }   // the boards take Home's change now, not when they next come to the front
        syncLang()   // cv.lang among the changes (Home's gear, the Language menu, a board): menus, title and Home follow
    }
    // a board reads the app's settings file again (ui/settings.js, its pull), the canvas inside it too (owner 2026-10-04: «the
    // settings do not sync»): after a change on Home, and whenever a board comes to the front
    func pullSettings(_ session: ProjectView) {
        evaluate(session, "window.hyimgSettingsPull && window.hyimgSettingsPull()")
    }
    // the ground under every page is the board's paper of the app's theme (owner 2026-10-04: «the background in the app itself, the
    // server brings only the dots, so it is seamless»): the window, the web views before their first paint, Chromium's too
    func applyGround() {
        let t = (readSettings()["cv.theme"] as? String) ?? "auto"
        let dark = t == "dark" || (t == "auto" && NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua)
        // the paper's colour of that theme: the owner's own (settings cv.paperDark / cv.paperLight, «#rrggbb») or the default
        let own = (readSettings()[dark ? "cv.paperDark" : "cv.paperLight"] as? String).flatMap { UInt32($0.trimmingCharacters(in: CharacterSet(charactersIn: "#")), radix: 16) }
        let rgb: UInt32 = own ?? (dark ? 0x17171a : 0xebe6dc)
        window?.backgroundColor = NSColor(srgbRed: CGFloat((rgb >> 16) & 0xff) / 255, green: CGFloat((rgb >> 8) & 0xff) / 255, blue: CGFloat(rgb & 0xff) / 255, alpha: 1)
        HYCefView.setGround(rgb)
    }
    // for the agent (owner 2026-09-30: "you should see which project I'm in and what I selected"): scripts/active.py reads this
    func writeActive() {
        let dir = registry.file.deletingLastPathComponent()
        var d: [String: Any] = ["t": Date().timeIntervalSince1970, "view": selected == nil ? "home" : "project", "tabs": tabs.map(\.uuidString)]
        if let id = selected, let p = registry.projects.first(where: { $0.id == id }) {
            d["project"] = ["id": id.uuidString, "name": p.name, "libraryRoot": p.libraryRoot, "stateRoot": p.stateRoot, "styleRefs": p.styleRefs ?? "", "port": p.port]
        }
        if let data = try? JSONSerialization.data(withJSONObject: d, options: [.prettyPrinted]) { try? data.write(to: dir.appendingPathComponent("active.json"), options: .atomic) }
    }
    func closeTab(_ id: UUID) {
        let finish = {
            self.sessions[id]?.cef?.closeBrowser()   // CEF
            self.sessions[id]?.server.stopSynchronously()
            self.sessions.removeValue(forKey: id)
            let k = self.tabs.firstIndex(of: id) ?? 0
            self.tabs.removeAll { $0 == id }
            self.tabBar?.items = self.tabItems()
            if self.selected == id {
                if self.tabs.isEmpty { self.showProjects() }
                else if let p = self.registry.projects.first(where: { $0.id == self.tabs[min(k, self.tabs.count - 1)] }) { self.openProject(p) }
            } else { self.saveTabs(); self.writeActive(); if self.selected == nil { self.pushHome() } }
        }
        if let session = sessions[id] { performAfterSaving(session, operation: finish) } else { finish() }
    }
    @objc func closeCurrentTab() { if let selected { closeTab(selected) } }
    // ⌃Tab / ⌃⇧Tab walk the open tabs, Home included, in a ring (owner 2026-09-30)
    @objc func nextTab() { stepTab(1) }
    @objc func previousTab() { stepTab(-1) }
    func stepTab(_ d: Int) {
        let ring: [UUID?] = [nil] + tabs.map { Optional($0) }
        guard ring.count > 1 else { return }
        let k = ring.firstIndex(of: selected) ?? 0, next = ring[(k + d + ring.count) % ring.count]
        if let id = next, let p = registry.projects.first(where: { $0.id == id }) { openProject(p) } else { showProjects() }
    }
    func alert(_ text: String, detail: String = "") {
        let alert = NSAlert()
        alert.messageText = text
        alert.informativeText = detail
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
    @objc func addProject() { addProject(into: nil) }
    func addProject(into folder: String?) {
        let panel = NSOpenPanel()
        panel.title = L("Add a folder of images")
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { let project = try registry.register(path: url.path, name: nil, styleRefs: nil); fileInto(folder, project); openProject(project) }
        catch { alert(L("Couldn't add the board"), detail: error.localizedDescription) }
    }
    // «New board» picks the board's folder (owner 2026-10-06: «I selected the folder, it took a file instead»): it was a Save panel,
    // which always makes a new folder named by its name field inside the one shown, so choosing an existing folder made
    // «Product Atlas Gen2/GEMINI.md/». Now it is an Open panel for folders: an existing one, or a new one from its New Folder button.
    // A folder that already has a board opens that board.
    @objc func createProject() { createProject(into: nil) }
    func createProject(into folder: String?) {
        let panel = NSOpenPanel()
        panel.title = L("Folder for the new board")
        panel.message = L("Choose the folder of the board's images, or make a new one with New Folder.")
        panel.prompt = L("Create board")
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do { let project = try registry.register(path: url.path, name: nil, styleRefs: nil); fileInto(folder, project); openProject(project) }
        catch { alert(L("Couldn't create the board"), detail: error.localizedDescription) }
    }
    // a board made while a project was picked on Home goes into that project (home.json, the same list Home's drag writes)
    func fileInto(_ folder: String?, _ project: Project) {
        guard let folder else { return }
        var h = readHome(); var folders = h["folders"] as? [[String: Any]] ?? []
        guard let k = folders.firstIndex(where: { $0["id"] as? String == folder }) else { return }
        var ids = folders[k]["projects"] as? [String] ?? []
        for i in folders.indices { folders[i]["projects"] = (folders[i]["projects"] as? [String] ?? []).filter { $0 != project.id.uuidString } }   // one project per board
        ids = ids.filter { $0 != project.id.uuidString } + [project.id.uuidString]; folders[k]["projects"] = ids
        h["folders"] = folders; writeHome(h); pushHome()
    }
    func rename(_ project: Project) {
        let prompt = NSAlert()
        prompt.messageText = L("Board name")
        prompt.informativeText = L("The folder name and the files stay the same.")
        let field = NSTextField(string: project.name)
        field.frame = NSRect(x: 0, y: 0, width: 360, height: 24)
        prompt.accessoryView = field
        prompt.addButton(withTitle: L("Save"))
        prompt.addButton(withTitle: L("Cancel"))
        prompt.window.initialFirstResponder = field
        guard prompt.runModal() == .alertFirstButtonReturn else { return }
        renameTo(project, field.stringValue)
    }
    // the rename itself, from the modal above or from the field in the board's crumb: the catalog, the tabs, Home, the crumb
    // off the list after a question; its tab and server close first, the folder stays untouched
    func removeBoard(_ project: Project) {
        let ask = NSAlert()
        ask.messageText = String(format: L("Remove “%@” from Hyimg?"), project.name)
        ask.informativeText = L("The board leaves the list. Its folder, pictures and saved board stay on disk; adding the folder again brings it back.")
        ask.addButton(withTitle: L("Remove")).hasDestructiveAction = true
        ask.addButton(withTitle: L("Cancel"))
        guard ask.runModal() == .alertFirstButtonReturn else { return }
        closeTab(project.id)
        do { try registry.remove(id: project.id); tabBar?.items = tabItems(); pushHome(); writeActive() }
        catch { alert(L("Couldn't remove the board"), detail: error.localizedDescription) }
    }
    func renameTo(_ project: Project, _ newName: String) {
        do {
            try registry.rename(id: project.id, name: newName); tabBar?.items = tabItems(); pushHome(); writeActive()
            if let s = sessions.values.first(where: { $0.server.project.id == project.id }), let name = registry.projects.first(where: { $0.id == project.id })?.name {
                evaluate(s, "window.hyimgProjName && window.hyimgProjName(\(jsString(name)))")   // the board's crumb shows the new name at once
            }
        }
        catch {
            alert(L("Couldn't rename the board"), detail: error.localizedDescription)
            if let s = sessions.values.first(where: { $0.server.project.id == project.id }) { evaluate(s, "window.hyimgProjName && window.hyimgProjName(\(jsString(project.name)))") }   // the crumb takes its old name back
        }
    }
    func relink(_ project: Project) {
        let panel = NSOpenPanel()
        panel.title = L("Choose the folder of “%@”", project.name)
        panel.message = L("No files are moved. The previous _review folder, if it is still there, stays the source of the data.")
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        let relink = {
            do {
                try self.registry.relink(id: project.id, path: url.path)
                self.sessions[project.id]?.server.stopSynchronously()
                self.sessions.removeValue(forKey: project.id)
                self.tabs.removeAll { $0 == project.id }; self.tabBar?.items = self.tabItems()
                self.showProjects()
            } catch { self.alert(L("Couldn't link the folder"), detail: error.localizedDescription) }
        }
        if let session = sessions[project.id] { performAfterSaving(session, operation: relink) }
        else { relink() }
    }
    func openProject(_ project: Project) {
        guard FileManager.default.fileExists(atPath: project.libraryRoot) else { showProjects(); relink(project); return }
        if selected != project.id { markSeen(selected) }   // the board it replaces in front
        selected = project.id
        markSeen(project.id)
        if !tabs.contains(project.id) { tabs.append(project.id); tabBar?.items = tabItems() }
        tabBar?.selected = project.id
        updateTitle()
        var opened = defaults.dictionary(forKey: key("opened")) as? [String: Double] ?? [:]; opened[project.id.uuidString] = Date().timeIntervalSince1970; defaults.set(opened, forKey: key("opened"))
        saveTabs(); writeActive()
        let session = makeSession(project)
        if let folder = folderOf(project.id) { evaluate(session, "window.hyimgFolder && window.hyimgFolder(\(jsString(folder.name)), \(jsString(folder.id)), \(jsString(folder.icon)), \(jsString(folder.color)))") }   // the project with its icon
        openSession(project, session)
    }
    // a board's page and server, made once and kept while the board is open
    func makeSession(_ project: Project) -> ProjectView {
        let session: ProjectView
        if let existing = sessions[project.id] { session = existing }
        else {
            session = ProjectView(project: project, sourceRoot: sourceRoot)
            if useChromium && startChromium() { attachChromium(session) }   // CEF
            else { session.web.configuration.userContentController.add(self, name: "hyimg") }   // the canvas gear «Движок»
            session.web.appearance = NSApp.effectiveAppearance   // the page's «Авто» theme follows macOS, not the dark window chrome
            session.web.setValue(false, forKey: "drawsBackground")   // the window's paper shows until the page paints
            session.web.navigationDelegate = self
            session.web.uiDelegate = self
            sessions[project.id] = session
        }
        return session
    }
    func openSession(_ project: Project, _ session: ProjectView) {
        // owner 2026-10-04: «we go from Home to the chosen board and the loading happens there, the server and so on, and then the
        // animation», and «until the canvas is drawn with its UI, even if the pictures are not there yet, the dolly zoom does not start».
        // Home leaves at once and keeps the board's plate and the steps in the middle (hyimgOpen); the board comes in front when its
        // canvas says it is drawn (canvasReady, then Home finishes the steps and answers «handoff») and plays its entrance there.
        if let home = homeWeb, inFront(home) {
            opening = project.id
            let name = (try? JSONSerialization.data(withJSONObject: [project.name])).flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
            home.evaluateJavaScript("window.hyimgOpen ? window.hyimgOpen(\"\(project.id.uuidString)\", \(name)[0]) : null") { [weak self] result, error in
                if (result as? Bool) != true {   // an older Home without it
                    self?.appLog("hyimgOpen answered \(String(describing: result)) \(error.map { "\($0)" } ?? ""): the board comes in front at once")
                    self?.handoff(project.id)
                }
            }
            let id = project.id
            DispatchQueue.main.asyncAfter(deadline: .now() + 120) { [weak self] in   // a canvas that never says it is drawn does not keep Home up (a big board took longer than 20 s)
                guard let self, self.opening == id else { return }
                self.appLog("no canvasReady in 120 s: the board comes in front")
                self.handoff(id)
            }
            if session.loaded { evaluate(session, "window.hyimgPrep && window.hyimgPrep()") }   // its page hides until its entrance
            if session.drawn { askHandoff(project.id) }   // drawn already: it comes once Home is gone
            else {
                homeProgress(project.id, L("Opening “%@”", project.name))
                stage(session)
                if !session.loading && !session.loaded { load(session) }
            }
        } else {   // no Home behind (a test catalog, a failure, a tab): at once, the canvas starts its entrance when it is drawn
            front(session)
            if session.drawn { evaluate(session, "window.hyimgIntro && window.hyimgIntro()") }
            else if !session.loading && !session.loaded { load(session) }
        }
    }
    var opening: UUID?   // the board coming from Home
    // the canvas of a board is drawn (review/canvas.html drawn()): in front it comes in now; opening from Home, Home finishes and hands over
    func canvasReady(_ session: ProjectView, _ text: String?) {
        session.drawn = true
        appLog("canvasReady \(session.server.project.name) opening=\(opening == session.server.project.id) front=\(inFront(session.surface))")
        let id = session.server.project.id
        if opening != id { homeProgress(id, L("Board drawn"), done: true) }   // steps of a board opened without Home do not hang on its cover
        if inFront(session.surface) { evaluate(session, "window.hyimgIntro && window.hyimgIntro()"); return }
        guard selected == id, opening == id else { return }   // drawn in the background: its entrance plays when it comes
        if let text, !text.isEmpty { homeProgress(id, text) }
        homeProgress(id, L("Board drawn"), done: true)
        askHandoff(id)
    }
    // the board's grid, sent by its page as it starts: Home's loading stars fly along it (review/ui/stars.js)
    func dotSpec(_ session: ProjectView, _ spec: Any?) {
        let id = session.server.project.id
        if opening != id, inFront(session.surface) { evaluate(session, "window.hyimgStarsNow && window.hyimgStarsNow()"); return }   // loading in front: its own stars
        guard opening == id, let spec, let data = try? JSONSerialization.data(withJSONObject: spec), let json = String(data: data, encoding: .utf8) else { return }
        homeWeb?.evaluateJavaScript("window.hyimgStars && window.hyimgStars(\"\(id.uuidString)\", \(json))")
    }
    func askHandoff(_ id: UUID) {
        homeWeb?.evaluateJavaScript("window.hyimgHandoff ? window.hyimgHandoff(\"\(id.uuidString)\") : null") { [weak self] result, _ in
            if (result as? Bool) != true { self?.handoff(id) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 6) { [weak self] in self?.handoff(id) }   // a stuck Home never keeps the board away
    }
    func handoff(_ id: UUID, stars: [String: Any]? = nil, lines: [String]? = nil) {
        guard opening == id else { return }
        opening = nil
        guard selected == id, let session = sessions[id] else { return }
        // Home's loading stars go on in the canvas from where they are (their seed and start time, review/ui/stars.js) and Home's
        // steps go on there as they stood: the page takes them first, under Home, and comes in front a moment later, so its own
        // shorter list never shows («it fades, then appears again», owner 2026-10-04)
        var o: [String: Any] = [:]; if let stars { o["stars"] = stars }; if let lines { o["lines"] = lines }
        let arg = o.isEmpty ? "" : (try? JSONSerialization.data(withJSONObject: o)).flatMap { String(data: $0, encoding: .utf8) } ?? ""
        if session.drawn { evaluate(session, "window.hyimgIntro && window.hyimgIntro(\(arg))") }
        appLog("handoff \(session.server.project.name) drawn=\(session.drawn) stars=\(stars != nil) lines=\(lines?.count ?? 0)")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) { [weak self, weak session] in
            guard let self, let session, self.selected == id else { return }
            self.front(session, why: "handoff")
        }
    }
    // Chromium makes a page only inside a window: while Home stays in front the project's view waits in the window hidden, so its
    // page loads behind Home (without it the canvas never started and «Открываю» stayed forever, owner 2026-10-04)
    func stage(_ session: ProjectView) {
        guard let cef = session.cef, cef.window == nil, let content, let home = homeWeb, home.superview === content else { return }
        place(cef, below: home)   // under Home: it loads and draws there, Home keeps the clicks and the keys
    }
    func place(_ view: NSView, below other: NSView? = nil) {
        guard let content, view.superview !== content else { return }
        view.isHidden = false
        view.translatesAutoresizingMaskIntoConstraints = false
        if let other { content.addSubview(view, positioned: .below, relativeTo: other) } else { content.addSubview(view) }
        NSLayoutConstraint.activate([view.topAnchor.constraint(equalTo: content.topAnchor), view.bottomAnchor.constraint(equalTo: content.bottomAnchor), view.leadingAnchor.constraint(equalTo: content.leadingAnchor), view.trailingAnchor.constraint(equalTo: content.trailingAnchor)])
    }
    func isLive(_ view: NSView) -> Bool { view === homeWeb || sessions.values.contains { $0.surface === view } }
    // a short log of what the app opens (~/Library/Logs/Hyimg/app.log), for finding out what happened in the app itself
    func appLog(_ line: String) {
        let url = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Hyimg/app.log")
        let text = "\(ISO8601DateFormatter().string(from: Date())) \(line)\n"
        if let h = try? FileHandle(forWritingTo: url) { h.seekToEndOfFile(); h.write(Data(text.utf8)); try? h.close() } else { try? text.write(to: url, atomically: true, encoding: .utf8) }
    }
    // the top band of the page in front: where the window drags from and where its plates take the clicks (DragStrip)
    func frontBand() -> DragStrip.Band? {
        guard let front = content?.subviews.last else { return nil }
        if front === homeWeb { return homeBand }
        return sessions.values.first { $0.surface === front }?.band
    }
    func inFront(_ view: NSView?) -> Bool { view != nil && content?.subviews.last === view }
    func bringToTop(_ view: NSView) {   // reorders without taking any page out of the window
        guard let content, content.subviews.last !== view else { return }
        content.sortSubviews({ a, b, context in
            let top = Unmanaged<NSView>.fromOpaque(context!).takeUnretainedValue()
            return a === top ? .orderedDescending : b === top ? .orderedAscending : .orderedSame
        }, context: Unmanaged.passUnretained(view).toOpaque())
    }
    func front(_ session: ProjectView, why: String = "") {
        appLog("front \(session.server.project.name) \(why) drawn=\(session.drawn) loaded=\(session.loaded)")   // a board in front before its entrance (owner 2026-10-04)
        if opening == session.server.project.id { opening = nil }
        syncLang()   // the fallback for a language changed where the app was not told (owner 2026-10-06)
        pullSettings(session)
        replaceContent(session.surface)
        if let cef = session.cef { cef.focusPage() } else { window?.makeFirstResponder(session.web) }
    }
    func evaluate(_ session: ProjectView, _ js: String) {
        if let cef = session.cef { cef.runJavaScript(js) } else { session.web.evaluateJavaScript(js) }
    }
    // a step of opening a project, shown on Home over its card (review/home.html window.hyimgProgress)
    func homeProgress(_ id: UUID, _ text: String, done: Bool = false, failed: Bool = false) {
        guard let web = homeWeb, let data = try? JSONSerialization.data(withJSONObject: ["id": id.uuidString, "text": text, "done": done, "failed": failed]),
              let json = String(data: data, encoding: .utf8) else { return }
        web.evaluateJavaScript("window.hyimgProgress && window.hyimgProgress(\(json))")
    }
    // the page of a board is there (its canvas still builds the board): a step on Home
    func pageLoaded(_ session: ProjectView) {
        let id = session.server.project.id
        let folder = folderOf(id)   // the board's Home folder on its crumb (none: the crumb has no folder step)
        evaluate(session, "window.hyimgFolder && window.hyimgFolder(\(jsString(folder?.name ?? "")), \(jsString(folder?.id ?? "")), \(jsString(folder?.icon ?? "")), \(jsString(folder?.color ?? "")))")
        if opening == id { homeProgress(id, L("Page loaded, building the board")) }
    }
    // CEF: the same events the WKWebView delegate handles, from Chromium
    func attachChromium(_ session: ProjectView) {
        let id = session.server.project.id.uuidString
        let cef = HYCefView(cachePath: cefRoot.appendingPathComponent(id).path)
        session.cef = cef
        let port = session.server.project.port
        cef.allowNavigation = { url in
            guard let u = URL(string: url) else { return false }
            if u.scheme == "data" || u.scheme == "about" || u.scheme == "blob" { return true }
            if u.scheme == "http", u.host == "127.0.0.1", u.port == port { return true }
            if ["http", "https", "mailto"].contains(u.scheme ?? "") { NSWorkspace.shared.open(u) }
            return false
        }
        cef.onLoadStart = { [weak session] url in
            guard let session, url.hasPrefix("http://127.0.0.1:\(port)") else { return }
            session.loading = true
        }
        cef.onLoad = { [weak self, weak session] ok, url, error in
            guard let self, let session else { return }
            if ok {
                guard url.hasPrefix("http://127.0.0.1:\(port)") else { return }
                session.loaded = true; session.loading = false; session.shown = true
                self.pageLoaded(session)
            } else {
                session.loaded = false; session.loading = false
                self.showFailure(session, message: error ?? L("The page did not load"))
                if self.selected == session.server.project.id { self.front(session) }
            }
        }
        cef.onMessage = { [weak self, weak session] line in
            guard let self, let session else { return }
            if line.hasPrefix("HYIMG_MSG:{\"action\":\"canvasReady\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                self.canvasReady(session, body["text"] as? String)
            } else if line.hasPrefix("HYIMG_MSG:{\"action\":\"dotspec\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                self.dotSpec(session, body["spec"])
            } else if line.hasPrefix("HYIMG_MSG:{\"action\":\"log\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let text = body["text"] as? String {
                self.appLog("page \(session.server.project.name): \(text)")   // the page's own notes into the app's log
            } else if line.hasPrefix("HYIMG_MSG:{\"action\":\"step\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let text = body["text"] as? String {
                if self.opening == session.server.project.id { self.homeProgress(session.server.project.id, text) }   // the board's own steps on Home
            } else if line.hasPrefix("HYIMG_MSG:{\"action\":\"crumb\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let page = body["page"] as? String {
                if self.opening == session.server.project.id { self.homeCrumb(page) }   // the page's name on Home's loading plate
            } else if line.hasPrefix("HYIMG_MSG:{\"action\":\"dragband\""), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
               let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                session.band = DragStrip.band(body)
            } else if line.hasPrefix("HYIMG_FLUSH:") {
                let parts = line.split(separator: ":")
                if parts.count == 3, let respond = session.flushWaiters.removeValue(forKey: String(parts[1])) { respond(.success(parts[2] == "true")) }
            } else if line.hasPrefix("HYIMG_MSG:"), let data = line.dropFirst("HYIMG_MSG:".count).data(using: .utf8),
                      let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                self.handle(self.ofBoard(body, session))
            }
        }
        cef.onCrash = { [weak self, weak session] in
            guard let self, let session else { return }
            session.loaded = false; session.loading = false
            self.alert(L("The board's page quit"), detail: L("The latest unsaved changes may not have been written. Press ⌘R to open the saved version."))
        }
    }
    @objc func toggleEngine() {   // CEF: Вид › Движок Chromium; the open projects reopen in the other engine after saving
        let next = useChromium ? "webkit" : "chromium"
        if next == "chromium" && !HYCef.available() { alert(L("This build has no Chromium"), detail: L("Build Hyimg with CEF: ./build.sh downloads and links it.")); return }
        let open = Array(sessions.values)
        flushAll(open[...]) { result in
            if case .failure(let error) = result { self.alert(L("Changes not saved"), detail: error.localizedDescription); return }
            self.defaults.set(next, forKey: self.key("engine")); self.buildMenu()
            for s in open { s.cef?.closeBrowser(); s.server.stopSynchronously() }
            self.sessions.removeAll()
            if let id = self.selected, let p = self.registry.projects.first(where: { $0.id == id }) { self.openProject(p) } else { self.showProjects() }
        }
    }
    func load(_ session: ProjectView, restart: Bool = false) {
        session.loading = true
        session.drawn = false
        if !session.loaded {
            let wait = "<html><meta charset='utf-8'><body style='background:#171719;color:#ddd;font:16px -apple-system;padding:60px'>\(L("Opening the board…"))</body></html>"
            if let cef = session.cef { cef.loadHTML(wait) } else { session.web.loadHTMLString(wait, baseURL: nil) }
        }
        let started = Date(), id = session.server.project.id
        homeProgress(id, L("Board server · port %ld", session.server.project.port))
        session.server.ensure(restart: restart) { [weak self, weak session] result in
            guard let self, let session else { return }
            switch result {
            case .success(let url):
                self.homeProgress(id, L("Server responded · %ld ms", Int(Date().timeIntervalSince(started) * 1000)))
                self.homeProgress(id, L("Loading the canvas and the library"))
                session.loaded = false
                var open = URLComponents(url: url, resolvingAgainstBaseURL: false)
                if open?.path == "/" || open?.path == "" { open?.queryItems = [URLQueryItem(name: "view", value: "canvas")] }   // a project opens on its canvas
                if self.inFront(session.surface) { let items = open?.queryItems ?? []; open?.queryItems = items + [URLQueryItem(name: "stars", value: "1")] }   // loading in front: its own stars at once
                appLog("load \(session.server.project.name) \((open?.url ?? url).absoluteString) front=\(self.inFront(session.surface))")
                if let cef = session.cef { cef.loadURL((open?.url ?? url).absoluteString) } else { session.web.load(URLRequest(url: open?.url ?? url)) }
            case .failure(let error):
                session.loading = false
                self.homeProgress(id, L("Did not open: %@", error.localizedDescription), failed: true)
                if self.selected == session.server.project.id {
                    self.front(session)
                    self.showFailure(session, message: error.localizedDescription)
                    self.alert(L("Couldn't open the board"), detail: error.localizedDescription)
                }
            }
        }
    }
    func showFailure(_ session: ProjectView, message: String) {
        let safe = message.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
        let page = "<html><meta charset='utf-8'><body style='background:#171719;color:#ddd;font:16px -apple-system;padding:60px'><h2>\(L("The board did not open"))</h2><p>\(safe)</p><p>\(L("Press ⌘R to try again or go back Home (⌘⇧H)."))</p></body></html>"
        if let cef = session.cef { cef.loadHTML(page) } else { session.web.loadHTMLString(page, baseURL: nil) }
    }
    @objc func reload() {
        guard let selected, let session = sessions[selected] else { homeWeb?.reloadFromOrigin(); return }   // ⌘R on Home reloads home.html
        performAfterSaving(session) { self.load(session) }
    }
    // View › Media Library ⌘M and Hide Interface ⌘. (owner 2026-10-06, as in Figma): the page takes the keys itself first; these are the
    // menu's own way to the same (a key the page did not take, a click on the item)
    @objc func menuLibrary() { pageMenu("library") }
    @objc func menuHideUI() { pageMenu("hideui") }
    func pageMenu(_ what: String) {
        guard let selected, let session = sessions[selected] else { return }
        evaluate(session, "window.hyimgMenu && window.hyimgMenu(\"\(what)\")")
    }
    @objc func restartServer() {
        guard let selected, let session = sessions[selected] else { return }
        performAfterSaving(session) { self.load(session, restart: true) }
    }
    @objc func openInBrowser() {
        guard let selected, let session = sessions[selected], let url = session.pageURL ?? session.server.baseURL else { return }
        NSWorkspace.shared.open(url)
    }
    func flush(_ session: ProjectView, completion: @escaping (Result<Void, Error>) -> Void) {
        if let cef = session.cef {   // CEF: the page answers with a console line HYIMG_FLUSH:<token>:<true|false>
            SaveBarrier.flush(loaded: session.loaded, loading: session.loading, evaluate: { respond in
                let token = UUID().uuidString
                session.flushWaiters[token] = respond
                cef.runJavaScript("(async()=>{let ok=true;try{ok=typeof window.hyimgFlush==='function'?(await window.hyimgFlush())===true:true}catch(e){ok=false}console.log('HYIMG_FLUSH:\(token):'+ok)})()")
            }, completion: { result in session.flushWaiters.removeAll(); completion(result) })
            return
        }
        SaveBarrier.flush(loaded: session.loaded, loading: session.loading, evaluate: { respond in
            session.web.callAsyncJavaScript("return typeof window.hyimgFlush==='function' ? await window.hyimgFlush() : true;",
                                            arguments: [:], in: nil, in: .page) { result in
                respond(result.map { ($0 as? Bool) == true })
            }
        }, completion: completion)
    }
    func savingSheet() -> NSWindow? {
        guard let window, window.attachedSheet == nil else { return nil }
        let sheet = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 360, height: 90), styleMask: [.titled], backing: .buffered, defer: false)
        sheet.title = "Hyimg"
        let message = label(L("Saving changes…"), size: 15)
        message.frame = NSRect(x: 28, y: 32, width: 310, height: 24)
        sheet.contentView?.addSubview(message)
        window.beginSheet(sheet)
        return sheet
    }
    func dismissSavingSheet(_ sheet: NSWindow?) {
        guard let sheet else { return }
        window?.endSheet(sheet)
        sheet.orderOut(nil)
    }
    func performAfterSaving(_ session: ProjectView, operation: @escaping () -> Void) {
        guard !session.operationPending && !terminationPending else { return }
        session.operationPending = true
        let sheet = savingSheet(), id = session.server.project.id
        homeProgress(id, L("Saving"))   // shown on the project's cover when Home is in front
        flush(session) { result in
            self.dismissSavingSheet(sheet)
            session.operationPending = false
            switch result {
            case .success: self.homeProgress(id, L("Saved"), done: true); operation()
            case .failure(let error): self.homeProgress(id, L("Not saved"), failed: true); self.alert(L("Changes not saved"), detail: error.localizedDescription)
            }
        }
    }
    func flushAll(_ pending: ArraySlice<ProjectView>, completion: @escaping (Result<Void, Error>) -> Void) {
        guard let first = pending.first else { completion(.success(())); return }
        flush(first) { result in
            switch result {
            case .success: self.flushAll(pending.dropFirst(), completion: completion)
            case .failure(let error): completion(.failure(error))
            }
        }
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !terminationPending else { return .terminateCancel }
        guard !sessions.values.contains(where: { $0.operationPending }) else {
            alert(L("Wait for saving to finish"), detail: L("Another action with the board is in progress."))
            return .terminateCancel
        }
        terminationPending = true
        let sheet = savingSheet()
        DispatchQueue.main.async {
            // a project still opening for the first time has no page and nothing to save: it does not hold the quit
            let open = self.sessions.values.filter { $0.shown || !$0.loading }
            self.flushAll(Array(open)[...]) { result in
                self.dismissSavingSheet(sheet)
                switch result {
                case .success: HYCef.closeAllThen { sender.reply(toApplicationShouldTerminate: true) }   // CEF: browsers close before the process ends
                case .failure(let error):
                    self.terminationPending = false
                    self.alert(L("Couldn't save the changes"), detail: error.localizedDescription)
                    sender.reply(toApplicationShouldTerminate: false)
                }
            }
        }
        return .terminateLater
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        if let id = selected { BoardSeen.mark(seenFile, [id]) }   // the board in front at quit was seen to the end
        sessions.values.forEach { $0.server.stopSynchronously() }
        _ = homeWork.wait(timeout: .now() + 5)
        HYCef.shutdown()   // CEF
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "about" || url.scheme == "blob" { decisionHandler(.allow); return }
        if let session = sessions.values.first(where: { $0.web === webView }),
           url.scheme == "http", url.host == "127.0.0.1", url.port == session.server.project.port {
            decisionHandler(.allow)
        } else {
            if ["http", "https", "mailto"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, ["http", "https", "mailto"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let panel = NSAlert(); panel.messageText = message; panel.runModal(); completionHandler()
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let panel = NSAlert(); panel.messageText = message; panel.addButton(withTitle: L("confirm::OK")); panel.addButton(withTitle: L("Cancel"))
        completionHandler(panel.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let panel = NSAlert(); panel.messageText = prompt
        let field = NSTextField(string: defaultText ?? ""); field.frame = NSRect(x: 0, y: 0, width: 360, height: 24)
        panel.accessoryView = field; panel.addButton(withTitle: L("Save")); panel.addButton(withTitle: L("Cancel"))
        panel.window.initialFirstResponder = field
        completionHandler(panel.runModal() == .alertFirstButtonReturn ? field.stringValue : nil)
    }
    // <input type="file"> (owner 2026-10-06: «Open file…» in a 3D card): WKWebView shows no panel unless the app does, a file input just did
    // nothing. The page may name the formats it wants in window.hyimgAccept (".glb,.gltf,.obj"); they narrow the panel, else any file can be
    // chosen. Chromium (CEF) has its own panel.
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        webView.evaluateJavaScript("window.hyimgAccept || ''", in: frame, in: .page) { result in
            if case .success(let value) = result, let accept = value as? String {
                let types = accept.split(separator: ",").compactMap { UTType(filenameExtension: $0.trimmingCharacters(in: CharacterSet(charactersIn: ". "))) }
                if !types.isEmpty { panel.allowedContentTypes = types }
            }
            let done: (NSApplication.ModalResponse) -> Void = { completionHandler($0 == .OK ? panel.urls : nil) }
            if let window = webView.window { panel.beginSheetModal(for: window, completionHandler: done) } else { done(panel.runModal()) }
        }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        guard (error as NSError).code != NSURLErrorCancelled,
              let session = sessions.values.first(where: { $0.web === webView }) else { return }
        session.loaded = false
        session.loading = false
        showFailure(session, message: error.localizedDescription)
    }
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        guard let session = sessions.values.first(where: { $0.web === webView }), webView.url?.scheme == "http" else { return }
        session.loading = true
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let session = sessions.values.first(where: { $0.web === webView }),
              webView.url?.host == "127.0.0.1", webView.url?.port == session.server.project.port else { return }
        session.loaded = true
        session.loading = false
        session.shown = true
        pageLoaded(session)
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard let session = sessions.values.first(where: { $0.web === webView }) else { return }
        session.loaded = false
        session.loading = false
        alert(L("The board's page quit"), detail: L("The latest unsaved changes may not have been written. Press ⌘R to open the saved version."))
    }
    func buildMenu() {
        let menu = NSMenu()
        func item(_ title: String, _ action: Selector, _ key: String, _ modifiers: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
            item.keyEquivalentModifierMask = modifiers
            return item
        }
        func section(_ title: String, _ items: [NSMenuItem]) {
            let root = NSMenuItem()
            let submenu = NSMenu(title: title)
            items.forEach { submenu.addItem($0) }
            root.submenu = submenu
            menu.addItem(root)
        }
        func engineItem() -> NSMenuItem {   // CEF
            let it = item(L("Chromium Engine"), #selector(toggleEngine), ""); it.state = useChromium ? .on : .off
            it.toolTip = HYCef.available() ? L("Boards are drawn by Chromium on the GPU; off: WebKit (as in Safari)") : L("This build has no Chromium"); return it
        }
        // Hyimg › Language (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»): each language
        // named in itself, a checkmark on the current one
        func languageItem() -> NSMenuItem {
            let root = NSMenuItem(title: L("Language"), action: nil, keyEquivalent: "")
            let submenu = NSMenu(title: L("Language"))
            for (code, name) in [("en", "English"), ("ru", "Русский")] {
                let it = NSMenuItem(title: name, action: #selector(chooseLanguage(_:)), keyEquivalent: "")
                it.target = self; it.representedObject = code; it.state = Lang.current == code ? .on : .off
                submenu.addItem(it)
            }
            root.submenu = submenu
            return root
        }
        section("Hyimg", [languageItem(), .separator(), item(L("Hide Hyimg"), #selector(NSApplication.hide(_:)), "h"), .separator(), item(L("Quit Hyimg"), #selector(NSApplication.terminate(_:)), "q")])
        section(L("Board"), [item(L("Home"), #selector(showProjects), "h", [.command, .shift]), item(L("Board from Finder Folder…"), #selector(addProject as () -> Void), "o"), item(L("New Board…"), #selector(createProject as () -> Void), "n"), .separator(), item(L("Next Tab"), #selector(nextTab), "\t", [.control]), item(L("Previous Tab"), #selector(previousTab), "\t", [.control, .shift]), item(L("Close Tab"), #selector(closeCurrentTab), "w")])
        section(L("Edit"), [item(L("Undo"), Selector(("undo:")), "z"), item(L("Redo"), Selector(("redo:")), "z", [.command, .shift]), .separator(), item(L("Cut"), #selector(NSText.cut(_:)), "x"), item(L("Copy"), #selector(NSText.copy(_:)), "c"), item(L("Paste"), #selector(NSText.paste(_:)), "v"), item(L("Select All"), #selector(NSText.selectAll(_:)), "a")])
        section(L("View"), [item(L("Reload Page"), #selector(reload), "r"), item(L("Restart Server"), #selector(restartServer), "r", [.command, .shift]), item(L("Open in Browser"), #selector(openInBrowser), "o", [.command, .shift]), .separator(), item(L("Media Library"), #selector(menuLibrary), "m"), item(L("Hide Interface"), #selector(menuHideUI), "."), .separator(), engineItem(), .separator(), item(L("Enter Full Screen"), #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control])])
        section(L("Window"), [item(L("Minimize"), #selector(NSWindow.miniaturize(_:)), "")])   // ⌘M is the media library's (owner 2026-10-06, as in Figma); the yellow button still minimizes
        NSApp.mainMenu = menu
    }
    // The interface language (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»). One source: the
    // app's setting cv.lang in settings.json, the file every board's server reads and writes; Lang.current caches it for L().
    // Whatever changed it (the Language menu, Home's gear, a board's settings, a board's own POST that came first) ends here:
    // the menus are built again, the window title follows, Home reloads with the new window.HY_LANG; the boards reload themselves
    // when their settings pull sees the new value (ui/i18n.js T.changed()).
    func fileLang() -> String { Lang.pick(readSettings()["cv.lang"] as? String) }
    func syncLang() { let v = fileLang(); if v != Lang.current { applyLang(v) } }
    func applyLang(_ v: String) {
        Lang.current = v
        appLog("language \(v)")
        buildMenu()
        updateTitle()
        tabBar?.relabel()
        if let web = homeWeb {
            setHomeLang(web.configuration.userContentController)
            web.reloadFromOrigin()
        }
    }
    @objc func chooseLanguage(_ sender: NSMenuItem) {
        guard let v = sender.representedObject as? String else { return }
        writeSettings(["cv.lang": Lang.pick(v)])   // writeSettings applies it and makes the boards pull it
    }
    // Home is a file page: it learns the language from the app before its first line runs (ui/i18n.js reads window.HY_LANG)
    func setHomeLang(_ controller: WKUserContentController) {
        controller.removeAllUserScripts()   // only this script is there; the "hyimg" message handler stays
        controller.addUserScript(WKUserScript(source: "window.HY_LANG = \"\(Lang.current)\";", injectionTime: .atDocumentStart, forMainFrameOnly: true))
    }
    func updateTitle() {
        if let id = selected, let p = registry.projects.first(where: { $0.id == id }) { window?.title = L("Hyimg · %@", p.name) }
        else { window?.title = L("Hyimg · Home") }
    }
    // the fallback: a change the app was not told about (a board's page wrote the file itself) is taken when the app comes back
    func applicationDidBecomeActive(_ notification: Notification) { syncLang() }
}

let arguments = CommandLine.arguments
func argument(_ name: String) -> String? {
    guard let index = arguments.firstIndex(of: name), arguments.indices.contains(index + 1) else { return nil }
    return arguments[index + 1]
}
do {
    let catalogURL: URL
    if let path = argument("--catalog") {
        guard path.hasPrefix("/") else { throw RegistryError.invalid(L("The --catalog path must be absolute.")) }
        catalogURL = URL(fileURLWithPath: path)
    } else {
        catalogURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Hyimg/projects.json")
    }
    Lang.current = Lang.read(settings: catalogURL.deletingLastPathComponent().appendingPathComponent("settings.json"))   // errors in the owner's language (owner 2026-10-06)
    let registry = try ProjectRegistry(file: catalogURL)
    if let folder = argument("--register-project") {
        let project = try registry.register(path: folder, name: argument("--name"), styleRefs: argument("--style-refs"), compatibilityPort: argument("--compat-port").flatMap(Int.init))
        let data = try JSONEncoder().encode(project)
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    } else {
        let configuredRoot = Bundle.main.object(forInfoDictionaryKey: "HYIMGSourceRoot") as? String ?? ""
        let configuredURL = URL(fileURLWithPath: configuredRoot)
        let sourceRoot: URL
        if !configuredRoot.isEmpty && FileManager.default.fileExists(atPath: configuredURL.appendingPathComponent("review/server.py").path) {
            sourceRoot = configuredURL
        } else if let bundled = Bundle.main.resourceURL, FileManager.default.fileExists(atPath: bundled.appendingPathComponent("review/server.py").path) {
            sourceRoot = bundled
        } else {
            throw RegistryError.invalid(L("Neither the sources nor the bundled server were found. Rebuild the app with build.sh in the Hyimg folder."))
        }
        let initialProjectID: UUID?
        if let requested = argument("--open-project") {
            guard let id = UUID(uuidString: requested), registry.projects.contains(where: { $0.id == id }) else {
                throw RegistryError.invalid(L("The --open-project board is not in the catalog."))
            }
            initialProjectID = id
        } else { initialProjectID = nil }
        let app = HyimgApplication.shared   // CEF: Chromium needs this NSApplication subclass on macOS
        let delegate = App(registry: registry, sourceRoot: sourceRoot, initialProjectID: initialProjectID)
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        withExtendedLifetime(delegate) { app.run() }
    }
} catch {
    if arguments.contains("--register-project") {
        FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
        exit(1)
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.regular)
    let alert = NSAlert()
    alert.messageText = L("Hyimg could not start")
    alert.informativeText = error.localizedDescription
    alert.runModal()
    exit(1)
}
