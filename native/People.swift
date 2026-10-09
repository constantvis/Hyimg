import AppKit
import WebKit

// Who made a change, the app's side (owner 2026-10-07: two people, each on his own Mac, share boards through a shared Dropbox folder).
// The files are review/people.py's and review/places.py's, beside the catalog: profile.json (this Mac's person: id, name, colour),
// people.json (the address book, with the local renames) and places.json (the shared and the private folder). The app reads them for
// Home (People.home) and lets the Python modules write them, so there is one writer's code. Home and a board's page send
// {action: "profile", op} and get window.hyimgProfile(d) back:
//   save {name, color}     the first launch's answer or a change in Settings › Profile (people.py save)
//   signout                this Mac forgets its profile; Home asks again at the next start; nothing else is deleted
//   alias {person, name}   how this Mac shows another person
//   avatar {avatar}        this Mac's person's picture, a data URL the page cut to 256 px ("" takes it off)
//   badge {kind, picture}  an agent kind's picture on this Mac (agent-badges.json), "" back to the company's mark or our glyph
//   pick {which}           the shared or the private folder, chosen in a folder panel (places.py set)
//   visibility {id, to}    a board's folder moves into the shared or the private folder, asked first (places.py move), then the catalog
enum People {
    static let colors: Set<String> = ["yellow", "orange", "red", "pink", "purple", "blue", "green", "grey"]
    static func json(_ url: URL) -> [String: Any]? {
        guard let d = try? Data(contentsOf: url) else { return nil }
        return try? JSONSerialization.jsonObject(with: d) as? [String: Any]
    }
    static func name(_ v: Any?) -> String { ((v as? String) ?? "").split(whereSeparator: \.isWhitespace).joined(separator: " ") }
    static func color(_ v: Any?) -> String { (v as? String).flatMap { colors.contains($0) ? $0 : nil } ?? "" }
    // this Mac's person, or nil (no profile yet, or signed out)
    static func me(_ dir: URL) -> [String: Any]? {
        guard let p = json(dir.appendingPathComponent("profile.json")), let id = p["id"] as? String, UUID(uuidString: id) != nil, !name(p["name"]).isEmpty else { return nil }
        var out: [String: Any] = ["id": id.lowercased(), "name": name(p["name"]), "color": color(p["color"]).isEmpty ? "blue" : color(p["color"]), "created": p["created"] as? String ?? ""]
        if let a = avatar(p["avatar"]) { out["avatar"] = a }
        return out
    }
    static func places(_ dir: URL) -> [String: String] {
        let p = json(dir.appendingPathComponent("places.json")) ?? [:]
        var out: [String: String] = [:]
        for k in ["shared", "private"] { out[k] = (p[k] as? String).flatMap { $0.hasPrefix("/") ? $0 : nil } ?? "" }
        return out
    }
    static func inside(_ a: String, _ b: String) -> Bool {
        let x = ProjectRegistry.canonical(a), y = ProjectRegistry.canonical(b)
        return x == y || x.hasPrefix(y.hasSuffix("/") ? y : y + "/")
    }
    // "shared" | "private" | "" for a board's folder (review/places.py visibility)
    static func visibility(_ folder: String, _ places: [String: String]) -> String {
        for k in ["shared", "private"] {
            if let p = places[k], !p.isEmpty, inside(folder, p), ProjectRegistry.canonical(folder) != ProjectRegistry.canonical(p) { return k }
        }
        return ""
    }
    // the address book as a page shows it ({id: {name, own, color, alias?, me?}}), with the people the boards' cards name
    // (<state>/people/<id>.json) that this Mac has not met yet: a partner's edits show his name before any of his boards is opened here
    static func people(_ dir: URL, projects: [Project], me: [String: Any]?) -> [String: [String: Any]] {
        var out: [String: [String: Any]] = [:]
        for p in projects {
            let d = URL(fileURLWithPath: p.stateRoot).appendingPathComponent("people")
            for f in (try? FileManager.default.contentsOfDirectory(at: d, includingPropertiesForKeys: nil)) ?? [] where f.pathExtension == "json" {
                guard let c = json(f), let id = (c["id"] as? String)?.lowercased(), f.deletingPathExtension().lastPathComponent == id, !name(c["name"]).isEmpty else { continue }
                var e: [String: Any] = ["name": name(c["name"]), "own": name(c["name"]), "color": color(c["color"])]
                if let a = avatar(c["avatar"]) { e["avatar"] = a }
                e["agents"] = seen(out[id]?["agents"], c["agents"])
                out[id] = e
            }
        }
        for (k, v) in json(dir.appendingPathComponent("people.json")) ?? [:] {
            guard let e = v as? [String: Any], UUID(uuidString: k) != nil else { continue }
            let id = k.lowercased(), own = out[id]?["own"] as? String ?? name(e["name"]), alias = name(e["alias"]), card = out[id]
            out[id] = ["name": alias.isEmpty ? (own.isEmpty ? "?" : own) : alias, "own": own, "color": card?["color"] as? String ?? color(e["color"]),
                       "agents": seen(card?["agents"], e["agents"])]
            if !alias.isEmpty { out[id]?["alias"] = alias }
            if e["hidden"] as? Bool == true { out[id]?["hidden"] = true }
            if let a = avatar(card?["avatar"]) ?? avatar(e["avatar"]) { out[id]?["avatar"] = a }
        }
        if let me, let id = me["id"] as? String {
            out[id] = ["name": me["name"] ?? "", "own": me["name"] ?? "", "color": me["color"] ?? "", "me": true, "agents": out[id]?["agents"] ?? [String: Double]()]
            if let a = avatar(me["avatar"]) { out[id]?["avatar"] = a }
        }
        return out
    }
    // a person's picture (people.py clean_avatar): a small data URL, else nil
    static func avatar(_ v: Any?) -> String? {
        guard let s = v as? String, s.count <= 80_000, s.hasPrefix("data:image/png;base64,") || s.hasPrefix("data:image/jpeg;base64,") || s.hasPrefix("data:image/webp;base64,") else { return nil }
        return s
    }
    // this Mac's own pictures of the agent kinds (people.py badges): {kind: data URL}
    static let kinds: Set<String> = ["claude", "codex", "gemini", "kimi", "opencode", "agent"]
    static func badges(_ dir: URL) -> [String: String] {
        var out: [String: String] = [:]
        for (k, v) in json(dir.appendingPathComponent("agent-badges.json")) ?? [:] where kinds.contains(k) { if let a = avatar(v) { out[k] = a } }
        return out
    }
    // the agents seen acting for a person, {kind: last time}, the newest of two sources (people.py clean_agents keeps the kinds right)
    static func seen(_ a: Any?, _ b: Any?) -> [String: Double] {
        var out: [String: Double] = [:]
        for d in [a, b] { for (k, t) in (d as? [String: Any]) ?? [:] { if let t = (t as? NSNumber)?.doubleValue { out[k] = max(out[k] ?? 0, t) } } }
        return out
    }
    // what Home gets with the projects; BoardNews counts another person's edits as news from here on
    static func home(_ catalog: URL, projects: [Project]) -> [String: Any] {
        let dir = catalog.deletingLastPathComponent(), m = me(dir), pl = places(dir)
        BoardNews.me = m?["id"] as? String
        let vis = Dictionary(projects.map { ($0.id.uuidString, visibility($0.libraryRoot, pl)) }, uniquingKeysWith: { a, _ in a })
        return ["profile": m ?? NSNull(), "people": people(dir, projects: projects, me: m), "places": pl, "vis": vis, "badges": badges(dir)]
    }
}

