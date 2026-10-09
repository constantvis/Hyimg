import Foundation
#if !HYIMG_POLICY_ONLY
import AppKit
import ImageIO
import UserNotifications
#endif

// macOS notifications for what comes to the bell (owner 2026-10-08, a screenshot of Hyimg's banners: «очень крутая тема, чтобы я видел,
// что что-то произошло, что-то новое появилось. В Mac эти нотификации просто топ»). Every open board's server is asked what came since the
// last look (GET /api/notifications?since=, review/notifsince.py): an agent's news, a comment, a reply to this Mac's person, an @mention
// of him or of his agents, a reply to his note. Each new row becomes a banner: «Claude · Studio North» (who it is from, the board), the
// row's words, its first picture (review/feedthumbs.py's tile, its mark drawn in), grouped by board, the system's sound for mentions only.
// A click opens the place through the hyimg:// routing (LinkRouting.swift go: the board, its page, its objects or the area) and marks
// the row read.
//   when      every 10 s a board, up to 60 s while nothing comes; only the boards whose servers the app runs (sessions, asleep too)
//   never     twice (the ids seen and the newest time, per board, in the app's defaults), the rows of a board looked at for the first
//             time, this Mac's person's own rows from the app, a row older than a day, anything while «Mac notifications» is off (no
//             request at all then), a type turned off, while Hyimg is in front when «Only when Hyimg is in the background» is on, and
//             a board's rows while that board is in front with its bell open (the page is asked: window.hyimg «macBell»)
//   a burst   more than 5 rows of one board within a minute: one banner «Claude · Studio North», «7 updates», which opens its bell
//   asking    macOS asks for permission when the first banner would be shown, not at launch; Focus and Do Not Disturb are the system's
// The settings (Settings › Notifications, review/ui/macnotif.js) are the app's file: cv.mac "0" turns it off, cv.mac.<type> "0" turns
// a type off (agent, comment, reply, mention, note), cv.mac.bg "1" only in the background. All on by default.
// This first part is the policy, Foundation only (tests/test_native_macnotif.swift builds it with -D HYIMG_POLICY_ONLY); the app's side follows.

/// Settings › Notifications from the app's settings file (every value a string)
struct MacNotifSettings: Equatable {
    static let all = ["agent", "comment", "reply", "mention", "note"]
    var on = true
    var kinds = Set(MacNotifSettings.all)
    var onlyBackground = false
    init() {}
    init(_ s: [String: Any]) {
        let v = { (k: String) -> String in s[k].map { "\($0)" } ?? "" }
        on = v("cv.mac") != "0"
        kinds = Set(Self.all.filter { v("cv.mac.\($0)") != "0" })
        onlyBackground = v("cv.mac.bg") == "1"
    }
}

