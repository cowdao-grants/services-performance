# COW-609: Foundation - Data Models & Storage Implementation Plan

## Overview

Implement the foundational data models and storage infrastructure for the metrics collection framework. This is the first of three sub-tasks (COW-609, COW-610, COW-611) that together complete COW-587 (Metrics Collection Framework).

## Current State Analysis

### What Exists

- **`OrderMetadata`** (`load_generation/order_tracker.py:29-127`): Tracks order lifecycle timestamps and status transitions
- **`OrderMetrics`** (`load_generation/order_tracker.py:130-152`): Basic aggregate metrics with counts and averages only
- **`OrderTracker`** (`load_generation/order_tracker.py:155-426`): Manages order tracking with async polling
- **`output.py`** (`cli/output.py`): Export utilities for JSON, CSV, Prometheus formats
- **Empty metrics module** (`src/cow_performance/metrics/__init__.py`): Placeholder ready for implementation

### What's Missing

1. No dedicated metrics module structure
2. No `APIMetrics` model for API response timing
3. No `ResourceMetrics` model for Docker container stats
4. No `TestRunMetrics` model for aggregate test results
5. No thread-safe storage with `asyncio.Lock`
6. No `collections.deque` for bounded time-series data
7. No percentile calculations (only averages exist)
8. No metrics export functionality integrated with models

### Key Discoveries

- Existing models use dataclasses (not Pydantic) - we'll follow this pattern
- `output.py` uses separate serializer functions - we'll follow this pattern for exports
- Async patterns use cooperative shutdown with `_running` flags
- Tests use `pytest.mark.asyncio` for async test cases

## Desired End State

After this plan is complete:

1. **Metrics module structure** with organized submodules for models, storage, and export
2. **Complete data models** for all metrics types (order lifecycle, API, resource, test run)
3. **Thread-safe MetricsStore** supporting concurrent writes from multiple traders
4. **Export functionality** for JSON and CSV formats
5. **Relocated order metrics** from `load_generation` to `metrics` module (with backward-compatible re-exports)
6. **Unit tests** for all new components
7. **Initial documentation** describing the metrics foundation (with note about future updates)

### Verification

```bash
# All tests pass
poetry run pytest tests/unit/test_metrics_models.py tests/unit/test_metrics_store.py -v

# Linting passes
poetry run ruff check src/cow_performance/metrics/

# Type checking passes
poetry run mypy src/cow_performance/metrics/

# Existing tests still pass (backward compatibility)
poetry run pytest tests/unit/test_order_tracker.py -v
```

## What We're NOT Doing

- **COW-610 scope**: Order lifecycle tracking hooks, API instrumentation, resource monitoring
- **COW-611 scope**: Metrics aggregation, real-time streaming, CLI integration
- **Prometheus exporters**: Part of M3 milestone
- **Docker API integration**: Part of COW-610
- **Percentile calculations**: Part of COW-611 (aggregation)

## Implementation Approach

We'll implement this in 4 phases, each resulting in a working, testable increment:

1. **Phase 1**: Relocate existing models to metrics module
2. **Phase 2**: Define new data models (APIMetrics, ResourceMetrics, TestRunMetrics)
3. **Phase 3**: Implement MetricsStore with thread-safe storage
4. **Phase 4**: Add export functionality and documentation

---

## Phase 1: Relocate Existing Models to Metrics Module

### Overview

Move `OrderStatus`, `OrderMetadata`, and `OrderMetrics` from `load_generation/order_tracker.py` to `metrics/models.py`. Maintain backward compatibility by re-exporting from `load_generation`.

### Changes Required

#### 1. Create metrics module structure

**File**: `src/cow_performance/metrics/__init__.py`

```python
"""
Metrics collection framework for CoW Protocol performance testing.

This module provides data models, storage, and export functionality for
capturing and analyzing performance metrics during load testing.
"""

from cow_performance.metrics.models import (
    OrderStatus,
    OrderMetadata,
    OrderMetrics,
)

__all__ = [
    "OrderStatus",
    "OrderMetadata",
    "OrderMetrics",
]
```

#### 2. Create models submodule

**File**: `src/cow_performance/metrics/models.py`

Move from `load_generation/order_tracker.py`:
- `OrderStatus` enum (lines 15-26)
- `OrderMetadata` dataclass (lines 29-127)
- `OrderMetrics` dataclass (lines 130-152)

The file should include the same imports and full implementation.

#### 3. Update order_tracker.py imports

**File**: `src/cow_performance/load_generation/order_tracker.py`

```python
# Change from local definitions to imports
from cow_performance.metrics import OrderStatus, OrderMetadata, OrderMetrics
```

Remove the class definitions that were moved.

#### 4. Update load_generation __init__.py for backward compatibility

**File**: `src/cow_performance/load_generation/__init__.py`

Ensure re-exports still work:
```python
from cow_performance.metrics import OrderStatus, OrderMetadata, OrderMetrics
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_order_tracker.py -v` passes (backward compatibility)
- [x] `poetry run ruff check src/cow_performance/metrics/`
- [x] `poetry run mypy src/cow_performance/metrics/`
- [x] Imports work: `from cow_performance.metrics import OrderStatus, OrderMetadata, OrderMetrics`
- [x] Imports work: `from cow_performance.load_generation import OrderStatus` (backward compat)

#### Manual Verification

- [x] Review that no functionality was lost during the move

### Commit

