"""Circuit breaker for external LLM API calls."""
import logging
import threading
import time
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Opens after consecutive failures; half-open allows a probe call."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit %s: OPEN -> HALF_OPEN", self.name)
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info("Circuit %s: %s -> CLOSED", self.name, self._state.value)
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        "Circuit %s opened after %d failures",
                        self.name,
                        self._failure_count,
                    )
                self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        state = self.state
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def call(self, func: Callable[[], T], fallback: Callable[[], T]) -> T:
        if not self.allow_request():
            logger.warning("Circuit %s is OPEN; using fallback", self.name)
            return fallback()
        try:
            result = func()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
