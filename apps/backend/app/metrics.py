"""Helpers for emitting structured operational metrics via logging."""

from __future__ import annotations

import logging

_metrics_logger = logging.getLogger("app.metrics")


def increment_location_estimate_requests(source: str) -> None:
    """Emit a counter metric for served location estimate requests."""

    _metrics_logger.info(
        "location estimate response served",
        extra={
            "event_dataset": "zoo-tracker-api.metrics",
            "event_action": "location_estimate_request",
            "metric_name": "location_estimate_requests_total",
            "metric_type": "counter",
            "metric_value": 1,
            "location_source": source,
        },
    )


__all__ = ["increment_location_estimate_requests"]
