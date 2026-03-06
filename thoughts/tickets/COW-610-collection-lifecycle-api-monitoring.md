# COW-587.2: Collection - Lifecycle, API & Resource Monitoring

## Summary

Implement the core metrics collection components: order lifecycle tracking, API response timing, and resource utilization monitoring.

## Deliverables

### 1. Order Lifecycle Tracking

- [ ] Implement `OrderLifecycleTracker` class
- [ ] Hook into order creation to capture initial timestamp
- [ ] Hook into order submission to capture submission timestamp
- [ ] Poll orderbook API to detect when order appears
- [ ] Monitor for order status changes (open, filled, expired, cancelled)
- [ ] Detect settlement transactions on-chain (or via API)
- [ ] Calculate lifecycle durations:
  - Submission latency (creation → accepted by API)
  - Orderbook latency (accepted → visible in orderbook)
  - Time to fill (orderbook → filled)
  - Total lifecycle (creation → settled)
- [ ] Handle edge cases (never accepted, expired, cancelled, partial fills)

### 2. API Response Time Monitoring

- [ ] Implement HTTP client wrapper with timing instrumentation
- [ ] Track request/response times for all CoW API endpoints
- [ ] Calculate statistics (min, max, mean, median, P50/P90/P95/P99)
- [ ] Track request rate, success rate, error rate by status code
- [ ] Support per-endpoint metrics
- [ ] Implement connection pooling metrics

### 3. Resource Utilization Monitoring

- [ ] Implement `ResourceMonitor` class
- [ ] Monitor Docker containers (Orderbook API, Autopilot, Driver, Solver, Anvil)
- [ ] Collect via Docker API: CPU%, memory, network I/O, block I/O
- [ ] Sample at configurable intervals
- [ ] Store time-series data for trend analysis

## Technical Notes

* Use `time.perf_counter()` for high-precision timing
* Use Docker Python library for container monitoring
* Metrics collection should add <5% overhead

## Parent Issue

Part of COW-587: Metrics Collection Framework

## Metadata

- URL: https://linear.app/bleu-builders/issue/COW-610/cow-5872-collection-lifecycle-api-and-resource-monitoring
- Identifier: COW-610
- Status: Todo
- Priority: Not set
- Estimate: 3 Points
- Assignee: jefferson@bleu.studio
- Project: cow-performance-testing-suite
- Project milestone: M2 — Performance Benchmarking
- Git Branch: jefferson/cow-610-cow-5872-collection-lifecycle-api-resource-monitoring
- Created: 2026-01-27T20:11:40.042Z
- Updated: 2026-01-27T23:39:23.539Z
