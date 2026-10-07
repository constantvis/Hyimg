import Foundation

// native/Storage.swift: the memory report of the app's processes and the storage summary Home reads (Settings › Storage, 2026-10-07)
@main struct StorageTests {
    static func require(_ ok: Bool, _ name: String) {
        if ok { print("PASS: \(name)") } else { print("FAIL: \(name)"); exit(1) }
    }
    static func main() throws {
        // the kinds, from command lines as Chromium and the app start them
        require(MemoryReport.kind(["/x/Hyimg Helper", "--type=gpu-process"]).0 == "gpu", "a GPU process")
        require(MemoryReport.kind(["/x/Hyimg Helper (Renderer)", "--type=renderer"]).0 == "pages", "a page")
        require(MemoryReport.kind(["/x/Hyimg Helper", "--type=utility", "--utility-sub-type=network.mojom.NetworkService"]) == ("services", "network.mojom.NetworkService"), "a service with its name")
        require(MemoryReport.kind(["/usr/bin/python3", "/r/review/server.py", "4180"]) == ("servers", "4180"), "a board's server by its port")
        require(MemoryReport.kind(["/Applications/Blender.app/Contents/MacOS/Blender", "-b"]).0 == "blender", "Blender")
        // a real child: found under this process with its footprint, and this process as the app
        let child = Process()
        child.executableURL = URL(fileURLWithPath: "/bin/sleep"); child.arguments = ["5"]
        try child.run()
        defer { child.terminate() }
        Thread.sleep(forTimeInterval: 0.2)
        require(MemoryReport.children(of: getpid()).contains(child.processIdentifier), "the child is listed under the app")
        require(MemoryReport.arguments(child.processIdentifier).suffix(1) == ["5"], "its command line is read")
        let report = MemoryReport.report()
        let procs = report["procs"] as? [[String: Any]] ?? []
        require(procs.contains { ($0["pid"] as? Int) == Int(child.processIdentifier) && ($0["kind"] as? String) == "other" }, "the child is in the report")
        require(procs.contains { ($0["pid"] as? Int) == Int(getpid()) && ($0["kind"] as? String) == "app" && (($0["bytes"] as? UInt64) ?? 0) > 1_000_000 }, "the app's own footprint")
        let total = report["total"] as? UInt64 ?? 0, kinds = report["kinds"] as? [String: UInt64] ?? [:]
        require(total == kinds.values.reduce(0, +) && total > 0, "the total is the sum of the kinds")
        require(MemoryReport.report(names: ["5": "Board"]).isEmpty == false, "a report with names")
        // the summary beside a catalog: each board's bytes by id, its age
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("hyimg-storage-test-\(UUID())")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let catalog = dir.appendingPathComponent("projects.json")
        require(StorageSummary.read(catalog: catalog) == nil && StorageSummary.age(nil) == nil, "no summary yet")
        let t = Date().timeIntervalSince1970 - 60
        let json: [String: Any] = ["t": t, "boards": [["id": "ab-cd", "total": ["disk": 1234, "bytes": 1200]], ["id": "x"]]]
        try JSONSerialization.data(withJSONObject: json).write(to: StorageSummary.file(catalog: catalog))
        let s = StorageSummary.read(catalog: catalog)
        require(StorageSummary.boardBytes(s) == ["AB-CD": 1234], "a board's bytes on disk by its id")
        require(abs((StorageSummary.age(s) ?? 0) - 60) < 5, "its age")
    }
}
