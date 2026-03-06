# COW-591 Implementation Phases

> **Purpose**: Document the implementation order for COW-591 metrics. All metrics are grant deliverables; this file tracks the recommended implementation sequence.
>
> **Created**: 2026-02-05 (M3 Planning Revision)
> **Parent Ticket**: [COW-591-prometheus-exporters.md](../tickets/COW-591-prometheus-exporters.md)
> **PoC Analysis**: [poc-evaluation.md](../research/poc-evaluation.md) — Detailed analysis of PoC patterns for metrics and architecture

---

## Phase 1: Core Metrics (Implement First)

These metrics provide the foundational visibility needed for performance testing:

### Order Counters

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_orders_created_total` | Counter | `scenario`, `order_type` | Total orders created |
| `cow_perf_orders_submitted_total` | Counter | `scenario`, `order_type` | Total orders submitted to API |
| `cow_perf_orders_filled_total` | Counter | `scenario`, `order_type` | Total orders successfully filled |
| `cow_perf_orders_failed_total` | Counter | `scenario`, `order_type` | Total orders that failed |
| `cow_perf_orders_expired_total` | Counter | `scenario`, `order_type` | Total orders that expired |
| `cow_perf_orders_active` | Gauge | `scenario` | Currently active orders |

### Latency Histograms

| Metric | Type | Buckets | Description |
|--------|------|---------|-------------|
| `cow_perf_submission_latency_seconds` | Histogram | 0.1, 0.5, 1, 2, 5, 10, 30 | Time to submit order to API |
| `cow_perf_orderbook_latency_seconds` | Histogram | 0.1, 0.5, 1, 2, 5, 10, 30 | Time for orderbook acceptance |
| `cow_perf_settlement_latency_seconds` | Histogram | 10, 30, 60, 120, 300, 600 | Time from acceptance to settlement |
| `cow_perf_order_lifecycle_seconds` | Histogram | 10, 30, 60, 120, 300, 600, 900 | Total order lifecycle duration |

### Throughput Gauges

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_orders_per_second` | Gauge | `scenario` | Current order submission rate |
| `cow_perf_target_rate` | Gauge | `scenario` | Configured target submission rate |
| `cow_perf_actual_rate` | Gauge | `scenario` | Measured actual submission rate |

### Test Metadata

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_test_info` | Info | `test_id`, `scenario`, `git_commit`, `duration`, `python_version`, `platform`, `cow_perf_version` | Test run metadata |
| `cow_perf_test_start_timestamp` | Gauge | `scenario` | Test start Unix timestamp |
| `cow_perf_test_duration_seconds` | Gauge | `scenario` | Configured test duration |
| `cow_perf_num_traders` | Gauge | `scenario` | Number of simulated traders |
| `cow_perf_test_progress_percent` | Gauge | `scenario` | Test completion percentage |

**Note**: Platform metadata (`python_version`, `platform`, `cow_perf_version`) should be sourced from the existing baseline capture logic in `src/cow_performance/baselines/manager.py` to ensure consistency.

---

## Phase 2: Extended Metrics (Implement After Phase 1)

These metrics complete the full grant deliverable with additional visibility:

### Per-Trader Metrics

**Cardinality management strategy**: To avoid label explosion:
- Option A: Only expose top-N traders by volume (configurable, default 10)
- Option B: Use trader index instead of full address (trader_0, trader_1, ...)
- Option C: Aggregate per-trader metrics and expose distribution stats only

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_trader_orders_submitted` | Counter | `trader_address` | Orders submitted per trader |
| `cow_perf_trader_orders_filled` | Counter | `trader_address` | Orders filled per trader |
| `cow_perf_traders_active` | Gauge | - | Count of currently active traders |

### API Performance Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_api_requests_total` | Counter | `endpoint`, `method`, `status` | Total API requests |
| `cow_perf_api_response_time_seconds` | Histogram | 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5 | API response time distribution |
| `cow_perf_api_errors_total` | Counter | `endpoint`, `error_type` | API error count by type |

### Resource Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_container_cpu_percent` | Gauge | `container` | Container CPU usage % |
| `cow_perf_container_memory_bytes` | Gauge | `container` | Container memory usage |
| `cow_perf_container_network_rx_bytes` | Gauge | `container` | Container network received |
| `cow_perf_container_network_tx_bytes` | Gauge | `container` | Container network transmitted |

### Baseline Comparison Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_baseline_comparison_percent` | Gauge | `metric`, `baseline_id` | Percentage change from baseline |
| `cow_perf_regression_detected` | Gauge | `severity` | Count of detected regressions |
| `cow_perf_regressions_total` | Counter | `severity` | Total regressions detected |

### Scenario-Specific Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cow_perf_scenario_progress` | Gauge | `scenario` | Scenario-specific progress |

---

## PoC Reference

> **See also**: [poc-evaluation.md](../research/poc-evaluation.md) for complete PoC analysis including metrics patterns, architecture, and adoption recommendations.

The PoC (PR #17 on bleu/cowprotocol-services) uses K6 for load testing. Its Prometheus config (`playground/performance-test-suite/prometheus/prometheus.yml`) shows:

- Scrape interval: 15s (we use 5s for real-time updates)
- K6 metrics endpoint on port 6565
- CoW Protocol service endpoints (orderbook:8080, autopilot:9589, driver:9590)

Our exporter differs:
- Python-based using `prometheus-client` library (not K6)
- Exposes custom `cow_perf_*` metrics from our metrics framework
- Integrates with MetricsEventStream for real-time updates

---

## Implementation Checklist

### Phase 1 Checklist
- [ ] Add `prometheus-client` to pyproject.toml
- [ ] Create `src/cow_performance/prometheus/` module
- [ ] Implement `PrometheusExporter` class with HTTP server
- [ ] Define Phase 1 metrics (counters, histograms, gauges, info)
- [ ] Hook into `MetricsEventStream` callbacks
- [ ] Add `--prometheus-port` CLI flag
- [ ] Update `configs/prometheus.yml` with scrape target
- [ ] Test /metrics endpoint
- [ ] Verify Prometheus scrapes successfully

### Phase 2 Checklist
- [ ] Implement cardinality management for per-trader metrics
- [ ] Add API performance metrics
- [ ] Add resource metrics (integrate with ResourceMonitor)
- [ ] Add baseline comparison metrics (integrate with ComparisonEngine)
- [ ] Add scenario-specific metrics
- [ ] Document all metrics in `docs/`

---

## Notes

- All metrics are part of the grant deliverable
- Implementation phasing is for development efficiency, not scope reduction
- Phase 1 should be completed before moving to Phase 2
- Both phases must be complete for COW-591 to be considered done
