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
    // the board's id in its own folder (<state>/board.json, BoardIdentity.swift), shared by every Mac that syncs the folder; id stays
    // this catalog's own (tabs, web data, caches are keyed by it). nil until the board is first opened here
    var folderId: UUID? = nil
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
                throw RegistryError.invalid(L("The catalog is damaged: duplicate boards or invalid ports. The file was left unchanged."))
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
                throw RegistryError.invalid(L("The catalog has an invalid path or port."))
            }
            for other in projects.dropFirst(index + 1) {
                let projectWrites = [project.libraryRoot, project.stateRoot]
                let otherWrites = [other.libraryRoot, other.stateRoot]
                let conflict = projectWrites.contains { a in
                    (otherWrites + [other.styleRefs].compactMap { $0 }).contains { overlaps(a, $0) }
                } || otherWrites.contains { a in project.styleRefs.map { overlaps(a, $0) } ?? false }
                guard !conflict else { throw RegistryError.invalid(L("The folders of “%@” and “%@” overlap. Choose a separate folder outside another project's library, data and references.", project.name, other.name)) }
                guard project.compatibilityPort == nil || project.compatibilityPort != other.compatibilityPort else {
                    throw RegistryError.invalid(L("The extra port is assigned to more than one board."))
                }
            }
        }
    }
    static func folder(_ path: String) throws -> String {
        let url = URL(fileURLWithPath: path).standardizedFileURL.resolvingSymlinksInPath()
        var directory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &directory), directory.boolValue else {
            throw RegistryError.invalid(L("Folder not available: %@", url.path))
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
        guard !title.isEmpty else { throw RegistryError.invalid(L("Enter a board name.")) }
        guard compatibilityPort == nil || compatibilityPort == 4190 else { throw RegistryError.invalid(L("The extra port must be 4190.")) }
        guard compatibilityPort == nil || !projects.contains(where: { $0.compatibilityPort == compatibilityPort }) else { throw RegistryError.invalid(L("The extra port is already assigned to a board.")) }
        let refs = try styleRefs.map(Self.folder)
        let used = Set(projects.map(\.port))
        guard let port = (4180...65535).first(where: { $0 != 4190 && !used.contains($0) }) else {
            throw RegistryError.invalid(L("No free port number left in the catalog."))
        }
        let state = URL(fileURLWithPath: root).appendingPathComponent("_review").path
        // a folder that already carries its id (another Mac made it, Dropbox brought it): the catalog takes that id as its own, so the
        // other Mac's links name this board here too; an id this catalog already uses for another board is not taken twice
        let folderID = BoardFolder.read(state)?.id
        let taken = folderID.map { f in projects.contains { $0.id == f || $0.folderId == f || BoardFolder.read($0.stateRoot)?.id == f } } ?? true
        var project = Project(id: taken ? UUID() : folderID!, name: title, libraryRoot: root, stateRoot: state,
                              styleRefs: refs, port: port, compatibilityPort: compatibilityPort)
        if !taken { project.folderId = folderID }
        try save(projects + [project])
        return project
    }
    // the board's folder id, once it is known (App.ensureFolderID): the catalog maps its own id to it
    func setFolderID(id: UUID, folderId: UUID) throws {
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid(L("Board not found.")) }
        guard updated[index].folderId != folderId else { return }
        updated[index].folderId = folderId
        try save(updated)
    }
    func rename(id: UUID, name: String) throws {
        let title = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { throw RegistryError.invalid(L("Enter a board name.")) }
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid(L("Board not found.")) }
        updated[index].name = title
        try save(updated)
    }
    // off the catalog only: the folder, its pictures and its _review stay where they are (adding the folder again brings the board back)
    func remove(id: UUID) throws {
        guard projects.contains(where: { $0.id == id }) else { throw RegistryError.invalid(L("Board not found.")) }
        try save(projects.filter { $0.id != id })
    }
    func relink(id: UUID, path: String) throws {
        let root = try Self.folder(path)
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid(L("Board not found.")) }
        guard !updated.contains(where: { $0.id != id && $0.libraryRoot == root }) else {
            throw RegistryError.invalid(L("This folder is already linked to another board."))
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
            throw RegistryError.invalid(L("The new folder has no _review and the previous data folder is not available. Choose a folder with the board's saved data or add it as a new board."))
        }
        updated[index].libraryRoot = root
        try save(updated)
    }
    // a board's folder moved into the shared or the private folder (People.swift moveBoard, review/places.py): the catalog follows.
    // checkRelocate says beforehand whether the new place would overlap another board, so nothing moves that the catalog would refuse
    func checkRelocate(id: UUID, libraryRoot: String, stateRoot: String) throws { _ = try relocated(id: id, libraryRoot: libraryRoot, stateRoot: stateRoot) }
    func relocate(id: UUID, libraryRoot: String, stateRoot: String) throws { try save(relocated(id: id, libraryRoot: libraryRoot, stateRoot: stateRoot)) }
    private func relocated(id: UUID, libraryRoot: String, stateRoot: String) throws -> [Project] {
        var updated = projects
        guard let index = updated.firstIndex(where: { $0.id == id }) else { throw RegistryError.invalid(L("Board not found.")) }
        guard libraryRoot.hasPrefix("/"), stateRoot.hasPrefix("/"), !updated.contains(where: { $0.id != id && $0.libraryRoot == libraryRoot }) else {
            throw RegistryError.invalid(L("This folder is already linked to another board."))
        }
        updated[index].libraryRoot = libraryRoot; updated[index].stateRoot = stateRoot
        try Self.validateIsolation(updated)
        return updated
    }
}

