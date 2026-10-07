import AppKit
import WebKit

// Window chrome in the manner of Figma (owner 2026-09-30): no toolbar row, a tab strip in the title bar with a Home button
// and one tab per open project. Colours are the canvas tokens from review/canvas.html.
enum Palette {
    static let bar = NSColor(srgbRed: 0.047, green: 0.047, blue: 0.055, alpha: 1)       // --panel #0c0c0e
    static let tab = NSColor(srgbRed: 0.094, green: 0.094, blue: 0.106, alpha: 1)       // --raise #18181b
    static let hover = NSColor(srgbRed: 0.075, green: 0.075, blue: 0.086, alpha: 1)
    static let line = NSColor(srgbRed: 0.153, green: 0.153, blue: 0.165, alpha: 1)      // --line #27272a
    static let ink = NSColor(srgbRed: 0.98, green: 0.98, blue: 0.98, alpha: 1)          // --ink
    static let sub = NSColor(srgbRed: 0.631, green: 0.631, blue: 0.667, alpha: 1)       // --sub
}

// A WKWebView that takes the first click: without this the click that focuses the window (or the web view) is swallowed,
// and buttons on the canvas needed two clicks (owner 2026-09-30).
final class FirstClickWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class TabBar: NSView {
    // owner 2026-10-04: no strip of tabs; the page carries «⌂ › project › page» on a plate at its top left (canvas.html #crumb), the
    // projects are switched from Home. The bar stays as the place that centres the window buttons, with no height and no tabs
    static let inPage = true
    static var height: CGFloat { inPage ? 0 : 40 }
    struct Item { let id: UUID; let name: String }
    var items: [Item] = [] { didSet { rebuild() } }
    var selected: UUID? { didSet { if oldValue != selected { restyle() } } }   // nil: Home
    var onHome: () -> Void = {}
    var onSelect: (UUID) -> Void = { _ in }
    var onClose: (UUID) -> Void = { _ in }
    private let home = TabView(title: nil, symbol: "house")
    private var tabViews: [TabView] = []
    // room for the traffic lights; in full screen the window buttons live in the system strip above the tabs, so the tabs start at the
    // left edge (owner 2026-09-30, as in Figma)
    private var leftInset: CGFloat { window?.styleMask.contains(.fullScreen) == true ? 10 : 80 }

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = Palette.bar.cgColor
        home.onClick = { [weak self] in self?.onHome() }
        home.toolTip = L("Home · ⌘⇧H")
        if !TabBar.inPage { addSubview(home) }
        let rule = NSView(); rule.wantsLayer = true; rule.layer?.backgroundColor = Palette.line.cgColor
        rule.autoresizingMask = [.width, .maxYMargin]; rule.frame = NSRect(x: 0, y: 0, width: frame.width, height: 1)
        // with no height the bar keeps no rule: in full screen it slid down under the system's menu strip and the rule stayed as a
        // line across the board (owner 2026-10-05)
        if !TabBar.inPage { addSubview(rule) }
    }
    required init?(coder: NSCoder) { nil }
    // the interface language changed (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»)
    func relabel() {
        home.toolTip = L("Home · ⌘⇧H")
        home.setAccessibilityLabel(L("Home"))
        rebuild()   // the tabs' close buttons are made again with their new label
    }
    override var mouseDownCanMoveWindow: Bool { true }
    override var isFlipped: Bool { false }
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        NotificationCenter.default.removeObserver(self)
        guard let w = window else { return }
        for name in [NSWindow.didEnterFullScreenNotification, NSWindow.didExitFullScreenNotification, NSWindow.willEnterFullScreenNotification] {
            NotificationCenter.default.addObserver(forName: name, object: w, queue: .main) { [weak self] _ in self?.needsLayout = true; self?.layoutSubtreeIfNeeded() }
        }
    }
    override func mouseUp(with event: NSEvent) { if event.clickCount == 2 { window?.performZoom(nil) } }

    private func rebuild() {
        tabViews.forEach { $0.removeFromSuperview() }
        tabViews = TabBar.inPage ? [] : items.map { item in
            let v = TabView(title: item.name, symbol: nil)
            v.onClick = { [weak self] in self?.onSelect(item.id) }
            v.onClose = { [weak self] in self?.onClose(item.id) }
            v.toolTip = item.name
            v.identifier = NSUserInterfaceItemIdentifier(item.id.uuidString)
            addSubview(v)
            return v
        }
        restyle(); needsLayout = true
    }
    private func restyle() {
        home.active = selected == nil
        for (v, item) in zip(tabViews, items) { v.active = item.id == selected }
    }
    override func layout() {
        super.layout()
        let h: CGFloat = 30, y = (bounds.height - h) / 2
        home.frame = NSRect(x: leftInset, y: y, width: 36, height: h)
        var x = home.frame.maxX + 6
        let room = bounds.width - x - 12
        let natural = tabViews.map { min(240, max(110, $0.naturalWidth)) }
        let scale = natural.reduce(0, +) + CGFloat(max(0, natural.count - 1)) * 4 > room ? room / (natural.reduce(0, +) + CGFloat(max(0, natural.count - 1)) * 4) : 1
        for (v, w) in zip(tabViews, natural) { let ww = max(64, floor(w * scale)); v.frame = NSRect(x: x, y: y, width: ww, height: h); x += ww + 4 }
        placeTrafficLights()
    }
    // The window's own buttons sit in a capsule at the top left, on the line of the pages' plates (owner 2026-10-04: «make them part of
    // the interface, like Apple's floating window controls, everything in one line»). The pages draw the capsule (#wl in v2.html and
    // home.html, 80 x 38 at 12, 12); the title bar's container grows down over that corner only, so the buttons there take their
    // clicks and the space between them drags the window, and the page keeps the rest. AppKit lays the title bar out again on its
    // own (a resize, leaving full screen), so this runs again after those. In full screen the system has its own and the pages hide the capsule.
    static let lights = NSRect(x: 12, y: 12, width: 80, height: 38)   // top-left coordinates, as the pages have it
    private var lightGap: CGFloat?
    private var lightWatch: [NSObjectProtocol] = [], placing = false, replaced: [Date] = []
    func placeTrafficLights() {
        guard !placing, let w = window, !w.styleMask.contains(.fullScreen), let close = w.standardWindowButton(.closeButton),
              let bar = close.superview, let box = bar.superview, let frame = box.superview else { return }
        placing = true; defer { placing = false }
        let types: [NSWindow.ButtonType] = [.closeButton, .miniaturizeButton, .zoomButton]
        let buttons = types.compactMap { w.standardWindowButton($0) }
        // AppKit puts them back on its own more often than the window tells (a new title on the way to Home moved them, owner
        // 2026-10-04): whenever one of them or their bar moves, they go back to the capsule right after
        if lightWatch.isEmpty {
            for v in buttons + [bar, box] {
                v.postsFrameChangedNotifications = true
                lightWatch.append(NotificationCenter.default.addObserver(forName: NSView.frameDidChangeNotification, object: v, queue: .main) { [weak self] _ in
                    guard let self, !self.placing else { return }
                    // never a tug of war with AppKit: at most a dozen times a second
                    let now = Date(); self.replaced = self.replaced.filter { now.timeIntervalSince($0) < 1 } + [now]
                    if self.replaced.count <= 12 { DispatchQueue.main.async { self.placeTrafficLights() } }
                })
            }
        }
        if lightGap == nil, buttons.count == 3 { lightGap = buttons[1].frame.minX - buttons[0].frame.minX }   // the system's own spacing
        let L = TabBar.lights, height = L.maxY + 12, gap = lightGap ?? 20
        // the whole width, as the system has it: cut to the capsule's corner, its edge showed as a seam next to the buttons (owner 2026-10-04);
        // the page under it keeps its clicks as it did under the system's 28 pt title bar
        box.frame = NSRect(x: 0, y: frame.isFlipped ? 0 : frame.bounds.height - height, width: frame.bounds.width, height: height)
        bar.frame = box.bounds
        let bw = close.frame.width, bh = close.frame.height, x0 = L.minX + (L.width - (gap * CGFloat(buttons.count - 1) + bw)) / 2
        for (n, b) in buttons.enumerated() {
            b.setFrameOrigin(NSPoint(x: x0 + CGFloat(n) * gap, y: bar.isFlipped ? L.midY - bh / 2 : bar.bounds.height - L.midY - bh / 2))
        }
    }
}

