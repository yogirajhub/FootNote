"""
timing.py — StageTimer context manager for per-stage latency instrumentation.

Usage:
    timer = StageTimer()
    with timer.stage("retrieval"):
        chunks = await retrieve(...)
    print(timer.timings)  # {"retrieval": 123.4, ...}
"""
import time
from typing import Dict
from contextlib import contextmanager
import structlog

logger = structlog.get_logger()


class StageTimer:
    """
    Collects wall-clock durations (ms) for named pipeline stages.
    Thread-safe for sequential use; not meant for concurrent stages.
    """

    def __init__(self) -> None:
        self.timings: Dict[str, float] = {}
        self._start: float = 0.0
        self._pipeline_start: float = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        """Context manager that records duration of a named stage in ms."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.timings[name] = round(elapsed_ms, 2)
            logger.debug("Stage complete", stage=name, ms=elapsed_ms)

    @property
    def total_ms(self) -> float:
        """Wall-clock ms since this StageTimer was created."""
        return round((time.perf_counter() - self._pipeline_start) * 1000, 2)

    def log_summary(self, **extra) -> None:
        """Emit a single structured log line with all stage timings."""
        logger.info(
            "Pipeline timing summary",
            total_ms=self.total_ms,
            stages=self.timings,
            **extra,
        )
