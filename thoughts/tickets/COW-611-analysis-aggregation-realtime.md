# COW-587.3: Analysis - Aggregation & Real-time Updates

## Summary

Implement metrics aggregation for summary statistics and real-time streaming for live monitoring.

## Deliverables

### 1. Metrics Aggregation

- [x] Implement `MetricsAggregator` class (`src/cow_performance/metrics/aggregator.py`)
- [x] Calculate summary statistics across all orders:
  * Total orders created, submitted, filled
  * Success/failure rates
  * Average/median/percentile latencies (p50, p90, p95, p99)
  * Throughput (orders per second)
- [x] Group metrics by:
  * Time windows (per second, per minute) - `aggregate_orders_by_time_window()`
  * Order type (market, limit) - via token pair grouping
  * Token pair - `aggregate_orders_by_token_pair()`
  * Trader - `aggregate_orders_by_owner()`
- [x] Calculate performance indicators:
  * Orders per second (actual throughput) - `calculate_throughput()`
  * Average settlement time - `total_lifecycle.mean`
  * API success rate - `APIAggregateMetrics.success_rate`
  * Error rate - `failure_rate`

### 2. Real-time Metrics Updates

- [x] Implement metrics streaming for live monitoring (`src/cow_performance/metrics/streaming.py`)
  * `MetricsEventStream` - async event stream for real-time monitoring
  * `RollingMetricsSummary` - rolling window summary for live dashboards
- [x] Support callbacks for metrics updates (`MetricsStore.register_callback()`)
- [x] Integrate with CLI progress display (`src/cow_performance/cli/live_display.py`)
  * `LiveMetricsDisplay` - Rich Live display for real-time visualization
  * `create_performance_metrics_dict()` - CLI output with percentiles
- [x] Emit metrics events for external consumers (via callback system)

### 3. Bug Fixes (added during implementation)

- [x] Fix order UID tracking to use real UIDs from API response
  * Standard orders now capture real UID from API
  * Added `update_order_uid()` to `OrderTracker` and `MetricsStore`
- [x] Disable API monitoring for conditional orders (TWAP, stop-loss, good-after-time)
  * These use on-chain submission via ComposableCow, not the orderbook API
  * Added TODO comments for future on-chain event watching implementation

## Technical Notes

* Using `numpy` for efficient percentile calculations
* Implemented lazy calculation of derived metrics
* Callback-based streaming for real-time updates
* Async iteration support for event consumers

## Implementation Files

| Component | File |
|-----------|------|
| MetricsAggregator | `src/cow_performance/metrics/aggregator.py` |
| MetricsEventStream | `src/cow_performance/metrics/streaming.py` |
| RollingMetricsSummary | `src/cow_performance/metrics/streaming.py` |
| LiveMetricsDisplay | `src/cow_performance/cli/live_display.py` |
| UID Tracking Fix | `src/cow_performance/load_generation/trader_simulator.py` |

## Tests

- `tests/unit/test_metrics_aggregator.py` - MetricsAggregator unit tests
- `tests/unit/test_realtime_streaming.py` - Streaming unit tests
- `tests/unit/test_order_lifecycle.py` - UID tracking tests
- `tests/integration/test_cli_live_display.py` - Live display integration tests

## Parent Issue

Part of COW-587: Metrics Collection Framework

## Metadata

- URL: https://linear.app/bleu-builders/issue/COW-611/cow-5873-analysis-aggregation-and-real-time-updates
- Identifier: COW-611
- Status: Done
- Priority: Not set
- Estimate: 2 Points
- Assignee: jefferson@bleu.studio
- Project: cow-performance-testing-suite
- Project milestone: M2 — Performance Benchmarking
- Git Branch: jefferson/cow-611-cow-5873-analysis-aggregation-real-time-updates
- Created: 2026-01-27T20:11:58.449Z
- Updated: 2026-01-29T19:30:00.000Z
