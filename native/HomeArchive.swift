import Foundation

// Home's standard Archive, the app's side (owner 2026-10-08: «Папку архив (или проект) Архив сделай, пожалуйста, стандартный, ее не удалить,
// она просто есть. И туда будем пихать все, что не должно светиться нигде»). Home keeps it in home.json as the project with the id
// "archive" (review/ui/homearchive.js makes it, moves boards in and out, hides them on Home). What only the app can hide is here:
//   ⌃Tab's cards and the crumb's list of open boards leave an archived board out, unless it is the board in front (Switcher.swift cardIDs)
//   macOS notifications: its bell rows are read and remembered as any board's, never shown as banners (MacNotifications.swift got)
//   Home's «Start server» never starts it (main.swift warm); opening it from the Archive works as for any board
//   a write of home.json never drops it (kept, main.swift writeHome); a board made while it is open on Home goes into no project (fileInto)
// home.json is read each time: Home writes it, the app reads it (a read is a small file, only on ⌃Tab, a list of open boards, a poll
// that found news). This first part is Foundation only (tests/test_native_archive.swift builds it with -D HYIMG_POLICY_ONLY).
enum HomeArchive {
    static let id = "archive"
    /// the boards in the Archive, from home.json's contents
    static func boards(_ home: [String: Any]) -> Set<UUID> {
        let folders = home["folders"] as? [[String: Any]] ?? []
        guard let f = folders.first(where: { $0["id"] as? String == id }) else { return [] }
        return Set((f["projects"] as? [Any] ?? []).compactMap { ($0 as? String).flatMap(UUID.init(uuidString:)) })
    }
    /// the same from the file (none or unreadable: none archived)
    static func boards(file: URL) -> Set<UUID> {
        guard let d = try? Data(contentsOf: file), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [] }
        return boards(j)
    }
    /// what is written over home.json: a home without the Archive (an older Home, a stale writer) keeps the one the file has, without the
    /// boards it now files elsewhere, so the archived boards don't come back into Recent, All boards and the bell; a home with it is as is
    static func kept(_ new: [String: Any], old: [String: Any]) -> [String: Any] {
        var folders = new["folders"] as? [[String: Any]] ?? []
        guard !folders.contains(where: { $0["id"] as? String == id }),
              var box = (old["folders"] as? [[String: Any]] ?? []).first(where: { $0["id"] as? String == id }) else { return new }
        let filed = Set(folders.flatMap { ($0["projects"] as? [Any] ?? []).compactMap { $0 as? String } })
        let ids = (box["projects"] as? [Any] ?? []).compactMap { $0 as? String }.filter { !filed.contains($0) }
        box["projects"] = ids
        if let from = box["from"] as? [String: Any] { box["from"] = from.filter { ids.contains($0.key) } }
        folders.append(box)
        var out = new; out["folders"] = folders
        return out
    }
    /// the same against the file; a file there that can't be read is first copied beside it (home.unreadable-<time>.json), so a write
    /// from a Home that got nothing of it (home {}) does not take the owner's projects and favourites away for good
    static func kept(_ new: [String: Any], file: URL, now: Date = Date()) -> [String: Any] {
        guard let d = try? Data(contentsOf: file) else { return new }
        guard let old = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else {
            let aside = file.deletingLastPathComponent().appendingPathComponent("home.unreadable-\(Int(now.timeIntervalSince1970)).json")
            try? d.write(to: aside, options: .atomic)
            return new
        }
        return kept(new, old: old)
    }
    /// ⌃Tab's open boards without the archived ones; the board in front stays, it is the first card
    static func switchable(_ open: [UUID], archived: Set<UUID>, front: UUID?) -> [UUID] {
        open.filter { !archived.contains($0) || $0 == front }
    }
}

#if !HYIMG_POLICY_ONLY
extension App {
    /// the boards in Home's Archive now
    var archivedBoards: Set<UUID> { HomeArchive.boards(file: homeFile) }
}
#endif
