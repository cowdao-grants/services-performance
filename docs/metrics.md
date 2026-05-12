# Metrics Collection Framework

Complete reference for metrics collection, aggregation, analysis, and export.

## Overview

The metrics module provides data models, storage, collection, aggregation, and export for capturing performance metrics during CoW Protocol load testing.

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

Thread-safe in-memory storage with bounded capacity, efficient O(1) lookups, and filtering.

```python
from cow_performance.metrics import MetricsStore, MetricsStoreConfig

# Configure limits
config = MetricsStoreConfig(
    max_orders=100000,
    max_api_metrics_per_endpoint=10000,
    max_resource_samples_per_container=1000,
)
store = MetricsStore(config)

# Thread-safe writes
async with store.lock:
    store.add_order(metadata)
```

## Export

```python
from cow_performance.metrics import export_store_to_json, save_metrics_to_file

json_str = export_store_to_json(store)
save_metrics_to_file(store, Path("results.json"), format="json")
save_metrics_to_file(store, Path("orders.csv"), format="csv_orders")
```

## Testing

```bash
poetry run pytest tests/unit/test_metrics*.py -v
```

## Metrics Collection

### Order Lifecycle

Tracks: creation, submission, acceptance, fill, completion times.

Status flow: `CREATED → SUBMITTED → ACCEPTED → OPEN → FILLED/PARTIALLY_FILLED/EXPIRED/CANCELLED/FAILED`

### API Monitoring

Tracks: endpoint, method, response time, status code, payload sizes, errors.

### Resource Monitoring

Samples: CPU %, memory, network I/O, disk I/O.

**Implementation**: `src/cow_performance/monitoring/resource_monitor.py`

---

## Aggregation and Analysis

`MetricsAggregator` computes percentile stats (P50, P90, P95, P99) for latencies, response times, and resource usage.

```python
from cow_performance.metrics import MetricsAggregator

aggregator = MetricsAggregator(metrics_store)

# Per-trader breakdown
trader_stats = aggregator.aggregate_orders_by_owner()

# Time-series (5-min windows)
time_series = aggregator.aggregate_orders_by_time_window(300)

# API breakdown
api_breakdown = aggregator.aggregate_api_metrics_by_endpoint()

# Throughput (returns dict with orders_per_second, api_requests_per_second)
throughput = aggregator.calculate_throughput()
```

**Implementation**: `src/cow_performance/metrics/aggregator.py`

---

## Prometheus Integration

### Real-Time Metrics Export

Prometheus metrics are automatically exported on port 9091 (default) during test runs:

```bash
# Metrics available at http://localhost:9091/metrics
cow-perf run --config scenario.yml

# Custom port
cow-perf run --config scenario.yml --prometheus-port 9092

# Disable export
cow-perf run --config scenario.yml --prometheus-port 0
```

### Available Metrics

**Order Metrics:**
- `cow_perf_orders_created_total` - Counter
- `cow_perf_orders_submitted_total` - Counter
- `cow_perf_orders_filled_total` - Counter
- `cow_perf_orders_failed_total` - Counter
- `cow_perf_orders_expired_total` - Counter
- `cow_perf_orders_active` - Gauge

**Latency Histograms:**
- `cow_perf_submission_latency_seconds` - Submission time
- `cow_perf_orderbook_latency_seconds` - Acceptance time
- `cow_perf_settlement_latency_seconds` - Fill time
- `cow_perf_order_lifecycle_seconds` - Total lifecycle

**Throughput:**
- `cow_perf_orders_per_second` - Gauge
- `cow_perf_target_rate` - Gauge
- `cow_perf_actual_rate` - Gauge

**API Metrics:**
- `cow_perf_api_requests_total{endpoint, method, status}` - Counter
- `cow_perf_api_response_time_seconds{endpoint, method}` - Histogram
- `cow_perf_api_errors_total{endpoint, error_type}` - Counter

**Resource Metrics (per container):**
- `cow_perf_container_cpu_percent{container}` - Gauge
- `cow_perf_container_memory_bytes{container}` - Gauge
- `cow_perf_container_memory_percent{container}` - Gauge
- `cow_perf_container_network_rx_bytes{container}` - Gauge
- `cow_perf_container_network_tx_bytes{container}` - Gauge
- `cow_perf_container_disk_read_bytes{container}` - Gauge
- `cow_perf_container_disk_write_bytes{container}` - Gauge
- `cow_perf_container_disk_usage_bytes{container}` - Gauge