/// One row of the bell as /api/notifications gives it (notifsince.py: ts, type, from; feedthumbs.py: pv)
struct BellItem: Equatable {
    var id: String
    var ts: Double
    var type = "agent"
    var title = ""
    var text = ""
    var from = ""
    var person = ""   // by.person, lower case
    var via = ""      // by.via: "app" or an agent's kind
    var page = ""
    var ids: [String] = []
    var area: [Double]? = nil       // x, y, w, h in board units
    var tile: String? = nil         // the first picture's address on the board's server
    var markRect: [Double]? = nil   // its mark in shares of the picture: an area's outline
    var markPin: [Double]? = nil    // or a pin's point
    init(id: String, ts: Double, type: String = "agent", from: String = "", person: String = "", via: String = "") {
        self.id = id; self.ts = ts; self.type = type; self.from = from; self.person = person; self.via = via
    }
    init?(_ d: [String: Any]) {
        let num = { (v: Any?) -> Double? in (v as? NSNumber)?.doubleValue.isFinite == true ? (v as? NSNumber)?.doubleValue : nil }
        let nums = { (v: Any?) -> [Double]? in let a = (v as? [Any])?.compactMap(num); return a?.count == (v as? [Any])?.count ? a : nil }
        guard let id = d["id"] as? String, !id.isEmpty, id.count <= 200 else { return nil }
        self.id = id; ts = num(d["ts"]) ?? 0
        type = d["type"] as? String ?? "agent"; title = d["title"] as? String ?? ""; text = d["text"] as? String ?? ""; from = d["from"] as? String ?? ""
        let by = d["by"] as? [String: Any] ?? [:]
        person = (by["person"] as? String ?? "").lowercased(); via = by["via"] as? String ?? ""
        page = d["page"] as? String ?? ""; ids = (d["ids"] as? [Any] ?? []).compactMap { $0 as? String }
        if let a = d["area"] as? [String: Any], let x = num(a["x"]), let y = num(a["y"]), let w = num(a["w"]), let h = num(a["h"]) { area = [x, y, w, h] }
        if let t = (d["pv"] as? [[String: Any]])?.first, let src = t["src"] as? String, src.hasPrefix("/"), !src.hasPrefix("//") {
            tile = src
            let m = t["mark"] as? [String: Any]
            if let r = nums(m?["r"]), r.count == 4 { markRect = r } else if let p = nums(m?["pin"]), p.count == 2 { markPin = p }
        }
    }
}

/// What this Mac has seen of a board: the newest time and the ids, kept in the app's defaults
struct NotifCursor: Equatable {
    var ts: Double
    var ids: [String]
    var plist: [String: Any] { ["ts": ts, "ids": ids] }
    init(ts: Double, ids: [String]) { self.ts = ts; self.ids = ids }
    init?(_ v: Any?) {
        guard let d = v as? [String: Any], let t = (d["ts"] as? NSNumber)?.doubleValue, t.isFinite else { return nil }
        ts = t; ids = (d["ids"] as? [Any] ?? []).compactMap { $0 as? String }
    }
}

enum MacNotifPolicy {
    static let margin = 600.0       // the look goes this far before the newest time seen: rows Dropbox brings late
    static let firstLook = 3600.0   // a board looked at for the first time: an hour back, all of it only remembered
    static let keep = 300           // ids kept per board
    static let stale = 86_400.0     // a row older than a day is not news any more
    static let burstWindow = 60.0, burstMax = 5
    static let fastest = 10.0, slowest = 60.0

