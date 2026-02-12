import threading


_PORT_LOCKS: dict[str, threading.Lock] = {}
_PORT_LOCKS_GUARD = threading.Lock()


def get_port_lock(port: str) -> threading.Lock:
    key = str(port)
    with _PORT_LOCKS_GUARD:
        lock = _PORT_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PORT_LOCKS[key] = lock
        return lock
