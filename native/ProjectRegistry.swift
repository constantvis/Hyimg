import Foundation
import Darwin

struct Project: Codable, Equatable, Identifiable {
    let id: UUID
    var name: String
    var libraryRoot: String
    var stateRoot: String
    var styleRefs: String?
    let port: Int
    var compatibilityPort: Int? = nil
}

enum RegistryError: LocalizedError {
    case invalid(String)
    var errorDescription: String? {
        switch self { case .invalid(let message): return message }
    }
}

final class ProjectRegistry {
    let file: URL
    private(set) var projects: [Project]
    init(file: URL) throws {
        self.file = file
        if FileManager.default.fileExists(atPath: file.path) {
            projects = try JSONDecoder().decode([Project].self, from: Data(contentsOf: file))
            guard Set(projects.map(\.id)).count == projects.count,
                  Set(projects.map(\.port)).count == projects.count,
                  Set(projects.map(\.libraryRoot)).count == projects.count,
                  projects.allSatisfy({ $0.port >= 4180 && $0.port <= 65535 && $0.port != 4190 }) else {
                throw RegistryError.invalid("Каталог поврежден: повторные доски или недопустимые порты. Файл сохранен без изменений.")
            }
        } else { projects = [] }
        try Self.validateIsolation(projects)
    }
    static func canonical(_ path: String) -> String {
        if let resolved = realpath(path, nil) {
            defer { free(resolved) }
            return String(cString: resolved)
        }
        return URL(fileURLWithPath: path).standardizedFileURL.resolvingSymlinksInPath().path
    }
    static func validateIsolation(_ projects: [Project]) throws {
        func overlaps(_ first: String, _ second: String) -> Bool {
            let a = canonical(first), b = canonical(second)
            return a == b || a.hasPrefix(b == "/" ? b : b + "/") || b.hasPrefix(a == "/" ? a : a + "/")
        }
        for (index, project) in projects.enumerated() {
            guard project.libraryRoot.hasPrefix("/"), project.stateRoot.hasPrefix("/"), project.compatibilityPort == nil || project.compatibilityPort == 4190 else {
                throw RegistryError.invalid("Каталог содержит недопустимый путь или порт.")
            }
            for other in projects.dropFirst(index + 1) {
                let projectWrites = [project.libraryRoot, project.stateRoot]
                let otherWrites = [other.libraryRoot, other.stateRoot]
                let conflict = projectWrites.contains { a in
                    (otherWrites + [other.styleRefs].compactMap { $0 }).contains { overlaps(a, $0) }
                } || otherWrites.contains { a in project.styleRefs.map { overlaps(a, $0) } ?? false }
                guard !conflict else { throw RegistryError.invalid("Папки досок «\(project.name)» и «\(other.name)» пересекаются. Выберите отдельную папку вне библиотеки, данных и эталонов другого проекта.") }
                guard project.compatibilityPort == nil || project.compatibilityPort != other.compatibilityPort else {
                    throw RegistryError.invalid("Дополнительный порт закреплен за несколькими досками.")
                }
            }
        }
    }
    static func folder(_ path: String) throws -> String {
        let url = URL(fileURLWithPath: path).standardizedFileURL.resolvingSymlinksInPath()
        var directory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &directory), directory.boolValue else {
            throw RegistryError.invalid("Папка недоступна: \(url.path)")
        }
        return canonical(url.path)
    }
    private func save(_ updated: [Project]) throws {
        try Self.validateIsolation(updated)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(updated)
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: file, options: .atomic)
        projects = updated
    }
    @discardableResult func register(path: String, name: String?, styleRefs: String?, compatibilityPort: Int? = nil) throws -> Project {
        let root = try Self.folder(path)
        if let existing = projects.first(where: { $0.libraryRoot == root }) { return existing }
        let title = (name ?? URL(fileURLWithPath: root).lastPathComponent).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { throw RegistryError.invalid("Введите название доски.") }
        guard compatibilityPort == nil || compatibilityPort == 4190 else { throw RegistryError.invalid("Дополнительный порт должен быть 4190.") }
        guard compatibilityPort == nil || !projects.contains(where: { $0.compatibilityPort == compatibilityPort }) else { throw RegistryError.invalid("Дополнительный порт уже закреплен за доской.") }
        let refs = try styleRefs.map(Self.folder)
        let used = Set(projects.map(\.port))
        guard let port = (4180...65535).first(where: { $0 != 4190 && !used.contains($0) }) else {
            throw RegistryError.invalid("Нет свободного номера порта в каталоге.")
        }
        let project = Project(id: UUID(), name: title, libraryRoot: root,
                              stateRoot: URL(fileURLWithPath: root).appendingPathComponent("_review").path,
                              styleRefs: refs, port: port, compatibilityPort: compatibilityPort)
        try save(projects + [project])
        return project
    }
    func rename(id: UUID, name: String) throws {
        let title = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { throw RegistryError.invalid("Введите название доски.") }
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid("Доска не найдена.") }
        updated[index].name = title
        try save(updated)
    }
    func relink(id: UUID, path: String) throws {
        let root = try Self.folder(path)
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid("Доска не найдена.") }
        guard !updated.contains(where: { $0.id != id && $0.libraryRoot == root }) else {
            throw RegistryError.invalid("Эта папка уже связана с другой доской.")
        }
        let old = updated[index]
        if old.libraryRoot == root { return }
        let replacementState = URL(fileURLWithPath: root).appendingPathComponent("_review").path
        // Relinking changes only catalog pointers. Existing state is never copied or deleted.
        if FileManager.default.fileExists(atPath: old.stateRoot) {
            updated[index].stateRoot = old.stateRoot
        } else if FileManager.default.fileExists(atPath: replacementState) {
            updated[index].stateRoot = replacementState
        } else {
            throw RegistryError.invalid("В новой папке нет _review, а прежняя папка данных недоступна. Выберите папку с сохраненными данными доски или добавьте ее как новую доску.")
        }
        updated[index].libraryRoot = root
        try save(updated)
    }
}