After Phase 1, create a commit:
```
refactor: move order metrics models to metrics module

Move OrderStatus, OrderMetadata, and OrderMetrics from
load_generation/order_tracker.py to metrics/models.py.
Maintain backward compatibility via re-exports.

Part of COW-609: Foundation - Data Models & Storage
```

---

## Phase 2: Define New Data Models

### Overview

Add new data models for API metrics, resource metrics, and test run aggregates.

### Changes Required

#### 1. Add APIMetrics model

**File**: `src/cow_performance/metrics/models.py`

```python
@dataclass
class APIMetrics:
    """
    Metrics for a single API request.

    Captures timing, status, and payload information for
    performance analysis of API interactions.
    """

    endpoint: str
    method: str  # GET, POST, PUT, DELETE
    timestamp: float  # When the request was made
    duration: float  # Response time in seconds
    status_code: int
    payload_size: int = 0  # Request payload size in bytes
    response_size: int = 0  # Response size in bytes
    error_message: str | None = None

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return self.duration * 1000

    @property
    def is_success(self) -> bool:
        """Check if request was successful (2xx status)."""
        return 200 <= self.status_code < 300
```

#### 2. Add ResourceMetrics model

**File**: `src/cow_performance/metrics/models.py`

```python
@dataclass
class ResourceSample:
    """
    A single resource utilization sample.

    Represents a point-in-time snapshot of container resource usage.
    """

    timestamp: float
    cpu_percent: float  # CPU usage percentage (0-100+)
    memory_bytes: int  # Current memory usage in bytes
    memory_limit_bytes: int  # Memory limit in bytes
    network_rx_bytes: int = 0  # Network bytes received
    network_tx_bytes: int = 0  # Network bytes transmitted
    block_read_bytes: int = 0  # Block I/O read
    block_write_bytes: int = 0  # Block I/O write

    @property
    def memory_percent(self) -> float:
        """Get memory usage as percentage of limit."""
        if self.memory_limit_bytes == 0:
            return 0.0
        return (self.memory_bytes / self.memory_limit_bytes) * 100


@dataclass
class ResourceMetrics:
    """
    Aggregated resource metrics for a container.

    Stores time-series samples and provides summary statistics.
    """

    container_name: str
    samples: list[ResourceSample] = field(default_factory=list)

    def add_sample(self, sample: ResourceSample) -> None:
        """Add a resource sample."""
        self.samples.append(sample)

    @property
    def avg_cpu_percent(self) -> float:
        """Get average CPU usage."""
        if not self.samples:
            return 0.0
        return sum(s.cpu_percent for s in self.samples) / len(self.samples)

    @property
    def max_cpu_percent(self) -> float:
        """Get maximum CPU usage."""
        if not self.samples:
            return 0.0
        return max(s.cpu_percent for s in self.samples)

    @property
    def avg_memory_percent(self) -> float:
        """Get average memory usage percentage."""
        if not self.samples:
            return 0.0
        return sum(s.memory_percent for s in self.samples) / len(self.samples)

    @property
    def max_memory_bytes(self) -> int:
        """Get maximum memory usage."""
        if not self.samples:
            return 0
        return max(s.memory_bytes for s in self.samples)
```

#### 3. Add TestRunMetrics model

**File**: `src/cow_performance/metrics/models.py`

```python
@dataclass
class TestRunMetrics:
    """
    Aggregate metrics for an entire test run.

    Combines order lifecycle, API, and resource metrics into
    a comprehensive test summary.
    """

    # Test identification
    test_id: str
    start_time: float
    end_time: float | None = None

    # Configuration snapshot
    num_traders: int = 0
    duration_seconds: float = 0.0

    # Order counts
    total_orders: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_failed: int = 0
    orders_expired: int = 0

    # Timing summaries (in seconds)
    avg_submission_latency: float = 0.0
    avg_time_to_fill: float = 0.0
    avg_total_lifecycle: float = 0.0

    # Throughput
    orders_per_second: float = 0.0

    # API summary
    total_api_calls: int = 0
    api_success_rate: float = 0.0
    avg_api_response_time: float = 0.0

    @property
    def test_duration(self) -> float | None:
        """Get actual test duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time

    @property
    def success_rate(self) -> float:
        """Get order success rate (filled / submitted)."""
        if self.orders_submitted == 0:
            return 0.0
        return self.orders_filled / self.orders_submitted
```

#### 4. Update metrics __init__.py exports

**File**: `src/cow_performance/metrics/__init__.py`

Add new exports:
```python
from cow_performance.metrics.models import (
    OrderStatus,
    OrderMetadata,
    OrderMetrics,
    APIMetrics,
    ResourceSample,
    ResourceMetrics,
    TestRunMetrics,
)

__all__ = [
    "OrderStatus",
    "OrderMetadata",
    "OrderMetrics",
    "APIMetrics",
    "ResourceSample",
    "ResourceMetrics",
    "TestRunMetrics",
]
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_metrics_models.py -v` passes
- [x] `poetry run ruff check src/cow_performance/metrics/`
- [x] `poetry run mypy src/cow_performance/metrics/`
- [x] All models can be imported: `from cow_performance.metrics import APIMetrics, ResourceMetrics, TestRunMetrics`

#### Manual Verification

- [x] Models have appropriate docstrings
- [x] Property methods work correctly (test in REPL or unit test)

### Commit