final class TabView: NSView {
    var onClick: () -> Void = {}
    var onClose: (() -> Void)?
    var active = false { didSet { restyle() } }
    private var hovering = false { didSet { restyle() } }
    private let label = NSTextField(labelWithString: "")
    private let icon = NSImageView()
    private let close = NSButton()
    private let hasTitle: Bool
    var naturalWidth: CGFloat { hasTitle ? ceil((label.stringValue as NSString).size(withAttributes: [.font: label.font ?? NSFont.systemFont(ofSize: 12.5)]).width) + 58 : 36 }

    init(title: String?, symbol: String?) {
        hasTitle = title != nil
        super.init(frame: .zero)
        wantsLayer = true
        layer?.cornerRadius = 8
        if let title {
            label.stringValue = title
            label.font = .systemFont(ofSize: 12.5, weight: .medium)
            label.lineBreakMode = .byTruncatingTail
            label.cell?.truncatesLastVisibleLine = true
            addSubview(label)
            close.image = NSImage(systemSymbolName: "xmark", accessibilityDescription: L("Close Tab"))?.withSymbolConfiguration(.init(pointSize: 9, weight: .semibold))
            close.isBordered = false
            close.bezelStyle = .regularSquare
            close.target = self; close.action = #selector(closeTab)
            close.contentTintColor = Palette.sub
            addSubview(close)
        }
        if let symbol {
            icon.image = NSImage(systemSymbolName: symbol, accessibilityDescription: L("Home"))?.withSymbolConfiguration(.init(pointSize: 13, weight: .medium))
            addSubview(icon)
        }
        setAccessibilityRole(.button)
        setAccessibilityLabel(title ?? L("Home"))
        restyle()
    }
    required init?(coder: NSCoder) { nil }
    override var mouseDownCanMoveWindow: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func updateTrackingAreas() {
        trackingAreas.forEach(removeTrackingArea)
        addTrackingArea(NSTrackingArea(rect: bounds, options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect], owner: self))
    }
    override func mouseEntered(with event: NSEvent) { hovering = true }
    override func mouseExited(with event: NSEvent) { hovering = false }
    override func mouseDown(with event: NSEvent) {}
    override func mouseUp(with event: NSEvent) { if bounds.contains(convert(event.locationInWindow, from: nil)) { onClick() } }
    override func otherMouseUp(with event: NSEvent) { if event.buttonNumber == 2 { onClose?() } }   // middle click closes, as in browsers
    override func accessibilityPerformPress() -> Bool { onClick(); return true }
    @objc private func closeTab() { onClose?() }
    override func layout() {
        super.layout()
        if hasTitle {
            let cw: CGFloat = 18
            close.frame = NSRect(x: bounds.width - cw - 8, y: (bounds.height - cw) / 2, width: cw, height: cw)
            let lh = label.intrinsicContentSize.height
            label.frame = NSRect(x: 12, y: (bounds.height - lh) / 2, width: max(0, close.frame.minX - 16), height: lh)
        } else {
            icon.frame = NSRect(x: (bounds.width - 16) / 2, y: (bounds.height - 16) / 2, width: 16, height: 16)
        }
    }
    private func restyle() {
        layer?.backgroundColor = (active ? Palette.tab : hovering ? Palette.hover : .clear).cgColor
        label.textColor = active ? Palette.ink : Palette.sub
        icon.contentTintColor = active ? Palette.ink : Palette.sub
        close.isHidden = !(active || hovering)
    }
}

