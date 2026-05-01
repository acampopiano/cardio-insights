from threading import Lock


class TokenBlocklist:
    """Almacen en memoria para marcar tokens JWT revocados por su jti."""

    def __init__(self) -> None:
        """Inicializa set interno y lock para acceso concurrente seguro."""
        self._tokens: set[str] = set()
        self._lock = Lock()

    def add(self, jti: str) -> None:
        """Registra un jti como revocado para invalidar ese token."""
        with self._lock:
            self._tokens.add(jti)

    def contains(self, jti: str) -> bool:
        """Indica si un jti ya fue revocado previamente."""
        with self._lock:
            return jti in self._tokens


blocklist = TokenBlocklist()