After Phase 2, create a commit:
```
feat(metrics): add API, resource, and test run metrics models

Add new data models for comprehensive metrics collection:
- APIMetrics: HTTP request/response timing
- ResourceSample: Point-in-time container resource snapshot
- ResourceMetrics: Aggregated container resource metrics
- TestRunMetrics: Aggregate metrics for entire test runs

Part of COW-609: Foundation - Data Models & Storage
```

---

## Phase 3: Implement MetricsStore

### Overview

Create a thread-safe, in-memory metrics store that supports concurrent writes from multiple traders and efficient lookups.

### Changes Required

#### 1. Create storage submodule

**File**: `src/cow_performance/metrics/store.py`

```python
"""
Thread-safe metrics storage for concurrent performance testing.

Provides in-memory storage with efficient lookups and bounded
time-series data using collections.deque.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from cow_performance.metrics.models import (
    OrderMetadata,
    APIMetrics,
    ResourceSample,
    ResourceMetrics,
)


@dataclass
class MetricsStoreConfig:
    """Configuration for MetricsStore."""

    # Maximum number of API metrics to retain (per endpoint)
    max_api_metrics_per_endpoint: int = 10000

    # Maximum number of resource samples to retain (per container)
    max_resource_samples_per_container: int = 1000

    # Maximum number of orders to track
    max_orders: int = 100000


class MetricsStore:
    """
    Thread-safe in-memory metrics storage.

    Supports concurrent writes from multiple traders using asyncio.Lock.
    Uses collections.deque for bounded time-series data to limit memory usage.

    Example:
        store = MetricsStore()

        # Track an order
        async with store.lock:
            store.add_order(metadata)

        # Record API call
        async with store.lock:
            store.add_api_metric(metric)

        # Get all orders
        orders = store.get_all_orders()
    """

    def __init__(self, config: MetricsStoreConfig | None = None):
        """
        Initialize the metrics store.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or MetricsStoreConfig()
        self._lock = asyncio.Lock()

        # Order metrics storage (dict for O(1) lookup by UID)
        self._orders: dict[str, OrderMetadata] = {}

        # API metrics storage (deque per endpoint for bounded storage)
        self._api_metrics: dict[str, deque[APIMetrics]] = {}

        # Resource metrics storage (ResourceMetrics per container)
        self._resource_metrics: dict[str, ResourceMetrics] = {}

        # Callbacks for metrics updates (for real-time streaming in COW-611)
        self._callbacks: list[Callable[[str, object], None]] = []

    @property
    def lock(self) -> asyncio.Lock:
        """Get the asyncio lock for thread-safe operations."""
        return self._lock

    # --- Order Methods ---

    def add_order(self, metadata: OrderMetadata) -> None:
        """
        Add or update order metadata.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            metadata: The order metadata to store
        """
        if len(self._orders) >= self.config.max_orders:
            # Remove oldest order (first inserted)
            oldest_key = next(iter(self._orders))
            del self._orders[oldest_key]

        self._orders[metadata.order_uid] = metadata
        self._notify_callbacks("order", metadata)

    def get_order(self, order_uid: str) -> OrderMetadata | None:
        """
        Get order metadata by UID.

        Args:
            order_uid: The order UID to look up

        Returns:
            OrderMetadata if found, None otherwise
        """
        return self._orders.get(order_uid)

    def get_all_orders(self) -> list[OrderMetadata]:
        """
        Get all tracked orders.

        Returns:
            List of all OrderMetadata instances
        """
        return list(self._orders.values())

    def get_orders_by_status(self, status: str) -> list[OrderMetadata]:
        """
        Get orders filtered by status.

        Args:
            status: The status to filter by (e.g., "filled", "failed")

        Returns:
            List of matching OrderMetadata instances
        """
        return [o for o in self._orders.values() if o.current_status.value == status]

    def get_orders_by_owner(self, owner: str) -> list[OrderMetadata]:
        """
        Get orders filtered by owner address.

        Args:
            owner: The owner address to filter by

        Returns:
            List of matching OrderMetadata instances
        """
        return [o for o in self._orders.values() if o.owner == owner]

    # --- API Metrics Methods ---

    def add_api_metric(self, metric: APIMetrics) -> None:
        """
        Add an API metric.

        Uses deque with maxlen for bounded storage per endpoint.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            metric: The API metric to store
        """
        endpoint = metric.endpoint
        if endpoint not in self._api_metrics:
            self._api_metrics[endpoint] = deque(
                maxlen=self.config.max_api_metrics_per_endpoint
            )

        self._api_metrics[endpoint].append(metric)
        self._notify_callbacks("api", metric)

    def get_api_metrics(self, endpoint: str | None = None) -> list[APIMetrics]:
        """
        Get API metrics, optionally filtered by endpoint.

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            List of APIMetrics instances
        """
        if endpoint is not None:
            return list(self._api_metrics.get(endpoint, []))

        # Return all metrics from all endpoints
        result = []
        for metrics in self._api_metrics.values():
            result.extend(metrics)
        return result

    def get_api_endpoints(self) -> list[str]:
        """
        Get list of endpoints that have metrics.

        Returns:
            List of endpoint strings
        """
        return list(self._api_metrics.keys())

    # --- Resource Metrics Methods ---

    def add_resource_sample(self, container_name: str, sample: ResourceSample) -> None:
        """
        Add a resource sample for a container.

        Uses deque with maxlen for bounded storage.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            container_name: The container name
            sample: The resource sample to store
        """
        if container_name not in self._resource_metrics:
            self._resource_metrics[container_name] = ResourceMetrics(
                container_name=container_name,
                samples=[],
            )

        metrics = self._resource_metrics[container_name]

        # Use deque behavior: remove oldest if at limit
        if len(metrics.samples) >= self.config.max_resource_samples_per_container:
            metrics.samples.pop(0)

        metrics.add_sample(sample)
        self._notify_callbacks("resource", sample)

    def get_resource_metrics(self, container_name: str | None = None) -> dict[str, ResourceMetrics]:
        """
        Get resource metrics, optionally filtered by container.

        Args:
            container_name: Optional container to filter by

        Returns:
            Dict mapping container name to ResourceMetrics
        """
        if container_name is not None:
            if container_name in self._resource_metrics:
                return {container_name: self._resource_metrics[container_name]}
            return {}

        return dict(self._resource_metrics)

    def get_container_names(self) -> list[str]:
        """
        Get list of containers that have metrics.

        Returns:
            List of container name strings
        """
        return list(self._resource_metrics.keys())

    # --- Callback Methods (for COW-611 real-time streaming) ---

    def register_callback(self, callback: Callable[[str, object], None]) -> None:
        """
        Register a callback for metrics updates.

        Callbacks receive (metric_type, metric_object) on each update.
        This is a hook for COW-611 real-time streaming.

        Args:
            callback: Function to call on metrics updates
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, object], None]) -> None:
        """
        Unregister a metrics callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, metric_type: str, metric: object) -> None:
        """Notify all registered callbacks of a metrics update."""
        for callback in self._callbacks:
            try:
                callback(metric_type, metric)
            except Exception:
                # Don't let callback errors affect metrics collection
                pass

    # --- Utility Methods ---

    def clear(self) -> None:
        """
        Clear all stored metrics.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.
        """
        self._orders.clear()
        self._api_metrics.clear()
        self._resource_metrics.clear()

    def summary(self) -> dict[str, int]:
        """
        Get a summary of stored metrics counts.

        Returns:
            Dict with counts for each metric type
        """
        return {
            "orders": len(self._orders),
            "api_endpoints": len(self._api_metrics),
            "api_metrics_total": sum(len(m) for m in self._api_metrics.values()),
            "containers": len(self._resource_metrics),
            "resource_samples_total": sum(
                len(m.samples) for m in self._resource_metrics.values()
            ),
        }
```

