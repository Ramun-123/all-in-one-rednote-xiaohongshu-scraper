thonimport threading
import time
from typing import Callable, TypeVar, Any, cast

T = TypeVar("T")

class RateLimiter:
    """
    Simple token-bucket style rate limiter.
    Ensures that at most `calls_per_minute` are executed, with an optional burst.
    """

    def __init__(self, calls_per_minute: int = 60, burst: int = 5) -> None:
        self.calls_per_minute = max(1, calls_per_minute)
        self.interval = 60.0 / float(self.calls_per_minute)
        self.burst = max(1, burst)

        self._lock = threading.Lock()
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return