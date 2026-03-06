# COW-611: Analysis - Aggregation & Real-time Updates Implementation Plan

## Overview

Implement metrics aggregation for comprehensive summary statistics and real-time streaming for live monitoring. This is the third and final sub-task (COW-611) of COW-587 (Metrics Collection Framework), building upon the foundation (COW-609) and collection (COW-610) layers.

## Current State Analysis

### What Exists (from COW-609 and COW-610)

- **MetricsStore** (`metrics/store.py`): Thread-safe storage with callback hooks already implemented for COW-611
  - `register_callback()` / `unregister_callback()` ready for streaming
  - `_notify_callbacks()` called on every `add_order()`, `add_api_metric()`, `add_resource_sample()`
- **OrderTracker.get_metrics()** (`load_generation/order_tracker.py:289-341`): Calculates **only simple averages** currently
- **OrderMetrics** (`metrics/models.py:129-151`): Has avg_* fields but **no percentile fields**
- **CLI output** (`cli/output.py:169-174`): Already has **placeholders expecting p50, p95, p99 latencies**
- **Dependencies**: `numpy` and `scipy` already in `pyproject.toml` for efficient percentile calculations
- **Rich Progress**: Already used in `run.py:316-338` for spinner during tests

### What's Missing (COW-611 Deliverables)

1. **MetricsAggregator class** - No dedicated aggregation component
2. **Percentile calculations** (p50, p95, p99) - Only averages exist
3. **Grouping by dimensions** (time window, order type, token pair, trader)
4. **Real-time streaming** - Callback hooks exist but unused
5. **CLI progress integration** - Only spinner, no live metrics display
6. **External metrics events** - No event emission mechanism

### Key Discoveries

- CLI output.py already expects `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms` in `metrics["performance"]` (line 169-174)
- numpy is available for efficient percentile calculations
- Rich `Live` display can replace `Progress` for real-time metrics (not currently used)
- OrderMetadata has `sell_token`, `buy_token`, `owner` fields for grouping

## Desired End State

After this plan is complete:

1. **MetricsAggregator** calculates comprehensive statistics including percentiles
2. **Grouping support** by time window, order type, token pair, and trader
3. **Real-time streaming** using existing MetricsStore callback hooks
4. **CLI Live display** showing metrics updates during test execution
5. **Performance metrics** populated with percentiles in run.py output
6. **Unit tests** for all new components

### Verification

```bash
# All tests pass
poetry run pytest tests/unit/test_metrics_aggregator.py tests/unit/test_realtime_streaming.py -v

# Linting passes
poetry run ruff check src/cow_performance/metrics/

# Type checking passes
poetry run mypy src/cow_performance/metrics/

# Existing tests still pass
poetry run pytest tests/unit/ -v

# Full lint workflow
poetry run black src/ tests/ && poetry run ruff check --fix src/ tests/ && poetry run mypy src/
```

## What We're NOT Doing

- **Prometheus exporters**: Part of M3 milestone
- **External webhook/HTTP streaming**: Out of scope, callbacks are in-process only
- **Persistent storage**: Metrics remain in-memory only
- **Historical analysis**: No time-series database integration
- **Complex windowing algorithms**: Simple time-based bucketing only

## Implementation Approach

We'll implement in 4 phases, each resulting in a working, testable increment:

1. **Phase 1**: MetricsAggregator with percentile calculations
2. **Phase 2**: Grouping and dimensional aggregation
3. **Phase 3**: Real-time streaming with MetricsEventStream
4. **Phase 4**: CLI integration with Rich Live display

---

## Phase 1: MetricsAggregator with Percentile Calculations

### Overview

Create a `MetricsAggregator` class that computes comprehensive statistics including percentiles (p50, p95, p99) for order lifecycle, API metrics, and resource utilization.

### Changes Required

#### 1. Create aggregator module

**File**: `src/cow_performance/metrics/aggregator.py`

```python
"""
Metrics aggregation for comprehensive performance statistics.

Provides percentile calculations, summary statistics, and derived metrics
for order lifecycle, API, and resource utilization data.
"""

from dataclasses import dataclass, field

import numpy as np

from cow_performance.metrics.models import (
    APIMetrics,
    OrderMetadata,
    OrderStatus,
    ResourceMetrics,
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
        times_to_submit = [
            t for order in orders if (t := order.get_time_to_submit()) is not None
        ]
        times_to_accept = [
            t for order in orders if (t := order.get_time_to_accept()) is not None
        ]
        times_to_fill = [
            t for order in orders if (t := order.get_time_to_fill()) is not None
        ]
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
            api_metrics = [
                m for m in api_metrics
                if start_time <= m.timestamp <= end_time
            ]

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
```

#### 2. Update metrics __init__.py exports

**File**: `src/cow_performance/metrics/__init__.py`

Add new exports:
```python
from cow_performance.metrics.aggregator import (
    MetricsAggregator,
    PercentileStats,
    OrderAggregateMetrics,
    APIAggregateMetrics,
    ResourceAggregateMetrics,
)
```

#### 3. Create unit tests

**File**: `tests/unit/test_metrics_aggregator.py`