**Trader Metrics:**
- `cow_perf_trader_orders_submitted{trader_index}` - Counter
- `cow_perf_trader_orders_filled{trader_index}` - Counter
- `cow_perf_traders_active` - Gauge

**Comparison Metrics:**
- `cow_perf_baseline_comparison_percent{metric, baseline_id}` - Gauge
- `cow_perf_regression_detected{severity}` - Gauge
- `cow_perf_regressions_total{severity}` - Counter

**Acceptance Latency (new):**
- `cow_perf_order_acceptance_latency_seconds{scenario}` - Histogram
  - Measures total time from **order creation** to **orderbook acceptance** (creation → acceptance).
  - Complements the existing `cow_perf_orderbook_latency_seconds` (submission → acceptance) by including the
    time the order spends in the local queue before submission.
  - Buckets: 1, 5, 10, 30, 60, 120, 300, 600 seconds.
  - Useful query: `histogram_quantile(0.99, rate(cow_perf_order_acceptance_latency_seconds_bucket[5m]))`

**Scaling / Complexity Metrics (new — set by `cow-perf scale`):**
- `cow_perf_scaling_phase_order_count_target{scenario}` - Gauge
  - Records the target order count for the currently running (or last completed) scaling phase.
- `cow_perf_scaling_complexity_slope{scenario, metric}` - Gauge
  - Power-law slope k from log-log regression (y ~ x^k) for each analysed metric.
  - Interpretation: k ≈ 1 → O(n) linear; k ≈ 2 → O(n²) quadratic; k < 1 → sub-linear.
- `cow_perf_container_rss_snapshot_bytes{scenario, container, snapshot}` - Gauge
  - Container RSS memory sampled before/after each scaling step.
  - The `snapshot` label identifies the measurement point (e.g., `before`, `after`).

### Memory Metrics (scaling experiment)

During `cow-perf scale` runs, container RSS memory is sampled via the Docker SDK
before and after each step. The deltas are included in the JSON scaling report
(`total_memory_delta_bytes` per phase) and in the complexity analysis.

To observe heap growth interactively, the `cow_perf_container_memory_bytes{container}`
gauge (already scraped by Prometheus) shows the rolling RSS — compare its value
at the start and end of each scaling step.

### Grafana Integration

Use with Docker monitoring stack:

```bash
# Start Prometheus and Grafana
docker compose --profile monitoring up -d

# Run test (metrics automatically scraped)
cow-perf run --config scenario.yml

# View dashboards at http://localhost:3000
```

**Implementation**: `src/cow_performance/prometheus/`

---

## Understanding Test Reports

### Report Structure

Test reports (`.cow-perf/results/`) contain:

```json
{
  "test_id": "unique-test-identifier",
  "timestamp": "2026-03-23T10:30:00Z",
  "scenario_name": "smoke-test",
  "verdict": "SUCCESS",  // SUCCESS | WARNING | FAILURE

  "orders": {
    "total_submitted": 232,
    "orders_filled": 201,
    "orders_failed": 5,
    "success_rate": 0.979,  // 97.9%
    "fill_rate": 0.866       // 86.6%
  },

  "latency": {
    "avg_order_latency_ms": 5395.24,
    "p50_latency_ms": 4823.15,
    "p95_latency_ms": 7842.33,
    "p99_latency_ms": 9123.45,
    "max_latency_ms": 12456.78
  },

  "throughput": {
    "orders_per_second": 1.93,
    "target_rate": 30.0,
    "actual_rate": 29.2
  },

  "api_metrics": {
    "total_requests": 235,
    "avg_response_time_ms": 145.2,
    "p95_response_time_ms": 287.5,
    "error_rate": 0.021
  },

  "resources": {
    "orderbook": {
      "avg_cpu_percent": 45.2,
      "max_cpu_percent": 78.3,
      "avg_memory_mb": 512.4
    }
  },

  "success_criteria": {
    "min_success_rate": {"threshold": 0.95, "actual": 0.979, "passed": true},
    "max_p95_latency": {"threshold": 10.0, "actual": 7.842, "passed": true}
  }
}
```

### Verdict Calculation

**SUCCESS**: All success criteria met
**WARNING**: Minor issues (soft failures, close to thresholds)
**FAILURE**: Critical criteria failed

