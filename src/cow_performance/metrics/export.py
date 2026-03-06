"""
Export utilities for metrics data.

Provides functions to serialize metrics to JSON and CSV formats,
following the existing output.py patterns.
"""

import csv
import json
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from typing import Any

from cow_performance.metrics.models import (
    APIMetrics,
    OrderMetadata,
    ResourceMetrics,
    TestRunMetrics,
)
from cow_performance.metrics.store import MetricsStore


def order_metadata_to_dict(metadata: OrderMetadata) -> dict[str, Any]:
    """
    Convert OrderMetadata to a serializable dictionary.

    Args:
        metadata: The order metadata to convert

    Returns:
        Dictionary representation
    """
    return {
        "order_uid": metadata.order_uid,
        "owner": metadata.owner,
        "creation_time": metadata.creation_time,
        "submission_time": metadata.submission_time,
        "acceptance_time": metadata.acceptance_time,
        "first_fill_time": metadata.first_fill_time,
        "completion_time": metadata.completion_time,
        "current_status": metadata.current_status.value,
        "sell_token": metadata.sell_token,
        "buy_token": metadata.buy_token,
        "sell_amount": metadata.sell_amount,
        "buy_amount": metadata.buy_amount,
        "filled_amount": metadata.filled_amount,
        "error_message": metadata.error_message,
        # Calculated durations
        "time_to_submit": metadata.get_time_to_submit(),
        "time_to_accept": metadata.get_time_to_accept(),
        "time_to_fill": metadata.get_time_to_fill(),
        "total_lifecycle_time": metadata.get_total_lifecycle_time(),
    }


def api_metrics_to_dict(metric: APIMetrics) -> dict[str, Any]:
    """
    Convert APIMetrics to a serializable dictionary.

    Args:
        metric: The API metric to convert

    Returns:
        Dictionary representation
    """
    return asdict(metric)


def resource_metrics_to_dict(metrics: ResourceMetrics) -> dict[str, Any]:
    """
    Convert ResourceMetrics to a serializable dictionary.

    Args:
        metrics: The resource metrics to convert

    Returns:
        Dictionary representation with samples and aggregates
    """
    return {
        "container_name": metrics.container_name,
        "sample_count": len(metrics.samples),
        "avg_cpu_percent": metrics.avg_cpu_percent,
        "max_cpu_percent": metrics.max_cpu_percent,
        "avg_memory_percent": metrics.avg_memory_percent,
        "max_memory_bytes": metrics.max_memory_bytes,
        "samples": [asdict(s) for s in metrics.samples],
    }


def test_run_metrics_to_dict(metrics: TestRunMetrics) -> dict[str, Any]:
    """
    Convert TestRunMetrics to a serializable dictionary.

    Args:
        metrics: The test run metrics to convert

    Returns:
        Dictionary representation
    """
    result = asdict(metrics)
    result["test_duration"] = metrics.test_duration
    result["success_rate"] = metrics.success_rate
    return result


def export_store_to_json(store: MetricsStore, pretty: bool = True) -> str:
    """
    Export entire MetricsStore to JSON string.

    Args:
        store: The metrics store to export
        pretty: Whether to pretty-print (default True)

    Returns:
        JSON string representation
    """
    data = {
        "orders": [order_metadata_to_dict(o) for o in store.get_all_orders()],
        "api_metrics": {
            endpoint: [api_metrics_to_dict(m) for m in store.get_api_metrics(endpoint)]
            for endpoint in store.get_api_endpoints()
        },
        "resource_metrics": {
            name: resource_metrics_to_dict(metrics)
            for name, metrics in store.get_resource_metrics().items()
        },
        "summary": store.summary(),
    }

    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)


def export_orders_to_csv(store: MetricsStore) -> str:
    """
    Export order metrics to CSV string.

    Args:
        store: The metrics store to export

    Returns:
        CSV string representation
    """
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "order_uid",
            "owner",
            "status",
            "creation_time",
            "submission_time",
            "acceptance_time",
            "completion_time",
            "time_to_submit",
            "time_to_accept",
            "time_to_fill",
            "total_lifecycle_time",
            "sell_token",
            "buy_token",
            "sell_amount",
            "buy_amount",
            "filled_amount",
            "error_message",
        ]
    )

    # Data rows
    for order in store.get_all_orders():
        writer.writerow(
            [
                order.order_uid,
                order.owner,
                order.current_status.value,
                order.creation_time,
                order.submission_time,
                order.acceptance_time,
                order.completion_time,
                order.get_time_to_submit(),
                order.get_time_to_accept(),
                order.get_time_to_fill(),
                order.get_total_lifecycle_time(),
                order.sell_token,
                order.buy_token,
                order.sell_amount,
                order.buy_amount,
                order.filled_amount,
                order.error_message,
            ]
        )

    return output.getvalue()


def export_api_metrics_to_csv(store: MetricsStore) -> str:
    """
    Export API metrics to CSV string.

    Args:
        store: The metrics store to export

    Returns:
        CSV string representation
    """
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "endpoint",
            "method",
            "timestamp",
            "duration_ms",
            "status_code",
            "is_success",
            "payload_size",
            "response_size",
            "error_message",
        ]
    )

    # Data rows
    for metric in store.get_api_metrics():
        writer.writerow(
            [
                metric.endpoint,
                metric.method,
                metric.timestamp,
                metric.duration_ms,
                metric.status_code,
                metric.is_success,
                metric.payload_size,
                metric.response_size,
                metric.error_message,
            ]
        )

    return output.getvalue()


def save_metrics_to_file(
    store: MetricsStore,
    output_path: Path,
    format: str = "json",
) -> None:
    """
    Save metrics store to file.

    Args:
        store: The metrics store to export
        output_path: Path where to save the file
        format: Output format ("json", "csv_orders", "csv_api")

    Raises:
        ValueError: If format is not supported
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        content = export_store_to_json(store)
    elif format == "csv_orders":
        content = export_orders_to_csv(store)
    elif format == "csv_api":
        content = export_api_metrics_to_csv(store)
    else:
        raise ValueError(f"Unsupported format: {format}. " f"Supported: json, csv_orders, csv_api")

    with open(output_path, "w") as f:
        f.write(content)
