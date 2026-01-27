import threading
from typing import Any, Callable, Optional

try:
    from librpiplc import rpiplc as plc  # type: ignore
except Exception:  # pragma: no cover
    plc = None

_plc_lock = threading.RLock()
_plc_init_lock = threading.Lock()
_plc_initialized = False


def ensure_plc_init() -> None:
    global _plc_initialized
    if plc is None:
        return
    if _plc_initialized:
        return
    with _plc_init_lock:
        if _plc_initialized:
            return
        try:
            plc.init("RPIPLC_V6", "RPIPLC_38AR")
            _plc_initialized = True
        except Exception:
            # leave uninitialized; callers will tolerate None/failed ops
            return


def safe_plc_call(op_name: str, func: Callable[..., Any], *args, **kwargs) -> Optional[Any]:
    if plc is None:
        return None
    ensure_plc_init()
    try:
        with _plc_lock:
            return func(*args, **kwargs)
    except Exception:
        return None


__all__ = ["plc", "safe_plc_call", "ensure_plc_init"]
