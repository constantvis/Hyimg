import AppKit
import WebKit
import Darwin

@MainActor final class WebKitHarness: NSObject, WKNavigationDelegate {
    let source: URL
    let output: URL
    let storeID = UUID()
    let otherStoreID = UUID()
    var server: ServerSession?
    var window: NSWindow?
    var web: WKWebView?
    var finishedURL: URL?
    init(source: URL, output: URL) { self.source = source; self.output = output }
    func require(_ condition: Bool, _ scenario: String) throws {
        guard condition else { throw RegistryError.invalid("FAIL: \(scenario)") }
        print("PASS: \(scenario)")
        fflush(stdout)
    }
    func unusedPort() throws -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { throw RegistryError.invalid("socket failed") }
        defer { close(fd) }
        var address = sockaddr_in()
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let bound = withUnsafePointer(to: &address) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) } }
        guard bound == 0 else { throw RegistryError.invalid("bind failed") }
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &address) { $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &length) } }
        return Int(UInt16(bigEndian: address.sin_port))
    }
    func createWeb(id: UUID) -> WKWebView {
        web?.navigationDelegate = nil
        web?.removeFromSuperview()
        web = nil
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = WKWebsiteDataStore(forIdentifier: id)
        let view = WKWebView(frame: NSRect(x: 0, y: 0, width: 1280, height: 800), configuration: configuration)
        view.navigationDelegate = self
        window?.contentView = view
        web = view
        finishedURL = nil
        return view
    }
    func wait(_ condition: String, view: WKWebView, seconds: Double = 30) async throws {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if let value = try? await view.evaluateJavaScript(condition), (value as? Bool) == true { return }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw RegistryError.invalid("Timed out: \(condition)")
    }
    func snapshot(_ view: WKWebView, name: String) async throws {
        let configuration = WKSnapshotConfiguration()
        configuration.rect = view.bounds
        let image = try await view.takeSnapshot(configuration: configuration)
        guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let data = bitmap.representation(using: .png, properties: [:]) else { throw RegistryError.invalid("snapshot encoding failed") }
        try data.write(to: output.appendingPathComponent(name))
        try require(data.count > 1000, "WKWebView snapshot \(name) contains rendered pixels")
    }
    func run() async throws {
        let fm = FileManager.default
        try fm.createDirectory(at: output, withIntermediateDirectories: true)
        let library = output.appendingPathComponent("fixture-\(UUID())")
        try fm.createDirectory(at: library, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: library) }
        let image = NSImage(size: NSSize(width: 640, height: 480))
        image.lockFocus()
        NSColor.darkGray.setFill()
        NSRect(x: 0, y: 0, width: 640, height: 480).fill()
        NSColor.lightGray.setFill()
        NSRect(x: 180, y: 80, width: 280, height: 320).fill()
        image.unlockFocus()
        guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) else { throw RegistryError.invalid("fixture failed") }
        try png.write(to: library.appendingPathComponent("fixture.png"))
        let project = Project(id: storeID, name: "WebKit test", libraryRoot: try ProjectRegistry.folder(library.path), stateRoot: ProjectRegistry.canonical(library.path) + "/_review", styleRefs: nil, port: try unusedPort())
        let session = ServerSession(project: project, sourceRoot: source, logDirectory: output.appendingPathComponent("logs"))
        server = session
        let url: URL = try await withCheckedThrowingContinuation { continuation in session.ensure { continuation.resume(with: $0) } }
        let window = NSWindow(contentRect: NSRect(x: -2400, y: 0, width: 1280, height: 800), styleMask: [.titled], backing: .buffered, defer: false)
        self.window = window
        window.title = "Hyimg test harness"
        window.setFrame(NSRect(x: -2400, y: 0, width: 1280, height: 800), display: false)
        window.orderBack(nil)
        do {
        let firstView = createWeb(id: storeID)
        // the app opens projects on the canvas; this check needs the library in view, as a user gets it with one click
        firstView.configuration.userContentController.addUserScript(WKUserScript(source: "if (!localStorage.getItem('view')) localStorage.setItem('view', 'panel');", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        // a board opens with its library closed; the link asks for it (?view=panel), as the library's own links do
        var withLibrary = URLComponents(url: url, resolvingAgainstBaseURL: false)!; withLibrary.queryItems = (withLibrary.queryItems ?? []) + [URLQueryItem(name: "view", value: "panel")]
        firstView.load(URLRequest(url: withLibrary.url!))
        try await wait("document.readyState === 'complete' && typeof window.hyimgFlush === 'function' && [...document.images].some(i => i.complete && i.naturalWidth > 0 && i.getBoundingClientRect().width > 0)", view: firstView)
        try require(finishedURL?.host == "127.0.0.1" && finishedURL?.port == project.port, "didFinish reports only the expected local project origin")
        try require(true, "real reviewer HTML renders a library fixture image in WKWebView")
        try await snapshot(firstView, name: "library.png")
        _ = try await firstView.evaluateJavaScript("setView('panel')")
        try await wait("document.querySelector('#cvFrame').contentDocument?.readyState === 'complete' && typeof document.querySelector('#cvFrame').contentWindow?.hyimgFlush === 'function'", view: firstView)
        _ = try await firstView.evaluateJavaScript("const f = document.querySelector('#cvFrame'); f.contentDocument.querySelector('#bnote').click(); const t = f.contentDocument.querySelector('.note textarea'); t.value = 'NATIVE_PENDING_SAVE_SENTINEL'; t.dispatchEvent(new Event('input', {bubbles:true})); t.blur();")
        let boardFile = URL(fileURLWithPath: project.stateRoot).appendingPathComponent("boards/main.json")
        let beforeFlush = (try? String(contentsOf: boardFile, encoding: .utf8)) ?? ""
        try require(!beforeFlush.contains("NATIVE_PENDING_SAVE_SENTINEL"), "queued canvas note has not reached disk before explicit flush")
        let flush = try await firstView.callAsyncJavaScript("return await window.hyimgFlush();", arguments: [:], in: nil, contentWorld: .page)
        try require((flush as? Bool) == true, "top-level async save flush reaches initialized canvas iframe")
        let savedBoard = try Data(contentsOf: boardFile)
        try savedBoard.write(to: output.appendingPathComponent("saved-board.json"))
        try require(String(decoding: savedBoard, as: UTF8.self).contains("NATIVE_PENDING_SAVE_SENTINEL"), "awaited WKWebView flush persists queued canvas note to real board JSON")
        try await snapshot(firstView, name: "canvas.png")
        _ = try await firstView.evaluateJavaScript("localStorage.setItem('hyimg-native-test', 'persistent-sentinel')")
        }
        let second = createWeb(id: storeID)
        second.load(URLRequest(url: url))
        try await wait("document.readyState === 'complete' && typeof window.hyimgFlush === 'function'", view: second)
        let restored = try await second.evaluateJavaScript("localStorage.getItem('hyimg-native-test')")
        try require((restored as? String) == "persistent-sentinel", "same project UUID preserves localStorage when WKWebView is recreated")
        let isolated = createWeb(id: otherStoreID)
        isolated.load(URLRequest(url: url))
        try await wait("document.readyState === 'complete' && typeof window.hyimgFlush === 'function'", view: isolated)
        let isolatedValue = try await isolated.evaluateJavaScript("localStorage.getItem('hyimg-native-test') === null")
        try require((isolatedValue as? Bool) == true, "different project UUID isolates localStorage on the same origin")
        window.orderOut(nil)
        web?.navigationDelegate = nil
        web?.removeFromSuperview()
        window.contentView = nil
        web = nil
        print("NATIVE_WEBKIT_HARNESS_PASSED")
        fflush(stdout)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { finishedURL = webView.url }
}

@main struct WebKitTestMain {
    @MainActor static func main() {
        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        let harness = WebKitHarness(source: URL(fileURLWithPath: CommandLine.arguments[1]), output: URL(fileURLWithPath: CommandLine.arguments[2]))
        Task { @MainActor in
            do {
                try await harness.run()
                harness.server?.stopSynchronously()
                // Only the two synthetic stores created by this test are removed.
                for id in [harness.storeID, harness.otherStoreID] {
                    var lastError: Error?
                    for _ in 0..<20 {
                        try await Task.sleep(nanoseconds: 250_000_000)
                        let error: Error? = await withCheckedContinuation { continuation in
                            WKWebsiteDataStore.remove(forIdentifier: id) { continuation.resume(returning: $0) }
                        }
                        lastError = error
                        if error == nil { break }
                    }
                    if let lastError { throw lastError }
                }
                print("PASS: synthetic WebKit stores removed")
                exit(0)
            } catch {
                harness.server?.stopSynchronously()
                FileHandle.standardError.write(Data(("FAIL: \(error.localizedDescription)\n").utf8))
                exit(1)
            }
        }
        app.run()
    }
}
