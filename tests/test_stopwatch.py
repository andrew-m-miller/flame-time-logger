"""Unit tests for the pure timing logic (no Flame, no Qt, no ShotGrid)."""

import time

import pytest

from flame_time_logger.stopwatch import Stopwatch, round_to_quarter_hour


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [
        (0, 0),
        (-5, 0),
        (7, 0),
        (7.49, 0),
        (8, 15),
        (15, 15),
        (22, 15),
        (23, 30),
        (37, 30),
        (38, 45),
        (52, 45),
        (53, 60),
        (90, 90),
    ],
)
def test_round_to_quarter_hour(minutes, expected):
    assert round_to_quarter_hour(minutes) == expected


def test_stopwatch_accumulates_across_pause(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: now["t"])

    sw = Stopwatch()
    sw.start()
    now["t"] += 30  # run 30s
    sw.pause()
    assert sw.elapsed_seconds() == pytest.approx(30)

    now["t"] += 100  # paused: should not count
    assert sw.elapsed_seconds() == pytest.approx(30)

    sw.resume()
    now["t"] += 15  # run another 15s
    assert sw.elapsed_seconds() == pytest.approx(45)


def test_stopwatch_double_start_is_noop(monkeypatch):
    now = {"t": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: now["t"])

    sw = Stopwatch()
    sw.start()
    now["t"] += 10
    sw.start()  # should not reset the running segment
    now["t"] += 5
    assert sw.elapsed_seconds() == pytest.approx(15)


def test_reset(monkeypatch):
    now = {"t": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: now["t"])

    sw = Stopwatch()
    sw.start()
    now["t"] += 42
    sw.reset()
    assert sw.elapsed_seconds() == 0
    assert not sw.is_running