// What the Home page shows for a project: a few frames from the top left of its canvas (their ready thumbnails),
// when the boards last changed and how many frames are on the canvas. Read only, off the main thread.
enum HomeData {
    static func sanitize(_ rel: String) -> String {
        String(rel.unicodeScalars.map { ("a"..."z").contains($0) || ("A"..."Z").contains($0) || ("0"..."9").contains($0) || $0 == "." || $0 == "_" || $0 == "-" ? Character($0) : "_" })
    }
    // where the board's server keeps its thumbnails: the app's cache since 2026-10-07 (review/thumbcache.py), the state folder before
    static func thumbsFolder(_ p: Project) -> URL {
        let env = ProcessInfo.processInfo.environment["HYIMG_CACHE_ROOT"]
        let root = env.map { URL(fileURLWithPath: $0) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Caches/Hyimg")
        let cache = root.appendingPathComponent(p.id.uuidString).appendingPathComponent("thumbs")
        return FileManager.default.fileExists(atPath: cache.path) ? cache : URL(fileURLWithPath: p.stateRoot).appendingPathComponent("_thumbs")
    }
    static func info(for p: Project) -> [String: Any] {
        let fm = FileManager.default
        let boards = URL(fileURLWithPath: p.stateRoot).appendingPathComponent("boards")
        var updated: TimeInterval = 0, paths: [String] = [], firsts: [(Double, Double, String)] = []
        let files = ((try? fm.contentsOfDirectory(at: boards, includingPropertiesForKeys: [.contentModificationDateKey])) ?? [])
            .filter { $0.pathExtension == "json" && !$0.lastPathComponent.contains(".notes-index") && !$0.lastPathComponent.hasPrefix("_") }
        for f in files {
            if let d = try? f.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate { updated = max(updated, d.timeIntervalSince1970) }
            guard let data = try? Data(contentsOf: f), let b = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let items = b["items"] as? [String: [String: Any]] else { continue }
            for it in items.values {
                guard let path = it["path"] as? String else { continue }
                paths.append(path)
                if f.lastPathComponent == "main.json" || firsts.isEmpty { firsts.append(((it["y"] as? Double) ?? 0, (it["x"] as? Double) ?? 0, path)) }
            }
        }
        var covers: [String] = []
        let thumbs = thumbsFolder(p)
        if let names = try? fm.contentsOfDirectory(atPath: thumbs.path) {
            var byKey: [String: String] = [:]
            for n in names where n.hasSuffix(".jpg") {
                let parts = n.split(separator: ".")
                guard parts.count >= 4 else { continue }
                let key = parts.dropLast(3).joined(separator: ".")
                if parts[parts.count - 2] == "640" || byKey[key] == nil { byKey[key] = n }
            }
            // rows of the board from the top, left to right: the first frames the owner laid out
            let ordered = firsts.sorted { abs($0.0 - $1.0) > 200 ? $0.0 < $1.0 : $0.1 < $1.1 }
            for (_, _, path) in ordered where covers.count < 3 {
                if let n = byKey[sanitize(path)] { covers.append(thumbs.appendingPathComponent(n).absoluteString) }
            }
        }
        return ["id": p.id.uuidString, "name": p.name, "path": p.libraryRoot, "available": fm.fileExists(atPath: p.libraryRoot),
                "updated": updated, "onCanvas": Set(paths).count, "covers": covers]
    }
}

// The window is dragged by the empty part of its top band (owner 2026-10-04: «what the buttons don't cover up top should drag the
// window; the buttons may change, so they sit above the drag area»). The page in front says how tall its band is and where its plates
// are in it (review/ui/dragband.js, the "dragband" message): a click on a plate falls through to the page, a click anywhere else in the
// band drags the window, a double click does what the title bar's would. Scrolls, pinches and the other buttons over the band still
// reach the page (the canvas pans and zooms under it). A page that has said nothing yet (loading, an error page) has the old 8 points.
final class DragStrip: NSView {
    static let height: CGFloat = 96   // the most a page may claim
    struct Band { var height: CGFloat; var holes: [NSRect] }
    static func band(_ body: [String: Any]) -> Band? {
        guard let h = body["h"] as? NSNumber, let holes = body["holes"] as? [[NSNumber]] else { return nil }
        return Band(height: min(height, CGFloat(truncating: h)), holes: holes.compactMap { r in
            r.count == 4 ? NSRect(x: CGFloat(truncating: r[0]), y: CGFloat(truncating: r[1]), width: CGFloat(truncating: r[2]), height: CGFloat(truncating: r[3])) : nil })
    }
    var band: () -> Band? = { nil }
    override var isFlipped: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func hitTest(_ point: NSPoint) -> NSView? {
        guard !isHidden, let superview else { return nil }
        let p = convert(point, from: superview), b = band() ?? Band(height: 8, holes: [])
        guard p.x >= 0, p.x <= bounds.width, p.y >= 0, p.y < b.height else { return nil }
        return b.holes.contains { $0.contains(p) } ? nil : self
    }
    override func mouseDown(with event: NSEvent) {
        guard event.clickCount == 2 else { window?.performDrag(with: event); return }
        switch UserDefaults.standard.string(forKey: "AppleActionOnDoubleClick") {   // System Settings › Desktop & Dock › double-click a title bar
        case "Minimize": window?.performMiniaturize(nil)
        case "None": break
        default: window?.performZoom(nil)
        }
    }
    // what the page has under the pointer, as if the band were not there
    private var held: NSView?
    private func under(_ event: NSEvent) -> NSView? {
        guard let superview else { return nil }
        let p = superview.convert(event.locationInWindow, from: nil)
        for v in superview.subviews.reversed() where v !== self { if let hit = v.hitTest(p) { return hit } }
        return nil
    }
    override func scrollWheel(with event: NSEvent) { under(event)?.scrollWheel(with: event) }
    override func magnify(with event: NSEvent) { under(event)?.magnify(with: event) }
    override func smartMagnify(with event: NSEvent) { under(event)?.smartMagnify(with: event) }
    override func rotate(with event: NSEvent) { under(event)?.rotate(with: event) }
    override func rightMouseDown(with event: NSEvent) { held = under(event); held?.rightMouseDown(with: event) }
    override func rightMouseDragged(with event: NSEvent) { held?.rightMouseDragged(with: event) }
    override func rightMouseUp(with event: NSEvent) { held?.rightMouseUp(with: event); held = nil }
    override func otherMouseDown(with event: NSEvent) { held = under(event); held?.otherMouseDown(with: event) }
    override func otherMouseDragged(with event: NSEvent) { held?.otherMouseDragged(with: event) }
    override func otherMouseUp(with event: NSEvent) { held?.otherMouseUp(with: event); held = nil }
}
