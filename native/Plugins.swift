import AppKit

// Settings › Plugins, the app's side (review/ui/plugins.js, review/plugins_admin.py; owner 2026-10-07: «В настройках включить,
// выключить и посмотреть»). A page sends {action: "plugins", op} and gets window.hyimgPlugins(d) back: Home from the app, a board in its
// canvas frame.
//   list            every plugin with its version, what it does, its folder, on or off (plugins_admin.py list)
//   add             a folder chosen in a panel; plugins_admin.py checks its manifest.json and links it into the plugins folder
//   remove {name}   only the link goes, never the plugin's folder; Home asks first with the page's words (confirm, title, note, ok, cancel)
//   reveal {path}   the plugin's folder in Finder
//   changed         a board removed one through its server: the other boards and Home look again
// On and off is the app's setting cv.plugoff, sent like any other setting; each board takes it itself (ui/plugins-board.js), no server
// restart. After an add or a remove every board looks again and reloads with its plugins as they are now.
extension App {
    func pluginsMessage(_ body: [String: Any], _ project: Project?) {
        let op = body["op"] as? String ?? "list", dir = registry.file.deletingLastPathComponent(), root = sourceRoot
        let session = project.flatMap { sessions[$0.id] }
        // a board's settings live in its canvas frame (v2.html holds it as #cvFrame); Home is its own page
        let inCanvas = { (call: String) in "(function(){var w=window;try{var f=document.getElementById('cvFrame');if(f&&f.contentWindow)w=f.contentWindow}catch(e){}\(call)})()" }
        let everyone = { [weak self] in
            guard let self else { return }
            self.sessions.values.forEach { self.evaluate($0, inCanvas("w.hyimgPluginsChanged&&w.hyimgPluginsChanged()")) }
            self.homeWeb?.evaluateJavaScript("window.hyPlugins && window.hyPlugins.load()")
        }
        let reply: ([String: Any]) -> Void = { [weak self] value in
            var v = value; v["op"] = op
            guard let self, let data = try? JSONSerialization.data(withJSONObject: v), let json = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                if let session { self.evaluate(session, inCanvas("w.hyimgPlugins&&w.hyimgPlugins(\(json))")) }
                else { self.homeWeb?.evaluateJavaScript("window.hyimgPlugins && window.hyimgPlugins(\(json))") }
                if (op == "add" || op == "remove") && v["error"] == nil && v["cancelled"] == nil { everyone() }
            }
        }
        let run = { (args: [String]) in
            DispatchQueue.global(qos: .userInitiated).async { reply(Self.runReview("plugins_admin.py", args, dir: dir, root: root) ?? ["error": "plugins_admin.py did not answer"]) }
        }
        switch op {
        case "list": run(["list"])
        case "add":
            let panel = NSOpenPanel()
            panel.title = L("Add a plugin"); panel.message = L("Choose the plugin's folder, the one with manifest.json.")
            panel.prompt = L("Add"); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = false
            guard panel.runModal() == .OK, let url = panel.url else { reply(["cancelled": true]); return }
            run(["add", url.path])
        case "remove":
            guard let name = body["name"] as? String, !name.isEmpty else { return }
            if body["confirm"] as? Bool == true {   // Home is a file page without the board's dialog: the app asks with the page's words
                let alert = NSAlert()
                alert.messageText = body["title"] as? String ?? ""; alert.informativeText = body["note"] as? String ?? ""
                alert.addButton(withTitle: body["ok"] as? String ?? L("Remove")); alert.addButton(withTitle: body["cancel"] as? String ?? L("Cancel"))
                guard alert.runModal() == .alertFirstButtonReturn else { reply(["cancelled": true]); return }
            }
            run(["remove", name])
        case "reveal":
            guard let p = body["path"] as? String, FileManager.default.fileExists(atPath: (p as NSString).appendingPathComponent("manifest.json")) else { return }
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: p)])
        case "changed": everyone()
        default: break
        }
    }
}
