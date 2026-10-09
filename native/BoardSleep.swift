import Foundation
#if !HYIMG_POLICY_ONLY
import AppKit
import WebKit
#endif

// Sleeping boards (owner 2026-10-08, the concept «Вкладки со сном» on the Hyimg App board): a board left behind for a while gives back its
// page, about 640 MB of a web view, and keeps its server (about 35 MB), so agents, the bell, Home's news and hyimg:// links go on working.
// Coming back loads the page again: its page and camera from its own storage (cv.page, cv.cam.<page>), its selection from what it said
// before it slept. A board never sleeps with an edit not saved, an edit under way, a studio open (Image, 3D, Dev Studio), a render or an
// upload running, or a video playing; it is asked first (review/ui/switcher.js hyimgSleepAsk) and saved before its page goes.
// The setting: Settings › Performance › «Sleep background boards» (cv.sleep: 5, 10 by default, 30 minutes, 0 never); under memory
// pressure a board behind a minute or more sleeps sooner: on macOS's warning the longest behind, on a critical one all of them.
// This first part is the policy, Foundation only (tests/test_native_sleep.swift builds it with -D HYIMG_POLICY_ONLY); the app's side follows.
enum SleepPolicy {
    static let defaultMinutes = 10
    /// the setting cv.sleep: whole minutes; "0" or "never": never; nothing or anything else: the default
    static func minutes(_ setting: String?) -> Int? {
        guard let s = setting?.trimmingCharacters(in: .whitespaces), !s.isEmpty else { return defaultMinutes }
        if s == "never" { return nil }
        guard let n = Int(s) else { return defaultMinutes }
        return n > 0 ? n : nil
    }
    /// under memory pressure a board left a minute ago may sleep, not one just left (macOS warns often on a busy Mac)
    static let pressureGrace: TimeInterval = 60
    /// a board behind since `since` is due to sleep at `now` (under pressure: after the grace, if sleeping is on at all)
    static func due(since: Date?, now: Date, minutes: Int?, front: Bool, asleep: Bool, hasPage: Bool, pressure: Bool = false) -> Bool {
        guard let minutes, let since, !front, !asleep, hasPage else { return false }
        let wait = Double(minutes) * 60
        return now.timeIntervalSince(since) >= (pressure ? min(wait, pressureGrace) : wait)
    }
    /// what the page says keeps it awake; nil: it may sleep. No answer keeps it awake too
    static func blocker(_ state: [String: Any]?) -> String? {
        guard let s = state else { return "no answer from the page" }
        if (s["unsaved"] as? Bool) == true { return "unsaved edits" }
        if (s["editing"] as? Bool) == true { return "an edit under way" }
        if let studio = s["studio"] as? String, !studio.isEmpty, studio != "board" { return "\(studio) studio open" }
        if let busy = s["busy"] as? [Any], !busy.isEmpty { return "busy: \(busy.map { "\($0)" }.joined(separator: ", "))" }
        if (s["video"] as? Bool) == true { return "a video playing" }
        return nil
    }
    /// the boards that may sleep now, the longest behind first
    static func order(_ behind: [(id: UUID, since: Date)]) -> [UUID] { behind.sorted { $0.since < $1.since }.map(\.id) }
}

/// A board's state in the switcher, the crumb's list and active.json: in front, behind with its page, asleep, waking up, loading
enum BoardState: String {
    case open, warm, sleeping, waking, loading
    static func of(front: Bool, asleep: Bool, drawn: Bool, loading: Bool, waking: Bool) -> BoardState {
        if asleep { return .sleeping }
        if !drawn && waking { return .waking }
        if !drawn && loading { return .loading }
        return front ? .open : .warm
    }
}

/// The switcher's order (⌘Tab's): the board in front first, then the others by when they were last in front, the newest first
enum SwitchOrder {
    static func cards(front: UUID?, open: [UUID], lastFront: [UUID: Date]) -> [UUID] {
        let rest = open.filter { $0 != front }.enumerated().sorted { a, b in
            let x = lastFront[a.element] ?? .distantPast, y = lastFront[b.element] ?? .distantPast
            return x != y ? x > y : a.offset < b.offset
        }.map(\.element)
        return (front.map { open.contains($0) ? [$0] : [] } ?? []) + rest
    }
    /// the card ⌃Tab starts on: the next one (the board before this one), or the last one going back
    static func firstPick(count: Int, step: Int) -> Int { count < 2 ? 0 : step < 0 ? count - 1 : 1 }
    static func move(_ pick: Int, by step: Int, count: Int) -> Int { count == 0 ? 0 : ((pick + step) % count + count) % count }
    /// Home is the card in front only while it is Home: on top with a board chosen it is leaving for that board (its plate and steps,
    /// 750 ms for a drawn board, the whole load for one asleep), and that board is in front. Counted as Home, it was the first card: a
    /// quick ⌃Tab went to the board again and Home picked was the card in front, so releasing on it did nothing (owner 2026-10-09: «не
    /// всегда переключается на Home screen, особенно если мы открыли только одну вкладку. Я быстро переключаюсь назад»)
    static func homeFront(onTop: Bool, leavingFor board: UUID?) -> Bool { onTop && board == nil }
    /// the cards as the app sends them: the one in front first (Home when it is in front), then the boards (cards), Home last
    static func deck(homeFront: Bool, front: UUID?, open: [UUID], lastFront: [UUID: Date]) -> [String] {
        let order = cards(front: homeFront ? nil : front, open: open, lastFront: lastFront).map(\.uuidString)
        return homeFront ? ["home"] + order : order + ["home"]
    }
    /// releasing ⌃ on `pick`: the card to go to; nil on the card in front (the first) or none
    static func target(_ ids: [String], pick: Int) -> String? { pick > 0 && ids.indices.contains(pick) ? ids[pick] : nil }
}