// A board's id in its own folder (owner 2026-10-08: he and his partner use two Macs signed into one Dropbox account; every board folder
// syncs to both, each Mac's catalog gives it its own UUID). <state>/board.json {"id", "name", "created"} is written once, when the
// board is first opened on any Mac, and never rewritten; both Macs read it and hyimg:// links carry its id (review/boardid.py reads the
// same file for the server). Two Macs writing it before Dropbox synced leave «board (… conflicted copy …).json» beside it: its id
// still names the board (ids).
enum BoardFolder {
    static let file = "board.json"
    static func read(_ stateRoot: String) -> (id: UUID, name: String)? {
        read(URL(fileURLWithPath: stateRoot).appendingPathComponent(file))
    }
    static func read(_ url: URL) -> (id: UUID, name: String)? {
        guard let d = try? Data(contentsOf: url), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let id = (j["id"] as? String).flatMap(UUID.init) else { return nil }
        return (id, (j["name"] as? String) ?? "")
    }
    // board.json's id first, then the ids of its conflicted copies
    static func ids(_ stateRoot: String) -> [UUID] {
        var out = read(stateRoot).map { [$0.id] } ?? []
        let names = ((try? FileManager.default.contentsOfDirectory(atPath: stateRoot)) ?? []).filter { $0.hasPrefix("board (") && $0.hasSuffix(").json") }
        for n in names.sorted() {
            if let id = read(URL(fileURLWithPath: stateRoot).appendingPathComponent(n))?.id, !out.contains(id) { out.append(id) }
        }
        return out
    }
    // the folder's id: the one already there, else `id` written now (a board's first open). The state folder is made when its parent
    // is there (a new board's _review, which its server would make anyway). nil: nothing there and nothing could be written
    @discardableResult static func ensure(stateRoot: String, id: UUID, name: String) -> UUID? {
        if let existing = read(stateRoot) { return existing.id }
        let dir = URL(fileURLWithPath: stateRoot), fm = FileManager.default
        guard fm.fileExists(atPath: dir.deletingLastPathComponent().path) else { return nil }
        let created = ISO8601DateFormatter().string(from: Date())
        guard (try? fm.createDirectory(at: dir, withIntermediateDirectories: true)) != nil,
              let data = try? JSONSerialization.data(withJSONObject: ["id": id.uuidString.lowercased(), "name": name, "created": created], options: [.prettyPrinted, .sortedKeys]),
              (try? data.write(to: dir.appendingPathComponent(file), options: .atomic)) != nil else { return nil }
        return id
    }
}