#### 2. Update metrics __init__.py exports

**File**: `src/cow_performance/metrics/__init__.py`

Add store exports:
```python
from cow_performance.metrics.store import MetricsStore, MetricsStoreConfig
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_metrics_store.py -v` passes
- [x] `poetry run ruff check src/cow_performance/metrics/store.py`
- [x] `poetry run mypy src/cow_performance/metrics/store.py`
- [x] Imports work: `from cow_performance.metrics import MetricsStore, MetricsStoreConfig`

#### Manual Verification

- [x] Thread-safety works with concurrent async operations
- [x] Deque bounds are respected (add more than max, oldest removed)
- [x] Lookups by order_uid, owner, status work correctly

### Commit

After Phase 3, create a commit:
```
feat(metrics): implement thread-safe MetricsStore

Add MetricsStore class with:
- Thread-safe operations using asyncio.Lock
- Bounded time-series storage using collections.deque
- Efficient O(1) lookups by order UID
- Filtering by status, owner, endpoint, container
- Callback hooks for real-time streaming (COW-611)
- Configurable limits via MetricsStoreConfig

Part of COW-609: Foundation - Data Models & Storage
```

---

## Phase 4: Export Functionality and Documentation

### Overview

Add export functionality for metrics (JSON, CSV) following the existing `output.py` pattern, plus initial documentation.

### Changes Required

#### 1. Create export submodule

**File**: `src/cow_performance/metrics/export.py`

```python
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
    OrderMetadata,
    APIMetrics,
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
    writer.writerow([
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
    ])

    # Data rows
    for order in store.get_all_orders():
        writer.writerow([
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
        ])

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
    writer.writerow([
        "endpoint",
        "method",
        "timestamp",
        "duration_ms",
        "status_code",
        "is_success",
        "payload_size",
        "response_size",
        "error_message",
    ])

    # Data rows
    for metric in store.get_api_metrics():
        writer.writerow([
            metric.endpoint,
            metric.method,
            metric.timestamp,
            metric.duration_ms,
            metric.status_code,
            metric.is_success,
            metric.payload_size,
            metric.response_size,
            metric.error_message,
        ])

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
        raise ValueError(
            f"Unsupported format: {format}. "
            f"Supported: json, csv_orders, csv_api"
        )

    with open(output_path, "w") as f:
        f.write(content)
```

#### 2. Update metrics __init__.py exports

**File**: `src/cow_performance/metrics/__init__.py`

Final complete version:
```python
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

Storage:
    - MetricsStore: Thread-safe in-memory metrics storage
    - MetricsStoreConfig: Configuration for storage limits

Export:
    - export_store_to_json: Export full store to JSON
    - export_orders_to_csv: Export orders to CSV
    - export_api_metrics_to_csv: Export API metrics to CSV
    - save_metrics_to_file: Save to file with format selection
"""

from cow_performance.metrics.models import (
    OrderStatus,
    OrderMetadata,
    OrderMetrics,
    APIMetrics,
    ResourceSample,
    ResourceMetrics,
    TestRunMetrics,
)
from cow_performance.metrics.store import MetricsStore, MetricsStoreConfig
from cow_performance.metrics.export import (
    export_store_to_json,
    export_orders_to_csv,
    export_api_metrics_to_csv,
    save_metrics_to_file,
    order_metadata_to_dict,
    api_metrics_to_dict,
    resource_metrics_to_dict,
    test_run_metrics_to_dict,
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
    # Storage
    "MetricsStore",
    "MetricsStoreConfig",
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
```

