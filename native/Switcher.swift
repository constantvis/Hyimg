import AppKit

// ⌃Tab between boards and the crumb's list of boards (owner 2026-10-08, the concept «Вкладки со сном», variants 1 and 2: «Топ, очень
// нравится. Главное, чтобы таб еще с анимацией был: blur + scale down, и scale, когда released. При этом верхнюю панель можно сохранить и
// потом показывать, что мы переключились на другую страницу ... даже если другая страница грузится»). No strip of tabs:
//   ⌃Tab, ⌃ held: the open boards as cards over the page in front, its board blurred and a little smaller (review/ui/switcher.js draws
//     both); Tab or → the next card, ⌃⇧Tab or ← back, the pointer picks too, releasing ⌃ opens the card, Esc closes. A quick ⌃Tab goes
//     to the board before this one without the cards. The board in front is the first card, Home the last.
//   the board's name on the crumb lists the open boards at the top of its menu (switcher.js hySwitchRows, canvas.html builds the menu)
//   a board whose page is drawn comes at once: its page under the veil and smaller is brought in front, then scales up into place
//   a board asleep or not loaded loads under the page in front, which keeps its top row: the crumb shows the board's name and a spinner,
//     Home and Settings work, ⌃Tab goes elsewhere, Esc goes back; once the board is drawn it comes in as above
// Both engines alike: the pages do the motion (opacity and transform), the app only orders the views.
final class SwitchState {
    static let shared = SwitchState()
    var open = false            // ⌃ held, the cards up or about to show
    var shown = false           // the page in front was told to draw them
    var ids: [String] = []      // the cards: board ids, "home"
    var pick = 0
    var drawnOn: NSView?        // the page that draws them
    var showWork: DispatchWorkItem?
    var pending: UUID?          // the board switched to, loading under the one in front
    var host: UUID?             // the board in front meanwhile: its page keeps the top row and the veil
    var wait = SwitchWait()     // the board switched to waits for what is on its screen to be drawn (BoardSleep.swift)
    var covers: [UUID: (at: Date, urls: [String])] = [:]   // the cards' pictures, the board's first frames from its own server
    var coverWork: Set<UUID> = []
}

