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

# Unit tests for export
poetry run pytest tests/unit/test_metrics_export.py -v

# All metrics tests
poetry run pytest tests/unit/test_metrics*.py -v
```

## Next Steps

This foundation layer will be extended by:

- **COW-610**: Collection - Order lifecycle hooks, API instrumentation, resource monitoring
- **COW-611**: Analysis - Aggregation, percentiles, real-time streaming