#### 3. Add documentation

**File**: `docs/metrics.md`

```markdown
# Metrics Collection Framework

> **Note**: This documentation covers the foundation layer (COW-609). Additional
> documentation will be added as COW-610 (collection) and COW-611 (aggregation)
> are completed.

## Overview

The metrics module provides data models, storage, and export functionality for
capturing performance metrics during CoW Protocol load testing.

## Quick Start

```python
from cow_performance.metrics import (
    MetricsStore,
    OrderMetadata,
    OrderStatus,
    APIMetrics,
    export_store_to_json,
)

# Create a metrics store
store = MetricsStore()

# Track an order
metadata = OrderMetadata(
    order_uid="0x1234...",
    owner="0xabcd...",
    creation_time=time.time(),
)
async with store.lock:
    store.add_order(metadata)

# Record an API call
api_metric = APIMetrics(
    endpoint="/api/v1/orders",
    method="POST",
    timestamp=time.time(),
    duration=0.150,  # 150ms
    status_code=201,
    payload_size=512,
)
async with store.lock:
    store.add_api_metric(api_metric)

# Export metrics
json_output = export_store_to_json(store)
```

## Data Models

### OrderMetadata

Tracks individual order lifecycle with timestamps:

| Field | Type | Description |
|-------|------|-------------|
| `order_uid` | str | Unique order identifier |
| `owner` | str | Order owner address |
| `creation_time` | float | When order was created |
| `submission_time` | float | When submitted to API |
| `acceptance_time` | float | When accepted by orderbook |
| `first_fill_time` | float | When first fill occurred |
| `completion_time` | float | When order reached terminal state |
| `current_status` | OrderStatus | Current lifecycle status |

Calculated durations (properties):
- `get_time_to_submit()`: creation → submission
- `get_time_to_accept()`: submission → acceptance
- `get_time_to_fill()`: acceptance → first fill
- `get_total_lifecycle_time()`: creation → completion

### APIMetrics

Captures HTTP request/response timing:

| Field | Type | Description |
|-------|------|-------------|
| `endpoint` | str | API endpoint path |
| `method` | str | HTTP method |
| `timestamp` | float | Request timestamp |
| `duration` | float | Response time in seconds |
| `status_code` | int | HTTP status code |
| `payload_size` | int | Request payload bytes |
| `response_size` | int | Response bytes |

### ResourceMetrics

Aggregated container resource metrics with time-series samples.

### TestRunMetrics

Complete test run summary combining all metric types.

## MetricsStore

Thread-safe in-memory storage with:

- **Concurrent access**: Uses `asyncio.Lock` for thread safety
- **Bounded storage**: Uses `collections.deque` to limit memory
- **Efficient lookups**: O(1) by order UID
- **Filtering**: By status, owner, endpoint, container

### Configuration

```python
from cow_performance.metrics import MetricsStore, MetricsStoreConfig

config = MetricsStoreConfig(
    max_api_metrics_per_endpoint=10000,  # default
    max_resource_samples_per_container=1000,  # default
    max_orders=100000,  # default
)
store = MetricsStore(config)
```

### Thread-Safe Usage

Always acquire the lock when modifying the store:

```python
# Safe concurrent writes
async with store.lock:
    store.add_order(metadata)

# Reads don't require lock (but may see stale data)
orders = store.get_all_orders()
```

## Export

Export to JSON or CSV:

```python
from cow_performance.metrics import (
    export_store_to_json,
    export_orders_to_csv,
    export_api_metrics_to_csv,
    save_metrics_to_file,
)

# Export to JSON string
json_str = export_store_to_json(store)

# Export orders to CSV string
csv_str = export_orders_to_csv(store)

# Save to file
save_metrics_to_file(store, Path("results.json"), format="json")
save_metrics_to_file(store, Path("orders.csv"), format="csv_orders")
```

## Testing

Run the metrics tests:

```bash
# Unit tests for models
poetry run pytest tests/unit/test_metrics_models.py -v

# Unit tests for store
poetry run pytest tests/unit/test_metrics_store.py -v

# All metrics tests
poetry run pytest tests/unit/test_metrics*.py -v
```

## Next Steps

This foundation layer will be extended by:

- **COW-610**: Collection - Order lifecycle hooks, API instrumentation, resource monitoring
- **COW-611**: Analysis - Aggregation, percentiles, real-time streaming
```

#### 4. Create unit tests

**File**: `tests/unit/test_metrics_models.py`

