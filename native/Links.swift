import Foundation

// hyimg:// links (owner 2026-10-07: «Можно ли сделать ссылку, которую нажимаешь, и открывается приложение? ... При этом чтобы оставалась
// возможность классической ссылки»). The app registers the scheme (build.sh, CFBundleURLTypes); a click on such a link anywhere in macOS
// brings Hyimg up on that board. Two routes, nothing else:
//   hyimg://home                                                      Home
//   hyimg://board/<board uuid>?page=<page>&obj=<id,id>&at=<x,y,z>&dir=<folder>
//       a board by its stable id (ports change between runs): the id in its folder (board.json, shared by the Macs that sync it, owner
//       2026-10-08) or, in older links, this Mac's catalog id; the page, the objects selected and centred, or a camera. dir is the board's
//       folder relative to the Dropbox root, a hint for a Mac that has not added the board yet (BoardIdentity.swift)
// The query is the board's own http link's (canvas.html LINK: page, obj, at), so a link converts both ways (review/ui/applink.js,
// review/hylink.py). Everything is validated here before the app acts: an unknown route, an unknown or repeated parameter, a path, a
// value outside its pattern gives nil and the app opens nothing. No command or address ever comes from a link, and no absolute path: dir
// is only looked up under this Mac's Dropbox root, read, and offered on Home; nothing is opened or registered from it without a click.
// This file is Foundation only: the native tests compile it alone (tests/test_native_links.swift); the app's side is LinkRouting.swift.
enum AppLink: Equatable {
    case home
    case board(Target)

    struct Target: Equatable {
        let project: UUID
        var page: String? = nil
        var obj: [String] = []
        var at: String? = nil
        var dir: String? = nil   // the board's folder relative to the Dropbox root: the app's, never sent to the page
        // the board page's own address parameters (canvas.html LINK), for its first load or for window.hyimgGo
        var query: [URLQueryItem] {
            [page.map { URLQueryItem(name: "page", value: $0) }, obj.isEmpty ? nil : URLQueryItem(name: "obj", value: obj.joined(separator: ",")),
             at.map { URLQueryItem(name: "at", value: $0) }].compactMap { $0 }
        }
        var json: String {
            var o: [String: Any] = ["obj": obj]; if let page { o["page"] = page }; if let at { o["at"] = at }
            return (try? JSONSerialization.data(withJSONObject: o)).flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        }
    }

    static let scheme = "hyimg"
    static let maxLength = 8192, maxObjects = 500
    // a page or an object id on the board: what the canvas and the server make ([A-Za-z0-9_-], server.py board_path, canvas uid())
    static func isID(_ s: String) -> Bool {
        !s.isEmpty && s.count <= 64 && s.unicodeScalars.allSatisfy { CharacterSet.alphanumerics.contains($0) && $0.isASCII || $0 == "_" || $0 == "-" }
    }
    // a folder relative to the Dropbox root: parts without «.», «..», empty ones or control characters (review/hylink.py DIR)
    static func isFolder(_ s: String) -> Bool {
        !s.isEmpty && s.count <= 1024 && s.split(separator: "/", omittingEmptySubsequences: false).allSatisfy { p in
            !p.isEmpty && p != "." && p != ".." && !p.unicodeScalars.contains { $0.value < 32 || $0.value == 127 }
        }
    }
    // a camera «x,y,z» as the canvas writes it: three finite plain numbers, the zoom above 0
    static func isCamera(_ s: String) -> Bool {
        let parts = s.split(separator: ",", omittingEmptySubsequences: false)
        guard s.count <= 64, parts.count == 3, parts.allSatisfy({ !$0.isEmpty && $0.allSatisfy { "0123456789.-".contains($0) } }) else { return false }
        let n = parts.compactMap { Double($0) }
        return n.count == 3 && n.allSatisfy(\.isFinite) && n[2] > 0
    }

    static func parse(_ url: URL) -> AppLink? { parse(url.absoluteString) }
    static func parse(_ text: String) -> AppLink? {
        guard text.count <= maxLength, let c = URLComponents(string: text), c.scheme?.lowercased() == scheme,
              c.user == nil, c.password == nil, c.port == nil, c.fragment == nil else { return nil }
        let parts = c.path.split(separator: "/").map(String.init), items = c.queryItems ?? []
        switch (c.host ?? "").lowercased() {
        case "home": return parts.isEmpty && items.isEmpty ? .home : nil
        case "board":
            guard parts.count == 1, let id = UUID(uuidString: parts[0]) else { return nil }
            var t = Target(project: id), seen = Set<String>()
            for q in items {
                guard let v = q.value, seen.insert(q.name).inserted else { return nil }   // a parameter twice: which one would win is a guess
                switch q.name {
                case "page": guard isID(v) else { return nil }; t.page = v
                case "obj":
                    let ids = v.split(separator: ",").map(String.init)
                    guard !ids.isEmpty, ids.count <= maxObjects, ids.allSatisfy(isID) else { return nil }
                    t.obj = ids
                case "at": guard isCamera(v) else { return nil }; t.at = v
                case "dir": guard isFolder(v) else { return nil }; t.dir = v
                default: return nil
                }
            }
            return .board(t)
        default: return nil
        }
    }

    // the link of a board (hy.py link and the canvas build the same text)
    static func url(_ t: Target) -> URL? {
        var c = URLComponents(); c.scheme = scheme; c.host = "board"; c.path = "/" + t.project.uuidString.lowercased()
        // percent-encoded by hand: URLComponents leaves «&», «=» and «+» of a folder's name as they are, which would split the query
        var safe = CharacterSet.urlQueryAllowed; safe.remove(charactersIn: "&=+#?")
        let q = t.query + (t.dir.map { [URLQueryItem(name: "dir", value: $0)] } ?? [])
        c.percentEncodedQueryItems = q.isEmpty ? nil : q.map { URLQueryItem(name: $0.name, value: $0.value?.addingPercentEncoding(withAllowedCharacters: safe)) }
        return c.url
    }
    // View › Open in Browser: the page in the browser says it was sent there from the app, so it neither offers the app back nor
    // sends itself there (the setting «Open board links in the app»)
    static func stayInBrowser(_ url: URL) -> URL {
        guard var c = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return url }
        c.queryItems = (c.queryItems ?? []).filter { $0.name != "stay" } + [URLQueryItem(name: "stay", value: "1")]
        return c.url ?? url
    }
    // what the app's log keeps of a link: its route and the board, not the ids inside it
    static func describe(_ link: AppLink?) -> String {
        switch link {
        case .home: return "home"
        case .board(let t): return "board \(t.project.uuidString) page=\(t.page ?? "-") obj=\(t.obj.count) at=\(t.at == nil ? "no" : "yes") dir=\(t.dir == nil ? "no" : "yes")"
        case nil: return "invalid"
        }
    }
}
