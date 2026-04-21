"""Тести для локального детектора мережевих аномалій."""

import math
from typing import Any, cast

import pytest
from prometheus_client import CollectorRegistry, Histogram

from src.api.network_analytics import (
    NetworkAnomalyDetector,
    _histogram_quantile,
    _Series,
    _severity_for,
)


class TestSeries:
    def test_first_sample_returns_nan(self) -> None:
        series = _Series(name="m")
        assert math.isnan(series.update(100.0))

    def test_converges_toward_mean(self) -> None:
        series = _Series(name="m", alpha=0.2)
        # Подаємо стабільний сигнал, тож mean має збігтися до 10.
        for _ in range(50):
            series.update(10.0)
        assert series.mean is not None
        assert abs(series.mean - 10.0) < 0.01
        assert math.sqrt(series.variance) < 0.01

    def test_detects_outlier(self) -> None:
        series = _Series(name="m", alpha=0.2)
        for _ in range(30):
            series.update(10.0)
        # Додаємо невеликий природний шум перед великим викидом.
        for v in [10.1, 9.9, 10.2, 9.8, 10.0]:
            series.update(v)
        z = series.update(200.0)
        assert z > 3.0


class TestSeverity:
    def test_minor(self) -> None:
        assert _severity_for(3.1, threshold=3.0) == "minor"

    def test_major(self) -> None:
        assert _severity_for(4.6, threshold=3.0) == "major"

    def test_critical(self) -> None:
        assert _severity_for(6.1, threshold=3.0) == "critical"


class TestHistogramQuantile:
    def test_returns_zero_when_empty(self) -> None:
        registry = CollectorRegistry()
        hist = Histogram("test_empty", "t", buckets=(0.1, 0.5, 1.0), registry=registry)
        assert _histogram_quantile(hist, 0.95) == 0.0

    def test_quantile_with_samples(self) -> None:
        registry = CollectorRegistry()
        hist = Histogram("test_h", "t", buckets=(0.1, 0.5, 1.0, 5.0), registry=registry)
        # 100 швидких спостережень і 5 повільних.
        for _ in range(100):
            hist.observe(0.05)
        for _ in range(5):
            hist.observe(2.0)
        p95 = _histogram_quantile(hist, 0.95)
        # p95 має залишитися у діапазоні «швидких» bucket-ів.
        assert 0.0 < p95 <= 0.1
        p99 = _histogram_quantile(hist, 0.99)
        assert p99 >= p95


class TestDetectorLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop_are_idempotent(self) -> None:
        detector = NetworkAnomalyDetector(
            session_factory=cast(Any, lambda: None),
            window_seconds=3600,
        )
        await detector.start()
        await detector.start()
        await detector.stop()
        await detector.stop()