```python
"""Unit tests for metrics data models."""

import time

import pytest

from cow_performance.metrics import (
    OrderStatus,
    OrderMetadata,
    OrderMetrics,
    APIMetrics,
    ResourceSample,
    ResourceMetrics,
    TestRunMetrics,
)


class TestOrderMetadata:
    """Tests for OrderMetadata model."""

    def test_create_order_metadata(self):
        """Test creating order metadata."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        assert metadata.order_uid == "0x1234"
        assert metadata.owner == "0xabcd"
        assert metadata.current_status == OrderStatus.CREATED

    def test_update_status_records_history(self):
        """Test that status updates are recorded in history."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        metadata.update_status(OrderStatus.SUBMITTED)
        metadata.update_status(OrderStatus.ACCEPTED)
        metadata.update_status(OrderStatus.FILLED)

        assert len(metadata.status_history) == 3
        assert metadata.current_status == OrderStatus.FILLED

    def test_lifecycle_times_calculated(self):
        """Test lifecycle time calculations."""
        base_time = time.time()
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=base_time,
        )

        metadata.update_status(OrderStatus.SUBMITTED, base_time + 0.1)
        metadata.update_status(OrderStatus.ACCEPTED, base_time + 0.2)
        metadata.update_status(OrderStatus.FILLED, base_time + 0.5)

        assert metadata.get_time_to_submit() == pytest.approx(0.1, rel=0.01)
        assert metadata.get_time_to_accept() == pytest.approx(0.1, rel=0.01)
        assert metadata.get_time_to_fill() == pytest.approx(0.3, rel=0.01)
        assert metadata.get_total_lifecycle_time() == pytest.approx(0.5, rel=0.01)

    def test_is_terminal_state(self):
        """Test terminal state detection."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        assert not metadata.is_terminal_state()

        metadata.update_status(OrderStatus.FILLED)
        assert metadata.is_terminal_state()


class TestAPIMetrics:
    """Tests for APIMetrics model."""

    def test_create_api_metrics(self):
        """Test creating API metrics."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.150,
            status_code=201,
            payload_size=512,
        )

        assert metric.endpoint == "/api/v1/orders"
        assert metric.method == "POST"
        assert metric.duration == 0.150

    def test_duration_ms_property(self):
        """Test duration_ms calculation."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="GET",
            timestamp=time.time(),
            duration=0.150,
            status_code=200,
        )

        assert metric.duration_ms == 150.0

    def test_is_success_property(self):
        """Test is_success detection."""
        success = APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=200,
        )
        assert success.is_success

        created = APIMetrics(
            endpoint="/test",
            method="POST",
            timestamp=time.time(),
            duration=0.1,
            status_code=201,
        )
        assert created.is_success

        error = APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=500,
        )
        assert not error.is_success


class TestResourceMetrics:
    """Tests for ResourceSample and ResourceMetrics."""

    def test_resource_sample_memory_percent(self):
        """Test memory percentage calculation."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_bytes=500_000_000,  # 500MB
            memory_limit_bytes=1_000_000_000,  # 1GB
        )

        assert sample.memory_percent == 50.0

    def test_resource_sample_zero_limit(self):
        """Test memory percent with zero limit."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_bytes=500_000_000,
            memory_limit_bytes=0,
        )

        assert sample.memory_percent == 0.0

    def test_resource_metrics_aggregation(self):
        """Test resource metrics aggregation."""
        metrics = ResourceMetrics(container_name="test-container")

        metrics.add_sample(ResourceSample(
            timestamp=time.time(),
            cpu_percent=20.0,
            memory_bytes=100_000_000,
            memory_limit_bytes=1_000_000_000,
        ))
        metrics.add_sample(ResourceSample(
            timestamp=time.time(),
            cpu_percent=40.0,
            memory_bytes=200_000_000,
            memory_limit_bytes=1_000_000_000,
        ))

        assert metrics.avg_cpu_percent == 30.0
        assert metrics.max_cpu_percent == 40.0
        assert metrics.max_memory_bytes == 200_000_000


class TestTestRunMetrics:
    """Tests for TestRunMetrics model."""

    def test_create_test_run_metrics(self):
        """Test creating test run metrics."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            num_traders=10,
            duration_seconds=60.0,
        )

        assert metrics.test_id == "test-001"
        assert metrics.num_traders == 10

    def test_test_duration_property(self):
        """Test test_duration calculation."""
        start = time.time()
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=start,
            end_time=start + 60.0,
        )

        assert metrics.test_duration == 60.0

    def test_success_rate_property(self):
        """Test success rate calculation."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            orders_submitted=100,
            orders_filled=80,
        )

        assert metrics.success_rate == 0.8

    def test_success_rate_zero_submitted(self):
        """Test success rate with zero orders."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            orders_submitted=0,
            orders_filled=0,
        )

        assert metrics.success_rate == 0.0
```

**File**: `tests/unit/test_metrics_store.py`

