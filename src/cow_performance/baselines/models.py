"""Data models for performance baselines."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)

SCHEMA_VERSION = "1.0"


@dataclass
class PerformanceBaseline:
    """Complete baseline snapshot with all metrics and metadata."""

    # Identification
    id: str  # UUID
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    schema_version: str = SCHEMA_VERSION

    # Git Information
    git_commit: str | None = None
    git_branch: str | None = None
    git_repo: str | None = None
    has_uncommitted_changes: bool = False

    # Test Configuration
    scenario_name: str = ""
    duration_seconds: float = 0.0
    num_traders: int = 0
    test_config: dict[str, Any] = field(default_factory=dict)

    # Environment
    python_version: str = ""
    platform: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)

    # Aggregated Metrics
    order_metrics: OrderAggregateMetrics | None = None
    api_metrics: APIAggregateMetrics | None = None
    resource_metrics: dict[str, ResourceAggregateMetrics] = field(default_factory=dict)

    # Throughput
    orders_per_second: float = 0.0
    peak_orders_per_second: float = 0.0


@dataclass
class BaselineMetadata:
    """Lightweight baseline info for index entries."""

    id: str
    name: str
    tags: list[str]
    git_commit: str | None
    git_branch: str | None
    created_at: float
    orders_per_second: float  # Key metric for quick comparison


def percentile_stats_to_dict(stats: PercentileStats) -> dict[str, Any]:
    """Serialize PercentileStats to dict."""
    return asdict(stats)


def percentile_stats_from_dict(data: dict[str, Any]) -> PercentileStats:
    """Deserialize PercentileStats from dict."""
    return PercentileStats(**data)


def order_aggregate_to_dict(metrics: OrderAggregateMetrics) -> dict[str, Any]:
    """Serialize OrderAggregateMetrics to dict."""
    return {
        "total_orders": metrics.total_orders,
        "orders_created": metrics.orders_created,
        "orders_submitted": metrics.orders_submitted,
        "orders_accepted": metrics.orders_accepted,
        "orders_filled": metrics.orders_filled,
        "orders_partially_filled": metrics.orders_partially_filled,
        "orders_expired": metrics.orders_expired,
        "orders_cancelled": metrics.orders_cancelled,
        "orders_failed": metrics.orders_failed,
        "success_rate": metrics.success_rate,
        "failure_rate": metrics.failure_rate,
        "time_to_submit": percentile_stats_to_dict(metrics.time_to_submit),
        "time_to_accept": percentile_stats_to_dict(metrics.time_to_accept),
        "time_to_fill": percentile_stats_to_dict(metrics.time_to_fill),
        "total_lifecycle": percentile_stats_to_dict(metrics.total_lifecycle),
    }


def order_aggregate_from_dict(data: dict[str, Any]) -> OrderAggregateMetrics:
    """Deserialize OrderAggregateMetrics from dict."""
    return OrderAggregateMetrics(
        total_orders=data.get("total_orders", 0),
        orders_created=data.get("orders_created", 0),
        orders_submitted=data.get("orders_submitted", 0),
        orders_accepted=data.get("orders_accepted", 0),
        orders_filled=data.get("orders_filled", 0),
        orders_partially_filled=data.get("orders_partially_filled", 0),
        orders_expired=data.get("orders_expired", 0),
        orders_cancelled=data.get("orders_cancelled", 0),
        orders_failed=data.get("orders_failed", 0),
        success_rate=data.get("success_rate", 0.0),
        failure_rate=data.get("failure_rate", 0.0),
        time_to_submit=percentile_stats_from_dict(data.get("time_to_submit", {})),
        time_to_accept=percentile_stats_from_dict(data.get("time_to_accept", {})),
        time_to_fill=percentile_stats_from_dict(data.get("time_to_fill", {})),
        total_lifecycle=percentile_stats_from_dict(data.get("total_lifecycle", {})),
    )


def api_aggregate_to_dict(metrics: APIAggregateMetrics) -> dict[str, Any]:
    """Serialize APIAggregateMetrics to dict."""
    return {
        "total_requests": metrics.total_requests,
        "successful_requests": metrics.successful_requests,
        "failed_requests": metrics.failed_requests,
        "success_rate": metrics.success_rate,
        "response_time": percentile_stats_to_dict(metrics.response_time),
        "status_code_counts": metrics.status_code_counts,
        "requests_per_second": metrics.requests_per_second,
    }


def api_aggregate_from_dict(data: dict[str, Any]) -> APIAggregateMetrics:
    """Deserialize APIAggregateMetrics from dict."""
    return APIAggregateMetrics(
        total_requests=data.get("total_requests", 0),
        successful_requests=data.get("successful_requests", 0),
        failed_requests=data.get("failed_requests", 0),
        success_rate=data.get("success_rate", 0.0),
        response_time=percentile_stats_from_dict(data.get("response_time", {})),
        status_code_counts=data.get("status_code_counts", {}),
        requests_per_second=data.get("requests_per_second", 0.0),
    )


def resource_aggregate_to_dict(metrics: ResourceAggregateMetrics) -> dict[str, Any]:
    """Serialize ResourceAggregateMetrics to dict."""
    return {
        "container_name": metrics.container_name,
        "sample_count": metrics.sample_count,
        "cpu_percent": percentile_stats_to_dict(metrics.cpu_percent),
        "memory_percent": percentile_stats_to_dict(metrics.memory_percent),
        "memory_bytes": percentile_stats_to_dict(metrics.memory_bytes),
    }


def resource_aggregate_from_dict(data: dict[str, Any]) -> ResourceAggregateMetrics:
    """Deserialize ResourceAggregateMetrics from dict."""
    return ResourceAggregateMetrics(
        container_name=data.get("container_name", ""),
        sample_count=data.get("sample_count", 0),
        cpu_percent=percentile_stats_from_dict(data.get("cpu_percent", {})),
        memory_percent=percentile_stats_from_dict(data.get("memory_percent", {})),
        memory_bytes=percentile_stats_from_dict(data.get("memory_bytes", {})),
    )


def baseline_to_dict(baseline: PerformanceBaseline) -> dict[str, Any]:
    """Serialize PerformanceBaseline to dict for JSON storage."""
    result: dict[str, Any] = {
        # Identification
        "id": baseline.id,
        "name": baseline.name,
        "description": baseline.description,
        "tags": baseline.tags,
        "created_at": baseline.created_at,
        "schema_version": baseline.schema_version,
        # Git
        "git_commit": baseline.git_commit,
        "git_branch": baseline.git_branch,
        "git_repo": baseline.git_repo,
        "has_uncommitted_changes": baseline.has_uncommitted_changes,
        # Test config
        "scenario_name": baseline.scenario_name,
        "duration_seconds": baseline.duration_seconds,
        "num_traders": baseline.num_traders,
        "test_config": baseline.test_config,
        # Environment
        "python_version": baseline.python_version,
        "platform": baseline.platform,
        "dependencies": baseline.dependencies,
        # Throughput
        "orders_per_second": baseline.orders_per_second,
        "peak_orders_per_second": baseline.peak_orders_per_second,
    }

    # Metrics (can be None)
    if baseline.order_metrics is not None:
        result["order_metrics"] = order_aggregate_to_dict(baseline.order_metrics)
    else:
        result["order_metrics"] = None

    if baseline.api_metrics is not None:
        result["api_metrics"] = api_aggregate_to_dict(baseline.api_metrics)
    else:
        result["api_metrics"] = None

    # Resource metrics (dict)
    result["resource_metrics"] = {
        name: resource_aggregate_to_dict(metrics)
        for name, metrics in baseline.resource_metrics.items()
    }

    return result


def baseline_from_dict(data: dict[str, Any]) -> PerformanceBaseline:
    """Deserialize PerformanceBaseline from dict."""
    # Parse order_metrics
    order_metrics = None
    if data.get("order_metrics") is not None:
        order_metrics = order_aggregate_from_dict(data["order_metrics"])

    # Parse api_metrics
    api_metrics = None
    if data.get("api_metrics") is not None:
        api_metrics = api_aggregate_from_dict(data["api_metrics"])

    # Parse resource_metrics
    resource_metrics = {}
    for name, metrics_data in data.get("resource_metrics", {}).items():
        resource_metrics[name] = resource_aggregate_from_dict(metrics_data)

    return PerformanceBaseline(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        tags=data.get("tags", []),
        created_at=data.get("created_at", 0.0),
        schema_version=data.get("schema_version", SCHEMA_VERSION),
        git_commit=data.get("git_commit"),
        git_branch=data.get("git_branch"),
        git_repo=data.get("git_repo"),
        has_uncommitted_changes=data.get("has_uncommitted_changes", False),
        scenario_name=data.get("scenario_name", ""),
        duration_seconds=data.get("duration_seconds", 0.0),
        num_traders=data.get("num_traders", 0),
        test_config=data.get("test_config", {}),
        python_version=data.get("python_version", ""),
        platform=data.get("platform", ""),
        dependencies=data.get("dependencies", {}),
        order_metrics=order_metrics,
        api_metrics=api_metrics,
        resource_metrics=resource_metrics,
        orders_per_second=data.get("orders_per_second", 0.0),
        peak_orders_per_second=data.get("peak_orders_per_second", 0.0),
    )


def metadata_to_dict(metadata: BaselineMetadata) -> dict[str, Any]:
    """Serialize BaselineMetadata to dict."""
    return asdict(metadata)


def metadata_from_dict(data: dict[str, Any]) -> BaselineMetadata:
    """Deserialize BaselineMetadata from dict."""
    return BaselineMetadata(
        id=data["id"],
        name=data["name"],
        tags=data.get("tags", []),
        git_commit=data.get("git_commit"),
        git_branch=data.get("git_branch"),
        created_at=data.get("created_at", 0.0),
        orders_per_second=data.get("orders_per_second", 0.0),
    )
