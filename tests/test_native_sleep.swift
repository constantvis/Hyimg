import Foundation

// Sleeping boards and ⌃Tab's order (native/BoardSleep.swift, owner 2026-10-08 «Вкладки со сном»): the setting, the timer, what keeps a
// board awake (an edit not saved, an edit under way, a studio, a render or an upload, a video), the states and the cards' order.
// Built with -D HYIMG_POLICY_ONLY: the policy alone, no AppKit.
@main struct SleepPolicyTests {
    static func main() {
        var failed = 0
        func require(_ condition: Bool, _ name: String) {
            if condition { print("PASS: \(name)") } else { print("FAIL: \(name)"); failed += 1 }
        }
        // the setting cv.sleep
        require(SleepPolicy.minutes(nil) == 10, "no setting: 10 minutes")
        require(SleepPolicy.minutes("") == 10, "empty setting: 10 minutes")
        require(SleepPolicy.minutes("5") == 5 && SleepPolicy.minutes("30") == 30, "5 and 30 minutes")
        require(SleepPolicy.minutes("0") == nil && SleepPolicy.minutes("never") == nil, "0 and never: never")
        require(SleepPolicy.minutes("soon") == 10, "a value it does not know: the default")
        // the timer
        let t0 = Date(timeIntervalSince1970: 1_000_000)
        func due(_ after: Double, minutes: Int? = 10, front: Bool = false, asleep: Bool = false, page: Bool = true, pressure: Bool = false) -> Bool {
            SleepPolicy.due(since: t0, now: t0.addingTimeInterval(after), minutes: minutes, front: front, asleep: asleep, hasPage: page, pressure: pressure)
        }
        require(!due(9 * 60 + 59), "behind 9:59 of 10 minutes: awake")
        require(due(10 * 60), "behind 10 minutes: due")
        require(due(5 * 60, minutes: 5) && !due(4 * 60, minutes: 5), "5 minutes")
        require(!due(3600, minutes: nil), "never: not even after an hour")
        require(!due(3600, front: true), "the board in front never sleeps")
        require(!due(3600, asleep: true), "asleep already")
        require(!due(3600, page: false), "no page yet (loading): nothing to sleep")
        require(!due(10, pressure: true), "memory pressure: not a board just left")
        require(due(60, pressure: true) && !due(60, minutes: nil, pressure: true), "memory pressure: a board left a minute ago, unless sleep is off")
        require(!SleepPolicy.due(since: nil, now: t0, minutes: 10, front: false, asleep: false, hasPage: true), "never seen in front: no time yet")
        // what keeps it awake
        let idle: [String: Any] = ["unsaved": false, "editing": false, "studio": "", "busy": [String](), "video": false]
        require(SleepPolicy.blocker(idle) == nil, "an idle board may sleep")
        require(SleepPolicy.blocker(nil) != nil, "no answer from the page: awake")
        func with(_ k: String, _ v: Any) -> [String: Any] { var s = idle; s[k] = v; return s }
        require(SleepPolicy.blocker(with("unsaved", true)) != nil, "unsaved edits: awake")
        require(SleepPolicy.blocker(with("editing", true)) != nil, "an edit under way: awake")
        require(SleepPolicy.blocker(with("studio", "image")) != nil, "Image Studio open: awake")
        require(SleepPolicy.blocker(with("studio", "3d")) != nil && SleepPolicy.blocker(with("studio", "dev")) != nil, "3D and Dev Studio: awake")
        require(SleepPolicy.blocker(with("studio", "board")) == nil, "Board mode is no studio")
        require(SleepPolicy.blocker(with("busy", ["saving the image…"])) != nil, "an upload running: awake")
        require(SleepPolicy.blocker(with("busy", ["plg:render"])) != nil, "a render running: awake")
        require(SleepPolicy.blocker(with("video", true)) != nil, "a video playing: awake")
        // under pressure the longest behind first
        let a = UUID(), b = UUID(), c = UUID()
        require(SleepPolicy.order([(a, t0.addingTimeInterval(20)), (b, t0), (c, t0.addingTimeInterval(5))]) == [b, c, a], "the longest behind sleeps first")
        // states
        require(BoardState.of(front: true, asleep: false, drawn: true, loading: false, waking: false) == .open, "in front: open")
        require(BoardState.of(front: false, asleep: false, drawn: true, loading: false, waking: false) == .warm, "behind with its page: warm")
        require(BoardState.of(front: false, asleep: true, drawn: false, loading: false, waking: false) == .sleeping, "asleep")
        require(BoardState.of(front: true, asleep: false, drawn: false, loading: true, waking: true) == .waking, "waking up")
        require(BoardState.of(front: true, asleep: false, drawn: false, loading: true, waking: false) == .loading, "loading for the first time")
        // ⌃Tab's cards: the board in front, then the last in front first
        let last: [UUID: Date] = [a: t0, b: t0.addingTimeInterval(30), c: t0.addingTimeInterval(10)]
        require(SwitchOrder.cards(front: a, open: [a, b, c], lastFront: last) == [a, b, c], "front first, then the newest")
        require(SwitchOrder.cards(front: c, open: [a, b, c], lastFront: last) == [c, b, a], "the order follows the time in front")
        require(SwitchOrder.cards(front: nil, open: [a, b, c], lastFront: [:]) == [a, b, c], "no times: the tabs' order")
        require(SwitchOrder.firstPick(count: 4, step: 1) == 1 && SwitchOrder.firstPick(count: 4, step: -1) == 3, "⌃Tab starts on the next, ⌃⇧Tab on the last")
        require(SwitchOrder.firstPick(count: 1, step: 1) == 0, "one card: it")
        require(SwitchOrder.move(3, by: 1, count: 4) == 0 && SwitchOrder.move(0, by: -1, count: 4) == 3, "the cards go round")
        // the switched-to board's wait for its screen (Switcher.swift): only the latest wait's answer brings it in, once. ⌃Tab to a board,
        // Esc while it waits, ⌃Tab to it again: the first wait's answer or its cap brought it in before the second wait was over
        var w = SwitchWait()
        let t1 = w.start(a), t2 = w.start(a)
        require(t1 != t2, "each wait its own token")
        require(!w.take(a, t1), "the answer of a wait given up does not bring the board in")
        require(!w.take(b, t2), "nor an answer for another board")
        require(w.take(a, t2), "the latest wait's answer does")
        require(!w.take(a, t2), "once: the cap after the answer does nothing")
        let t3 = w.start(c); w.cancel()
        require(!w.take(c, t3), "a wait given up (Esc, Home) ends")
        if failed > 0 { print("\(failed) failed"); exit(1) }
    }
}