    /// ?since= for a board
    static func since(_ c: NotifCursor?, now: Double) -> Double { max(0, c.map { $0.ts - margin } ?? now - firstLook) }
    /// the rows not seen before, oldest first, and the cursor after them; a board without a cursor: none, all of them remembered
    static func fresh(_ items: [BellItem], cursor: NotifCursor?, now: Double) -> (new: [BellItem], cursor: NotifCursor) {
        var seen = Set(cursor?.ids ?? []), got: [BellItem] = []
        for i in items.sorted(by: { $0.ts < $1.ts }) where seen.insert(i.id).inserted { got.append(i) }
        var ids = (cursor?.ids ?? []) + got.map(\.id)
        if ids.count > keep { ids.removeFirst(ids.count - keep) }
        let newest = min(now, got.map(\.ts).max() ?? 0)   // a row from a Mac whose clock runs ahead never moves the look past now
        return (cursor == nil ? [] : got, NotifCursor(ts: max(cursor?.ts ?? now, newest), ids: ids))
    }
    /// this Mac's person's own row, made in the app (his agents' rows are news to him)
    static func own(_ i: BellItem, me: String?) -> Bool {
        guard let me = me?.lowercased(), !me.isEmpty else { return false }
        return i.person == me && (i.via.isEmpty || i.via == "app")
    }
    /// the new rows that become banners
    static func wanted(_ items: [BellItem], _ s: MacNotifSettings, me: String?, now: Double, appActive: Bool, bellOpen: Bool) -> [BellItem] {
        guard s.on, !(s.onlyBackground && appActive), !bellOpen else { return [] }
        return items.filter { s.kinds.contains($0.type) && !own($0, me: me) && now - $0.ts < stale }
    }
    struct Recent: Equatable { var t: Double; var from: String }
    enum Post: Equatable { case one(BellItem); case summary(count: Int, from: String) }
    /// one banner a row, or one for them all when the board gave more than burstMax within burstWindow (recent: that board's rows)
    static func plan(_ items: [BellItem], recent: inout [Recent], now: Double) -> [Post] {
        recent.removeAll { now - $0.t >= burstWindow }
        guard !items.isEmpty else { return [] }
        recent += items.map { Recent(t: now, from: $0.from) }
        guard recent.count > burstMax else { return items.map { .one($0) } }
        let names = Set(recent.map(\.from))
        return [.summary(count: recent.count, from: names.count == 1 ? names.first ?? "" : "")]
    }
    /// how long until a board is asked again: soon after news, slower while nothing comes
    static func next(_ current: Double, got: Bool) -> Double { got ? fastest : min(slowest, max(fastest, current * 1.5)) }
    /// a banner's words: title «from · board», subtitle what happened (a comment's), body the row's words; the sound for a mention
    static func content(_ i: BellItem, board: String) -> (title: String, subtitle: String, body: String, sound: Bool) {
        let title = i.from.isEmpty ? board : "\(i.from) · \(board)"
        if i.type == "agent" || i.text.isEmpty { return (title, "", clip(i.text.isEmpty ? i.title : i.title + "\n" + i.text), i.type == "mention") }
        return (title, i.title, clip(i.text), i.type == "mention")
    }
    static func clip(_ s: String, _ n: Int = 240) -> String {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.count <= n ? t : String(t.prefix(n - 1)) + "…"
    }
    /// the board's camera «x,y,z» that shows an area (canvas.html goNtf does the same on the page), for a window of that size
    static func camera(_ a: [Double], width: Double, height: Double) -> String? {
        guard a.count == 4, a.allSatisfy(\.isFinite), a[2] > 0, a[3] > 0, width > 200, height > 260 else { return nil }
        let pad = 80.0, z = min(2, (width - pad * 2) / a[2], (height - pad * 2 - 60) / a[3])
        guard z >= 0.001 else { return nil }
        return String(format: "%.1f,%.1f,%.4f", a[0] - (width / z - a[2]) / 2, a[1] - (height / z - a[3]) / 2, z)
    }
}

#if !HYIMG_POLICY_ONLY
/// The app's side: the timer, the requests, the banners, the clicks
final class MacNotifier {
    static let shared = MacNotifier()
    weak var app: App?
    var timer: Timer?
    var due: [UUID: Date] = [:], every: [UUID: Double] = [:], asking = Set<UUID>()
    var recent: [UUID: [MacNotifPolicy.Recent]] = [:]
    var bellAsks: [String: (Bool) -> Void] = [:]
    var wasOn = true
    // a bundle's app only (a bare binary has no notification centre and would stop); a test catalog never shows banners
    var center: UNUserNotificationCenter? { Bundle.main.bundleIdentifier == nil ? nil : UNUserNotificationCenter.current() }
    var enabled: Bool { !CommandLine.arguments.contains("--catalog") || ProcessInfo.processInfo.environment["HYIMG_MAC_NOTIFY"] == "1" }