// What happened on a board without the owner (owner 2026-10-06: «on Home show how many new events happened on each board without
// him»): the events a board's server writes (review/events.py: <stateRoot>/boards/_events/<page>.jsonl, one JSON line per event,
// newest last) are read here straight from the files, so a closed board needs no server and Home never starts one. Only the pages
// whose log changed after the owner last saw the board are opened, each from its end back to its first older line (a busy page's
// log is a few MB; the new part is its last lines). What the owner did himself (who "owner") does not count: agents, the AI and
// other sessions do. The result is per page, kind and author, Home words it (review/home.html newsText).
// With two people sharing a board (owner 2026-10-07) an event's by.person says whose it is: another person's own edits («owner» on his
// Mac) are news here too; rows carry that person's id as u, Home names him from the address book (ui/people.js newsWho).
enum BoardNews {
    static var me: String?   // this Mac's profile id (People.home); nil: no profile, every app edit counts as one's own as before
    static let chunk = 64 * 1024
    static let cap = 5000   // events read per page at most: Home shows «99+» long before that
    // the events of one log newer than since, newest first
    static func newer(_ file: URL, since: Double) -> [[String: Any]] {
        guard let h = try? FileHandle(forReadingFrom: file) else { return [] }
        defer { try? h.close() }
        var end = (try? h.seekToEnd()) ?? 0, carry = Data(), out: [[String: Any]] = []
        while end > 0 {
            let start = end > UInt64(chunk) ? end - UInt64(chunk) : 0
            guard (try? h.seek(toOffset: start)) != nil, let data = try? h.read(upToCount: Int(end - start)) else { break }
            var parts = (data + carry).split(separator: 0x0a, omittingEmptySubsequences: false)
            carry = start > 0 && !parts.isEmpty ? Data(parts.removeFirst()) : Data()   // a line begun in the chunk before waits for it
            for line in parts.reversed() where !line.isEmpty {
                guard let e = try? JSONSerialization.jsonObject(with: Data(line)) as? [String: Any] else { continue }
                if ((e["ts"] as? Double) ?? 0) <= since { return out }
                out.append(e)
                if out.count >= cap { return out }
            }
            end = start
        }
        return out
    }
    // the pages a board lists (boards/pages.json, in their order) with their names; none listed: its first page "main" (server.py load_pages)
    static func pages(_ stateRoot: String) -> [(id: String, title: String)] {
        let f = URL(fileURLWithPath: stateRoot).appendingPathComponent("boards/pages.json")
        guard let d = try? Data(contentsOf: f), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let list = j["pages"] as? [[String: Any]], !list.isEmpty else { return [("main", "")] }
        return list.compactMap { p in (p["id"] as? String).map { ($0, p["title"] as? String ?? "") } }
    }
    // {n: events, t: the newest one's time, since: the last look, rows: [{p: page name, k: kind, w: author, n: events, c: pictures}]}, or nil when nothing is new.
    // c counts pictures where an event has them: added, removed, moved; for a new group the pictures added with it (events.py "new").
    static func summary(stateRoot: String, since: Double) -> [String: Any]? {
        let dir = URL(fileURLWithPath: stateRoot).appendingPathComponent("boards/_events")
        guard let files = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: [.contentModificationDateKey]) else { return nil }
        let changed = files.filter { f in
            f.pathExtension == "jsonl" && ((try? f.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate?.timeIntervalSince1970) ?? 0) > since
        }
        if changed.isEmpty { return nil }
        let listed = pages(stateRoot), order = Dictionary(listed.enumerated().map { ($1.id, $0) }, uniquingKeysWith: { a, _ in a })
        var rows: [String: [String: Any]] = [:], n = 0, last = 0.0
        for f in changed {
            let page = f.deletingPathExtension().lastPathComponent
            guard let k = order[page] else { continue }   // a deleted page's log stays behind; its news is gone with it
            for e in newer(f, since: since) {
                let who = e["who"] as? String ?? "", person = ((e["by"] as? [String: Any])?["person"] as? String)?.lowercased() ?? ""
                let mine = person.isEmpty || person == me?.lowercased()
                if (who == "owner" || who.isEmpty) && mine { continue }
                let agent = (e["agent"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? who
                let kind = e["kind"] as? String ?? "", key = "\(page)\u{1}\(kind)\u{1}\(agent)\u{1}\(person)"
                let pics = kind == "group" ? (e["new"] as? Int ?? 0) : ["add", "remove", "move"].contains(kind) ? (e["count"] as? Int ?? 0) : 0
                var r = rows[key] ?? ["p": listed[k].title, "pid": page, "o": k, "k": kind, "w": agent, "n": 0, "c": 0]
                if !person.isEmpty { r["u"] = person }
                r["n"] = (r["n"] as? Int ?? 0) + 1; r["c"] = (r["c"] as? Int ?? 0) + pics
                rows[key] = r; n += 1; last = max(last, (e["ts"] as? Double) ?? 0)
            }
        }
        if n == 0 { return nil }
        let sorted = rows.values.sorted { a, b in
            let oa = a["o"] as? Int ?? 0, ob = b["o"] as? Int ?? 0
            return oa != ob ? oa < ob : (a["n"] as? Int ?? 0) > (b["n"] as? Int ?? 0)
        }
        return ["n": n, "t": last, "since": since, "rows": sorted]   // since: Home's bell tells the news from the bell rows of that time on
    }
}

// When the owner last saw each board (seen.json beside projects.json and home.json, {board id: seconds since 1970}): the app writes it
// when a board comes to the front and when it leaves the front, so what agents did while he looked at it is not news. It is the
// owner's reading state of this Mac's app, like home.json, not the board's data: the state root is the board server's alone (one
// writer per state root), may be synced to other Macs, and a test catalog (--catalog) gets its own file with nothing else to do.
enum BoardSeen {
    static func read(_ file: URL) -> [String: Double] {
        guard let d = try? Data(contentsOf: file), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [:] }
        return j.compactMapValues { ($0 as? NSNumber)?.doubleValue }
    }
    static func write(_ file: URL, _ seen: [String: Double]) {
        guard let data = try? JSONSerialization.data(withJSONObject: seen, options: [.prettyPrinted, .sortedKeys]) else { return }
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: file, options: .atomic)
    }
    static func mark(_ file: URL, _ ids: [UUID], at t: Double = Date().timeIntervalSince1970) {
        guard !ids.isEmpty else { return }
        var seen = read(file); ids.forEach { seen[$0.uuidString] = t }; write(file, seen)
    }
}

