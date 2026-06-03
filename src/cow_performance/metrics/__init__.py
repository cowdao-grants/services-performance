"""
Metrics collection framework for CoW Protocol performance testing.

This module provides data models, storage, and export functionality for
capturing and analyzing performance metrics during load testing.

Models:
    - OrderStatus: Order lifecycle states
    - OrderMetadata: Individual order tracking with timestamps
    - OrderMetrics: Aggregate order statistics (basic)
    - APIMetrics: HTTP request/response timing
    - ResourceSample: Point-in-time container resource snapshot
    - ResourceMetrics: Aggregated container resource metrics
    - TestRunMetrics: Complete test run summary

Aggregation:
    - MetricsAggregator: Comprehensive statistics with percentiles
    - PercentileStats: Statistical summary with p50/p90/p95/p99
    - OrderAggregateMetrics: Order metrics with timing percentiles
    - APIAggregateMetrics: API metrics with response time percentiles
    - ResourceAggregateMetrics: Resource metrics with CPU/memory percentiles

Streaming:
    - MetricsEventStream: Async event stream for real-time monitoring
    - MetricEvent: Single metric event for streaming
    - MetricEventType: Types of metric events (order, api, resource)
    - RollingMetricsSummary: Rolling window summary for live dashboards

Storage:
    - MetricsStore: Thread-safe in-memory metrics storage
    - MetricsStoreConfig: Configuration for storage limits

Expiration Tracking:
    - ExpirationChecker: Background task to track order expiration

Export:
    - export_store_to_json: Export full store to JSON
    - export_orders_to_csv: Export orders to CSV
    - export_api_metrics_to_csv: Export API metrics to CSV
    - save_metrics_to_file: Save to file with format selection
"""

from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    MetricsAggregator,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)
from cow_performance.metrics.expiration_checker import ExpirationChecker
from cow_performance.metrics.export import (
    api_metrics_to_dict,
    export_api_metrics_to_csv,
    export_orders_to_csv,
    export_store_to_json,
    order_metadata_to_dict,
    resource_metrics_to_dict,
    save_metrics_to_file,
    test_run_metrics_to_dict,
)
from cow_performance.metrics.models import (
    APIMetrics,
    OrderMetadata,
    OrderMetrics,
    OrderStatus,
    ResourceMetrics,
    ResourceSample,
    TestRunMetrics,
)
from cow_performance.metrics.store import MetricsStore, MetricsStoreConfig
from cow_performance.metrics.streaming import (
    MetricEvent,
    MetricEventType,
    MetricsEventStream,
    RollingMetricsSummary,
)

__all__ = [
    # Models
    "OrderStatus",
    "OrderMetadata",
    "OrderMetrics",
    "APIMetrics",
    "ResourceSample",
    "ResourceMetrics",
    "TestRunMetrics",
    # Aggregation
    "MetricsAggregator",
    "PercentileStats",
    "OrderAggregateMetrics",
    "APIAggregateMetrics",
    "ResourceAggregateMetrics",
    # Streaming
    "MetricsEventStream",
    "MetricEvent",
    "MetricEventType",
    "RollingMetricsSummary",
    # Storage
    "MetricsStore",
    "MetricsStoreConfig",
    # Expiration Tracking
    "ExpirationChecker",
    # Export
    "export_store_to_json",
    "export_orders_to_csv",
    "export_api_metrics_to_csv",
    "save_metrics_to_file",
    "order_metadata_to_dict",
    "api_metrics_to_dict",
    "resource_metrics_to_dict",
    "test_run_metrics_to_dict",
]