```python
"""Unit tests for MetricsStore."""

import asyncio
import time

import pytest

from cow_performance.metrics import (
    MetricsStore,
    MetricsStoreConfig,
    OrderMetadata,
    OrderStatus,
    APIMetrics,
    ResourceSample,
)


class TestMetricsStore:
    """Tests for MetricsStore class."""

    @pytest.fixture
    def store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def small_store(self):
        """Create a store with small limits for testing bounds."""
        config = MetricsStoreConfig(
            max_orders=3,
            max_api_metrics_per_endpoint=3,
            max_resource_samples_per_container=3,
        )
        return MetricsStore(config)

    def test_add_and_get_order(self, store):
        """Test adding and retrieving orders."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        store.add_order(metadata)
        retrieved = store.get_order("0x1234")

        assert retrieved is not None
        assert retrieved.order_uid == "0x1234"

    def test_get_nonexistent_order(self, store):
        """Test getting a nonexistent order returns None."""
        assert store.get_order("0x9999") is None

    def test_get_all_orders(self, store):
        """Test getting all orders."""
        for i in range(5):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            store.add_order(metadata)

        orders = store.get_all_orders()
        assert len(orders) == 5

    def test_get_orders_by_status(self, store):
        """Test filtering orders by status."""
        for i in range(3):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            store.add_order(metadata)

        # Update some to different statuses
        store.get_order("0x0000").update_status(OrderStatus.FILLED)
        store.get_order("0x0001").update_status(OrderStatus.FILLED)

        filled = store.get_orders_by_status("filled")
        assert len(filled) == 2

    def test_get_orders_by_owner(self, store):
        """Test filtering orders by owner."""
        store.add_order(OrderMetadata(
            order_uid="0x0001",
            owner="0xaaaa",
            creation_time=time.time(),
        ))
        store.add_order(OrderMetadata(
            order_uid="0x0002",
            owner="0xbbbb",
            creation_time=time.time(),
        ))
        store.add_order(OrderMetadata(
            order_uid="0x0003",
            owner="0xaaaa",
            creation_time=time.time(),
        ))

        owner_a_orders = store.get_orders_by_owner("0xaaaa")
        assert len(owner_a_orders) == 2

    def test_orders_bounded_by_max(self, small_store):
        """Test that orders are bounded by max_orders config."""
        for i in range(5):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            small_store.add_order(metadata)

        # Should only have 3 (the limit)
        orders = small_store.get_all_orders()
        assert len(orders) == 3

        # First orders should be removed
        assert small_store.get_order("0x0000") is None
        assert small_store.get_order("0x0001") is None
        # Later orders should exist
        assert small_store.get_order("0x0004") is not None

    def test_add_and_get_api_metrics(self, store):
        """Test adding and retrieving API metrics."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.150,
            status_code=201,
        )

        store.add_api_metric(metric)
        metrics = store.get_api_metrics("/api/v1/orders")

        assert len(metrics) == 1
        assert metrics[0].endpoint == "/api/v1/orders"

    def test_get_api_metrics_all_endpoints(self, store):
        """Test getting metrics from all endpoints."""
        store.add_api_metric(APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.1,
            status_code=201,
        ))
        store.add_api_metric(APIMetrics(
            endpoint="/api/v1/orders/status",
            method="GET",
            timestamp=time.time(),
            duration=0.05,
            status_code=200,
        ))

        all_metrics = store.get_api_metrics()
        assert len(all_metrics) == 2

    def test_api_metrics_bounded(self, small_store):
        """Test that API metrics are bounded per endpoint."""
        for i in range(5):
            metric = APIMetrics(
                endpoint="/api/test",
                method="GET",
                timestamp=time.time(),
                duration=0.1,
                status_code=200,
            )
            small_store.add_api_metric(metric)

        metrics = small_store.get_api_metrics("/api/test")
        assert len(metrics) == 3  # bounded to max

    def test_add_resource_sample(self, store):
        """Test adding resource samples."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=25.0,
            memory_bytes=100_000_000,
            memory_limit_bytes=1_000_000_000,
        )

        store.add_resource_sample("test-container", sample)
        metrics = store.get_resource_metrics("test-container")

        assert "test-container" in metrics
        assert len(metrics["test-container"].samples) == 1

    def test_resource_samples_bounded(self, small_store):
        """Test that resource samples are bounded per container."""
        for i in range(5):
            sample = ResourceSample(
                timestamp=time.time(),
                cpu_percent=float(i * 10),
                memory_bytes=100_000_000,
                memory_limit_bytes=1_000_000_000,
            )
            small_store.add_resource_sample("test-container", sample)

        metrics = small_store.get_resource_metrics("test-container")
        assert len(metrics["test-container"].samples) == 3  # bounded

    def test_clear_store(self, store):
        """Test clearing the store."""
        store.add_order(OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        ))
        store.add_api_metric(APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=200,
        ))

        store.clear()

        assert len(store.get_all_orders()) == 0
        assert len(store.get_api_metrics()) == 0

    def test_summary(self, store):
        """Test getting store summary."""
        store.add_order(OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        ))
        store.add_api_metric(APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=200,
        ))

        summary = store.summary()

        assert summary["orders"] == 1
        assert summary["api_metrics_total"] == 1

    @pytest.mark.asyncio
    async def test_thread_safe_concurrent_writes(self, store):
        """Test concurrent writes are thread-safe."""
        async def add_orders(start_idx: int, count: int):
            for i in range(count):
                async with store.lock:
                    store.add_order(OrderMetadata(
                        order_uid=f"0x{start_idx + i:04x}",
                        owner="0xabcd",
                        creation_time=time.time(),
                    ))
                await asyncio.sleep(0.001)

        # Run multiple concurrent tasks
        await asyncio.gather(
            add_orders(0, 10),
            add_orders(100, 10),
            add_orders(200, 10),
        )

        orders = store.get_all_orders()
        assert len(orders) == 30

    def test_callback_registration(self, store):
        """Test callback registration and notification."""
        received = []

        def callback(metric_type: str, metric: object):
            received.append((metric_type, metric))

        store.register_callback(callback)

        store.add_order(OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        ))

        assert len(received) == 1
        assert received[0][0] == "order"

        store.unregister_callback(callback)

        store.add_order(OrderMetadata(
            order_uid="0x5678",
            owner="0xabcd",
            creation_time=time.time(),
        ))

        # Should still be 1 after unregistering
        assert len(received) == 1
```

**File**: `tests/unit/test_metrics_export.py`

