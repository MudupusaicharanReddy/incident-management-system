from __future__ import annotations

import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_second: int, capacity: int) -> None:
        self.rate_per_second = rate_per_second
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self, cost: int = 1) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate_per_second)
            self._last_refill = now
            if self._tokens >= cost:
                self._tokens -= cost
                return True
            return False