    func start(_ app: App) {
        self.app = app
        guard enabled, let center else { return }
        center.delegate = app
        let t = Timer(timeInterval: 5, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common); timer = t
    }
    var cursorsKey: String { app.map { $0.key("macNotifSeen") } ?? "macNotifSeen" }
    var cursors: [String: Any] {
        get { app?.defaults.dictionary(forKey: cursorsKey) ?? [:] }
        set { app?.defaults.set(newValue, forKey: cursorsKey) }
    }
    func tick() {
        guard let app else { return }
        guard MacNotifSettings(app.readSettings()).on else {   // off: no request at all; on again, every board starts from that moment
            if wasOn { wasOn = false; cursors = [:]; due = [:]; every = [:] }
            return
        }
        wasOn = true
        let now = Date()
        for (id, session) in app.sessions where !asking.contains(id) && (due[id] ?? .distantPast) <= now { poll(id, session.server.project) }
    }
    func poll(_ id: UUID, _ project: Project) {
        let cursor = NotifCursor(cursors[id.uuidString]), since = MacNotifPolicy.since(cursor, now: Date().timeIntervalSince1970)
        guard var c = URLComponents(string: "http://127.0.0.1:\(project.port)/api/notifications") else { return }
        c.queryItems = [URLQueryItem(name: "since", value: String(format: "%.3f", since)), URLQueryItem(name: "limit", value: cursor == nil ? "300" : "40")]
        guard let url = c.url else { return }
        var request = URLRequest(url: url); request.timeoutInterval = 5
        asking.insert(id)
        URLSession.shared.dataTask(with: request) { data, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            let rows = ok ? data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }?["items"] as? [[String: Any]] : nil
            DispatchQueue.main.async { self.asking.remove(id); self.got(id, project, rows?.compactMap(BellItem.init)) }
        }.resume()
    }
    func got(_ id: UUID, _ project: Project, _ items: [BellItem]?) {
        let now = Date().timeIntervalSince1970
        guard let items, let app else {   // the server is not up (yet): asked again later, slower
            every[id] = MacNotifPolicy.next(every[id] ?? MacNotifPolicy.fastest, got: false); due[id] = Date().addingTimeInterval(every[id]!); return
        }
        var all = cursors
        let (new, cursor) = MacNotifPolicy.fresh(items, cursor: NotifCursor(all[id.uuidString]), now: now)
        all[id.uuidString] = cursor.plist; cursors = all
        every[id] = MacNotifPolicy.next(every[id] ?? MacNotifPolicy.fastest, got: !new.isEmpty); due[id] = Date().addingTimeInterval(every[id]!)
        let me = People.me(app.registry.file.deletingLastPathComponent())?["id"] as? String, s = MacNotifSettings(app.readSettings())
        let posts = MacNotifPolicy.wanted(new, s, me: me, now: now, appActive: NSApp.isActive, bellOpen: false)
        guard !posts.isEmpty, !app.archivedBoards.contains(id) else { return }   // a board in Home's Archive: remembered, never a banner
        // the board in front with its bell open shows these rows already: its page is asked (no answer: not open)
        guard NSApp.isActive, app.selected == id, let session = app.sessions[id] else { post(posts, project); return }
        askBell(session) { [weak self] open in if !open { self?.post(posts, project) } }
    }
    // a board's settings and bell live in its canvas frame (v2.html holds it as #cvFrame); the answer comes back as {action: "macBell"}
    static func inCanvas(_ body: String) -> String {
        "(function(){var d=document;try{var f=document.getElementById('cvFrame');if(f&&f.contentDocument)d=f.contentDocument}catch(e){}\(body)})()"
    }
    func askBell(_ session: ProjectView, _ then: @escaping (Bool) -> Void) {
        let token = UUID().uuidString
        bellAsks[token] = then
        app?.evaluate(session, Self.inCanvas("var n=d.getElementById('ntf'),m={action:'macBell',token:'\(token)',open:!!(n&&n.classList.contains('open'))};"
            + "try{if(window.webkit&&webkit.messageHandlers&&webkit.messageHandlers.hyimg){webkit.messageHandlers.hyimg.postMessage(m);return}}catch(e){}"
            + "console.log('HYIMG_MSG:'+JSON.stringify(m))"))
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in self?.bellAsks.removeValue(forKey: token)?(false) }
    }
    func post(_ items: [BellItem], _ project: Project) {
        var r = recent[project.id] ?? []
        let plan = MacNotifPolicy.plan(items, recent: &r, now: Date().timeIntervalSince1970)
        recent[project.id] = r
        allowed { [weak self] ok in if ok { plan.forEach { self?.show($0, project) } } }
    }
    // the system asks the first time a banner would be shown; a «Don't Allow» is the system's to change (System Settings › Notifications)
    func allowed(_ then: @escaping (Bool) -> Void) {
        guard let center else { then(false); return }
        center.getNotificationSettings { st in
            switch st.authorizationStatus {
            case .authorized, .provisional: DispatchQueue.main.async { then(true) }
            case .notDetermined: center.requestAuthorization(options: [.alert, .sound]) { ok, _ in DispatchQueue.main.async { then(ok) } }
            default: DispatchQueue.main.async { then(false) }
            }
        }
    }
    func show(_ p: MacNotifPolicy.Post, _ project: Project) {
        let c = UNMutableNotificationContent(), board = project.id.uuidString
        c.threadIdentifier = board
        switch p {
        case .summary(let n, let from):
            c.title = from.isEmpty ? project.name : "\(from) · \(project.name)"; c.body = L("%ld updates", n)
            c.userInfo = ["board": board, "summary": true]
            add("\(board):summary", c)
        case .one(let i):
            let words = MacNotifPolicy.content(i, board: project.name)
            c.title = words.title; c.subtitle = words.subtitle; c.body = words.body
            if words.sound { c.sound = .default }
            var info: [String: Any] = ["board": board, "id": i.id, "page": i.page, "ids": i.ids]
            if let a = i.area { info["area"] = a }
            c.userInfo = info
            picture(i, project) { [weak self] file in
                if let file, let a = try? UNNotificationAttachment(identifier: "picture", url: file, options: nil) { c.attachments = [a] }
                self?.add("\(board):\(i.id)", c)
            }
        }
    }
    func add(_ identifier: String, _ c: UNNotificationContent) {
        center?.add(UNNotificationRequest(identifier: identifier, content: c, trigger: nil)) { [weak self] error in
            if let error { DispatchQueue.main.async { self?.app?.appLog("notification not shown: \(error.localizedDescription)") } }
        }
    }
    // the row's first picture from its board's server, its mark drawn in, as a png in the temporary folder (the system takes the file)
    func picture(_ i: BellItem, _ project: Project, _ done: @escaping (URL?) -> Void) {
        guard let tile = i.tile, let url = URL(string: "http://127.0.0.1:\(project.port)" + tile) else { done(nil); return }
        var request = URLRequest(url: url); request.timeoutInterval = 4
        URLSession.shared.dataTask(with: request) { data, response, _ in
            let file = (response as? HTTPURLResponse)?.statusCode == 200 ? data.flatMap { Self.png($0, rect: i.markRect, pin: i.markPin) } : nil
            DispatchQueue.main.async { done(file) }
        }.resume()
    }
    static func png(_ data: Data, rect: [Double]?, pin: [Double]?) -> URL? {
        guard let src = CGImageSourceCreateWithData(data as CFData, nil), let image = CGImageSourceCreateImageAtIndex(src, 0, nil),
              let space = CGColorSpace(name: CGColorSpace.sRGB), image.width > 0, image.height > 0, image.width <= 4096, image.height <= 4096,
              let ctx = CGContext(data: nil, width: image.width, height: image.height, bitsPerComponent: 8, bytesPerRow: 0, space: space,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        let W = CGFloat(image.width), H = CGFloat(image.height), line = max(2, W / 120)
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: W, height: H))
        let dark = CGColor(gray: 0, alpha: 0.55), light = CGColor(gray: 1, alpha: 1)
        if let r = rect {   // the area, white over a dark edge, so it shows on any picture (the bell draws it in the author's colour)
            let box = CGRect(x: r[0] * W, y: H - (r[1] + r[3]) * H, width: r[2] * W, height: r[3] * H)
            ctx.setLineWidth(line + 2); ctx.setStrokeColor(dark); ctx.stroke(box); ctx.setLineWidth(line); ctx.setStrokeColor(light); ctx.stroke(box)
        } else if let p = pin {
            let d = max(8, W / 18), dot = CGRect(x: p[0] * W - d / 2, y: H - p[1] * H - d / 2, width: d, height: d)
            ctx.setFillColor(dark); ctx.fillEllipse(in: dot.insetBy(dx: -2, dy: -2)); ctx.setFillColor(light); ctx.fillEllipse(in: dot)
        }
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("HyimgNotifications", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let file = dir.appendingPathComponent(UUID().uuidString + ".png")
        guard let out = ctx.makeImage(), let dest = CGImageDestinationCreateWithURL(file as CFURL, "public.png" as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(dest, out, nil)
        return CGImageDestinationFinalize(dest) ? file : nil
    }
    // a click: the app in front, the board on the row's page with its objects (or the area), the row read; a burst's banner opens the bell
    func clicked(_ info: [AnyHashable: Any], attempt: Int = 0) {
        guard let app, app.window != nil else {   // launched by the click: the window comes a moment later
            if attempt < 100 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { self.clicked(info, attempt: attempt + 1) } }
            return
        }
        guard let s = info["board"] as? String, let id = UUID(uuidString: s), let project = app.registry.projects.first(where: { $0.id == id }) else { return }
        if let row = info["id"] as? String { read(project, row) }
        let t = app.bellPlace(id, page: info["page"], objects: info["ids"], area: info["area"])
        NSApp.activate(ignoringOtherApps: true); app.window?.makeKeyAndOrderFront(nil)
        app.go(project, t)
        if info["summary"] as? Bool == true { openBell(id) }
    }
    func openBell(_ id: UUID, attempt: Int = 0) {
        guard let app, let session = app.sessions[id] else { return }
        guard session.drawn else {
            if attempt < 480 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { self.openBell(id, attempt: attempt + 1) } }
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {   // after its entrance
            app.evaluate(session, Self.inCanvas("var b=d.getElementById('bntf'),n=d.getElementById('ntf');if(b&&n&&!n.classList.contains('open'))b.click()"))
        }
    }
    // the row read on its board (the server that may be starting for the click: a few tries)
    func read(_ project: Project, _ row: String, attempt: Int = 0) {
        guard let url = URL(string: "http://127.0.0.1:\(project.port)/api/notifications") else { return }
        var request = URLRequest(url: url); request.httpMethod = "POST"; request.timeoutInterval = 3
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["action": "read", "ids": [row]])
        URLSession.shared.dataTask(with: request) { _, response, _ in
            guard (response as? HTTPURLResponse)?.statusCode != 200, attempt < 30 else { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.read(project, row, attempt: attempt + 1) }
        }.resume()
    }
}

