import Foundation

// hyimg:// links (owner 2026-10-07: «ссылку, которую нажимаешь, и открывается приложение»): native/Links.swift takes only its two routes
// and well-formed ids; anything else gives nil and the app opens nothing.
@main struct LinkTests {
    static func main() throws {
        func require(_ value: Bool, _ name: String) throws {
            guard value else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        let id = UUID(uuidString: "6F1C2B9E-7D35-4C1B-9B7A-2E8D5A0C4F11")!, s = id.uuidString.lowercased()

        try require(AppLink.parse("hyimg://home") == .home && AppLink.parse("HYIMG://Home/") == .home, "home")
        try require(AppLink.parse("hyimg://board/\(s)") == .board(.init(project: id)), "a board alone, the id in lower case")
        try require(AppLink.parse("hyimg://board/\(id.uuidString)") == .board(.init(project: id)), "a board, the id in upper case")
        let full = AppLink.parse("hyimg://board/\(s)?page=p_2&obj=i1abc,g-9,n_x&at=-120.5,40,0.4500")
        try require(full == .board(.init(project: id, page: "p_2", obj: ["i1abc", "g-9", "n_x"], at: "-120.5,40,0.4500")), "page, objects and camera")
        if case .board(let t) = full {
            try require(t.query.map { "\($0.name)=\($0.value ?? "")" } == ["page=p_2", "obj=i1abc,g-9,n_x", "at=-120.5,40,0.4500"], "the board page's own parameters")
            try require(AppLink.url(t).map { AppLink.parse($0) == full } == true, "url() reads back the same")
            try require(t.json.contains("\"obj\":[\"i1abc\",\"g-9\",\"n_x\"]") && t.json.contains("\"page\":\"p_2\""), "json for window.hyimgGo")
        } else { try require(false, "page, objects and camera parsed") }

        // refused: other schemes and routes, paths, extra parts, unknown or repeated parameters, ids and cameras outside their patterns
        let bad = [
            "http://board/\(s)", "file:///etc/passwd", "hyimg://", "hyimg://settings", "hyimg://open?path=/etc", "hyimg://home?x=1", "hyimg://home/extra",
            "hyimg://board", "hyimg://board/", "hyimg://board/not-a-uuid", "hyimg://board/\(s)/more", "hyimg://board/\(s)/../\(s)",
            "hyimg://user:pw@board/\(s)", "hyimg://board:4180/\(s)", "hyimg://board/\(s)#frag",
            "hyimg://board/\(s)?view=canvas", "hyimg://board/\(s)?cmd=rm", "hyimg://board/\(s)?page=a&page=b", "hyimg://board/\(s)?page",
            "hyimg://board/\(s)?page=../etc", "hyimg://board/\(s)?page=%2E%2E%2Fx", "hyimg://board/\(s)?page=a%20b", "hyimg://board/\(s)?page=" + String(repeating: "a", count: 65),
            "hyimg://board/\(s)?page=страница", "hyimg://board/\(s)?obj=", "hyimg://board/\(s)?obj=a,b;c", "hyimg://board/\(s)?obj=a/b",
            "hyimg://board/\(s)?obj=" + (0..<501).map { "i\($0)" }.joined(separator: ","),
            "hyimg://board/\(s)?at=1,2", "hyimg://board/\(s)?at=1,2,0", "hyimg://board/\(s)?at=1,2,-1", "hyimg://board/\(s)?at=1e3,2,1",
            "hyimg://board/\(s)?at=nan,2,1", "hyimg://board/\(s)?at=1,2,inf", "hyimg://board/\(s)?at=1,,1",
            "hyimg://board/\(s)?page=" + String(repeating: "a", count: 9000),
        ]
        for b in bad { try require(AppLink.parse(b) == nil, "refused: \(b.prefix(70))") }
        try require(AppLink.parse("hyimg://board/\(s)?obj=a,,b") == .board(.init(project: id, obj: ["a", "b"])), "empty pieces of obj are skipped")
        // dir (owner 2026-10-08): the board's folder relative to the Dropbox root, a hint for the other Mac; never a way out of the root
        var d = AppLink.Target(project: id, page: "main"); d.dir = "Studio/Brand/Media Lab/#drafts"
        try require(AppLink.parse("hyimg://board/\(s)?page=main&dir=Studio/Brand/Media%20Lab/%23drafts") == .board(d), "a folder in Dropbox")
        for b in ["dir=", "dir=/WORK", "dir=WORK/", "dir=WORK//x", "dir=../x", "dir=WORK/../x", "dir=./x", "dir=a%00b", "dir=a%0Ab", "dir=x&dir=y",
                  "dir=" + String(repeating: "a", count: 1025)] {
            try require(AppLink.parse("hyimg://board/\(s)?\(b)") == nil, "refused: \(b.prefix(40))")
        }

        // View › Open in Browser marks the address, once
        let u = AppLink.stayInBrowser(URL(string: "http://127.0.0.1:4180/?view=canvas&stay=1&stars=1")!)
        try require(u.absoluteString == "http://127.0.0.1:4180/?view=canvas&stars=1&stay=1", "stay=1 once: \(u.absoluteString)")
        try require(AppLink.describe(full).hasPrefix("board \(id.uuidString) page=p_2 obj=3") && AppLink.describe(nil) == "invalid", "the log keeps no ids")
        print("All link tests passed")
    }
}
