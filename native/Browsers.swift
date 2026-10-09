import AppKit
import UniformTypeIdentifiers

// «Open in <Browser>» (owner 2026-10-09 on Dev Studio's «Open»: «Может быть, Open in browser тогда нужно написать. И также добавить логотип,
// какой у нас стандартный браузер ... кнопку со стрелочкой, чтобы выбрать браузер»; review/ui/hy/openin.js). A page sends {action:
// "browsers", op} and gets window.hyimgBrowsers(d) back: a board in its canvas frame, Home in its page.
//   list             {op, browsers: [{id, name, icon}], default, last}: every app macOS opens https links with (one per bundle id, by name),
//                    icon a 64 px PNG as a data URL; default the system's browser; last the one chosen here before ("" when none or gone)
//   open {url, app}  the http or https url in that app, which must be one of the list; it becomes the last; {op, app, ok} or {op, error}
// The last one is this Mac user's (UserDefaults), the same on every board.
extension App {
    func browsersMessage(_ body: [String: Any], _ project: Project?) {
        let op = body["op"] as? String ?? "list"
        let session = project.flatMap { sessions[$0.id] }
        let reply: ([String: Any]) -> Void = { [weak self] value in
            var v = value; v["op"] = op
            guard let self, let data = try? JSONSerialization.data(withJSONObject: v), let json = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                let js = Browsers.inCanvas("w.hyimgBrowsers&&w.hyimgBrowsers(\(json))")
                if let session { self.evaluate(session, js) } else { self.homeWeb?.evaluateJavaScript(js) }
            }
        }
        switch op {
        case "list": reply(Browsers.listing())
        case "open":
            guard let text = body["url"] as? String, let url = Browsers.webURL(text) else { reply(["error": "not a web address"]); return }
            guard let id = body["app"] as? String, let app = Browsers.handlers().first(where: { $0.id == id }) else { reply(["error": "not a browser"]); return }
            NSWorkspace.shared.open([url], withApplicationAt: app.url, configuration: NSWorkspace.OpenConfiguration()) { _, error in
                if let error { reply(["error": error.localizedDescription]); return }
                UserDefaults.standard.set(id, forKey: Browsers.lastKey)
                reply(["app": id, "ok": true])
            }
        default: break
        }
    }
}

enum Browsers {
    struct Handler { let id: String; let name: String; let url: URL }
    static let lastKey = "hyimg.browser.last"
    static let probe = URL(string: "https://example.com")!
    static var icons: [String: String] = [:]   // app path -> its data URL, drawn once a launch

    // a board's pages live in its canvas frame (v2.html holds it as #cvFrame); Home is its own page
    static func inCanvas(_ call: String) -> String {
        "(function(){var w=window;try{var f=document.getElementById('cvFrame');if(f&&f.contentWindow)w=f.contentWindow}catch(e){}\(call)})()"
    }

    // only http and https: a page cannot make the app open a file or another scheme
    static func webURL(_ text: String) -> URL? {
        guard let url = URL(string: text), let scheme = url.scheme?.lowercased(), scheme == "http" || scheme == "https", url.host != nil else { return nil }
        return url
    }

    // the browsers: the apps that open https links and also open web pages as files (HTML and XHTML), one per bundle id (macOS lists
    // copies of one app, the first is the one it would use), not Hyimg itself. Opening https alone is not enough: on the owner's Mac 2026-10-09
    // that list had 24 apps, downloaders, a VPN, Instagram and ChatGPT among them; HTML and XHTML left the browsers and 3 others, and a
    // utility (a link router, a VPN) is left out too. The system's default browser is always in
    static func handlers() -> [Handler] {
        let own = Bundle.main.bundleIdentifier, ws = NSWorkspace.shared
        let ids = { (urls: [URL]) in Set(urls.compactMap { Bundle(url: $0)?.bundleIdentifier }) }
        let pages = ids(ws.urlsForApplications(toOpen: UTType.html)).intersection(ids(ws.urlsForApplications(toOpen: UTType(filenameExtension: "xhtml") ?? .html)))
        let def = ws.urlForApplication(toOpen: probe).flatMap { Bundle(url: $0)?.bundleIdentifier }
        var seen = Set<String>(), out: [Handler] = []
        for url in ws.urlsForApplications(toOpen: probe) {
            guard let bundle = Bundle(url: url), let id = bundle.bundleIdentifier, id != own, !seen.contains(id) else { continue }
            let utility = bundle.object(forInfoDictionaryKey: "LSApplicationCategoryType") as? String == "public.app-category.utilities"
            guard id == def || (pages.contains(id) && !utility) else { continue }
            seen.insert(id)
            var name = FileManager.default.displayName(atPath: url.path)
            if name.hasSuffix(".app") { name = String(name.dropLast(4)) }
            out.append(Handler(id: id, name: name, url: url))
        }
        return out.sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending }
    }

    static func listing() -> [String: Any] {
        let list = handlers()
        let def = NSWorkspace.shared.urlForApplication(toOpen: probe).flatMap { Bundle(url: $0)?.bundleIdentifier } ?? ""
        let last = UserDefaults.standard.string(forKey: lastKey) ?? ""
        return ["browsers": list.map { ["id": $0.id, "name": $0.name, "icon": icon($0.url)] },
                "default": def, "last": list.contains { $0.id == last } ? last : ""]
    }

    // the app's icon as the Finder draws it, 32 pt at 2x, a PNG data URL ("" when it cannot be drawn)
    static func icon(_ app: URL) -> String {
        if let known = icons[app.path] { return known }
        let image = NSWorkspace.shared.icon(forFile: app.path), px = 64
        guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                         isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return "" }
        rep.size = NSSize(width: 32, height: 32)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        image.draw(in: NSRect(x: 0, y: 0, width: 32, height: 32), from: .zero, operation: .copy, fraction: 1)
        NSGraphicsContext.restoreGraphicsState()
        guard let png = rep.representation(using: .png, properties: [:]) else { return "" }
        let data = "data:image/png;base64," + png.base64EncodedString()
        icons[app.path] = data
        return data
    }
}
