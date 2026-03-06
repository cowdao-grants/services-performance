"""
Metrics aggregation for comprehensive performance statistics.

Provides percentile calculations, summary statistics, and derived metrics
for order lifecycle, API, and resource utilization data.
"""

from dataclasses import dataclass, field

import numpy as np

from cow_performance.metrics.models import (
    OrderMetadata,
    OrderStatus,
)
from cow_performance.metrics.store import MetricsStore


@dataclass
class PercentileStats:
    """Statistical summary with percentiles."""

    count: int = 0
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    std_dev: float = 0.0

    @classmethod
    def from_values(cls, values: list[float]) -> "PercentileStats":
        """
        Calculate percentile statistics from a list of values.

        Args:
            values: List of numeric values

        Returns:
            PercentileStats instance with calculated statistics
        """
        if not values:
            return cls()

        arr = np.array(values)
        return cls(
            count=len(values),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            p50=float(np.percentile(arr, 50)),
            p90=float(np.percentile(arr, 90)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            std_dev=float(np.std(arr)),
        )


@dataclass
class OrderAggregateMetrics:
    """Aggregated order metrics with percentiles."""

    # Counts
    total_orders: int = 0
    orders_created: int = 0
    orders_submitted: int = 0
    orders_accepted: int = 0
    orders_filled: int = 0
    orders_partially_filled: int = 0
    orders_expired: int = 0
    orders_cancelled: int = 0
    orders_failed: int = 0

    # Rates
    success_rate: float = 0.0  # filled / submitted
    failure_rate: float = 0.0  # failed / submitted

    # Timing statistics with percentiles
    time_to_submit: PercentileStats = field(default_factory=PercentileStats)
    time_to_accept: PercentileStats = field(default_factory=PercentileStats)
    time_to_fill: PercentileStats = field(default_factory=PercentileStats)
    total_lifecycle: PercentileStats = field(default_factory=PercentileStats)


@dataclass
class APIAggregateMetrics:
    """Aggregated API metrics with percentiles."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0

    # Response time statistics (in milliseconds)
    response_time: PercentileStats = field(default_factory=PercentileStats)

    # By status code
    status_code_counts: dict[int, int] = field(default_factory=dict)

    # Throughput
    requests_per_second: float = 0.0


@dataclass
class ResourceAggregateMetrics:
    """Aggregated resource utilization metrics."""

    container_name: str = ""
    sample_count: int = 0

    cpu_percent: PercentileStats = field(default_factory=PercentileStats)
    memory_percent: PercentileStats = field(default_factory=PercentileStats)
    memory_bytes: PercentileStats = field(default_factory=PercentileStats)


class MetricsAggregator:
    """
    Aggregates metrics from MetricsStore with comprehensive statistics.

    Computes summary statistics including percentiles (p50, p90, p95, p99)
    for order lifecycle, API metrics, and resource utilization.

    Example:
        store = MetricsStore()
        # ... metrics collected ...
        aggregator = MetricsAggregator(store)
        order_stats = aggregator.aggregate_orders()
        api_stats = aggregator.aggregate_api_metrics()
    """

    def __init__(self, metrics_store: MetricsStore):
        """
        Initialize the aggregator.

        Args:
            metrics_store: The metrics store to aggregate from
        """
        self._store = metrics_store

    def aggregate_orders(
        self,
        orders: list[OrderMetadata] | None = None,
    ) -> OrderAggregateMetrics:
        """
        Aggregate order metrics with percentile calculations.

        Args:
            orders: Optional list of orders (uses all orders from store if None)

        Returns:
            OrderAggregateMetrics with comprehensive statistics
        """
        if orders is None:
            orders = self._store.get_all_orders()

        metrics = OrderAggregateMetrics(total_orders=len(orders))

        if not orders:
            return metrics

        # Count by status
        for order in orders:
            status = order.current_status
            if status == OrderStatus.CREATED:
                metrics.orders_created += 1
            elif status == OrderStatus.SUBMITTED:
                metrics.orders_submitted += 1
            elif status in (OrderStatus.ACCEPTED, OrderStatus.OPEN):
                metrics.orders_accepted += 1
            elif status == OrderStatus.FILLED:
                metrics.orders_filled += 1
            elif status == OrderStatus.PARTIALLY_FILLED:
                metrics.orders_partially_filled += 1
            elif status == OrderStatus.EXPIRED:
                metrics.orders_expired += 1
            elif status == OrderStatus.CANCELLED:
                metrics.orders_cancelled += 1
            elif status == OrderStatus.FAILED:
                metrics.orders_failed += 1

        # Calculate rates
        submitted = (
            metrics.orders_submitted
            + metrics.orders_accepted
            + metrics.orders_filled
            + metrics.orders_partially_filled
            + metrics.orders_expired
            + metrics.orders_cancelled
            + metrics.orders_failed
        )
        if submitted > 0:
            metrics.success_rate = metrics.orders_filled / submitted
            metrics.failure_rate = metrics.orders_failed / submitted

        # Collect timing values
        times_to_submit = [t for order in orders if (t := order.get_time_to_submit()) is not None]
        times_to_accept = [t for order in orders if (t := order.get_time_to_accept()) is not None]
        times_to_fill = [t for order in orders if (t := order.get_time_to_fill()) is not None]
        total_lifecycles = [
            t for order in orders if (t := order.get_total_lifecycle_time()) is not None
        ]

        # Calculate percentile statistics
        metrics.time_to_submit = PercentileStats.from_values(times_to_submit)
        metrics.time_to_accept = PercentileStats.from_values(times_to_accept)
        metrics.time_to_fill = PercentileStats.from_values(times_to_fill)
        metrics.total_lifecycle = PercentileStats.from_values(total_lifecycles)

        return metrics

    def aggregate_api_metrics(
        self,
        endpoint: str | None = None,
        time_range: tuple[float, float] | None = None,
    ) -> APIAggregateMetrics:
        """
        Aggregate API metrics with percentile calculations.

        Args:
            endpoint: Optional endpoint to filter by
            time_range: Optional (start, end) timestamp range to filter by

        Returns:
            APIAggregateMetrics with comprehensive statistics
        """
        api_metrics = self._store.get_api_metrics(endpoint)

        # Filter by time range if specified
        if time_range is not None:
            start_time, end_time = time_range
            api_metrics = [m for m in api_metrics if start_time <= m.timestamp <= end_time]

        metrics = APIAggregateMetrics(total_requests=len(api_metrics))

        if not api_metrics:
            return metrics

        # Count successes and failures
        for m in api_metrics:
            if m.is_success:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1

            # Count by status code
            metrics.status_code_counts[m.status_code] = (
                metrics.status_code_counts.get(m.status_code, 0) + 1
            )

        # Success rate
        if metrics.total_requests > 0:
            metrics.success_rate = metrics.successful_requests / metrics.total_requests

        # Response time statistics (convert to milliseconds)
        response_times_ms = [m.duration_ms for m in api_metrics]
        metrics.response_time = PercentileStats.from_values(response_times_ms)

        # Throughput calculation
        if len(api_metrics) >= 2:
            timestamps = sorted(m.timestamp for m in api_metrics)
            duration = timestamps[-1] - timestamps[0]
            if duration > 0:
                metrics.requests_per_second = len(api_metrics) / duration

        return metrics

    def aggregate_resource_metrics(
        self,
        container_name: str | None = None,
    ) -> dict[str, ResourceAggregateMetrics]:
        """
        Aggregate resource metrics with percentile calculations.

        Args:
            container_name: Optional container to filter by

        Returns:
            Dict mapping container name to ResourceAggregateMetrics
        """
        resource_metrics = self._store.get_resource_metrics(container_name)
        result: dict[str, ResourceAggregateMetrics] = {}

        for name, container_metrics in resource_metrics.items():
            samples = container_metrics.samples
            if not samples:
                result[name] = ResourceAggregateMetrics(
                    container_name=name,
                    sample_count=0,
                )
                continue

            cpu_values = [s.cpu_percent for s in samples]
            memory_percent_values = [s.memory_percent for s in samples]
            memory_bytes_values = [float(s.memory_bytes) for s in samples]

            result[name] = ResourceAggregateMetrics(
                container_name=name,
                sample_count=len(samples),
                cpu_percent=PercentileStats.from_values(cpu_values),
                memory_percent=PercentileStats.from_values(memory_percent_values),
                memory_bytes=PercentileStats.from_values(memory_bytes_values),
            )

        return result

    def get_summary(self) -> dict[str, object]:
        """
        Get a comprehensive summary of all metrics.

        Returns:
            Dict with order, API, and resource aggregate metrics
        """
        return {
            "orders": self.aggregate_orders(),
            "api": self.aggregate_api_metrics(),
            "resources": self.aggregate_resource_metrics(),
        }

    # --- Grouping Methods (Phase 2) ---

    def aggregate_orders_by_owner(self) -> dict[str, OrderAggregateMetrics]:
        """
        Aggregate orders grouped by owner address.

        Returns:
            Dict mapping owner address to OrderAggregateMetrics
        """
        orders = self._store.get_all_orders()
        groups: dict[str, list[OrderMetadata]] = {}

        for order in orders:
            owner = order.owner
            if owner not in groups:
                groups[owner] = []
            groups[owner].append(order)

        return {
            owner: self.aggregate_orders(orders=group_orders)
            for owner, group_orders in groups.items()
        }

    def aggregate_orders_by_token_pair(self) -> dict[str, OrderAggregateMetrics]:
        """
        Aggregate orders grouped by token pair.

        Returns:
            Dict mapping "sell_token->buy_token" to OrderAggregateMetrics
        """
        orders = self._store.get_all_orders()
        groups: dict[str, list[OrderMetadata]] = {}

        for order in orders:
            pair_key = f"{order.sell_token}->{order.buy_token}"
            if pair_key not in groups:
                groups[pair_key] = []
            groups[pair_key].append(order)

        return {
            pair: self.aggregate_orders(orders=group_orders)
            for pair, group_orders in groups.items()
        }

    def aggregate_orders_by_time_window(
        self,
        window_seconds: float = 60.0,
    ) -> list[tuple[float, float, OrderAggregateMetrics]]:
        """
        Aggregate orders grouped by time windows.

        Args:
            window_seconds: Size of each time window in seconds

        Returns:
            List of (start_time, end_time, OrderAggregateMetrics) tuples
        """
        orders = self._store.get_all_orders()
        if not orders:
            return []

        # Find time range
        timestamps = [o.creation_time for o in orders]
        min_time = min(timestamps)
        max_time = max(timestamps)

        # Create windows
        windows: list[tuple[float, float, OrderAggregateMetrics]] = []
        current_start = min_time

        while current_start < max_time:
            current_end = current_start + window_seconds
            window_orders = [o for o in orders if current_start <= o.creation_time < current_end]

            if window_orders:
                metrics = self.aggregate_orders(orders=window_orders)
                windows.append((current_start, current_end, metrics))

            current_start = current_end

        return windows

    def aggregate_api_metrics_by_endpoint(self) -> dict[str, APIAggregateMetrics]:
        """
        Aggregate API metrics grouped by endpoint.

        Returns:
            Dict mapping endpoint to APIAggregateMetrics
        """
        endpoints = self._store.get_api_endpoints()
        return {endpoint: self.aggregate_api_metrics(endpoint=endpoint) for endpoint in endpoints}

    def aggregate_api_metrics_by_time_window(
        self,
        window_seconds: float = 60.0,
    ) -> list[tuple[float, float, APIAggregateMetrics]]:
        """
        Aggregate API metrics grouped by time windows.

        Args:
            window_seconds: Size of each time window in seconds

        Returns:
            List of (start_time, end_time, APIAggregateMetrics) tuples
        """
        api_metrics = self._store.get_api_metrics()
        if not api_metrics:
            return []

        # Find time range
        timestamps = [m.timestamp for m in api_metrics]
        min_time = min(timestamps)
        max_time = max(timestamps)

        # Create windows
        windows: list[tuple[float, float, APIAggregateMetrics]] = []
        current_start = min_time

        while current_start < max_time:
            current_end = current_start + window_seconds
            metrics = self.aggregate_api_metrics(time_range=(current_start, current_end))

            if metrics.total_requests > 0:
                windows.append((current_start, current_end, metrics))

            current_start = current_end

        return windows

    def calculate_throughput(
        self,
        window_seconds: float = 1.0,
    ) -> dict[str, float]:
        """
        Calculate throughput metrics.

        Args:
            window_seconds: Time window for rate calculation (unused, for API compat)

        Returns:
            Dict with throughput metrics (orders_per_second, api_requests_per_second)
        """
        orders = self._store.get_all_orders()
        api_metrics = self._store.get_api_metrics()

        result: dict[str, float] = {
            "orders_per_second": 0.0,
            "api_requests_per_second": 0.0,
        }

        # Orders per second
        if len(orders) >= 2:
            timestamps = sorted(o.creation_time for o in orders)
            duration = timestamps[-1] - timestamps[0]
            if duration > 0:
                result["orders_per_second"] = len(orders) / duration

        # API requests per second
        if len(api_metrics) >= 2:
            timestamps = sorted(m.timestamp for m in api_metrics)
            duration = timestamps[-1] - timestamps[0]
            if duration > 0:
                result["api_requests_per_second"] = len(api_metrics) / duration

        return result
