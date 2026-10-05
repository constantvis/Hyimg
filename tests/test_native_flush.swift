import Foundation

@main struct SaveBarrierTests {
    static func main() throws {
        func require(_ condition: Bool, _ name: String) throws {
            guard condition else { throw RegistryError.invalid("FAIL: \(name)") }
            print("PASS: \(name)")
        }
        var response: ((Result<Bool, Error>) -> Void)?
        var completed = 0
        var succeeded = false
        var failed = false
        SaveBarrier.flush(loaded: true, loading: false, evaluate: { response = $0 }) { result in
            completed += 1
            if case .success = result { succeeded = true }
        }
        try require(completed == 0, "pending page save blocks destructive continuation")
        response?(.success(true))
        try require(completed == 1 && succeeded, "confirmed page save releases continuation once")
        response?(.success(false))
        try require(completed == 1, "duplicate page callback cannot release continuation twice")
        SaveBarrier.flush(loaded: true, loading: false, evaluate: { $0(.success(false)) }) { result in
            if case .failure = result { failed = true }
        }
        try require(failed, "page save false cancels destructive continuation")
        failed = false
        SaveBarrier.flush(loaded: true, loading: false, evaluate: { $0(.failure(RegistryError.invalid("network failure"))) }) { result in
            if case .failure = result { failed = true }
        }
        try require(failed, "JavaScript error cancels destructive continuation")
        failed = false
        var evaluated = false
        SaveBarrier.flush(loaded: false, loading: true, evaluate: { _ in evaluated = true }) { result in
            if case .failure = result { failed = true }
        }
        try require(failed && !evaluated, "loading document cannot silently skip save readiness")
        succeeded = false
        SaveBarrier.flush(loaded: false, loading: false, evaluate: { _ in evaluated = true }) { result in
            if case .success = result { succeeded = true }
        }
        try require(succeeded && !evaluated, "unused session needs no page save")
        failed = false
        completed = 0
        SaveBarrier.flush(loaded: true, loading: false, timeout: 0.01, evaluate: { response = $0 }) { result in
            completed += 1
            if case .failure = result { failed = true }
        }
        let deadline = Date().addingTimeInterval(1)
        while completed == 0 && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.02)) }
        try require(failed && completed == 1, "unresponsive page cancels operation on timeout")
        response?(.success(true))
        try require(completed == 1, "late success after timeout cannot trigger destructive operation")
        print("NATIVE_SAVE_BARRIER_TESTS_PASSED")
    }
}