```python
"""Unit tests for metrics export functionality."""

import json
import time
from pathlib import Path

import pytest

from cow_performance.metrics import (
    MetricsStore,
    OrderMetadata,
    OrderStatus,
    APIMetrics,
    export_store_to_json,
    export_orders_to_csv,
    export_api_metrics_to_csv,
    save_metrics_to_file,
    order_metadata_to_dict,
)


class TestMetricsExport:
    """Tests for metrics export functions."""

    @pytest.fixture
    def populated_store(self):
        """Create a store with sample data."""
        store = MetricsStore()

        # Add orders
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )
        metadata.update_status(OrderStatus.SUBMITTED)
        metadata.update_status(OrderStatus.FILLED)
        store.add_order(metadata)

        # Add API metrics
        store.add_api_metric(APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.150,
            status_code=201,
            payload_size=512,
        ))

        return store

    def test_order_metadata_to_dict(self):
        """Test converting order metadata to dict."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=1000.0,
        )
        metadata.update_status(OrderStatus.FILLED, 1001.0)

        result = order_metadata_to_dict(metadata)

        assert result["order_uid"] == "0x1234"
        assert result["owner"] == "0xabcd"
        assert result["current_status"] == "filled"
        assert result["total_lifecycle_time"] == pytest.approx(1.0)

    def test_export_store_to_json(self, populated_store):
        """Test exporting store to JSON."""
        json_str = export_store_to_json(populated_store)
        data = json.loads(json_str)

        assert "orders" in data
        assert "api_metrics" in data
        assert "resource_metrics" in data
        assert "summary" in data
        assert len(data["orders"]) == 1

    def test_export_orders_to_csv(self, populated_store):
        """Test exporting orders to CSV."""
        csv_str = export_orders_to_csv(populated_store)

        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # header + 1 order
        assert "order_uid" in lines[0]
        assert "0x1234" in lines[1]

    def test_export_api_metrics_to_csv(self, populated_store):
        """Test exporting API metrics to CSV."""
        csv_str = export_api_metrics_to_csv(populated_store)

        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # header + 1 metric
        assert "endpoint" in lines[0]
        assert "/api/v1/orders" in lines[1]

    def test_save_metrics_to_file_json(self, populated_store, tmp_path):
        """Test saving metrics to JSON file."""
        output_path = tmp_path / "metrics.json"
        save_metrics_to_file(populated_store, output_path, format="json")

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert "orders" in data

    def test_save_metrics_to_file_csv_orders(self, populated_store, tmp_path):
        """Test saving orders to CSV file."""
        output_path = tmp_path / "orders.csv"
        save_metrics_to_file(populated_store, output_path, format="csv_orders")

        assert output_path.exists()
        content = output_path.read_text()
        assert "order_uid" in content

    def test_save_metrics_invalid_format(self, populated_store, tmp_path):
        """Test that invalid format raises ValueError."""
        output_path = tmp_path / "metrics.xyz"

        with pytest.raises(ValueError, match="Unsupported format"):
            save_metrics_to_file(populated_store, output_path, format="invalid")
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_metrics_models.py tests/unit/test_metrics_store.py tests/unit/test_metrics_export.py -v` passes
- [x] `poetry run ruff check src/cow_performance/metrics/`
- [x] `poetry run mypy src/cow_performance/metrics/`
- [x] `poetry run black --check src/cow_performance/metrics/`
- [x] All existing tests still pass: `poetry run pytest`

#### Manual Verification

- [x] Documentation in `docs/metrics.md` is clear and accurate
- [x] Exports produce valid JSON and CSV
- [x] Module docstring accurately describes available functionality

### Commit

After Phase 4, create a commit:
```
feat(metrics): add export functionality and documentation

Add metrics export utilities:
- export_store_to_json: Full store to JSON
- export_orders_to_csv: Orders to CSV
- export_api_metrics_to_csv: API metrics to CSV
- save_metrics_to_file: Save with format selection

Add initial documentation (docs/metrics.md) covering:
- Quick start guide
- Data model reference
- MetricsStore usage
- Export functionality

Note: Documentation will be expanded after COW-610 and COW-611.

Part of COW-609: Foundation - Data Models & Storage
```

---

## Testing Strategy

### Unit Tests

Located in `tests/unit/`:
- `test_metrics_models.py`: Data model validation, property calculations
- `test_metrics_store.py`: Storage operations, bounds, thread safety
- `test_metrics_export.py`: JSON/CSV export, file saving

### Test Coverage

Key areas:
- Model creation and property calculations
- Status transitions and timestamp recording
- Thread-safe concurrent operations
- Bounded storage (deque behavior)
- Export format correctness
- Backward compatibility with existing code

### Running Tests

```bash
# All metrics tests
poetry run pytest tests/unit/test_metrics*.py -v

# With coverage
poetry run pytest tests/unit/test_metrics*.py -v --cov=cow_performance.metrics

# Existing tests (backward compatibility)
poetry run pytest tests/unit/test_order_tracker.py -v
```

---

## Documentation Notes

The documentation created in Phase 4 (`docs/metrics.md`) is **initial documentation** covering the foundation layer only. It will be expanded when:

- **COW-610** is complete: Add sections on order lifecycle hooks, API instrumentation, resource monitoring
- **COW-611** is complete: Add sections on aggregation, percentiles, real-time streaming, CLI integration

A note about this is included in the documentation file itself.

---

## References

- Original ticket: `thoughts/tickets/COW-609-foundation-data-models-storage.md`
- Parent ticket: `thoughts/tickets/COW-587-metrics-collection-framework.md`
- Related tickets: COW-610, COW-611
- Existing code: `src/cow_performance/load_generation/order_tracker.py`
- Export patterns: `src/cow_performance/cli/output.py`