```python
"""Unit tests for MetricsAggregator."""

import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricsAggregator,
    MetricsStore,
    OrderMetadata,
    OrderStatus,
    PercentileStats,
    ResourceSample,
)


class TestPercentileStats:
    """Tests for PercentileStats class."""

    def test_from_empty_values(self):
        """Test percentile stats from empty list."""
        stats = PercentileStats.from_values([])
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.p50 == 0.0

    def test_from_single_value(self):
        """Test percentile stats from single value."""
        stats = PercentileStats.from_values([100.0])
        assert stats.count == 1
        assert stats.mean == 100.0
        assert stats.min == 100.0
        assert stats.max == 100.0
        assert stats.p50 == 100.0

    def test_from_multiple_values(self):
        """Test percentile stats from multiple values."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        stats = PercentileStats.from_values(values)

        assert stats.count == 10
        assert stats.min == 10.0
        assert stats.max == 100.0
        assert stats.mean == 55.0
        assert stats.p50 == pytest.approx(55.0, rel=0.1)
        assert stats.p90 == pytest.approx(91.0, rel=0.1)
        assert stats.p95 == pytest.approx(95.5, rel=0.1)
        assert stats.p99 == pytest.approx(99.1, rel=0.1)


class TestMetricsAggregator:
    """Tests for MetricsAggregator class."""

    @pytest.fixture
    def store_with_orders(self):
        """Create a store with sample orders."""
        store = MetricsStore()
        base_time = time.time()

        # Add orders with various statuses and timings
        for i in range(10):
            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner=f"0x{i % 3:040x}",  # 3 different owners
                creation_time=base_time + i * 0.1,
                sell_token="0xsell",
                buy_token="0xbuy",
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i * 0.1 + 0.01)
            order.update_status(OrderStatus.ACCEPTED, base_time + i * 0.1 + 0.02)

            # Vary the outcomes
            if i < 7:
                order.update_status(OrderStatus.FILLED, base_time + i * 0.1 + 0.1 + i * 0.01)
            elif i == 7:
                order.update_status(OrderStatus.EXPIRED, base_time + i * 0.1 + 0.5)
            elif i == 8:
                order.update_status(OrderStatus.CANCELLED, base_time + i * 0.1 + 0.3)
            else:
                order.update_status(OrderStatus.FAILED, base_time + i * 0.1 + 0.05)

            store.add_order(order)

        return store

    @pytest.fixture
    def store_with_api_metrics(self):
        """Create a store with sample API metrics."""
        store = MetricsStore()
        base_time = time.time()

        for i in range(100):
            metric = APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=base_time + i * 0.1,
                duration=0.05 + (i % 10) * 0.01,  # 50-140ms
                status_code=201 if i < 90 else 500,  # 90% success rate
            )
            store.add_api_metric(metric)

        return store

    def test_aggregate_orders_empty(self):
        """Test aggregating empty order list."""
        store = MetricsStore()
        aggregator = MetricsAggregator(store)

        metrics = aggregator.aggregate_orders()

        assert metrics.total_orders == 0
        assert metrics.success_rate == 0.0
        assert metrics.time_to_submit.count == 0

    def test_aggregate_orders_with_data(self, store_with_orders):
        """Test aggregating orders with data."""
        aggregator = MetricsAggregator(store_with_orders)

        metrics = aggregator.aggregate_orders()

        assert metrics.total_orders == 10
        assert metrics.orders_filled == 7
        assert metrics.orders_expired == 1
        assert metrics.orders_cancelled == 1
        assert metrics.orders_failed == 1
        assert metrics.success_rate == pytest.approx(0.7, rel=0.01)
        assert metrics.time_to_submit.count > 0
        assert metrics.time_to_fill.count == 7  # Only filled orders have fill time

    def test_aggregate_api_metrics_empty(self):
        """Test aggregating empty API metrics."""
        store = MetricsStore()
        aggregator = MetricsAggregator(store)

        metrics = aggregator.aggregate_api_metrics()

        assert metrics.total_requests == 0
        assert metrics.success_rate == 0.0

    def test_aggregate_api_metrics_with_data(self, store_with_api_metrics):
        """Test aggregating API metrics with data."""
        aggregator = MetricsAggregator(store_with_api_metrics)

        metrics = aggregator.aggregate_api_metrics()

        assert metrics.total_requests == 100
        assert metrics.successful_requests == 90
        assert metrics.failed_requests == 10
        assert metrics.success_rate == 0.9
        assert metrics.response_time.count == 100
        assert metrics.response_time.p50 > 0
        assert metrics.response_time.p95 > metrics.response_time.p50
        assert 201 in metrics.status_code_counts
        assert 500 in metrics.status_code_counts

    def test_aggregate_api_metrics_by_endpoint(self, store_with_api_metrics):
        """Test filtering API metrics by endpoint."""
        aggregator = MetricsAggregator(store_with_api_metrics)

        # Add metrics for another endpoint
        for i in range(10):
            store_with_api_metrics.add_api_metric(APIMetrics(
                endpoint="/api/v1/version",
                method="GET",
                timestamp=time.time(),
                duration=0.01,
                status_code=200,
            ))

        metrics = aggregator.aggregate_api_metrics(endpoint="/api/v1/orders")
        assert metrics.total_requests == 100  # Only /api/v1/orders

    def test_aggregate_resource_metrics(self):
        """Test aggregating resource metrics."""
        store = MetricsStore()

        for i in range(50):
            sample = ResourceSample(
                timestamp=time.time(),
                cpu_percent=20.0 + i * 0.5,  # 20-45%
                memory_bytes=100_000_000 + i * 1_000_000,
                memory_limit_bytes=1_000_000_000,
            )
            store.add_resource_sample("orderbook", sample)

        aggregator = MetricsAggregator(store)
        metrics = aggregator.aggregate_resource_metrics()

        assert "orderbook" in metrics
        orderbook_metrics = metrics["orderbook"]
        assert orderbook_metrics.sample_count == 50
        assert orderbook_metrics.cpu_percent.count == 50
        assert orderbook_metrics.cpu_percent.min == pytest.approx(20.0, rel=0.01)
        assert orderbook_metrics.cpu_percent.max == pytest.approx(44.5, rel=0.01)

    def test_get_summary(self, store_with_orders, store_with_api_metrics):
        """Test getting comprehensive summary."""
        # Use store with orders
        aggregator = MetricsAggregator(store_with_orders)
        summary = aggregator.get_summary()

        assert "orders" in summary
        assert "api" in summary
        assert "resources" in summary
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_metrics_aggregator.py -v` passes
- [x] `poetry run ruff check src/cow_performance/metrics/aggregator.py`
- [x] `poetry run mypy src/cow_performance/metrics/aggregator.py`
- [x] Import works: `from cow_performance.metrics import MetricsAggregator, PercentileStats`

