"""Фоновий аналізатор мережевих метрик і детектор аномалій."""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from prometheus_client.metrics import Counter, Histogram
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.api.metrics import (
    HTTP_REQUEST_ERRORS_TOTAL,
    HTTP_REQUEST_LATENCY_SECONDS,
    HTTP_REQUESTS_TOTAL,
    NETWORK_ANOMALIES_TOTAL,
)
from src.core.config import settings
from src.core.logger import logger
from src.db.base import async_session_factory
from src.db.orm_models import NetworkAnomalyORM


@dataclass
class _Series:
    """Стан ковзної статистики однієї метрики на базі EWMA."""

    name: str
    alpha: float = 0.2  # Експоненційне згладжування, приблизно 5 останніх вікон.
    mean: float | None = None
    variance: float = 0.0
    samples: list[float] = field(default_factory=list)

    def update(self, value: float) -> float:
        """Оновлює стан і повертає |z-score|. `nan`, якщо замало даних."""
        self.samples.append(value)
        if self.mean is None:
            self.mean = value
            self.variance = 0.0
            return math.nan

        previous_mean = self.mean
        previous_variance = self.variance
        previous_std = math.sqrt(previous_variance) if previous_variance > 0 else 0.0
        zscore = 0.0 if previous_std == 0.0 else abs(value - previous_mean) / previous_std

        delta = value - previous_mean
        self.mean = previous_mean + self.alpha * delta
        self.variance = (1 - self.alpha) * (previous_variance + self.alpha * delta * delta)
        return zscore


class NetworkAnomalyDetector:
    """Фоновий детектор мережевих аномалій."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker | None = None,
        window_seconds: float | None = None,
        zscore_threshold: float | None = None,
        min_samples: int | None = None,
    ) -> None:
        self._session_factory = session_factory or async_session_factory
        self._window_seconds = window_seconds or settings.network_anomaly_window_seconds
        self._threshold = zscore_threshold or settings.network_anomaly_zscore_threshold
        self._min_samples = min_samples or settings.network_anomaly_min_samples

        self._series: dict[str, _Series] = {
            "latency_p95_ms": _Series("latency_p95_ms"),
            "request_rate_rps": _Series("request_rate_rps"),
            "error_rate": _Series("error_rate"),
        }
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_snapshot: dict[str, float] = {
            "requests_total": 0.0,
            "errors_total": 0.0,
        }

    async def start(self) -> None:
        """Запускає фоновий цикл детектора."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"Network anomaly detector: window={self._window_seconds}s, "
            f"z>={self._threshold}, min_samples={self._min_samples}"
        )

    async def stop(self) -> None:
        """Зупиняє фоновий цикл детектора та очікує завершення task."""
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        """Періодично опитує метрики та запускає один крок детекції."""
        while self._running:
            try:
                await asyncio.sleep(self._window_seconds)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Network anomaly detector: помилка в циклі")

    async def _tick(self) -> None:
        """Знімає поточні метрики, оновлює EWMA та фіксує аномальні події."""
        values = self._sample_metrics()
        now = datetime.now(UTC).replace(tzinfo=None)

        for name, value in values.items():
            series = self._series[name]
            zscore = series.update(value)

            if math.isnan(zscore) or len(series.samples) < self._min_samples:
                continue
            if zscore < self._threshold:
                continue

            severity = _severity_for(zscore, self._threshold)
            mean = series.mean if series.mean is not None else 0.0
            std = math.sqrt(series.variance) if series.variance > 0 else 0.0
            NETWORK_ANOMALIES_TOTAL.labels(metric=name, severity=severity).inc()
            logger.warning(
                f"Network anomaly: {name}={value:.4f}, mean={mean:.4f}, std={std:.4f}, z={zscore:.2f}, {severity}"
            )

            try:
                await self._persist(
                    timestamp=now,
                    metric=name,
                    value=value,
                    mean=mean,
                    std=std,
                    zscore=zscore,
                    severity=severity,
                )
            except Exception:
                logger.exception("Network anomaly detector: не вдалося записати подію у БД")

    def _sample_metrics(self) -> dict[str, float]:
        """Рахує поточні значення метрик зі стану Prometheus collector-ів."""
        latency_p95_ms = _histogram_quantile(HTTP_REQUEST_LATENCY_SECONDS, 0.95) * 1000.0

        requests_total = _counter_sum(HTTP_REQUESTS_TOTAL)
        errors_total = _counter_sum(HTTP_REQUEST_ERRORS_TOTAL)

        prev_requests = self._last_snapshot["requests_total"]
        prev_errors = self._last_snapshot["errors_total"]
        self._last_snapshot["requests_total"] = requests_total
        self._last_snapshot["errors_total"] = errors_total

        delta_requests = max(0.0, requests_total - prev_requests)
        delta_errors = max(0.0, errors_total - prev_errors)

        request_rate_rps = delta_requests / self._window_seconds if self._window_seconds > 0 else 0.0
        error_rate = (delta_errors / delta_requests) if delta_requests > 0 else 0.0

        return {
            "latency_p95_ms": latency_p95_ms,
            "request_rate_rps": request_rate_rps,
            "error_rate": error_rate,
        }

    async def _persist(
        self,
        *,
        timestamp: datetime,
        metric: str,
        value: float,
        mean: float,
        std: float,
        zscore: float,
        severity: str,
    ) -> None:
        """Зберігає виявлену мережеву аномалію в PostgreSQL."""
        session_factory = cast(async_sessionmaker, self._session_factory)
        async with session_factory() as session:
            row = NetworkAnomalyORM(
                timestamp=timestamp,
                metric=metric,
                value=value,
                baseline_mean=mean,
                baseline_std=std,
                zscore=zscore,
                severity=severity,
            )
            session.add(row)
            await session.commit()


def _severity_for(zscore: float, threshold: float) -> str:
    """Класифікує серйозність інциденту за величиною z-score."""
    if zscore >= threshold * 2.0:
        return "critical"
    if zscore >= threshold * 1.5:
        return "major"
    return "minor"


def _counter_sum(counter: Counter) -> float:
    """Підсумовує значення за всіма labels-наборами Counter."""
    total = 0.0
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total += sample.value
    return total


def _histogram_quantile(histogram: Histogram, quantile: float) -> float:
    """Агрегує Histogram по всіх labels та повертає апроксимований квантиль (в секундах).

    Простий підхід: сумуємо buckets, знаходимо bucket, де перетинаємо `quantile`,
    і робимо лінійну інтерполяцію всередині bucket-а (як у `histogram_quantile`
    Prometheus). Для Grafana краще рахувати те саме PromQL-ом — тут лише для
    локального детектора.
    """
    bucket_totals: dict[float, float] = {}
    total_count = 0.0

    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name.endswith("_bucket"):
                le_raw = sample.labels.get("le")
                if le_raw is None:
                    continue
                le = float("inf") if le_raw == "+Inf" else float(le_raw)
                bucket_totals[le] = bucket_totals.get(le, 0.0) + sample.value
            elif sample.name.endswith("_count"):
                total_count += sample.value

    if total_count == 0 or not bucket_totals:
        return 0.0

    target = quantile * total_count
    sorted_bounds = sorted(bucket_totals.keys())
    prev_cum = 0.0
    prev_bound = 0.0
    for bound in sorted_bounds:
        cum = bucket_totals[bound]
        if cum >= target:
            if math.isinf(bound):
                return prev_bound
            span = bound - prev_bound
            fraction = (target - prev_cum) / (cum - prev_cum) if cum > prev_cum else 0.0
            return prev_bound + span * fraction
        prev_cum = cum
        prev_bound = bound

    return prev_bound
