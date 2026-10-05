import Foundation

final class SaveBarrier {
    static func flush(loaded: Bool, loading: Bool, timeout: TimeInterval = 15,
                      evaluate: (@escaping (Result<Bool, Error>) -> Void) -> Void,
                      completion: @escaping (Result<Void, Error>) -> Void) {
        if loading {
            completion(.failure(RegistryError.invalid("Страница еще загружается. Дождитесь открытия доски и повторите действие.")))
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
            finish(.failure(RegistryError.invalid("Страница не подтвердила сохранение за 15 секунд. Проверьте соединение с сервером и повторите действие.")))
        }
        timeoutWork = timer
        DispatchQueue.main.asyncAfter(deadline: .now() + timeout, execute: timer)
        evaluate { result in
            switch result {
            case .success(true): finish(.success(()))
            case .success(false): finish(.failure(RegistryError.invalid("Страница не смогла сохранить изменения. Действие отменено, доска остается открытой.")))
            case .failure(let error): finish(.failure(error))
            }
        }
    }
}