#### Manual Verification

- [x] Percentile calculations match expected values
- [x] numpy array operations are efficient for large datasets

### Commit

After Phase 1, create a commit:
```
feat(metrics): add MetricsAggregator with percentile calculations

Implement comprehensive metrics aggregation:
- PercentileStats class for p50/p90/p95/p99 calculations
- OrderAggregateMetrics with timing percentiles
- APIAggregateMetrics with response time percentiles
- ResourceAggregateMetrics with CPU/memory percentiles
- Uses numpy for efficient percentile calculations

Part of COW-611: Analysis - Aggregation & Real-time Updates
```

---

## Phase 2: Grouping and Dimensional Aggregation

### Overview

Add support for grouping metrics by dimensions: time windows, order type, token pair, and trader.

### Changes Required

#### 1. Add grouping methods to MetricsAggregator

**File**: `src/cow_performance/metrics/aggregator.py`

Add these methods to the `MetricsAggregator` class:

```python
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
            window_orders = [
                o for o in orders
                if current_start <= o.creation_time < current_end
            ]

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
        return {
            endpoint: self.aggregate_api_metrics(endpoint=endpoint)
            for endpoint in endpoints
        }

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
            metrics = self.aggregate_api_metrics(
                time_range=(current_start, current_end)
            )

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
            window_seconds: Time window for rate calculation

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
```

#### 2. Add unit tests for grouping

**File**: `tests/unit/test_metrics_aggregator.py`

Add these tests to the existing test file:

```python
class TestMetricsAggregatorGrouping:
    """Tests for MetricsAggregator grouping methods."""

    @pytest.fixture
    def store_with_diverse_orders(self):
        """Create a store with orders from multiple owners and token pairs."""
        store = MetricsStore()
        base_time = time.time()

        owners = ["0xAAA", "0xBBB", "0xCCC"]
        token_pairs = [
            ("0xWETH", "0xUSDC"),
            ("0xWETH", "0xDAI"),
            ("0xUSDC", "0xDAI"),
        ]

        for i in range(30):
            owner = owners[i % 3]
            sell_token, buy_token = token_pairs[i % 3]

            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner=owner,
                creation_time=base_time + i * 0.5,  # 0.5s apart
                sell_token=sell_token,
                buy_token=buy_token,
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i * 0.5 + 0.01)
            order.update_status(OrderStatus.FILLED, base_time + i * 0.5 + 0.1)
            store.add_order(order)

        return store

    def test_aggregate_orders_by_owner(self, store_with_diverse_orders):
        """Test grouping orders by owner."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        by_owner = aggregator.aggregate_orders_by_owner()

        assert len(by_owner) == 3
        assert "0xAAA" in by_owner
        assert "0xBBB" in by_owner
        assert "0xCCC" in by_owner

        # Each owner should have 10 orders
        for owner, metrics in by_owner.items():
            assert metrics.total_orders == 10

    def test_aggregate_orders_by_token_pair(self, store_with_diverse_orders):
        """Test grouping orders by token pair."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        by_pair = aggregator.aggregate_orders_by_token_pair()

        assert len(by_pair) == 3
        assert "0xWETH->0xUSDC" in by_pair
        assert "0xWETH->0xDAI" in by_pair
        assert "0xUSDC->0xDAI" in by_pair

    def test_aggregate_orders_by_time_window(self, store_with_diverse_orders):
        """Test grouping orders by time windows."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        windows = aggregator.aggregate_orders_by_time_window(window_seconds=5.0)

        # With 30 orders 0.5s apart (15s total), we should have ~3 windows of 5s each
        assert len(windows) >= 3

        # Each window should have metrics
        for start, end, metrics in windows:
            assert end - start == 5.0
            assert metrics.total_orders > 0

    def test_aggregate_api_metrics_by_endpoint(self):
        """Test grouping API metrics by endpoint."""
        store = MetricsStore()

        # Add metrics for different endpoints
        for endpoint in ["/api/v1/orders", "/api/v1/version", "/api/v1/trades"]:
            for _ in range(10):
                store.add_api_metric(APIMetrics(
                    endpoint=endpoint,
                    method="GET",
                    timestamp=time.time(),
                    duration=0.1,
                    status_code=200,
                ))

        aggregator = MetricsAggregator(store)
        by_endpoint = aggregator.aggregate_api_metrics_by_endpoint()

        assert len(by_endpoint) == 3
        for endpoint, metrics in by_endpoint.items():
            assert metrics.total_requests == 10

    def test_calculate_throughput(self, store_with_diverse_orders):
        """Test throughput calculation."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        throughput = aggregator.calculate_throughput()

        assert "orders_per_second" in throughput
        assert "api_requests_per_second" in throughput
        # 30 orders over ~15s = ~2 orders/second
        assert throughput["orders_per_second"] > 1.0
```

