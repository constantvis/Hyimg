import Foundation

// macOS notifications for the bell (native/MacNotifications.swift, owner 2026-10-08): the settings, never twice, a board looked at for the
// first time, this Mac's person's own rows, the types, the background-only switch, the bell open, a burst in one banner, the banner's
// words and the camera of an area. Built with -D HYIMG_POLICY_ONLY: the policy alone, no AppKit.
@main struct MacNotifPolicyTests {
    static func main() {
        var failed = 0
        func require(_ condition: Bool, _ name: String) {
            if condition { print("PASS: \(name)") } else { print("FAIL: \(name)"); failed += 1 }
        }
        // the settings: all on by default; "0" turns off, cv.mac.bg "1" only in the background
        let none = MacNotifSettings([:])
        require(none.on && none.kinds == Set(["agent", "comment", "reply", "mention", "note"]) && !none.onlyBackground, "no settings: on, every type, any time")
        require(!MacNotifSettings(["cv.mac": "0"]).on && MacNotifSettings(["cv.mac": "1"]).on, "the master switch")
        let some = MacNotifSettings(["cv.mac.reply": "0", "cv.mac.note": "0", "cv.mac.agent": "1", "cv.mac.bg": "1"])
        require(some.kinds == Set(["agent", "comment", "mention"]) && some.onlyBackground, "types off one by one, background only")
        require(MacNotifSettings(["cv.mac.bg": 1]).onlyBackground && MacNotifSettings(["cv.mac.mention": 0]).kinds.contains("mention") == false,
                "numbers as the file may hold them")

        // a row as the server gives it
        let row = BellItem(["id": "c:t1:m2", "ts": 1000.5, "type": "mention", "title": "Mentioned you", "text": "look", "from": "Bob", "page": "main",
                            "ids": ["i1", 7], "by": ["person": "ABC", "via": "app"], "area": ["x": 1, "y": 2, "w": 30, "h": 40],
                            "pv": [["src": "/feedthumb?x=1", "k": "crop", "mark": ["r": [0.1, 0.2, 0.5, 0.5]]]]])
        require(row?.id == "c:t1:m2" && row?.ts == 1000.5 && row?.person == "abc" && row?.ids == ["i1"] && row?.area == [1, 2, 30, 40], "a row's fields")
        require(row?.tile == "/feedthumb?x=1" && row?.markRect == [0.1, 0.2, 0.5, 0.5] && row?.markPin == nil, "its first picture and its mark")
        require(BellItem(["title": "no id"]) == nil && BellItem(["id": "x", "pv": [["src": "http://elsewhere/x.png"]]])?.tile == nil,
                "a row without an id is no row; a picture from anywhere but its board is not taken")

        // never twice; a board looked at for the first time posts nothing and remembers it all
        let a = BellItem(id: "a", ts: 100), b = BellItem(id: "b", ts: 200), c = BellItem(id: "c", ts: 150)
        let first = MacNotifPolicy.fresh([b, a], cursor: nil, now: 1000)
        require(first.new.isEmpty && Set(first.cursor.ids) == ["a", "b"] && first.cursor.ts == 1000, "first look: nothing posted, all remembered")
        let second = MacNotifPolicy.fresh([b, a, c], cursor: first.cursor, now: 1010)
        require(second.new.map(\.id) == ["c"] && second.cursor.ids.suffix(1) == ["c"], "the same rows again: only the new one")
        let third = MacNotifPolicy.fresh([b, a, c], cursor: second.cursor, now: 1020)
        require(third.new.isEmpty, "asked again: nothing")
        let order = MacNotifPolicy.fresh([BellItem(id: "y", ts: 3000), BellItem(id: "x", ts: 2000), BellItem(id: "x", ts: 2000)], cursor: third.cursor, now: 5000)
        require(order.new.map(\.id) == ["x", "y"] && order.cursor.ts == 3000, "oldest first, a row twice in one answer once, the cursor at the newest")
        let ahead = MacNotifPolicy.fresh([BellItem(id: "z", ts: 99_999)], cursor: order.cursor, now: 6000)
        require(ahead.new.count == 1 && ahead.cursor.ts == 6000, "a row from a clock ahead never moves the cursor past now")
        require(MacNotifPolicy.since(nil, now: 10_000) == 6400 && MacNotifPolicy.since(NotifCursor(ts: 5000, ids: []), now: 10_000) == 4400,
                "since: an hour back the first time, then 10 minutes before the newest seen")
        var many = NotifCursor(ts: 0, ids: [])
        for k in 0..<400 { many = MacNotifPolicy.fresh([BellItem(id: "r\(k)", ts: Double(k))], cursor: many, now: 1e6).cursor }
        require(many.ids.count == MacNotifPolicy.keep && many.ids.last == "r399" && many.ids.first == "r100", "the newest 300 ids kept")
        // the cursor survives the defaults (a property list)
        let saved = NotifCursor(NSDictionary(dictionary: second.cursor.plist) as? [String: Any])
        require(saved == second.cursor && NotifCursor(["ids": ["a"]]) == nil && NotifCursor("junk") == nil, "the cursor in the defaults and back")

        // what becomes a banner
        let me = "D6B4F7A0-0000-4000-8000-000000000001"
        let mineApp = BellItem(id: "1", ts: 990, type: "comment", person: me.lowercased(), via: "app")
        let mineAgent = BellItem(id: "2", ts: 990, type: "agent", from: "Claude", person: me.lowercased(), via: "claude")
        let bob = BellItem(id: "3", ts: 990, type: "reply", from: "Bob", person: "b0b", via: "app")
        let mention = BellItem(id: "4", ts: 990, type: "mention", from: "Codex · Bob", person: "b0b", via: "codex")
        let old = BellItem(id: "5", ts: 990 - 86_400, type: "comment", from: "Bob", person: "b0b")
        let rows = [mineApp, mineAgent, bob, mention, old]
        func ids(_ s: MacNotifSettings, active: Bool = false, bell: Bool = false, me m: String? = me) -> [String] {
            MacNotifPolicy.wanted(rows, s, me: m, now: 1000, appActive: active, bellOpen: bell).map(\.id)
        }
        require(MacNotifPolicy.own(mineApp, me: me) && !MacNotifPolicy.own(mineAgent, me: me) && !MacNotifPolicy.own(bob, me: me), "own: his rows from the app only")
        require(!MacNotifPolicy.own(BellItem(id: "x", ts: 0, person: me.lowercased(), via: ""), me: nil), "no profile: nothing is his")
        require(ids(none) == ["2", "3", "4"], "his agent's news, Bob's reply and the mention; not his own, not a day old")
        require(ids(MacNotifSettings(["cv.mac": "0"])).isEmpty, "off: nothing")
        require(ids(MacNotifSettings(["cv.mac.agent": "0", "cv.mac.reply": "0"])) == ["4"], "types turned off")
        require(ids(none, active: true) == ["2", "3", "4"], "any time by default, Hyimg in front too")
        require(ids(MacNotifSettings(["cv.mac.bg": "1"]), active: true).isEmpty && ids(MacNotifSettings(["cv.mac.bg": "1"])) == ["2", "3", "4"],
                "only in the background: nothing while Hyimg is in front")
        require(ids(none, active: true, bell: true).isEmpty, "the board in front with its bell open: nothing")
        require(MacNotifPolicy.wanted([BellItem(id: "u", ts: 990, type: "later")], none, me: me, now: 1000, appActive: false, bellOpen: false).isEmpty,
                "a type the settings do not know: not shown")

        // a burst: more than 5 rows of one board within a minute, one banner
        var recent: [MacNotifPolicy.Recent] = []
        let four = (0..<4).map { BellItem(id: "n\($0)", ts: 0, from: "Claude") }
        require(MacNotifPolicy.plan(four, recent: &recent, now: 100).count == 4, "4 rows: 4 banners")
        let three = (4..<7).map { BellItem(id: "n\($0)", ts: 0, from: "Claude") }
        require(MacNotifPolicy.plan(three, recent: &recent, now: 110) == [.summary(count: 7, from: "Claude")], "3 more within the minute: one «7 updates»")
        require(MacNotifPolicy.plan([BellItem(id: "late", ts: 0, from: "Bob")], recent: &recent, now: 200) == [.one(BellItem(id: "late", ts: 0, from: "Bob"))],
                "a minute later: one banner again")
        var burst: [MacNotifPolicy.Recent] = []
        let mixed = [BellItem(id: "m1", ts: 0, from: "Claude")] + (2...6).map { BellItem(id: "m\($0)", ts: 0, from: "Bob") }
        require(MacNotifPolicy.plan(mixed, recent: &burst, now: 0) == [.summary(count: 6, from: "")], "6 at once from two people: the board's name alone")
        require(MacNotifPolicy.plan([], recent: &burst, now: 1) == [], "nothing new: nothing")
        require(MacNotifPolicy.next(10, got: false) == 15 && MacNotifPolicy.next(50, got: false) == 60 && MacNotifPolicy.next(60, got: true) == 10,
                "asked every 10 s, slower up to 60 s while nothing comes, 10 s again after news")

        // the banner's words
        var news = BellItem(id: "n", ts: 0, type: "agent", from: "Claude"); news.title = "delivered 6-shot before/after series in Blender"; news.text = "awaiting selection"
        let w = MacNotifPolicy.content(news, board: "Studio North")
        require(w.title == "Claude · Studio North" && w.subtitle == "" && w.body == "delivered 6-shot before/after series in Blender\nawaiting selection" && !w.sound,
                "an agent's news: «Claude · Studio North», its title and text, silent")
        var reply = BellItem(id: "r", ts: 0, type: "mention", from: "Bob"); reply.title = "Mentioned you"; reply.text = "@Ann look"
        let m = MacNotifPolicy.content(reply, board: "Studio North")
        require(m.title == "Bob · Studio North" && m.subtitle == "Mentioned you" && m.body == "@Ann look" && m.sound, "a mention: who, what happened, the words, a sound")
        require(MacNotifPolicy.content(BellItem(id: "x", ts: 0), board: "B").title == "B", "no sender: the board's name")
        require(MacNotifPolicy.clip(String(repeating: "x", count: 500)).count == 240, "long words cut")

        // an area's camera, as the bell's click does it
        let cam = MacNotifPolicy.camera([100, 200, 400, 300], width: 1440, height: 900)   // zoom at most 2, the area in the middle
        require(cam == "-60.0,125.0,2.0000", "the camera of an area: \(cam ?? "nil")")
        require(MacNotifPolicy.camera([0, 0, 0, 10], width: 1440, height: 900) == nil && MacNotifPolicy.camera([0, 0, 10, 10], width: 100, height: 100) == nil,
                "no camera for an empty area or a tiny window")

        print(failed == 0 ? "ALL PASS" : "\(failed) FAILED")
        exit(failed == 0 ? 0 : 1)
    }
}