extension App {
    func profileMessage(_ body: [String: Any], _ project: Project?) {
        guard body["action"] as? String == "profile" else { macNotifMessage(body); return }   // a board's bell, open or not (MacNotifications.swift)
        let op = body["op"] as? String ?? "", dir = registry.file.deletingLastPathComponent(), root = sourceRoot
        // the answer goes where the question came from: a board's page names its board (ofBoard), Home names none
        let session = op == "visibility" ? nil : project.flatMap { sessions[$0.id] }
        let reply: ([String: Any]) -> Void = { [weak self] value in
            guard let self, let data = try? JSONSerialization.data(withJSONObject: value), let json = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                let js = "window.hyimgProfile && window.hyimgProfile(\(json))"
                if let session { self.evaluate(session, js) } else { self.homeWeb?.evaluateJavaScript(js) }
                self.pushHome()
            }
        }
        switch op {
        case "save":
            let args = ["save", People.name(body["name"]), People.color(body["color"])]
            DispatchQueue.global(qos: .userInitiated).async { reply(Self.runReview("people.py", args, dir: dir, root: root) ?? ["error": "people.py did not answer"]) }
        case "signout":
            DispatchQueue.global(qos: .userInitiated).async { reply(Self.runReview("people.py", ["signout"], dir: dir, root: root) ?? ["error": "people.py did not answer"]) }
        case "alias":
            let args = ["alias", body["person"] as? String ?? "", People.name(body["name"])]
            DispatchQueue.global(qos: .userInitiated).async { reply(Self.runReview("people.py", args, dir: dir, root: root) ?? ["error": "people.py did not answer"]) }
        case "hide":   // Settings › Profile › Team: a person out of this Mac's lists, or back
            let args = ["hide", body["person"] as? String ?? "", (body["hidden"] as? Bool ?? true) ? "1" : "0"]
            DispatchQueue.global(qos: .userInitiated).async { reply(Self.runReview("people.py", args, dir: dir, root: root) ?? ["error": "people.py did not answer"]) }
        case "avatar", "badge":   // a picture the page cut (ui/crop.js), as a data URL in a temporary file ("" takes it off)
            let data = People.avatar(body[op == "avatar" ? "avatar" : "picture"]) ?? "", kind = body["kind"] as? String ?? ""
            if op == "badge" && !People.kinds.contains(kind) { return }
            DispatchQueue.global(qos: .userInitiated).async {
                let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("hyimg-avatar-\(UUID().uuidString).txt")
                if !data.isEmpty { try? data.write(to: tmp, atomically: true, encoding: .ascii) }
                defer { try? FileManager.default.removeItem(at: tmp) }
                let file = data.isEmpty ? "" : tmp.path, args = op == "avatar" ? ["avatar", file] : ["badge", kind, file]
                reply(Self.runReview("people.py", args, dir: dir, root: root) ?? ["error": "people.py did not answer"])
            }
        case "pick":
            guard let which = body["which"] as? String, ["shared", "private"].contains(which) else { return }
            let panel = NSOpenPanel()
            panel.title = which == "shared" ? L("The shared folder") : L("The private folder")
            panel.message = which == "shared" ? L("Boards in this folder are seen by everyone it is shared with, for example in Dropbox.")
                : L("Boards here are only yours while this folder is shared with no one.")
            panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
            guard panel.runModal() == .OK, let url = panel.url else { return }
            DispatchQueue.global(qos: .userInitiated).async {
                reply(Self.runReview("places.py", ["set", "--" + which, url.path], dir: dir, root: root) ?? ["error": "places.py did not answer"])
            }
        case "visibility":
            guard let project, let to = body["to"] as? String, ["shared", "private"].contains(to) else { return }
            moveBoard(project, to: to, dir: dir)
        default: break
        }
    }

    // a board into the shared or the private folder: asked first, its server stopped, its folder moved (places.py), the catalog after
    func moveBoard(_ project: Project, to: String, dir: URL) {
        let target = People.places(dir)[to] ?? ""
        guard !target.isEmpty else { alert(L("Choose the shared and the private folder in Settings › Profile first")); return }
        guard People.visibility(project.libraryRoot, People.places(dir)) != to else { return }
        let newRoot = URL(fileURLWithPath: target).appendingPathComponent(URL(fileURLWithPath: project.libraryRoot).lastPathComponent).path
        let inside = People.inside(project.stateRoot, project.libraryRoot)
        let newState = inside ? newRoot + String(ProjectRegistry.canonical(project.stateRoot).dropFirst(ProjectRegistry.canonical(project.libraryRoot).count)) : project.stateRoot
        do { try registry.checkRelocate(id: project.id, libraryRoot: newRoot, stateRoot: newState) }
        catch { alert(L("Couldn't move the board"), detail: error.localizedDescription); return }
        let ask = NSAlert()
        ask.messageText = to == "shared" ? L("Make “%@” shared?", project.name) : L("Make “%@” only yours?", project.name)
        ask.informativeText = L("Its folder moves to %@. Nothing is deleted: from another disk the old folder goes to the Trash after the copy is checked.", target)
        ask.addButton(withTitle: L("Move")); ask.addButton(withTitle: L("Cancel"))
        guard ask.runModal() == .alertFirstButtonReturn else { return }
        let id = project.id, src = project.libraryRoot, state = project.stateRoot, root = sourceRoot
        let run = {
            self.sessions[id]?.cef?.closeBrowser()
            self.sessions[id]?.server.stopSynchronously()
            self.sessions.removeValue(forKey: id)
            self.tabs.removeAll { $0 == id }; self.tabBar?.items = self.tabItems(); self.saveTabs()
            self.homeProgress(id, L("Moving the folder…"))
            DispatchQueue.global(qos: .userInitiated).async {
                let res = Self.runReview("places.py", ["move", src, to, "--state", state], dir: dir, root: root) ?? ["error": "places.py did not answer"]
                DispatchQueue.main.async {
                    if let root = res["libraryRoot"] as? String {
                        do { try self.registry.relocate(id: id, libraryRoot: root, stateRoot: res["stateRoot"] as? String ?? state) }
                        catch { self.alert(L("The folder moved, the catalog did not change"), detail: error.localizedDescription) }
                        self.homeProgress(id, to == "shared" ? L("Shared") : L("Only for me"), done: true)
                        if let kept = res["kept"] as? String { self.alert(L("The old folder stayed"), detail: kept) }
                    } else {
                        self.homeProgress(id, L("Not moved"), failed: true)
                        self.alert(L("Couldn't move the board"), detail: res["error"] as? String ?? "")
                    }
                    self.pushHome(); self.writeActive()
                }
            }
        }
        if let session = sessions[id] { performAfterSaving(session, operation: run) } else { run() }
    }

    // review/<script> with the profile's folder; its JSON answer
    static func runReview(_ script: String, _ args: [String], dir: URL, root: URL) -> [String: Any]? {
        guard let python = try? ServerSession.findPython(sourceRoot: root) else { return nil }
        let task = Process(), pipe = Pipe()
        task.executableURL = python
        task.arguments = [root.appendingPathComponent("review/" + script).path] + args
        var env = ProcessInfo.processInfo.environment
        env["HYIMG_PROFILE_DIR"] = dir.path
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        task.environment = env
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        do { try task.run() } catch { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()
        return try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    }
}