### Success Criteria

#### Automated Verification

- [x] All grouping tests pass
- [x] Linting passes
- [x] Type checking passes

#### Manual Verification

- [x] Grouping by owner correctly separates orders
- [x] Time windows don't overlap and cover all data

### Commit

After Phase 2, create a commit:
```
feat(metrics): add dimensional grouping to MetricsAggregator

Add support for grouping metrics by:
- Owner address (orders)
- Token pair (orders)
- Time windows (orders and API metrics)
- Endpoint (API metrics)
- Throughput calculation (orders/second, requests/second)

Part of COW-611: Analysis - Aggregation & Real-time Updates
```

---

## Phase 3: Real-time Streaming with MetricsEventStream

### Overview

Implement real-time metrics streaming using the existing callback hooks in MetricsStore. Create a `MetricsEventStream` class that provides async iteration over metrics events.

### Changes Required

#### 1. Create streaming module

**File**: `src/cow_performance/metrics/streaming.py`

```python
"""
Real-time metrics streaming for live monitoring.

Provides async event stream for metrics updates using MetricsStore callbacks.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator

from cow_performance.metrics.store import MetricsStore

logger = logging.getLogger(__name__)


class MetricEventType(str, Enum):
    """Types of metric events."""

    ORDER = "order"
    API = "api"
    RESOURCE = "resource"


@dataclass
class MetricEvent:
    """A single metric event for streaming."""

    event_type: MetricEventType
    data: Any
    timestamp: float


class MetricsEventStream:
    """
    Async event stream for real-time metrics monitoring.

    Uses MetricsStore callbacks to stream metrics updates as async events.
    Can be used with async for loops for live monitoring.

    Example:
        store = MetricsStore()
        stream = MetricsEventStream(store)

        async with stream:
            async for event in stream:
                print(f"New {event.event_type}: {event.data}")
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        buffer_size: int = 1000,
    ):
        """
        Initialize the event stream.

        Args:
            metrics_store: The metrics store to stream from
            buffer_size: Maximum number of events to buffer
        """
        self._store = metrics_store
        self._queue: asyncio.Queue[MetricEvent | None] = asyncio.Queue(maxsize=buffer_size)
        self._running = False

    def _callback(self, metric_type: str, metric: object) -> None:
        """
        Callback for MetricsStore updates.

        Converts metrics to events and adds to queue.
        """
        import time

        try:
            event = MetricEvent(
                event_type=MetricEventType(metric_type),
                data=metric,
                timestamp=time.time(),
            )

            # Non-blocking put - drop oldest if full
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event and add new one
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

        except Exception as e:
            logger.warning(f"Error in metrics stream callback: {e}")

    async def start(self) -> None:
        """Start streaming metrics events."""
        if self._running:
            return

        self._running = True
        self._store.register_callback(self._callback)
        logger.debug("MetricsEventStream started")

    async def stop(self) -> None:
        """Stop streaming and signal completion."""
        if not self._running:
            return

        self._running = False
        self._store.unregister_callback(self._callback)

        # Signal end of stream
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        logger.debug("MetricsEventStream stopped")

    async def __aenter__(self) -> "MetricsEventStream":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.stop()

    def __aiter__(self) -> AsyncIterator[MetricEvent]:
        """Return async iterator."""
        return self

    async def __anext__(self) -> MetricEvent:
        """Get next event from stream."""
        if not self._running:
            raise StopAsyncIteration

        event = await self._queue.get()

        if event is None:
            raise StopAsyncIteration

        return event

    async def get_event(self, timeout: float | None = None) -> MetricEvent | None:
        """
        Get next event with optional timeout.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            MetricEvent or None if timeout/stopped
        """
        try:
            if timeout is not None:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            else:
                event = await self._queue.get()

            return event

        except asyncio.TimeoutError:
            return None

    def is_running(self) -> bool:
        """Check if stream is currently running."""
        return self._running

    @property
    def pending_count(self) -> int:
        """Get number of pending events in queue."""
        return self._queue.qsize()


class RollingMetricsSummary:
    """
    Maintains a rolling summary of recent metrics.

    Useful for real-time dashboards showing recent performance.
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize rolling summary.

        Args:
            window_size: Number of recent events to track
        """
        from collections import deque

        self._window_size = window_size
        self._order_events: deque[MetricEvent] = deque(maxlen=window_size)
        self._api_events: deque[MetricEvent] = deque(maxlen=window_size)
        self._resource_events: deque[MetricEvent] = deque(maxlen=window_size)

    def add_event(self, event: MetricEvent) -> None:
        """Add an event to the rolling window."""
        if event.event_type == MetricEventType.ORDER:
            self._order_events.append(event)
        elif event.event_type == MetricEventType.API:
            self._api_events.append(event)
        elif event.event_type == MetricEventType.RESOURCE:
            self._resource_events.append(event)

    def get_recent_order_count(self) -> int:
        """Get count of orders in the rolling window."""
        return len(self._order_events)

    def get_recent_api_success_rate(self) -> float:
        """Get API success rate in the rolling window."""
        if not self._api_events:
            return 0.0

        successes = sum(
            1 for e in self._api_events
            if hasattr(e.data, "is_success") and e.data.is_success
        )
        return successes / len(self._api_events)

    def get_recent_avg_api_response_time(self) -> float:
        """Get average API response time in the rolling window (ms)."""
        if not self._api_events:
            return 0.0

        durations = [
            e.data.duration_ms
            for e in self._api_events
            if hasattr(e.data, "duration_ms")
        ]

        if not durations:
            return 0.0

        return sum(durations) / len(durations)

    def get_summary(self) -> dict[str, Any]:
        """Get current rolling summary."""
        return {
            "recent_orders": self.get_recent_order_count(),
            "recent_api_count": len(self._api_events),
            "recent_api_success_rate": self.get_recent_api_success_rate(),
            "recent_avg_api_response_ms": self.get_recent_avg_api_response_time(),
            "recent_resource_samples": len(self._resource_events),
        }
```