/// The switched-to board's wait until what is on its screen is drawn (Switcher.swift, review/ui/switchin.js): each wait has a token, and
/// only the answer of the latest wait brings the board in, once. A board switched to, left with Esc while it waited and switched to again
/// came in on the first wait's answer or its 7 s cap, before the new wait was over
struct SwitchWait {
    private(set) var board: UUID?
    private(set) var token = 0
    /// a new wait for `board`, the one before it given up: its token
    mutating func start(_ board: UUID) -> Int { self.board = board; token += 1; return token }
    /// an answer or the cap for `board` with `token`: true when it ends the wait under way
    mutating func take(_ board: UUID, _ token: Int) -> Bool {
        guard self.board == board, self.token == token else { return false }
        self.board = nil; return true
    }
    mutating func cancel() { board = nil }
}

#if !HYIMG_POLICY_ONLY
// A board's page and server (moved here from main.swift): the server stays while the board is open, the page may sleep and come back
final class ProjectView {
    let server: ServerSession
    var web: WKWebView   // a new one, never loaded, when the page sleeps: the old one's process goes with it
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
    var asleep = false   // its page is gone, its server runs (BoardSleep.swift)
    var waking = false   // its page is loading again after a sleep
    var restore: [String: Any]?   // what it gives back when it wakes: {page, sel}
    init(project: Project, sourceRoot: URL) {
        server = ServerSession(project: project, sourceRoot: sourceRoot)
        web = ProjectView.makeWeb(project)
    }
    static func makeWeb(_ project: Project) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = WKWebsiteDataStore(forIdentifier: project.id)
        configuration.preferences.isElementFullscreenEnabled = true   // a video's ⤢ opens the player in true full screen (owner 2026-10-06)
        let web = FirstClickWebView(frame: .zero, configuration: configuration)
        web.allowsBackForwardNavigationGestures = false
        web.isInspectable = true
        return web
    }
}

// the app's sleep bookkeeping
final class BoardSleep {
    static let shared = BoardSleep()
    var timer: Timer?
    var pressure: DispatchSourceMemoryPressure?
    var lastFront: [UUID: Date] = [:]   // when each board was last seen in front
    var asking: [String: ([String: Any]?) -> Void] = [:]   // the pages' answers to hyimgSleepAsk, by token
    var underWay: Set<UUID> = []   // asked or saving now
}