extension App {
    private var SW: SwitchState { SwitchState.shared }
    func installSwitcher() {
        // ⌃Tab never reaches the menu: the web view takes Tab for focus moves first, so it is caught for the whole app here, ⌃'s release too
        NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .flagsChanged]) { [weak self] e in self.map { $0.switcherEvent(e) } ?? e }
        NotificationCenter.default.addObserver(forName: NSApplication.didResignActiveNotification, object: nil, queue: .main) { [weak self] _ in
            self?.switcherClose(commit: false)
        }
        startSleep()
    }
    func switcherEvent(_ e: NSEvent) -> NSEvent? {
        guard e.window === window, NSApp.modalWindow == nil, window?.attachedSheet == nil else { return e }
        if e.type == .flagsChanged {
            if SW.open && !e.modifierFlags.contains(.control) { switcherClose(commit: true) }
            return e
        }
        let f = e.modifierFlags
        if e.keyCode == 48, f.contains(.control), !f.contains(.command) { switcherStep(f.contains(.shift) ? -1 : 1); return nil }
        if SW.open {
            switch e.keyCode {
            case 53: switcherClose(commit: false)          // Esc
            case 123, 126: switcherMove(-1)                 // ← ↑
            case 124, 125: switcherMove(1)                  // → ↓
            case 36, 76: switcherClose(commit: true)        // Return
            default: break
            }
            return nil
        }
        if e.keyCode == 53, SW.pending != nil, SW.host != nil { switchBack(); return nil }   // Esc: back from a board still loading
        return e
    }
    func switcherStep(_ step: Int) {
        if SW.open { switcherMove(step); return }
        let ids = cardIDs()
        guard ids.count > 1 else { return }
        SW.open = true; SW.shown = false; SW.ids = ids; SW.pick = SwitchOrder.firstPick(count: ids.count, step: step)
        // the cards wait a moment: a quick ⌃Tab goes to the board before without them (⌘Tab's way)
        let work = DispatchWorkItem { [weak self] in self?.switcherShow() }
        SW.showWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.14, execute: work)
    }
    func switcherShow() {
        guard SW.open, let view = content?.subviews.last else { return }
        SW.showWork = nil; SW.shown = true; SW.drawnOn = view
        pageEval("window.hyimgSwitcher && window.hyimgSwitcher(\(jsonArg(["open": true, "boards": boardCards(SW.ids), "pick": SW.pick])))", view)
    }
    func switcherMove(_ step: Int) {
        guard SW.open else { return }
        SW.pick = SwitchOrder.move(SW.pick, by: step, count: SW.ids.count)
        if SW.shown { pageEval("window.hyimgSwitcher && window.hyimgSwitcher({pick: \(SW.pick)})", SW.drawnOn) }
    }
    func switcherClose(commit: Bool) {
        guard SW.open else { return }
        SW.open = false; SW.showWork?.cancel(); SW.showWork = nil
        let target = commit && SW.ids.indices.contains(SW.pick) ? SW.ids[SW.pick] : nil
        let going = target != nil && target != SW.ids.first
        if SW.shown { pageEval("window.hyimgSwitcher && window.hyimgSwitcher({open: false, keep: \(going)})", SW.drawnOn) }
        SW.shown = false; SW.drawnOn = nil
        if going, let target { switchTo(target) }
    }
    func switchTo(_ id: String) {
        if id == "home" { showProjects(); return }
        guard let uuid = UUID(uuidString: id), let p = registry.projects.first(where: { $0.id == uuid }) else { return }
        if uuid == selected && SW.pending == nil && !(homeWeb.map { inFront($0) } ?? false) { return }   // in front already
        openProject(p)
    }
    // the page messages: a card or a row of the crumb's list clicked, the pointer on a card, a click beside the cards, a page's sleep answer
    func switchMessage(_ action: String, _ body: [String: Any]) -> Bool {
        switch action {
        case "switchTo":
            guard let to = body["to"] as? String else { break }
            if SW.open, let k = SW.ids.firstIndex(of: to) { SW.pick = k; switcherClose(commit: true) } else { switchTo(to) }
        case "switchPick":
            if SW.open, let i = body["i"] as? Int, SW.ids.indices.contains(i) { SW.pick = i }
        case "switchCancel": switcherClose(commit: false)
        case "switchShown":   // the board switched to has drawn what is on its screen (switcher.js hyimgSwitchWait), token: which wait
            guard let id = (body["id"] as? String).flatMap(UUID.init), let session = sessions[id] else { break }
            let token = body["token"] as? Int ?? SW.wait.token, now = SW.wait.board == id && SW.wait.token == token
            if now, (body["drawn"] as? Bool) == false { appLog("switch \(session.server.project.name): 5 s and its screen not drawn, it comes in as it is") }
            switchShown(session, token)
        case "sleepState": sleepAnswer(body)
        default: return false
        }
        return true
    }
    // openSession's way when no Home is in front: the switch with the motion, or false for the old way (a failure page in front, no page)
    func switchAnimated(_ project: Project, _ session: ProjectView) -> Bool {
        guard let top = content?.subviews.last, let host = sessions.values.first(where: { $0.surface === top }), host.drawn else { return false }
        if host === session {   // the board in front chosen again: back from the board that was loading (⌃Tab, its crumb's list)
            guard SW.pending != nil else { return false }
            switchBack(); return true
        }
        let hostID = host.server.project.id
        if session.drawn && session.loaded {   // its page is there: it comes once what is on its screen is drawn, at once when it is
            SW.pending = project.id; SW.host = hostID
            if session.surface.superview !== content { place(session.surface, below: host.surface) }
            switchWait(session, plate: host)
        } else {   // asleep or never loaded: the board in front keeps the row while this one loads under it
            SW.pending = project.id; SW.host = hostID
            let state = session.waking ? "sleeping" : "loading"
            evaluate(host, "window.hyimgSwitchOut && window.hyimgSwitchOut(\(jsonArg(["name": project.name, "state": state])))")
            if session.surface.superview !== content { place(session.surface, below: host.surface) }
            if !session.loading && !session.loaded { load(session) }
        }
        pushBoards(); writeActive()
        return true
    }
    // the board comes: its page under the veil and smaller, brought in front, then scaling up into place (switcher.js hyimgSwitchIn)
    func switchIn(_ session: ProjectView) {
        let id = session.server.project.id
        evaluate(session, "window.hyimgSwitchIn && window.hyimgSwitchIn('prep')")
        if session.surface.superview !== content, let top = content?.subviews.last { place(session.surface, below: top) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.08) { [weak self, weak session] in
            guard let self, let session, self.selected == id, !session.asleep else { return }
            self.front(session, why: "switch")
            self.evaluate(session, "window.hyimgSwitchIn && window.hyimgSwitchIn('play')")
        }
    }
    // canvasReady: a woken page takes its selection back; the board switched to comes in once what is on its screen is drawn. Laid out is
    // not drawn yet: the far view's pictures and the HTML cards' stills come after, and it came in half empty (owner 2026-10-08, «вот такой
    // баг при переключении»). The page says when (switchShown, at most 5 s); a page that never says comes in after 7 s
    func switchReady(_ session: ProjectView) -> Bool {
        let id = session.server.project.id
        if session.waking || session.restore != nil { restoreAfterSleep(session) }
        guard SW.pending == id, selected == id else { pushBoards(); writeActive(); return false }
        switchWait(session)
        return true
    }
    // the page is asked to say when what is on its screen is drawn. A board whose page is there takes the same way: drawn where it looks
    // it answers on its first tick; a board that finished loading behind (Esc before it came, ⌃Tab back to it) had drawn nothing at its
    // camera and came in empty (review of 77a608b). Its row stays in front meanwhile, and says «Opening» if the wait is felt (plate)
    func switchWait(_ session: ProjectView, plate host: ProjectView? = nil) {
        let id = session.server.project.id, token = SW.wait.start(id)
        evaluate(session, "window.hyimgSwitchWait && window.hyimgSwitchWait(5000, \(token))")
        if let host {
            let say = "window.hyimgSwitchOut && window.hyimgSwitchOut(\(jsonArg(["name": session.server.project.name, "state": "loading"])))"
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self, weak host] in
                guard let self, let host, self.SW.wait.board == id, self.SW.wait.token == token, self.SW.pending == id else { return }
                self.evaluate(host, say)
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 7) { [weak self, weak session] in
            guard let self, let session else { return }
            self.switchShown(session, token)
        }
    }
    // the board switched to is drawn: it comes in now, unless the switch went elsewhere meanwhile (Esc, ⌃Tab, Home) or this is the answer of
    // a wait given up since
    func switchShown(_ session: ProjectView, _ token: Int) {
        let id = session.server.project.id
        guard SW.pending == id, selected == id, session.drawn, !session.asleep, SW.wait.take(id, token) else { return }
        SW.pending = nil
        switchIn(session)
    }
    // front(): the page that kept the row goes back to its own look behind the new one, the boards learn who is in front
    func switchFronted(_ session: ProjectView) {
        noteFront()
        if SW.open { switcherClose(commit: false) }
        SW.pending = nil; SW.host = nil
        for x in sessions.values where x !== session && x.loaded { evaluate(x, "window.hyimgSwitchOut && window.hyimgSwitchOut(null, true)") }
        DispatchQueue.main.async { [weak self] in self?.noteFront(); self?.pushBoards(); self?.writeActive() }
    }
    // Esc, or the board in front picked again: the board that was loading goes on loading behind, the one in front stays
    func switchBack() {
        SW.wait.cancel()
        guard let h = SW.host, let host = sessions[h] else { SW.pending = nil; SW.host = nil; return }
        SW.pending = nil; SW.host = nil
        if selected != h { markSeen(selected); selected = h; tabBar?.selected = h; updateTitle(); saveTabs() }
        evaluate(host, "window.hyimgSwitchOut && window.hyimgSwitchOut(null)")
        noteFront(); pushBoards(); writeActive()
    }
    // showProjects(): Home in front, no switch under way, every page back to its own look
    func switchLeave() {
        noteFront()
        if SW.open { switcherClose(commit: false) }
        SW.pending = nil; SW.host = nil; SW.wait.cancel()
        for x in sessions.values where x.loaded { evaluate(x, "window.hyimgSwitchOut && window.hyimgSwitchOut(null, true)") }
        homeWeb?.evaluateJavaScript("window.hyimgSwitchOut && window.hyimgSwitchOut(null, true)")
    }
    func pageEval(_ js: String, _ view: NSView? = nil) {
        guard let v = view ?? content?.subviews.last else { return }
        if v === homeWeb { homeWeb?.evaluateJavaScript(js) } else if let x = sessions.values.first(where: { $0.surface === v }) { evaluate(x, js) }
    }
    func jsonArg(_ o: Any) -> String {
        (try? JSONSerialization.data(withJSONObject: o)).flatMap { String(data: $0, encoding: .utf8) } ?? "null"
    }
    // the cards: the one in front first (Home, when it is in front), then the open boards by when they were last in front, Home last;
    // a board in Home's Archive only while it is the one in front (HomeArchive.swift)
    func cardIDs() -> [String] {
        let homeFront = homeWeb.map { inFront($0) } ?? false
        let open = tabs.filter { id in sessions[id] != nil && registry.projects.contains { $0.id == id } }
        let boards = HomeArchive.switchable(open, archived: archivedBoards, front: homeFront ? nil : selected)
        let order = SwitchOrder.cards(front: homeFront ? nil : selected, open: boards, lastFront: BoardSleep.shared.lastFront).map(\.uuidString)
        return homeFront ? ["home"] + order : order + ["home"]
    }
    func boardState(_ id: UUID) -> BoardState? {
        guard let x = sessions[id] else { return nil }
        let front = selected == id && SW.pending != id && !(homeWeb.map { inFront($0) } ?? false)
        return BoardState.of(front: front, asleep: x.asleep, drawn: x.drawn, loading: x.loading || SW.pending == id, waking: x.waking)
    }
    func boardCards(_ ids: [String]? = nil) -> [[String: Any]] {
        let now = Date(), last = BoardSleep.shared.lastFront
        return (ids ?? cardIDs()).compactMap { id -> [String: Any]? in
            if id == "home" { return ["id": "home", "name": "", "state": "home"] }
            guard let u = UUID(uuidString: id), let p = registry.projects.first(where: { $0.id == u }), let st = boardState(u) else { return nil }
            return ["id": id, "name": p.name, "state": st.rawValue, "covers": covers(p), "ago": st == .open ? 0 : Int(now.timeIntervalSince(last[u] ?? now))]
        }
    }
    // for scripts/active.py: which boards are open and how (open, warm, sleeping, waking, loading)
    func activeBoards() -> [[String: Any]] {
        boardCards().filter { ($0["id"] as? String) != "home" }.map { ["id": $0["id"] ?? "", "name": $0["name"] ?? "", "state": $0["state"] ?? ""] }
    }
    // the open boards to every page that is there, for its crumb's list
    func pushBoards() {
        let js = "window.hyimgBoards && window.hyimgBoards(\(jsonArg(boardCards())))"
        for x in sessions.values where x.loaded && !x.asleep { evaluate(x, js) }
    }
    func covers(_ p: Project) -> [String] {
        let c = SW.covers[p.id]
        if c.map({ Date().timeIntervalSince($0.at) > 120 }) ?? true, !SW.coverWork.contains(p.id) {
            SW.coverWork.insert(p.id)
            DispatchQueue.global(qos: .utility).async { [weak self] in
                let urls = SwitchCovers.urls(p)
                DispatchQueue.main.async { self?.SW.covers[p.id] = (Date(), urls); self?.SW.coverWork.remove(p.id) }
            }
        }
        return c?.urls ?? []
    }
}

// A card's picture: the first frames of the board's main page, the rows from the top as Home's cards have them, from the board's own server
// (it runs while the board is open, asleep too)
enum SwitchCovers {
    static func urls(_ p: Project) -> [String] {
        let file = URL(fileURLWithPath: p.stateRoot).appendingPathComponent("boards/main.json")
        guard let data = try? Data(contentsOf: file), let b = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = b["items"] as? [String: [String: Any]] else { return [] }
        let firsts = items.values.compactMap { it -> (Double, Double, String)? in
            guard let path = it["path"] as? String, it["type"] == nil else { return nil }
            return ((it["y"] as? Double) ?? 0, (it["x"] as? Double) ?? 0, path)
        }.sorted { abs($0.0 - $1.0) > 200 ? $0.0 < $1.0 : $0.1 < $1.1 }
        var allowed = CharacterSet.alphanumerics; allowed.insert(charactersIn: "-._~/")
        return firsts.prefix(3).compactMap { f in
            f.2.addingPercentEncoding(withAllowedCharacters: allowed).map { "http://127.0.0.1:\(p.port)/thumb?p=\($0)&s=320" }
        }
    }
}