#### 2. Update metrics __init__.py exports

**File**: `src/cow_performance/metrics/__init__.py`

Add new exports:
```python
from cow_performance.metrics.streaming import (
    MetricsEventStream,
    MetricEvent,
    MetricEventType,
    RollingMetricsSummary,
)
```

#### 3. Create unit tests

**File**: `tests/unit/test_realtime_streaming.py`

```python
"""Unit tests for real-time metrics streaming."""

import asyncio
import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricEvent,
    MetricEventType,
    MetricsEventStream,
    MetricsStore,
    OrderMetadata,
    RollingMetricsSummary,
)


class TestMetricsEventStream:
    """Tests for MetricsEventStream class."""

    @pytest.fixture
    def store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def stream(self, store):
        """Create an event stream fixture."""
        return MetricsEventStream(store, buffer_size=100)

    @pytest.mark.asyncio
    async def test_stream_start_stop(self, stream):
        """Test starting and stopping stream."""
        assert not stream.is_running()

        await stream.start()
        assert stream.is_running()

        await stream.stop()
        assert not stream.is_running()

    @pytest.mark.asyncio
    async def test_stream_context_manager(self, store):
        """Test stream as async context manager."""
        stream = MetricsEventStream(store)

        async with stream:
            assert stream.is_running()

        assert not stream.is_running()

    @pytest.mark.asyncio
    async def test_stream_receives_order_events(self, store, stream):
        """Test that stream receives order events."""
        await stream.start()

        # Add order to store (triggers callback)
        store.add_order(OrderMetadata(
            order_uid="0x1234",
            owner="0xowner",
            creation_time=time.time(),
        ))

        # Get event with timeout
        event = await stream.get_event(timeout=1.0)

        assert event is not None
        assert event.event_type == MetricEventType.ORDER
        assert event.data.order_uid == "0x1234"

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_receives_api_events(self, store, stream):
        """Test that stream receives API events."""
        await stream.start()

        # Add API metric to store
        store.add_api_metric(APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.1,
            status_code=201,
        ))

        event = await stream.get_event(timeout=1.0)

        assert event is not None
        assert event.event_type == MetricEventType.API
        assert event.data.endpoint == "/api/v1/orders"

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_iteration(self, store, stream):
        """Test async iteration over stream."""
        await stream.start()

        # Add multiple events
        for i in range(5):
            store.add_order(OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner="0xowner",
                creation_time=time.time(),
            ))

        # Collect events
        events = []
        for _ in range(5):
            event = await stream.get_event(timeout=1.0)
            if event:
                events.append(event)

        assert len(events) == 5

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_buffer_overflow(self, store):
        """Test that buffer overflow drops oldest events."""
        stream = MetricsEventStream(store, buffer_size=5)
        await stream.start()

        # Add more events than buffer size
        for i in range(10):
            store.add_order(OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner="0xowner",
                creation_time=time.time(),
            ))

        # Should have dropped oldest events
        assert stream.pending_count <= 5

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_timeout(self, store, stream):
        """Test get_event with timeout."""
        await stream.start()

        # Don't add any events - should timeout
        event = await stream.get_event(timeout=0.1)

        assert event is None

        await stream.stop()


class TestRollingMetricsSummary:
    """Tests for RollingMetricsSummary class."""

    def test_add_order_event(self):
        """Test adding order events to rolling summary."""
        summary = RollingMetricsSummary(window_size=10)

        for i in range(5):
            event = MetricEvent(
                event_type=MetricEventType.ORDER,
                data=OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        assert summary.get_recent_order_count() == 5

    def test_add_api_event_success_rate(self):
        """Test API success rate calculation."""
        summary = RollingMetricsSummary(window_size=10)

        # Add 8 successful, 2 failed
        for i in range(10):
            event = MetricEvent(
                event_type=MetricEventType.API,
                data=APIMetrics(
                    endpoint="/test",
                    method="GET",
                    timestamp=time.time(),
                    duration=0.1,
                    status_code=200 if i < 8 else 500,
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        assert summary.get_recent_api_success_rate() == 0.8

    def test_rolling_window_drops_old_events(self):
        """Test that rolling window drops old events."""
        summary = RollingMetricsSummary(window_size=5)

        for i in range(10):
            event = MetricEvent(
                event_type=MetricEventType.ORDER,
                data=OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        # Should only have last 5
        assert summary.get_recent_order_count() == 5

    def test_get_summary(self):
        """Test getting full summary."""
        summary = RollingMetricsSummary()

        # Add some events
        summary.add_event(MetricEvent(
            event_type=MetricEventType.ORDER,
            data=OrderMetadata(order_uid="0x1", owner="0x", creation_time=time.time()),
            timestamp=time.time(),
        ))
        summary.add_event(MetricEvent(
            event_type=MetricEventType.API,
            data=APIMetrics(
                endpoint="/test",
                method="GET",
                timestamp=time.time(),
                duration=0.1,
                status_code=200,
            ),
            timestamp=time.time(),
        ))

        result = summary.get_summary()

        assert "recent_orders" in result
        assert "recent_api_count" in result
        assert "recent_api_success_rate" in result
        assert result["recent_orders"] == 1
        assert result["recent_api_count"] == 1
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_realtime_streaming.py -v` passes
- [x] Linting passes
- [x] Type checking passes