// The app's own words in English or Russian (owner 2026-10-06: «make 2 versions, Russian and English, switchable in settings»).
// The English text is the key, as in review/ui/i18n.js: L("Close Tab") is «Close Tab» | «Закрыть вкладку». A name or a number goes
// in through String(format:): L("Opening “%@”", name), L("Port %ld …", port). A context before «::» when one English word needs
// another Russian one (L("confirm::OK") shows «OK» | «Да»). Adding a string: write L("English") in the code and add the pair to
// Lang.ru below; a key missing there shows its English in Russian too. The language is the app's setting cv.lang in settings.json
// (App.syncLang keeps Lang.current in step with it); this file is compiled into the app and every native test, so all can use it.
enum Lang {
    static var current = "en"
    static func pick(_ v: String?) -> String { v == "ru" ? "ru" : "en" }
    // the setting from the app's settings file (absent or unreadable: English)
    static func read(settings file: URL) -> String {
        guard let d = try? Data(contentsOf: file), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return "en" }
        return pick(j["cv.lang"] as? String)
    }
    static let ru: [String: String] = [
        "The catalog is damaged: duplicate boards or invalid ports. The file was left unchanged.": "Каталог поврежден: повторные доски или недопустимые порты. Файл сохранен без изменений.",
        "The catalog has an invalid path or port.": "Каталог содержит недопустимый путь или порт.",
        "The folders of “%@” and “%@” overlap. Choose a separate folder outside another project's library, data and references.": "Папки досок «%@» и «%@» пересекаются. Выберите отдельную папку вне библиотеки, данных и эталонов другого проекта.",
        "The extra port is assigned to more than one board.": "Дополнительный порт закреплен за несколькими досками.",
        "Folder not available: %@": "Папка недоступна: %@",
        "Enter a board name.": "Введите название доски.",
        "The extra port must be 4190.": "Дополнительный порт должен быть 4190.",
        "The extra port is already assigned to a board.": "Дополнительный порт уже закреплен за доской.",
        "No free port number left in the catalog.": "Нет свободного номера порта в каталоге.",
        "Board not found.": "Доска не найдена.",
        "This folder is already linked to another board.": "Эта папка уже связана с другой доской.",
        "The new folder has no _review and the previous data folder is not available. Choose a folder with the board's saved data or add it as a new board.": "В новой папке нет _review, а прежняя папка данных недоступна. Выберите папку с сохраненными данными доски или добавьте ее как новую доску.",
        "Python 3.10+ with Pillow not found. In Terminal run python3 -m pip install Pillow for your Python 3.10+, or install Pillow into the .venv of the Hyimg folder. Then open the board again.": "Не найден Python 3.10+ с Pillow. В Terminal выполните python3 -m pip install Pillow для вашего Python 3.10+ или установите Pillow в .venv папки Hyimg. Затем откройте доску снова.",
        "Invalid board address.": "Некорректный адрес доски.",
        "The server was started by another process. Hyimg will not stop it. Quit it in the app that started it.": "Сервер запущен другим процессом. Hyimg не будет его останавливать. Завершите его в приложении, которое его запустило.",
        "Another process answers on the board's port. Restart canceled.": "Порт доски отвечает от другого процесса. Перезапуск отменен.",
        "Port %ld is in use by another server. Free the port and open the board again.": "Порт %ld занят другим сервером. Освободите порт и повторите открытие доски.",
        "%@ not found. Rebuild Hyimg from the current source folder.": "Не найден %@. Пересоберите Hyimg из текущей папки исходников.",
        "Start canceled.": "Запуск отменен.",
        "The server exited with code %ld. Log: %@": "Сервер завершился с кодом %ld. Лог: %@",
        "The server did not confirm the board within 30 seconds. Log: %@": "Сервер не подтвердил доску за 30 секунд. Лог: %@",
        "The page is still loading. Wait for the board to open and try again.": "Страница еще загружается. Дождитесь открытия доски и повторите действие.",
        "The page did not confirm saving within 15 seconds. Check the connection to the server and try again.": "Страница не подтвердила сохранение за 15 секунд. Проверьте соединение с сервером и повторите действие.",
        "The page could not save the changes. The action was canceled, the board stays open.": "Страница не смогла сохранить изменения. Действие отменено, доска остается открытой.",
        "Home · ⌘⇧H": "Главная · ⌘⇧H",
        "Close Tab": "Закрыть вкладку",
        "Home": "Главная",
        "Hyimg · Home": "Hyimg — Главная",
        "Hyimg · %@": "Hyimg — %@",
        "Starting “%@”": "Запускаю «%@»",
        "Waking “%@”": "Бужу «%@»",   // a board that slept opens again (BoardSleep.swift)
        "Opening “%@”": "Открываю «%@»",
        "Board drawn": "Доска нарисована",
        "Page loaded, building the board": "Страница загружена, строю доску",
        "Board server · port %ld": "Сервер доски · порт %ld",
        "Server responded · %ld ms": "Сервер ответил · %ld мс",
        "Loading the canvas and the library": "Загружаю холст и библиотеку",
        "Did not open: %@": "Не открылся: %@",
        "Saving": "Сохраняю",
        "Saved": "Сохранено",
        "Not saved": "Не сохранено",
        "Add a folder of images": "Добавить папку с изображениями",
        "Couldn't add the board": "Не удалось добавить доску",
        "Folder for the new board": "Папка для новой доски",
        "Remove “%@” from Hyimg?": "Убрать «%@» из Hyimg?",
        "The board leaves the list. Its folder, pictures and saved board stay on disk; adding the folder again brings it back.": "Доска уйдет из списка. Ее папка, картинки и сохраненная доска останутся на диске, а если добавить папку снова, доска вернется.",
        "Remove": "Убрать",
        "Couldn't remove the board": "Не получилось убрать доску",
        "Choose the folder of the board's images, or make a new one with New Folder.": "Выберите папку с картинками доски или создайте новую кнопкой «Новая папка».",
        "Create board": "Создать доску",
        "New board": "Новая доска",
        "Create": "Создать",
        "This folder already exists. Use “Add folder”.": "Папка уже существует. Используйте «Добавить папку».",
        "Couldn't create the board": "Не удалось создать доску",
        "Board name": "Название доски",
        "The folder name and the files stay the same.": "Название папки и файлы останутся прежними.",
        "Save": "Сохранить",
        "Cancel": "Отмена",
        "confirm::OK": "Да",
        "Couldn't rename the board": "Не удалось переименовать доску",
        "Choose the folder of “%@”": "Укажите папку доски «%@»",
        "No files are moved. The previous _review folder, if it is still there, stays the source of the data.": "Файлы не будут перемещены. Доступная прежняя папка _review сохранится как источник данных.",
        "Couldn't link the folder": "Не удалось связать папку",
        "The page did not load": "Страница не загрузилась",
        "The board's page quit": "Страница доски завершилась",
        "The latest unsaved changes may not have been written. Press ⌘R to open the saved version.": "Последние несохраненные изменения могли не записаться. Нажмите ⌘R, чтобы открыть сохраненную версию.",
        "This build has no Chromium": "В этой сборке Chromium нет",
        "Build Hyimg with CEF: ./build.sh downloads and links it.": "Соберите Hyimg с CEF: ./build.sh скачает и подключит его.",
        "Changes not saved": "Изменения не сохранены",
        "Opening the board…": "Открываю доску…",
        "Couldn't open the board": "Не удалось открыть доску",
        "The board did not open": "Доска не открылась",
        "Press ⌘R to try again or go back Home (⌘⇧H).": "Нажмите ⌘R для повторной попытки или вернитесь на главную (⌘⇧H).",
        "Saving changes…": "Сохраняю изменения…",
        "Wait for saving to finish": "Дождитесь сохранения",
        "Another action with the board is in progress.": "Сейчас выполняется другое действие с доской.",
        "Couldn't save the changes": "Не удалось сохранить изменения",
        "The --catalog path must be absolute.": "Путь --catalog должен быть абсолютным.",
        "Neither the sources nor the bundled server were found. Rebuild the app with build.sh in the Hyimg folder.": "Не найдены исходники и встроенный сервер. Пересоберите приложение командой build.sh в папке Hyimg.",
        "The --open-project board is not in the catalog.": "Доска --open-project не найдена в каталоге.",
        "Hyimg could not start": "Hyimg не запущен",
        "Language": "Язык",
        "Hide Hyimg": "Скрыть Hyimg",
        "Quit Hyimg": "Выйти из Hyimg",
        "Board": "Доска",
        "Board from Finder Folder…": "Доска из папки Finder…",
        "New Board…": "Новая доска…",
        "Next Tab": "Следующая вкладка",
        "Previous Tab": "Предыдущая вкладка",
        "Edit": "Правка",
        "Undo": "Отменить",
        "Redo": "Повторить",
        "Cut": "Вырезать",
        "Copy": "Скопировать",
        "Paste": "Вставить",
        "Select All": "Выбрать все",
        "View": "Вид",
        "Reload Page": "Обновить",
        "Restart Server": "Перезапустить сервер",
        "Open in Browser": "Открыть в браузере",
        "Chromium Engine": "Движок Chromium",
        "Boards are drawn by Chromium on the GPU; off: WebKit (as in Safari)": "Доска рисуется Chromium на видеокарте; выключено: WebKit (как Safari)",
        "Enter Full Screen": "Во весь экран",
        "Window": "Окно",
        "Minimize": "Свернуть",
        "Media Library": "Библиотека",
        "Hide Interface": "Скрыть интерфейс",
        // People.swift: shared and private boards (owner 2026-10-07)
        "The shared folder": "Общая папка",
        "The private folder": "Личная папка",
        "Boards in this folder are seen by everyone it is shared with, for example in Dropbox.": "Доски в этой папке видят все, с кем она открыта, например в Dropbox.",
        "Boards here are only yours while this folder is shared with no one.": "Доски здесь только ваши, пока эта папка ни с кем не открыта.",
        "Choose the shared and the private folder in Settings › Profile first": "Сначала выберите общую и личную папку в Настройках › Профиль",
        "Couldn't move the board": "Не получилось перенести доску",
        "Make “%@” shared?": "Сделать доску «%@» общей?",
        "Make “%@” only yours?": "Сделать доску «%@» только своей?",
        "Its folder moves to %@. Nothing is deleted: from another disk the old folder goes to the Trash after the copy is checked.":
            "Ее папка переедет в %@. Ничего не удаляется: с другого диска старая папка уйдет в Корзину после проверки копии.",
        "Move": "Перенести",
        "Moving the folder…": "Переношу папку…",
        "The folder moved, the catalog did not change": "Папка перенесена, каталог не изменился",
        "Shared": "Общая",
        "Only for me": "Только для меня",
        "The old folder stayed": "Старая папка осталась на месте",
        "Not moved": "Не перенесено",
        "Add a plugin": "Добавить плагин",   // Settings › Plugins (Plugins.swift)
        "Choose the plugin's folder, the one with manifest.json.": "Выберите папку плагина, ту, где лежит manifest.json.",
        "Add": "Добавить",
        "%ld updates": "Обновлений: %ld",   // a burst of one board's rows in one banner (MacNotifications.swift)
    ]
}
func L(_ key: String) -> String {
    if Lang.current == "ru", let v = Lang.ru[key] { return v }
    if let k = key.range(of: "::") { return String(key[k.upperBound...]) }
    return key
}
func L(_ key: String, _ args: CVarArg...) -> String { String(format: L(key), arguments: args) }