extension App {
    var sleepMinutes: Int? { SleepPolicy.minutes((readSettings()["cv.sleep"] as? String)) }
    func startSleep() {
        let s = BoardSleep.shared
        let timer = Timer(timeInterval: 30, repeats: true) { [weak self] _ in self?.sleepTick() }
        RunLoop.main.add(timer, forMode: .common); s.timer = timer
        // a warning: the board longest behind sleeps now; critical: every board behind a minute or more
        let source = DispatchSource.makeMemoryPressureSource(eventMask: [.warning, .critical], queue: .main)
        source.setEventHandler { [weak self, weak source] in
            let critical = source?.data.contains(.critical) == true
            self?.appLog("memory pressure (\(critical ? "critical" : "warning")): the boards behind sleep sooner"); self?.sleepTick(pressure: true, all: critical)
        }
        source.resume(); s.pressure = source
    }
    // the board chosen and the page in front are in front now: their time behind starts when they leave
    func noteFront() {
        let now = Date(), s = BoardSleep.shared
        if let id = selected { s.lastFront[id] = now }
        if let v = content?.subviews.last, let f = sessions.values.first(where: { $0.surface === v }) { s.lastFront[f.server.project.id] = now }
    }
    func isFront(_ session: ProjectView) -> Bool {
        let id = session.server.project.id
        return selected == id || inFront(session.surface) || opening == id || SwitchState.shared.pending == id || SwitchState.shared.host == id
    }
    func sleepTick(pressure: Bool = false, all: Bool = false) {
        noteFront()
        let s = BoardSleep.shared, now = Date(), minutes = sleepMinutes
        let due = sessions.values.filter {
            !s.underWay.contains($0.server.project.id) && !$0.operationPending && !terminationPending
                && SleepPolicy.due(since: s.lastFront[$0.server.project.id] ?? now, now: now, minutes: minutes, front: isFront($0), asleep: $0.asleep,
                                   hasPage: $0.loaded || $0.drawn, pressure: pressure)
        }
        let first = SleepPolicy.order(due.map { (id: $0.server.project.id, since: s.lastFront[$0.server.project.id] ?? now) })
        if all { first.forEach { id in if let x = sessions[id] { trySleep(x) } } } else if let id = first.first, let x = sessions[id] { trySleep(x) }
    }
    func trySleep(_ session: ProjectView) {
        let s = BoardSleep.shared, id = session.server.project.id, name = session.server.project.name
        s.underWay.insert(id)
        askSleepState(session) { [weak self, weak session] state in
            guard let self, let session else { s.underWay.remove(id); return }
            if let why = SleepPolicy.blocker(state) { s.underWay.remove(id); self.appLog("sleep \(name): kept awake, \(why)"); return }
            self.flush(session) { result in
                s.underWay.remove(id)
                guard case .success = result else { self.appLog("sleep \(name): kept awake, not saved"); return }
                guard !self.isFront(session), !session.asleep, session.loaded || session.drawn else { return }   // it came back meanwhile
                self.sleepNow(session, state ?? [:])
            }
        }
    }
    func askSleepState(_ session: ProjectView, completion: @escaping ([String: Any]?) -> Void) {
        let token = UUID().uuidString, s = BoardSleep.shared
        var done = false
        let finish: ([String: Any]?) -> Void = { state in if done { return }; done = true; s.asking.removeValue(forKey: token); completion(state) }
        s.asking[token] = finish
        evaluate(session, "window.hyimgSleepAsk && window.hyimgSleepAsk(\(jsString(token)))")
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { finish(nil) }   // an older page, a page that hangs: it stays awake
    }
    // the page's answer ({action: "sleepState", token, state}, through the same messages as its other actions)
    func sleepAnswer(_ body: [String: Any]) {
        guard let token = body["token"] as? String, let finish = BoardSleep.shared.asking[token] else { return }
        finish(body["state"] as? [String: Any] ?? [:])
    }
    // the page goes, the server stays: Chromium's browser closes, the WKWebView is let go (its process ends with it)
    func sleepNow(_ session: ProjectView, _ state: [String: Any]) {
        let p = session.server.project, behind = Date().timeIntervalSince(BoardSleep.shared.lastFront[p.id] ?? Date())
        appLog("sleep \(p.name) after \(Int(behind / 60)) min behind, its server stays on port \(p.port)")
        var keep: [String: Any] = [:]; keep["page"] = state["page"]; keep["sel"] = state["sel"]; session.restore = keep
        let webkit = session.cef == nil   // the WKWebView carries the page and its "hyimg" handler (makeSession's wire)
        if let cef = session.cef {
            cef.onCrash = nil; cef.onLoad = nil; cef.onLoadStart = nil; cef.onMessage = nil
            cef.closeBrowser(); cef.removeFromSuperview(); session.cef = nil
        }
        let old = session.web
        if window?.firstResponder === old { window?.makeFirstResponder(nil) }
        old.stopLoading(); old.navigationDelegate = nil; old.uiDelegate = nil
        if webkit { old.configuration.userContentController.removeScriptMessageHandler(forName: "hyimg") }
        old.removeFromSuperview()
        session.web = ProjectView.makeWeb(p)
        session.web.appearance = NSApp.effectiveAppearance
        session.loaded = false; session.loading = false; session.drawn = false; session.shown = false; session.band = nil
        session.flushWaiters.removeAll(); session.asleep = true; session.waking = false
        pushBoards(); writeActive()
    }
    // a board that slept is opened (makeSession): a new page, wired as a new board's; its server never stopped
    func revive(_ session: ProjectView) {
        appLog("wake \(session.server.project.name)")
        session.asleep = false; session.waking = true
        wire(session)
        homeProgress(session.server.project.id, L("Waking “%@”", session.server.project.name))
    }
    // a woken page is drawn: its selection back (its page and camera it took itself from its storage)
    func restoreAfterSleep(_ session: ProjectView) {
        session.waking = false
        guard let r = session.restore else { return }
        session.restore = nil
        if let data = try? JSONSerialization.data(withJSONObject: r), let json = String(data: data, encoding: .utf8) {
            evaluate(session, "window.hyimgSwitchRestore && window.hyimgSwitchRestore(\(json))")
        }
    }
}
#endif