#### Manual Verification

- [x] Events stream in real-time as metrics are added
- [x] Buffer overflow handles gracefully
- [x] Rolling summary accurately reflects recent metrics

### Commit

After Phase 3, create a commit:
```
feat(metrics): add real-time MetricsEventStream

Implement real-time metrics streaming:
- MetricsEventStream using MetricsStore callbacks
- Async iteration support for live monitoring
- RollingMetricsSummary for recent metrics tracking
- Buffer overflow handling with oldest-event dropping

Part of COW-611: Analysis - Aggregation & Real-time Updates
```

---

## Phase 4: CLI Integration with Rich Live Display

### Overview

Integrate metrics aggregation and streaming with the CLI. Replace the simple Progress spinner with a Rich Live display showing real-time metrics during test execution.

### Changes Required

#### 1. Create CLI live display component

**File**: `src/cow_performance/cli/live_display.py`

```python
"""
Live metrics display for CLI during test execution.

Provides real-time metrics visualization using Rich Live display.
"""

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cow_performance.metrics import (
    MetricsAggregator,
    MetricsEventStream,
    MetricsStore,
    RollingMetricsSummary,
)


class LiveMetricsDisplay:
    """
    Real-time metrics display for CLI.

    Shows live updating metrics during performance test execution
    using Rich Live display.
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        console: Console | None = None,
        refresh_rate: float = 1.0,
    ):
        """
        Initialize the live display.

        Args:
            metrics_store: The metrics store to display
            console: Optional Rich Console instance
            refresh_rate: Display refresh rate in seconds
        """
        self._store = metrics_store
        self._console = console or Console()
        self._refresh_rate = refresh_rate
        self._stream: MetricsEventStream | None = None
        self._rolling_summary = RollingMetricsSummary(window_size=100)
        self._running = False
        self._start_time: datetime | None = None
        self._live: Live | None = None
        self._task: asyncio.Task[None] | None = None

    def _build_header(self) -> Panel:
        """Build the header panel."""
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            elapsed_str = f"{elapsed:.1f}s"
        else:
            elapsed_str = "0.0s"

        header_text = Text()
        header_text.append("CoW Protocol Performance Test", style="bold cyan")
        header_text.append(f"  |  Elapsed: {elapsed_str}", style="green")

        return Panel(header_text, style="blue")

    def _build_order_stats_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the order statistics table."""
        metrics = aggregator.aggregate_orders()

        table = Table(title="Order Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Orders", str(metrics.total_orders))
        table.add_row("Filled", str(metrics.orders_filled))
        table.add_row("Failed", str(metrics.orders_failed))
        table.add_row("Expired", str(metrics.orders_expired))

        if metrics.total_orders > 0:
            table.add_row("Success Rate", f"{metrics.success_rate * 100:.1f}%")

        return table

    def _build_latency_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the latency statistics table."""
        metrics = aggregator.aggregate_orders()

        table = Table(title="Latency (seconds)", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("P50", style="green", justify="right")
        table.add_column("P95", style="yellow", justify="right")
        table.add_column("P99", style="red", justify="right")

        if metrics.time_to_fill.count > 0:
            table.add_row(
                "Time to Fill",
                f"{metrics.time_to_fill.p50:.3f}",
                f"{metrics.time_to_fill.p95:.3f}",
                f"{metrics.time_to_fill.p99:.3f}",
            )

        if metrics.total_lifecycle.count > 0:
            table.add_row(
                "Total Lifecycle",
                f"{metrics.total_lifecycle.p50:.3f}",
                f"{metrics.total_lifecycle.p95:.3f}",
                f"{metrics.total_lifecycle.p99:.3f}",
            )

        return table

    def _build_api_stats_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the API statistics table."""
        metrics = aggregator.aggregate_api_metrics()

        table = Table(title="API Metrics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Requests", str(metrics.total_requests))
        table.add_row("Success Rate", f"{metrics.success_rate * 100:.1f}%")

        if metrics.response_time.count > 0:
            table.add_row("Avg Response", f"{metrics.response_time.mean:.1f}ms")
            table.add_row("P95 Response", f"{metrics.response_time.p95:.1f}ms")

        if metrics.requests_per_second > 0:
            table.add_row("Requests/sec", f"{metrics.requests_per_second:.2f}")

        return table

    def _build_throughput_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the throughput table."""
        throughput = aggregator.calculate_throughput()

        table = Table(title="Throughput", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Orders/sec", f"{throughput['orders_per_second']:.2f}")
        table.add_row("API Requests/sec", f"{throughput['api_requests_per_second']:.2f}")

        return table

    def _build_display(self) -> Layout:
        """Build the complete display layout."""
        aggregator = MetricsAggregator(self._store)

        layout = Layout()

        # Header
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        layout["header"].update(self._build_header())

        # Body with stats
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        # Left column: Orders and Latency
        layout["left"].split(
            Layout(self._build_order_stats_table(aggregator)),
            Layout(self._build_latency_table(aggregator)),
        )

        # Right column: API and Throughput
        layout["right"].split(
            Layout(self._build_api_stats_table(aggregator)),
            Layout(self._build_throughput_table(aggregator)),
        )

        return layout

    async def _update_loop(self) -> None:
        """Background loop to process events and update rolling summary."""
        if self._stream is None:
            return

        while self._running:
            event = await self._stream.get_event(timeout=0.1)
            if event is not None:
                self._rolling_summary.add_event(event)

    async def start(self) -> None:
        """Start the live display."""
        if self._running:
            return

        self._running = True
        self._start_time = datetime.now()

        # Start event stream
        self._stream = MetricsEventStream(self._store)
        await self._stream.start()

        # Start background event processing
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        """Stop the live display."""
        if not self._running:
            return

        self._running = False

        # Stop event stream
        if self._stream:
            await self._stream.stop()

        # Cancel background task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_live_context(self) -> Live:
        """
        Get Rich Live context manager for display.

        Returns:
            Rich Live instance configured for metrics display
        """
        return Live(
            self._build_display(),
            console=self._console,
            refresh_per_second=1.0 / self._refresh_rate,
            transient=True,
        )

    def update(self) -> Layout:
        """
        Get updated display layout.

        Returns:
            Updated Rich Layout
        """
        return self._build_display()


def create_performance_metrics_dict(
    metrics_store: MetricsStore,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """
    Create performance metrics dict for CLI output.

    Includes percentile latencies expected by output.py.

    Args:
        metrics_store: The metrics store
        elapsed_seconds: Test duration in seconds

    Returns:
        Dict with performance metrics including percentiles
    """
    aggregator = MetricsAggregator(metrics_store)

    order_metrics = aggregator.aggregate_orders()
    api_metrics = aggregator.aggregate_api_metrics()
    throughput = aggregator.calculate_throughput()

    # Build performance dict with fields expected by output.py
    performance: dict[str, Any] = {
        "orders_per_second": throughput["orders_per_second"],
        "avg_order_latency_ms": order_metrics.total_lifecycle.mean * 1000,
    }

    # Add percentile latencies (in milliseconds)
    if order_metrics.total_lifecycle.count > 0:
        performance["p50_latency_ms"] = order_metrics.total_lifecycle.p50 * 1000
        performance["p95_latency_ms"] = order_metrics.total_lifecycle.p95 * 1000
        performance["p99_latency_ms"] = order_metrics.total_lifecycle.p99 * 1000

    # Add API metrics
    performance["api_success_rate"] = api_metrics.success_rate
    if api_metrics.response_time.count > 0:
        performance["avg_api_response_ms"] = api_metrics.response_time.mean
        performance["p95_api_response_ms"] = api_metrics.response_time.p95

    return performance
```

