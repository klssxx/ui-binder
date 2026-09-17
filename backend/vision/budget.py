"""Vision budget tracker — enforces cost limits across providers."""
from __future__ import annotations

import threading
from typing import Optional

from backend.vision.contract import VisionUsage


class VisionBudget:
    """Thread-safe budget tracker for vision API calls."""
    
    def __init__(self, max_cost_usd: float = 2.0):
        self.max_cost_usd = max_cost_usd
        self._spent = 0.0
        self._calls = 0
        self._lock = threading.Lock()
    
    def record(self, usage: VisionUsage) -> bool:
        """Record a call. Returns True if within budget."""
        with self._lock:
            self._spent += usage.estimated_cost_usd
            self._calls += 1
            return self._spent <= self.max_cost_usd
    
    @property
    def spent(self) -> float:
        with self._lock:
            return self._spent
    
    @property
    def calls(self) -> int:
        with self._lock:
            return self._calls
    
    def would_exceed(self, estimated_cost: float) -> bool:
        with self._lock:
            return (self._spent + estimated_cost) > self.max_cost_usd
    
    def reset(self):
        with self._lock:
            self._spent = 0.0
            self._calls = 0


# Global budget instance
_budget = VisionBudget()


def get_budget() -> VisionBudget:
    return _budget
