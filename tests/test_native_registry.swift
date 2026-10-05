import Foundation

@main struct RegistryTests {
    static func main() throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("hyimg-registry-test-\(UUID())")
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: root) }
        let file = root.appendingPathComponent("config/projects.json")
        let registry = try ProjectRegistry(file: file)
        func folder(_ name: String) throws -> URL {
            let url = root.appendingPathComponent(name)
            try fm.createDirectory(at: url, withIntermediateDirectories: true)
            return url
        }
        func require(_ value: Bool, _ name: String) throws {
            guard value else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        let first = try folder("first")
        let second = try folder("second")
        try Data("original-asset".utf8).write(to: first.appendingPathComponent("asset.jpg"))
        let a = try registry.register(path: first.path, name: "First", styleRefs: nil)
        let b = try registry.register(path: second.path, name: "Second", styleRefs: nil, compatibilityPort: 4190)
        try require(b.compatibilityPort == 4190, "compatibility listener recorded separately from assigned port")
        try require(a.id != b.id && a.port != b.port, "different project UUIDs and ports")
        let duplicate = try registry.register(path: first.path + "/../first", name: "Other", styleRefs: nil)
        try require(duplicate == a && registry.projects.count == 2, "canonical path duplicate returns existing project")
        let symlink = root.appendingPathComponent("alias")
        try fm.createSymbolicLink(at: symlink, withDestinationURL: first)
        let alias = try registry.register(path: symlink.path, name: nil, styleRefs: nil)
        try require(alias.id == a.id, "symlink path cannot duplicate a project")
        try registry.rename(id: a.id, name: "Renamed")
        let loaded = try ProjectRegistry(file: file)
        try require(loaded.projects[0].id == a.id && loaded.projects[0].port == a.port && loaded.projects[0].name == "Renamed", "rename persists and preserves identity and port")
        try require(try String(contentsOf: first.appendingPathComponent("asset.jpg"), encoding: .utf8) == "original-asset", "rename leaves asset bytes intact")
        let state = first.appendingPathComponent("_review")
        try fm.createDirectory(at: state, withIntermediateDirectories: false)
        let stateFile = state.appendingPathComponent("ratings.json")
        try Data("{\"rating\":5}".utf8).write(to: stateFile)
        let replacement = try folder("replacement")
        try registry.relink(id: a.id, path: replacement.path)
        let relinked = try ProjectRegistry(file: file).projects[0]
        try require(relinked.id == a.id && relinked.port == a.port && relinked.stateRoot == ProjectRegistry.canonical(state.path) && relinked.libraryRoot == ProjectRegistry.canonical(replacement.path), "relink retains original available state directory and project identity")
        try require(try String(contentsOf: stateFile, encoding: .utf8) == "{\"rating\":5}", "relink preserves rating bytes")
        let beforeInvalid = try Data(contentsOf: file)
        var rejected = false
        do { try registry.relink(id: a.id, path: second.path) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "duplicate relink rejected without changing catalog")
        rejected = false
        do { try registry.rename(id: a.id, name: "  ") } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "blank rename rejected without changing catalog")
        rejected = false
        do { _ = try registry.register(path: folder("extra-compat").path, name: nil, styleRefs: nil, compatibilityPort: 4190) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "compatibility port cannot be assigned twice")
        rejected = false
        do { _ = try registry.register(path: root.appendingPathComponent("missing").path, name: nil, styleRefs: nil) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "missing folder rejected without catalog changes")
        let child = second.appendingPathComponent("child")
        try fm.createDirectory(at: child, withIntermediateDirectories: true)
        rejected = false
        do { _ = try registry.register(path: child.path, name: nil, styleRefs: nil) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "child library rejected without catalog changes")
        rejected = false
        do { _ = try registry.register(path: root.path, name: nil, styleRefs: nil) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "parent library rejected without catalog changes")
        rejected = false
        do { try registry.relink(id: a.id, path: child.path) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeInvalid, "relink into another library rejected without catalog changes")
        let refs = try folder("shared-refs")
        let refsOwner = try folder("refs-owner")
        _ = try registry.register(path: refsOwner.path, name: nil, styleRefs: refs.path)
        let beforeRefs = try Data(contentsOf: file)
        rejected = false
        do { _ = try registry.register(path: refs.path, name: nil, styleRefs: nil) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == beforeRefs, "library inside existing reference mount rejected")
        let blockingFile = root.appendingPathComponent("not-a-directory")
        try Data("keep".utf8).write(to: blockingFile)
        let blockedRegistry = try ProjectRegistry(file: blockingFile.appendingPathComponent("projects.json"))
        rejected = false
        do { _ = try blockedRegistry.register(path: first.path, name: nil, styleRefs: nil) } catch { rejected = true }
        try require(rejected && blockedRegistry.projects.isEmpty, "failed atomic save leaves in-memory registry unchanged")
        for index in 0..<14 { _ = try registry.register(path: folder("port-\(index)").path, name: nil, styleRefs: nil) }
        try require(!registry.projects.contains(where: { $0.port == 4190 }) && Set(registry.projects.map(\.port)).count == registry.projects.count, "port allocation skips original server 4190")
        let moved = root.appendingPathComponent("moved")
        try fm.moveItem(at: first, to: moved)
        try registry.relink(id: a.id, path: moved.path)
        try require(registry.projects[0].stateRoot == ProjectRegistry.canonical(moved.appendingPathComponent("_review").path), "moved folder restores state path from its existing _review")
        let health = ServerHealth(app: "Hyimg", projectId: a.id.uuidString, libraryRoot: a.libraryRoot, pid: 123, port: a.port)
        try require(health.matches(a) && !health.matches(b), "health validates matching project identity")
        try require(!ServerHealth(app: "Other", projectId: a.id.uuidString, libraryRoot: a.libraryRoot, pid: 123, port: a.port).matches(a), "health rejects other app")
        try require(!ServerHealth(app: "Hyimg", projectId: a.id.uuidString, libraryRoot: a.libraryRoot, pid: 0, port: a.port).matches(a), "health rejects invalid PID")
        try require(!ServerHealth(app: "Hyimg", projectId: a.id.uuidString, libraryRoot: a.libraryRoot, pid: 123, port: 9999).matches(a), "health rejects wrong port")
        try require(!ServerHealth(app: "Hyimg", projectId: a.id.uuidString, libraryRoot: second.path, pid: 123, port: a.port).matches(a), "health rejects wrong library")
        let savedCatalog = try Data(contentsOf: file)
        let overlapping = Project(id: UUID(), name: "Bad parent", libraryRoot: root.path, stateRoot: root.appendingPathComponent("_review").path, styleRefs: nil, port: 62000)
        let badCatalog = try JSONEncoder().encode(registry.projects + [overlapping])
        try badCatalog.write(to: file)
        rejected = false
        do { _ = try ProjectRegistry(file: file) } catch { rejected = true }
        try require(rejected && Data(contentsOf: file) == badCatalog, "persisted overlapping catalog rejected without overwrite")
        try savedCatalog.write(to: file)
        try Data("not-json".utf8).write(to: file)
        rejected = false
        do { _ = try ProjectRegistry(file: file) } catch { rejected = true }
        try require(rejected && String(contentsOf: file, encoding: .utf8) == "not-json", "corrupt catalog fails without overwriting source")
        print("NATIVE_REGISTRY_TESTS_PASSED")
    }
}