#### 2. Update run.py to use new components

**File**: `src/cow_performance/cli/commands/run.py`

Add imports and update the test execution section:

```python
# Add imports at top
from cow_performance.cli.live_display import LiveMetricsDisplay, create_performance_metrics_dict

# Replace the Progress section (lines 316-338) with:

    # Choose display mode
    use_live_display = verbose and not dry_run

    if use_live_display:
        # Rich Live display for real-time metrics
        live_display = LiveMetricsDisplay(metrics_store, console)
        await live_display.start()

        try:
            with live_display.get_live_context() as live:
                start_time = datetime.now()
                test_task = asyncio.create_task(orchestrator.run())

                while not test_task.done():
                    live.update(live_display.update())
                    await asyncio.sleep(0.5)

                await test_task
                end_time = datetime.now()

        finally:
            await live_display.stop()
    else:
        # Simple spinner for non-verbose mode
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Running performance test with {num_traders} traders...",
                total=None,
            )

            try:
                start_time = datetime.now()
                await orchestrator.run()
                end_time = datetime.now()
                progress.update(task, description="[bold green]Test completed!")
            except Exception as e:
                progress.update(task, description="[bold red]Test failed!")
                console.print(f"\n[bold red]Error:[/bold red] {e}")
                raise

# Update the performance metrics section (around line 388-393):

    # Add performance metrics with percentiles
    elapsed = metrics["orchestration"]["elapsed_time"]
    perf_metrics = create_performance_metrics_dict(metrics_store, elapsed)
    metrics["performance"] = perf_metrics
```

