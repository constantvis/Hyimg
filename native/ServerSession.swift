import Foundation

struct ServerHealth: Decodable {
    let app: String
    let projectId: String
    let libraryRoot: String
    let pid: Int32
    let port: Int
    func matches(_ project: Project) -> Bool {
        app == "Hyimg" && projectId == project.id.uuidString && libraryRoot == project.libraryRoot && pid > 0 && port == project.port
    }
}

final class ServerSession {
    let project: Project
    let sourceRoot: URL
    let logURL: URL
    private var process: Process?
    private let queue = DispatchQueue(label: "Hyimg.server.\(UUID().uuidString)")
    private var cancelled = false
    var baseURL: URL? { URL(string: "http://127.0.0.1:\(project.port)/") }
    // the app's settings beside its catalog of projects; a test catalog has its own
    static var settingsFile: String?
    init(project: Project, sourceRoot: URL, logDirectory: URL? = nil) {
        self.project = project
        self.sourceRoot = sourceRoot
        let directory = logDirectory ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Hyimg")
        logURL = directory.appendingPathComponent("\(project.id.uuidString).log")
    }
    private func health() -> (ServerHealth?, Bool) {
        guard let url = baseURL?.appendingPathComponent("api/health") else { return (nil, false) }
        var request = URLRequest(url: url)
        request.timeoutInterval = 0.7
        let semaphore = DispatchSemaphore(value: 0)
        final class ResultBox: @unchecked Sendable { var value: (ServerHealth?, Bool) = (nil, false) }
        let box = ResultBox()
        let task = URLSession.shared.dataTask(with: request) { data, response, _ in
            box.value = (data.flatMap { try? JSONDecoder().decode(ServerHealth.self, from: $0) }, response != nil)
            semaphore.signal()
        }
        task.resume()
        if semaphore.wait(timeout: .now() + 1.0) == .timedOut { task.cancel(); return (nil, false) }
        return box.value
    }
    private func python() throws -> URL { try Self.findPython(sourceRoot: sourceRoot) }
    // the Python 3.10+ with Pillow the servers run on; found once (each probe starts a Python), shared with Settings › Storage
    private static var foundPython: URL?
    private static let pythonLock = NSLock()
    static func findPython(sourceRoot: URL) throws -> URL {
        pythonLock.lock(); defer { pythonLock.unlock() }
        if let found = foundPython, FileManager.default.isExecutableFile(atPath: found.path) { return found }
        let fm = FileManager.default
        var candidates: [String] = []
        if let override = ProcessInfo.processInfo.environment["HYIMG_PYTHON"], !override.isEmpty { candidates.append(override) }
        candidates += [sourceRoot.appendingPathComponent(".venv/bin/python3").path,
                       "/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
        let versions = "/Library/Frameworks/Python.framework/Versions"
        if let entries = try? fm.contentsOfDirectory(atPath: versions) {
            candidates += entries.sorted { $0.localizedStandardCompare($1) == .orderedDescending }.map { "\(versions)/\($0)/bin/python3" }
        }
        candidates += (ProcessInfo.processInfo.environment["PATH"] ?? "").split(separator: ":").map { "\($0)/python3" }
        candidates.append("/usr/bin/python3")
        for candidate in candidates where fm.isExecutableFile(atPath: candidate) {
            let probe = Process()
            probe.executableURL = URL(fileURLWithPath: candidate)
            probe.arguments = ["-c", "import sys; import PIL; sys.exit(0 if sys.version_info >= (3, 10) else 1)"]
            probe.standardOutput = FileHandle.nullDevice
            probe.standardError = FileHandle.nullDevice
            do { try probe.run(); probe.waitUntilExit(); if probe.terminationStatus == 0 { foundPython = URL(fileURLWithPath: candidate); return foundPython! } } catch { continue }
        }
        throw RegistryError.invalid(L("Python 3.10+ with Pillow not found. In Terminal run python3 -m pip install Pillow for your Python 3.10+, or install Pillow into the .venv of the Hyimg folder. Then open the board again."))
    }
    func ensure(restart: Bool = false, completion: @escaping (Result<URL, Error>) -> Void) {
        queue.async {
            do {
                guard !self.cancelled else { return }
                guard let base = self.baseURL else { throw RegistryError.invalid(L("Invalid board address.")) }
                if restart {
                    guard let owned = self.process, owned.isRunning else {
                        let (existing, _) = self.health()
                        if existing?.matches(self.project) == true {
                            throw RegistryError.invalid(L("The server was started by another process. Hyimg will not stop it. Quit it in the app that started it."))
                        }
                        try self.startAndWait(base: base)
                        DispatchQueue.main.async { completion(.success(base)) }
                        return
                    }
                    owned.terminate()
                    owned.waitUntilExit()
                    self.process = nil
                }
                let (existing, responds) = self.health()
                if existing?.matches(self.project) == true {
                    if let owned = self.process, owned.isRunning, existing?.pid != owned.processIdentifier {
                        throw RegistryError.invalid(L("Another process answers on the board's port. Restart canceled."))
                    }
                } else {
                    if responds { throw RegistryError.invalid(L("Port %ld is in use by another server. Free the port and open the board again.", self.project.port)) }
                    try self.startAndWait(base: base)
                }
                guard !self.cancelled else { return }
                DispatchQueue.main.async { completion(.success(base)) }
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }
    private func startAndWait(base: URL) throws {
        _ = try ProjectRegistry.folder(project.libraryRoot)
        let script = sourceRoot.appendingPathComponent("review/server.py")
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw RegistryError.invalid(L("%@ not found. Rebuild Hyimg from the current source folder.", script.path))
        }
        let executable = try python()
        let task = Process()
        task.executableURL = executable
        task.arguments = [script.path, String(project.port)]
        task.currentDirectoryURL = sourceRoot
        var environment = ProcessInfo.processInfo.environment
        environment["HYIMG_LIBRARY_ROOT"] = project.libraryRoot
        environment["HYIMG_STATE_ROOT"] = project.stateRoot
        environment["HYIMG_PROJECT_ID"] = project.id.uuidString
        environment["HYIMG_SETTINGS"] = ServerSession.settingsFile   // one file of settings for every project (owner 2026-10-04)
        environment["PYTHONUNBUFFERED"] = "1"
        environment["HYIMG_PARENT_PID"] = String(ProcessInfo.processInfo.processIdentifier)
        environment["HYIMG_STYLE_REFS"] = project.styleRefs
        environment["HYIMG_COMPAT_PORT"] = project.compatibilityPort.map(String.init)
        task.environment = environment
        try FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        let log = try FileHandle(forWritingTo: logURL)
        try log.seekToEnd()
        task.standardOutput = log
        task.standardError = log
        try task.run()
        process = task
        for _ in 0..<100 {
            if cancelled { task.terminate(); throw RegistryError.invalid(L("Start canceled.")) }
            let (result, _) = health()
            if let result, result.matches(project), result.pid == task.processIdentifier { return }
            if !task.isRunning { throw RegistryError.invalid(L("The server exited with code %ld. Log: %@", Int(task.terminationStatus), logURL.path)) }
            Thread.sleep(forTimeInterval: 0.2)
        }
        task.terminate()
        throw RegistryError.invalid(L("The server did not confirm the board within 30 seconds. Log: %@", logURL.path))
    }
    func stop() {
        queue.async {
            self.cancelled = true
            if let process = self.process, process.isRunning { process.terminate() }
            self.process = nil
        }
    }
    func stopSynchronously() {
        queue.sync {
            self.cancelled = true
            if let process = self.process, process.isRunning { process.terminate() }
            self.process = nil
        }
    }
}
