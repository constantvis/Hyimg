import Foundation
import Darwin

@main struct NativeServerTests {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("hyimg-native-server-\(UUID())").resolvingSymlinksInPath()
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let socketFD = socket(AF_INET, SOCK_STREAM, 0)
        guard socketFD >= 0 else { throw RegistryError.invalid("socket failed") }
        var address = sockaddr_in()
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        address.sin_port = 0
        let status = withUnsafePointer(to: &address) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(socketFD, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        guard status == 0 else { close(socketFD); throw RegistryError.invalid("bind failed") }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &address) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(socketFD, $0, &length) } }
        let port = Int(UInt16(bigEndian: address.sin_port))
        close(socketFD)
        let project = Project(id: UUID(), name: "Native runtime test", libraryRoot: try ProjectRegistry.folder(root.path), stateRoot: ProjectRegistry.canonical(root.path) + "/_review", styleRefs: nil, port: port)
        let source = URL(fileURLWithPath: CommandLine.arguments[1])
        let owner = ServerSession(project: project, sourceRoot: source, logDirectory: root.appendingPathComponent("logs"))
        defer { owner.stopSynchronously() }
        func run(_ session: ServerSession, restart: Bool = false) throws -> Result<URL, Error> {
            var result: Result<URL, Error>?
            session.ensure(restart: restart) { result = $0 }
            let deadline = Date().addingTimeInterval(45)
            while result == nil && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.03)) }
            guard let result else { throw RegistryError.invalid("completion timed out") }
            return result
        }
        func health() -> ServerHealth? {
            guard let url = owner.baseURL?.appendingPathComponent("api/health") else { return nil }
            let semaphore = DispatchSemaphore(value: 0)
            var value: ServerHealth?
            var request = URLRequest(url: url)
            request.timeoutInterval = 1
            URLSession.shared.dataTask(with: request) { data, _, _ in
                value = data.flatMap { try? JSONDecoder().decode(ServerHealth.self, from: $0) }
                semaphore.signal()
            }.resume()
            _ = semaphore.wait(timeout: .now() + 2)
            return value
        }
        func require(_ condition: Bool, _ name: String) throws {
            guard condition else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        _ = try run(owner).get()
        guard let first = health() else { throw RegistryError.invalid("first health missing") }
        try require(first.matches(project), "native session launches real Python server with project identity")
        let borrower = ServerSession(project: project, sourceRoot: source, logDirectory: root.appendingPathComponent("logs"))
        _ = try run(borrower).get()
        try require(health()?.pid == first.pid, "second session reuses validated server")
        let restart = try run(borrower, restart: true)
        if case .success = restart { throw RegistryError.invalid("unowned restart incorrectly succeeded") }
        try require(health()?.pid == first.pid, "unowned restart rejected and original PID survives")
        borrower.stopSynchronously()
        try require(health()?.pid == first.pid, "stopping borrower does not terminate unowned server")
        _ = try run(owner, restart: true).get()
        guard let second = health() else { throw RegistryError.invalid("restart health missing") }
        try require(second.matches(project) && second.pid != first.pid, "owned restart launches replacement PID with same project identity")
        owner.stopSynchronously()
        let deadline = Date().addingTimeInterval(4)
        while health() != nil && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
        try require(health() == nil, "owner stop terminates only its server")
        print("NATIVE_SERVER_TESTS_PASSED")
    }
}