#### 3. Create integration test

**File**: `tests/integration/test_cli_live_display.py`

```python
"""Integration tests for CLI live display."""

import asyncio
import time

import pytest

from cow_performance.cli.live_display import (
    LiveMetricsDisplay,
    create_performance_metrics_dict,
)
from cow_performance.metrics import (
    APIMetrics,
    MetricsStore,
    OrderMetadata,
    OrderStatus,
)


class TestLiveMetricsDisplay:
    """Tests for LiveMetricsDisplay."""

    @pytest.fixture
    def store_with_data(self):
        """Create a store with sample data."""
        store = MetricsStore()
        base_time = time.time()

        # Add orders
        for i in range(10):
            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner="0xowner",
                creation_time=base_time + i,
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i + 0.01)
            order.update_status(OrderStatus.FILLED, base_time + i + 0.1)
            store.add_order(order)

        # Add API metrics
        for i in range(20):
            store.add_api_metric(APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=base_time + i * 0.5,
                duration=0.05 + i * 0.005,
                status_code=201,
            ))

        return store

    @pytest.mark.asyncio
    async def test_live_display_start_stop(self, store_with_data):
        """Test live display lifecycle."""
        display = LiveMetricsDisplay(store_with_data)

        await display.start()
        await asyncio.sleep(0.1)  # Let it run briefly
        await display.stop()

    @pytest.mark.asyncio
    async def test_live_display_update(self, store_with_data):
        """Test that display updates without errors."""
        display = LiveMetricsDisplay(store_with_data)

        layout = display.update()
        assert layout is not None

    def test_create_performance_metrics_dict(self, store_with_data):
        """Test performance metrics dict creation."""
        metrics = create_performance_metrics_dict(store_with_data, elapsed_seconds=10.0)

        assert "orders_per_second" in metrics
        assert "avg_order_latency_ms" in metrics
        assert "p50_latency_ms" in metrics
        assert "p95_latency_ms" in metrics
        assert "p99_latency_ms" in metrics
        assert "api_success_rate" in metrics

        # Verify percentiles are reasonable
        assert metrics["p50_latency_ms"] <= metrics["p95_latency_ms"]
        assert metrics["p95_latency_ms"] <= metrics["p99_latency_ms"]
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/integration/test_cli_live_display.py -v` passes
- [x] All existing tests still pass: `poetry run pytest tests/unit/ -v`
- [x] Linting passes: `poetry run ruff check src/cow_performance/`
- [x] Type checking passes: `poetry run mypy src/cow_performance/`
- [x] Formatting passes: `poetry run black --check src/`

#### Manual Verification

- [ ] Run `poetry run cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --verbose`
- [ ] Verify live display shows updating metrics
- [ ] Verify final output includes p50, p95, p99 latencies
- [ ] Verify non-verbose mode still uses simple spinner

### Commit

After Phase 4, create a commit:
```
feat(cli): integrate metrics aggregation with live display

Wire up all metrics aggregation components:
- LiveMetricsDisplay showing real-time metrics during tests
- create_performance_metrics_dict populating percentiles
- Integration with run.py for verbose mode display
- Falls back to simple spinner for non-verbose mode

This completes COW-611: Analysis - Aggregation & Real-time Updates
```

---

## Testing Strategy

### Unit Tests

Located in `tests/unit/`:
- `test_metrics_aggregator.py`: Aggregation calculations, grouping
- `test_realtime_streaming.py`: Event stream, rolling summary

### Integration Tests

Located in `tests/integration/`:
- `test_cli_live_display.py`: Live display, metrics dict creation

### Manual Testing Steps

1. Start Docker services: `docker compose up -d`
2. Run with verbose: `poetry run cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --verbose`
3. Observe live metrics updating during test
4. Verify final output includes percentile latencies
5. Run without verbose to verify spinner fallback works

---

## Documentation Notes

After implementation, update `docs/metrics.md` to add sections covering:
- MetricsAggregator usage
- Percentile calculations
- Real-time streaming with MetricsEventStream
- CLI live display features

---

## References

- Original ticket: `thoughts/tickets/COW-611-analysis-aggregation-realtime.md`
- Parent ticket: `thoughts/tickets/COW-587-metrics-collection-framework.md`
- Foundation plan: `thoughts/plans/2026-01-28-cow-609-foundation-data-models-storage.md`
- Collection plan: `thoughts/plans/2026-01-28-cow-610-collection-lifecycle-api-monitoring.md`
- numpy percentile docs: https://numpy.org/doc/stable/reference/generated/numpy.percentile.html
- Rich Live docs: https://rich.readthedocs.io/en/stable/live.html
