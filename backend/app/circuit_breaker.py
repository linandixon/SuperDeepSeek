import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    success_threshold: int = 2
    timeout_seconds: int = 60


class CircuitBreaker:
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = "closed"
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.opened_at = 0.0

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "half_open":
            return True
        if time.time() - self.opened_at >= self.config.timeout_seconds:
            self.state = "half_open"
            self.consecutive_successes = 0
            return True
        return False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        if self.state == "half_open":
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.config.success_threshold:
                self.state = "closed"
                self.consecutive_successes = 0
        else:
            self.state = "closed"

    def record_failure(self) -> None:
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.config.failure_threshold:
            self.state = "open"
            self.opened_at = time.time()

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "consecutiveFailures": self.consecutive_failures,
            "consecutiveSuccesses": self.consecutive_successes,
            "openedAt": self.opened_at,
        }
