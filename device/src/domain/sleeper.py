"""Minimal interruptible sleeper utility used by automated sequences."""

import time
from typing import Callable


class InterruptibleSleeper:
    """Sleep helper that periodically checks a stop flag and raises when set."""

    def __init__(self, stop_flag: Callable[[], bool], poll_interval: float = 0.1) -> None:
        self._stop_flag = stop_flag
        self._poll_interval = max(0.01, float(poll_interval))

    def sleep(self, duration: float) -> None:
        """Sleep for `duration` seconds or raise InterruptedError if stop flag set."""
        remaining = max(0.0, float(duration))
        if remaining <= 0.0:
            return
        end_time = time.time() + remaining
        while remaining > 0:
            if self._stop_flag():
                raise InterruptedError("sleep interrupted by stop flag")
            step = min(self._poll_interval, remaining)
            time.sleep(step)
            remaining = end_time - time.time()
