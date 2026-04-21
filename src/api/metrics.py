"""Prometheus-метрики та middleware для Store API."""

import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

# Власний registry, щоб тести не конфліктували з глобальним.
REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS_TOTAL = Counter(
    "store_api_http_requests_total",
    "Total HTTP requests handled by Store API.",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "store_api_http_request_latency_seconds",
    "HTTP request latency in seconds, measured at Store API boundary.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

HTTP_REQUEST_ERRORS_TOTAL = Counter(
    "store_api_http_request_errors_total",
    "HTTP requests that failed before producing a response.",
    labelnames=("method", "path"),
    registry=REGISTRY,
)

SENSOR_READINGS_TOTAL = Counter(
    "urbanpulse_sensor_readings_total",
    "Number of sensor readings persisted, labelled by sensor type.",
    labelnames=("sensor_type",),
    registry=REGISTRY,
)

ANOMALY_FLAGS_TOTAL = Counter(
    "urbanpulse_sensor_anomaly_flags_total",
    "Number of edge-level anomaly flags observed on stored readings.",
    labelnames=("sensor_type", "flag"),
    registry=REGISTRY,
)

NETWORK_ANOMALIES_TOTAL = Counter(
    "urbanpulse_network_anomalies_total",
    "Number of network anomalies detected by the Z-score detector.",
    labelnames=("metric", "severity"),
    registry=REGISTRY,
)

WEBSOCKET_CONNECTIONS = Gauge(
    "urbanpulse_websocket_connections",
    "Active WebSocket connections per channel.",
    labelnames=("channel",),
    registry=REGISTRY,
)


metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Повертає поточний знімок метрик у форматі Prometheus."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """ASGI-middleware, що збирає лічильники та гістограму HTTP-запитів."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[StarletteResponse]],
    ) -> StarletteResponse:
        path = _template_path(request)
        method = request.method
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUEST_ERRORS_TOTAL.labels(method=method, path=path).inc()
            raise

        duration = time.perf_counter() - start
        HTTP_REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
        return response


def _template_path(request: Request) -> str:
    """Перетворює `request.url.path` у шаблон шляху (/sensor_readings/{id})."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    return request.url.path
