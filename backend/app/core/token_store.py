from threading import Lock


class TokenBlocklist:
    def __init__(self) -> None:
        self._tokens: set[str] = set()
        self._lock = Lock()

    def add(self, jti: str) -> None:
        with self._lock:
            self._tokens.add(jti)

    def contains(self, jti: str) -> bool:
        with self._lock:
            return jti in self._tokens


blocklist = TokenBlocklist()
