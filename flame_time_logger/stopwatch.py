"""Pure timing logic for the time logger.

Deliberately free of Qt and Flame imports so it can be unit-tested on any
machine. The dialog drives a :class:`Stopwatch` from a ``QTimer`` and reads
:meth:`Stopwatch.elapsed_seconds` once per second for display.
"""

from __future__ import annotations

import time

QUARTER_HOUR_MINUTES = 15


def round_to_quarter_hour(minutes: float) -> int:
    """Round a duration in minutes to the nearest quarter hour.

    Uses round-half-up (via ``math``-free integer arithmetic) so the result is
    deterministic and stable across platforms. Negative input is clamped to 0.

    Examples: 0->0, 7->0, 8->15, 22->15, 23->30, 37->30, 38->45.
    """
    if minutes <= 0:
        return 0
    # Round half up: add half a step before integer-dividing.
    steps = int((minutes + QUARTER_HOUR_MINUTES / 2) // QUARTER_HOUR_MINUTES)
    return steps * QUARTER_HOUR_MINUTES


class Stopwatch:
    """A start/pause/resume stopwatch that accumulates elapsed time.

    Time is measured with :func:`time.monotonic` so it is immune to wall-clock
    adjustments. Elapsed time accumulates across any number of pause/resume
    cycles.
    """

    def __init__(self) -> None:
        self._accumulated = 0.0  # seconds banked from previous run segments
        self._started_at: float | None = None  # monotonic time of current run

    @property
    def is_running(self) -> bool:
        return self._started_at is not None

    def start(self) -> None:
        """Begin (or resume) timing. No-op if already running."""
        if self._started_at is None:
            self._started_at = time.monotonic()

    # ``resume`` is a readable alias for ``start`` after a pause.
    resume = start

    def pause(self) -> None:
        """Stop accumulating time, banking the current segment. Idempotent."""
        if self._started_at is not None:
            self._accumulated += time.monotonic() - self._started_at
            self._started_at = None

    def reset(self) -> None:
        """Clear all elapsed time and stop the stopwatch."""
        self._accumulated = 0.0
        self._started_at = None

    def elapsed_seconds(self) -> float:
        """Total elapsed seconds, including any currently running segment."""
        elapsed = self._accumulated
        if self._started_at is not None:
            elapsed += time.monotonic() - self._started_at
        return elapsed

    def elapsed_minutes(self) -> float:
        return self.elapsed_seconds() / 60.0