---

## Metric Calculations

### Success Rate

```
success_rate = (total_submitted - orders_failed) / total_submitted
```

Example: `(232 - 5) / 232 = 0.979 = 97.9%`

### Fill Rate

```
fill_rate = orders_filled / total_submitted
```

Example: `201 / 232 = 0.866 = 86.6%`

**Note**: Fill rate will show 0% in Anvil fork mode because the database cannot detect settlement events (Anvil lacks `debug_traceTransaction`). See [Known Limitations](../README.md#known-limitations).

### Percentiles

Calculated using NumPy's percentile function on order latencies:

- **P50 (median)**: 50% of orders faster than this
- **P95**: 95% of orders faster than this (outlier threshold)
- **P99**: 99% of orders faster than this (worst-case excluding extremes)

### Throughput

```
orders_per_second = total_submitted / test_duration_seconds
```

Example: `232 orders / 120s = 1.93 orders/second`

### API Response Time

Average across all API calls:

```
avg_response_time = sum(all_durations) / num_requests
```

---

## Real-Time Metrics Streaming

### MetricsEventStream

Live metrics updates during test execution:

```python
from cow_performance.metrics.streaming import MetricsEventStream
from cow_performance.metrics.store import MetricsStore

store = MetricsStore()
stream = MetricsEventStream(store)

# Use as async context manager and async iterator
async with stream:
    async for event in stream:
        if event.event_type == "order":
            print(f"Order update: {event.data}")
        elif event.event_type == "api":
            print(f"API metric: {event.data}")
```

### Event Types

- `order` - Order lifecycle update (creation, submission, fill, failure, etc.)
- `api` - API request/response metric recorded
- `resource` - Container resource sample recorded

### CLI Live Display

During test runs, live metrics display updates every 5 seconds:

```
Running test... [120s remaining]
Orders: 45 submitted, 42 filled (93.3%)
Latency: 4.2s avg, 6.8s p95
Rate: 2.1/s (target: 2.0/s)
```

**Implementation**: `src/cow_performance/cli/live_display.py`

---

## Storage Management

### Bounded Storage

MetricsStore uses bounded storage to prevent memory exhaustion:

```python
config = MetricsStoreConfig(
    max_orders=100000,               # Max orders to keep
    max_api_metrics_per_endpoint=10000,  # Max API metrics per endpoint
    max_resource_samples_per_container=1000,  # Max resource samples
)
```

### Eviction Strategy

When limits reached:
- **Orders**: Oldest orders evicted first (FIFO)
- **API metrics**: Oldest per endpoint evicted
- **Resource samples**: Oldest samples evicted

### Memory Usage

Approximate memory per item:
- Order: ~500 bytes
- API metric: ~200 bytes
- Resource sample: ~100 bytes

**100k orders = ~50 MB**

### Callbacks on Metrics Updates

Register callbacks to receive metrics updates in real time:

```python
def on_metric_update(metric_type: str, metric: object) -> None:
    if metric_type == "order":
        save_to_database(metric)

store.register_callback(on_metric_update)
```

**Implementation**: `src/cow_performance/metrics/store.py`

---

## Complete Metrics Catalog

### Core Order Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `total_submitted` | Counter | Orders submitted to API |
| `orders_filled` | Counter | Orders fully filled |
| `orders_partially_filled` | Counter | Orders partially filled |
| `orders_failed` | Counter | Orders that failed |
| `orders_expired` | Counter | Orders that expired |
| `orders_cancelled` | Counter | Orders cancelled by user |
| `success_rate` | Ratio | (submitted - failed) / submitted |
| `fill_rate` | Ratio | filled / submitted |

### Latency Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `avg_order_latency_ms` | ms | Average time creation → fill |
| `p50_latency_ms` | ms | Median order latency |
| `p95_latency_ms` | ms | 95th percentile latency |
| `p99_latency_ms` | ms | 99th percentile latency |
| `max_latency_ms` | ms | Maximum order latency |
| `submission_latency_ms` | ms | Time to submit to API |
| `acceptance_latency_ms` | ms | Time for API to accept |
| `fill_latency_ms` | ms | Time from acceptance to fill |

### API Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `total_requests` | Counter | Total API requests made |
| `successful_requests` | Counter | HTTP 2xx responses |
| `failed_requests` | Counter | HTTP 4xx/5xx responses |
| `avg_response_time_ms` | ms | Average API response time |
| `p95_response_time_ms` | ms | 95th percentile API latency |
| `error_rate` | Ratio | failed / total requests |
| `timeout_count` | Counter | Request timeouts |

### Resource Metrics (per container)

| Metric | Unit | Description |
|--------|------|-------------|
| `cpu_percent` | % | CPU usage (can exceed 100%) |
| `memory_bytes` | bytes | Memory usage |
| `memory_percent` | % | Memory as % of limit |
| `network_rx_bytes` | bytes | Network received |
| `network_tx_bytes` | bytes | Network transmitted |
| `disk_read_bytes` | bytes | Disk read |
| `disk_write_bytes` | bytes | Disk write |

### Throughput Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| `orders_per_second` | /s | Actual order submission rate |
| `target_rate` | /s | Configured target rate |
| `rate_variance` | % | Deviation from target |

---

## Autopilot Auction Metrics (from CoW Protocol services)

These metrics are exported by the `autopilot` service (scraped at `autopilot:9589/metrics`) and used by the **Auction Activity** Grafana dashboard. They are always available while the Docker stack is running — no cow-perf test needs to be active.

| Metric | Type | Description | Example Query |
|--------|------|-------------|---------------|
| `gp_v2_autopilot_auction_creations` | counter | Total auctions initiated since startup | `rate(gp_v2_autopilot_auction_creations[5m]) * 60` → auctions/min |
| `gp_v2_autopilot_runloop_auction` | gauge | Last executed auction ID; stalls indicate a stuck run loop | direct read |
| `gp_v2_autopilot_auction_candidate_orders{class}` | gauge | Orders entering the current auction by class (Limit/Market/Liquidity) | `sum(gp_v2_autopilot_auction_candidate_orders)` |
| `gp_v2_autopilot_auction_solvable_orders{class}` | gauge | Subset of candidate orders that passed all filters | compare vs candidate for filter rate |
| `gp_v2_autopilot_auction_filtered_orders{reason}` | gauge | Orders excluded from the auction by reason (insufficient_balance, out_of_market, missing_price, dust_order, other) | `gp_v2_autopilot_auction_filtered_orders{reason="out_of_market"}` |
| `gp_v2_autopilot_runloop_auction_winners` | histogram | Number of winning solver solutions per auction (normally 1) | `_sum / _count` → avg winners/auction |
| `gp_v2_autopilot_runloop_matched_unsettled` | counter | Orders included in a losing solver solution — missed settlement opportunities | `increase(gp_v2_autopilot_runloop_matched_unsettled[5m])` |
| `gp_v2_autopilot_auction_overhead_time{phase}` | counter | Cumulative seconds spent per autopilot phase (settlement_indexer, maintenance_total, update_solvabe_orders, db_cleanup, serialize_request) | `rate(gp_v2_autopilot_auction_overhead_time[1m])` |
| `gp_v2_autopilot_auction_update_stage_time{stage}` | histogram | Per-stage time for the solvable orders cache update (balance_filtering, banned_user_filtering, etc.) | `histogram_quantile(0.95, rate(gp_v2_autopilot_auction_update_stage_time_bucket[5m]))` |
| `gp_v2_autopilot_table_rows{table}` | gauge | Row counts for key DB tables (settlements, orders, auctions, competition_auctions) | `gp_v2_autopilot_table_rows{table="settlements"}` |

### Auction Timing and Order Wait Time

All accepted orders enter the next auction update cycle (≤ one block period, currently 10s). The best available proxy for "how long an order waits before a solver first sees it" is:

```
wait_time ≈ cow_perf_order_acceptance_latency_seconds + (0 to 10s block wait)
```

`cow_perf_order_acceptance_latency_seconds` (a cow-perf histogram) measures creation → orderbook acceptance. The Auction Activity dashboard plots p50/p95/p99 of this metric.

### TVL per Auction

TVL (total value settled per auction in USD) is **not available** from existing metrics. The autopilot, driver, and orderbook services do not expose token amounts or USD values per auction. Tracking this would require new instrumentation on the autopilot side to emit per-auction sell/buy token amounts.

---

## See Also

- [Benchmarking Guide](benchmarking.md)
- [Reports and Baselines](reports.md)
- [CLI Reference](cli.md)
- [Prometheus Integration](../README.md#monitoring)
