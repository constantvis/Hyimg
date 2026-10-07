import Darwin
import Foundation

// Settings › Storage (owner 2026-10-07: «how much RAM the app uses right now», «how much each project takes»).
// MemoryReport: the memory of the app and of every process under it right now, by kind: the window, Chromium's GPU process, its
// pages, its services, each board's Python server, Blender and anything else a server started. The number is the physical footprint,
// the one Activity Monitor shows as Memory (proc_pid_rusage, ri_phys_footprint), not RSS, which leaves out compressed memory.
// StorageSummary: what review/storage.py measured last (storage.json beside the catalog), read as it is; the scan runs in Python.
enum MemoryReport {
    struct Proc { let pid: pid_t; let kind: String; let label: String; let bytes: UInt64 }

    static func footprint(_ pid: pid_t) -> UInt64? {
        var info = rusage_info_v4()
        let ok = withUnsafeMutablePointer(to: &info) { ptr in
            ptr.withMemoryRebound(to: rusage_info_t?.self, capacity: 1) { proc_pid_rusage(pid, RUSAGE_INFO_V4, $0) }
        }
        return ok == 0 ? info.ri_phys_footprint : nil
    }

    static func children(of pid: pid_t) -> [pid_t] {
        var buf = [pid_t](repeating: 0, count: 512)
        let n = proc_listchildpids(pid, &buf, Int32(buf.count * MemoryLayout<pid_t>.size))
        return n > 0 ? Array(buf.prefix(Int(n))).filter { $0 > 0 } : []
    }

    // a process's command line (sysctl KERN_PROCARGS2): argc, the executable's path, then the arguments
    static func arguments(_ pid: pid_t) -> [String] {
        var mib: [Int32] = [CTL_KERN, KERN_PROCARGS2, pid], size = 0
        guard sysctl(&mib, 3, nil, &size, nil, 0) == 0, size > 4 else { return [] }
        var buf = [UInt8](repeating: 0, count: size)
        guard sysctl(&mib, 3, &buf, &size, nil, 0) == 0, size > 4 else { return [] }
        let argc = Int(buf.withUnsafeBytes { $0.load(as: Int32.self) })
        let parts = buf[4..<size].split(separator: 0, omittingEmptySubsequences: true).map { String(decoding: $0, as: UTF8.self) }
        return Array(parts.prefix(argc + 1))   // the path first, then argv (argv[0] is the path again)
    }

    // what a process is, from its command line
    static func kind(_ args: [String]) -> (String, String) {
        let line = args.joined(separator: " ")
        if let type = args.first(where: { $0.hasPrefix("--type=") })?.dropFirst(7) {
            switch type {
            case "gpu-process": return ("gpu", "")
            case "renderer": return ("pages", "")
            default: return ("services", args.first { $0.hasPrefix("--utility-sub-type=") }.map { String($0.dropFirst(19)) } ?? String(type))
            }
        }
        if let i = args.firstIndex(where: { $0.hasSuffix("review/server.py") }) { return ("servers", i + 1 < args.count ? args[i + 1] : "") }
        if line.contains("Blender") || line.contains("blender") { return ("blender", "") }
        if line.contains("storage.py") { return ("scan", "") }
        return ("other", (args.first as NSString?)?.lastPathComponent ?? "")
    }

    // the app (root) and every process below it, each with its kind and footprint
    static func processes(root: pid_t = getpid()) -> [Proc] {
        var out: [Proc] = [], queue: [pid_t] = [root], seen: Set<pid_t> = []
        while let pid = queue.first {
            queue.removeFirst()
            guard seen.insert(pid).inserted, seen.count < 400 else { continue }
            let (kind, label) = pid == root ? ("app", "") : Self.kind(arguments(pid))
            if let bytes = footprint(pid) { out.append(Proc(pid: pid, kind: kind, label: label, bytes: bytes)) }
            queue += children(of: pid)
        }
        return out
    }

    // {"t", "total", "kinds": {kind: bytes}, "procs": [{pid, kind, label, bytes}]}; a server's label is its board's name (by port)
    static func report(root: pid_t = getpid(), names: [String: String] = [:]) -> [String: Any] {
        let procs = processes(root: root)
        var kinds: [String: UInt64] = [:]
        for p in procs { kinds[p.kind, default: 0] += p.bytes }
        return ["t": Date().timeIntervalSince1970, "total": procs.reduce(UInt64(0)) { $0 + $1.bytes }, "kinds": kinds,
                "procs": procs.sorted { $0.bytes > $1.bytes }.map { ["pid": Int($0.pid), "kind": $0.kind, "label": names[$0.label] ?? $0.label, "bytes": $0.bytes] }]
    }
}

enum StorageSummary {
    // storage.json beside the catalog of boards (review/storage.py summary_path)
    static func file(catalog: URL) -> URL { catalog.deletingLastPathComponent().appendingPathComponent("storage.json") }
    static func read(catalog: URL) -> [String: Any]? {
        guard let d = try? Data(contentsOf: file(catalog: catalog)) else { return nil }
        return try? JSONSerialization.jsonObject(with: d) as? [String: Any]
    }
    // each board's size on disk by its id, for Home
    static func boardBytes(_ summary: [String: Any]?) -> [String: Double] {
        var out: [String: Double] = [:]
        for b in (summary?["boards"] as? [[String: Any]]) ?? [] {
            if let id = b["id"] as? String, let total = b["total"] as? [String: Any], let n = total["disk"] as? NSNumber { out[id.uppercased()] = n.doubleValue }
        }
        return out
    }
    // how old it is in seconds (nil: never scanned)
    static func age(_ summary: [String: Any]?, now: Date = Date()) -> Double? {
        (summary?["t"] as? NSNumber).map { now.timeIntervalSince1970 - $0.doubleValue }
    }
}