extension App: UNUserNotificationCenterDelegate {
    // before the launch ends, so a click that launched the app reaches it (Apple: set the centre's delegate before launching finishes)
    @objc func applicationWillFinishLaunching(_ notification: Notification) { MacNotifier.shared.start(self) }
    // the page's answer: is its bell open (MacNotifier.askBell); Home's bell (below); People.swift's profileMessage hands over what is not its own
    func macNotifMessage(_ body: [String: Any]) {
        switch body["action"] as? String {
        case "macBell": if let token = body["token"] as? String { MacNotifier.shared.bellAsks.removeValue(forKey: token)?((body["open"] as? Bool) == true) }
        case "homeBell": homeBell()
        case "bellRead": if let read = body["read"] as? [String: Any] { homeBellRead(read) }
        default: break
        }
    }
    // a bell row's place on its board: its page, its objects, else the camera on its area for this window (a banner's click, Home's bell)
    func bellPlace(_ id: UUID, page: Any?, objects: Any?, area: Any?) -> AppLink.Target {
        var t = AppLink.Target(project: id)
        if let page = page as? String, AppLink.isID(page) { t.page = page }
        t.obj = Array(((objects as? [Any]) ?? []).compactMap { $0 as? String }.filter(AppLink.isID).prefix(AppLink.maxObjects))
        if t.obj.isEmpty, let a = (area as? [Any])?.compactMap({ ($0 as? NSNumber)?.doubleValue }), let size = window?.contentView?.bounds.size {
            t.at = MacNotifPolicy.camera(a, width: Double(size.width), height: Double(size.height))
        }
        return t
    }
    // Home's bell (review/ui/homebell.js, owner 2026-10-08: «вверху справа, где настройки, тоже нотификации»). Home is a file page and a
    // board's server answers only its own origin, so the app asks the servers it runs (asleep boards keep theirs) and hands the rows over:
    //   {action: "homeBell"}                 -> window.hyimgHomeBell({boards: [{id, base, items, unread}]}), a board whose server does not
    //                                           answer within 4 s left out (Home shows its news instead)
    //   {action: "bellRead", read: {id: [row ids]}}   the rows Home's list showed, read on their boards
    //   {action: "open", id, page, obj | area}       main.swift: the board at the row's place, as a banner's click (homeOpen)
    func homeBell() {
        let group = DispatchGroup()
        var boards: [[String: Any]] = []
        for (id, session) in sessions {
            let base = "http://127.0.0.1:\(session.server.project.port)"
            guard let url = URL(string: base + "/api/notifications?limit=30") else { continue }
            var request = URLRequest(url: url); request.timeoutInterval = 4
            group.enter()
            URLSession.shared.dataTask(with: request) { data, response, _ in
                let ok = (response as? HTTPURLResponse)?.statusCode == 200
                let j = ok ? data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } : nil
                DispatchQueue.main.async {
                    if let j, let items = j["items"] as? [[String: Any]] { boards.append(["id": id.uuidString, "base": base, "items": items, "unread": j["unread"] ?? 0]) }
                    group.leave()
                }
            }.resume()
        }
        group.notify(queue: .main) { [weak self] in
            guard let data = try? JSONSerialization.data(withJSONObject: ["boards": boards]), let json = String(data: data, encoding: .utf8) else { return }
            self?.homeWeb?.evaluateJavaScript("window.hyimgHomeBell && window.hyimgHomeBell(\(json))")
        }
    }
    func homeBellRead(_ read: [String: Any]) {
        for (key, value) in read {
            guard let id = UUID(uuidString: key), let session = sessions[id],
                  let url = URL(string: "http://127.0.0.1:\(session.server.project.port)/api/notifications") else { continue }
            let ids = Array(((value as? [Any]) ?? []).compactMap { $0 as? String }.filter { !$0.isEmpty && $0.count <= 200 }.prefix(300))
            guard !ids.isEmpty else { continue }
            var request = URLRequest(url: url); request.httpMethod = "POST"; request.timeoutInterval = 3
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? JSONSerialization.data(withJSONObject: ["action": "read", "ids": ids])
            URLSession.shared.dataTask(with: request).resume()
        }
    }
    // Home's «open»: a card opens its board; a row of Home's bell names its place too, and the board opens there
    func homeOpen(_ project: Project, _ body: [String: Any]) {
        guard body["page"] != nil || body["obj"] != nil || body["area"] != nil else { openProject(project); return }
        go(project, bellPlace(project.id, page: body["page"], objects: body["obj"], area: body["area"]))
    }
    // shown while Hyimg is in front too (the board in front with its bell open was left out before)
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier { DispatchQueue.main.async { MacNotifier.shared.clicked(info) } }
        completionHandler()
    }
}
#endif
