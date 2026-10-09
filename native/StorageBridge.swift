import AppKit
import WebKit

// Settings › Storage, the app's side (review/ui/storage.js, owner 2026-10-07). A page asks {action: "storage", op} and gets
// window.hyimgStorage({op, ...}) back: Home from the app, a board's page in its own engine.
//   summary   storage.py summary: what it measured last (storage.json beside the catalog) and the lost processes now; a scan starts
//             behind it, in its own low-priority Python process, when it is older than 5 minutes. Nothing waits for the scan.
//   ram       the memory of the app's processes right now (native/Storage.swift MemoryReport)
//   clear     «Очистить кэш»: storage.py clear-cache, only regenerable caches inside the cache folder (the page asked first)
//   backups   the app's older copies beside it beyond the newest 2, into the Trash (the page asked first)
//   caps      the thumbnail cache's ceiling, {board, total} in GB (storage.py caps)
//   stop      one lost server or Blender of Hyimg, parent gone (storage.py stop <pid>, review/procs.py checks it again)
//   perflog   the performance log's «Clear» on Home: perflog.py clear, in the cache folder perflog.py computes (the page asked first)
extension App {
    func storageMessage(_ body: [String: Any], _ project: Project?) {
        let op = body["op"] as? String ?? "summary"
        let catalog = registry.file, root = sourceRoot
        let reply: ([String: Any]) -> Void = { [weak self] value in
            var v = value; v["op"] = op
            guard let self, let data = try? JSONSerialization.data(withJSONObject: v), let json = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                let js = "window.hyimgStorage && window.hyimgStorage(\(json))"
                if let project, let session = self.sessions[project.id] { self.evaluate(session, js) } else { self.homeWeb?.evaluateJavaScript(js) }
            }
        }
        switch op {
        case "ram":
            var names: [String: String] = [:]
            for p in registry.projects { names[String(p.port)] = p.name }
            DispatchQueue.global(qos: .utility).async { reply(MemoryReport.report(names: names)) }
        case "summary":
            DispatchQueue.global(qos: .utility).async {
                let out = Self.runStorage(["summary"], root: root, catalog: catalog, wait: true)
                if let res = out.flatMap({ try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }) { reply(res); return }
                let summary = StorageSummary.read(catalog: catalog)   // no Python: what was measured last, as it is
                reply(["summary": summary ?? NSNull(), "age": StorageSummary.age(summary) ?? NSNull(), "scanning": false, "lost": []])
            }
        case "caps":   // the thumbnail cache's ceiling in GB, set at once (storage.py caps, review/thumbcache.py)
            let args = ["caps"] + ["board", "total"].flatMap { k in (body[k] as? NSNumber).map { ["--\(k)", $0.stringValue] } ?? [] }
            DispatchQueue.global(qos: .utility).async {
                let out = Self.runStorage(args, root: root, catalog: catalog, wait: true)
                reply(out.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? ["error": "storage.py did not answer"])
            }
        case "clear", "backups", "stop", "perflog":
            // Home is a file page without the board's dialog (ui/confirm.js is a module): the app asks with the page's own words
            if body["confirm"] as? Bool == true {
                let alert = NSAlert()
                alert.messageText = body["title"] as? String ?? ""; alert.informativeText = body["note"] as? String ?? ""
                alert.addButton(withTitle: body["ok"] as? String ?? "OK"); alert.addButton(withTitle: body["cancel"] as? String ?? L("Cancel"))
                guard alert.runModal() == .alertFirstButtonReturn else { reply(["cancelled": true]); return }
            }
            DispatchQueue.global(qos: .userInitiated).async {
                let args = op == "clear" ? ["clear-cache"] : op == "stop" ? ["stop", String(describing: body["pid"] ?? "")]
                    : op == "perflog" ? ["clear"] : ["backups", "--keep", "2"]
                let script = op == "perflog" ? "perflog.py" : "storage.py"
                let out = Self.runStorage(args, root: root, catalog: catalog, wait: true, script: script)
                let res = out.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? ["error": "\(script) did not answer"]
                if res["error"] == nil, op != "stop" { _ = Self.runStorage(["scan"], root: root, catalog: catalog, wait: false) }
                reply(res)
            }
        default: break
        }
    }

    // review/storage.py with the catalog's folder and the folder the app is installed in; its output when waited for. review/perflog.py
    // (script) runs the same way: the same Python and the app's environment, so HYIMG_CACHE_ROOT names the same cache for both
    @discardableResult
    static func runStorage(_ args: [String], root: URL, catalog: URL, wait: Bool, script: String = "storage.py") -> Data? {
        guard let python = try? ServerSession.findPython(sourceRoot: root) else { return nil }
        let task = Process(), pipe = Pipe()
        task.executableURL = python
        task.arguments = [root.appendingPathComponent("review/" + script).path] + args
        var env = ProcessInfo.processInfo.environment
        env["HYIMG_SUPPORT_ROOT"] = catalog.deletingLastPathComponent().path
        env["HYIMG_INSTALL_DIR"] = Bundle.main.bundleURL.deletingLastPathComponent().path   // the copies lie beside the app
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        task.environment = env
        task.standardOutput = wait ? pipe : FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        task.qualityOfService = wait ? .userInitiated : .background
        do { try task.run() } catch { return nil }
        guard wait else { return Data() }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()
        return data
    }
}
