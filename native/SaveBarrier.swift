import Foundation

final class SaveBarrier {
    static func flush(loaded: Bool, loading: Bool, timeout: TimeInterval = 15,
                      evaluate: (@escaping (Result<Bool, Error>) -> Void) -> Void,
                      completion: @escaping (Result<Void, Error>) -> Void) {
        if loading {
            completion(.failure(RegistryError.invalid(L("The page is still loading. Wait for the board to open and try again."))))
            return
        }
        guard loaded else { completion(.success(())); return }
        var completed = false
        var timeoutWork: DispatchWorkItem?
        func finish(_ result: Result<Void, Error>) {
            guard !completed else { return }
            completed = true
            timeoutWork?.cancel()
            timeoutWork = nil
            completion(result)
        }
        let timer = DispatchWorkItem {
            finish(.failure(RegistryError.invalid(L("The page did not confirm saving within 15 seconds. Check the connection to the server and try again."))))
        }
        timeoutWork = timer
        DispatchQueue.main.asyncAfter(deadline: .now() + timeout, execute: timer)
        evaluate { result in
            switch result {
            case .success(true): finish(.success(()))
            case .success(false): finish(.failure(RegistryError.invalid(L("The page could not save the changes. The action was canceled, the board stays open."))))
            case .failure(let error): finish(.failure(error))
            }
        }
    }
}
