# COW-591: 11 - Prometheus Exporters

**Linear URL**: https://linear.app/bleu-builders/issue/COW-591/11-prometheus-exporters
**Status**: Todo
**Priority**: High
**Estimate**: 5 Points
**Milestone**: M3 — Metrics & Visualization
**Git Branch**: `jefferson/cow-591-11-prometheus-exporters`

## Summary

Implement Prometheus exporters that expose load testing metrics, performance benchmarks, and test metadata in Prometheus format for integration with the existing monitoring stack.

## Background

The CoW Protocol Playground already uses Prometheus and Grafana for monitoring. Integrating the performance testing suite with this existing infrastructure enables unified monitoring and powerful visualization capabilities.

**Existing Dashboard Context:**
The PoC includes two comprehensive Grafana dashboards:

* `latency_dashboard.json` - Autopilot, driver, and solver latency metrics
* `main_dashboard.json` - API, database, orders, and RPC metrics

Our Prometheus exporters should be compatible with these existing dashboards while adding performance-testing-specific metrics.

## Deliverables

### 1. Prometheus Client Setup

**Subtasks:**

- [ ] Add `prometheus-client` Python library dependency
- [ ] Set up Prometheus HTTP server for metrics exposition
- [ ] Configure metrics port (default: 9090 or configurable)
- [ ] Implement graceful startup and shutdown
- [ ] Support running alongside test execution

### 2. Core Metrics Exposition

Implement Prometheus metrics for all key performance indicators.

**Subtasks:**

- [ ] **Order Metrics:**
  * Counter: `cow_perf_orders_created_total`
  * Counter: `cow_perf_orders_submitted_total`
  * Counter: `cow_perf_orders_filled_total`
  * Counter: `cow_perf_orders_failed_total`
  * Counter: `cow_perf_orders_expired_total`
  * Gauge: `cow_perf_orders_active`
- [ ] **Latency Metrics (Histograms):**
  * Histogram: `cow_perf_submission_latency_seconds` (buckets: 0.1, 0.5, 1, 2, 5, 10, 30)
  * Histogram: `cow_perf_orderbook_latency_seconds`
  * Histogram: `cow_perf_settlement_latency_seconds`
  * Histogram: `cow_perf_order_lifecycle_seconds`
- [ ] **API Performance Metrics:**
  * Counter: `cow_perf_api_requests_total{endpoint, method, status}`
  * Histogram: `cow_perf_api_response_time_seconds{endpoint, method}`
  * Counter: `cow_perf_api_errors_total{endpoint, error_type}`
- [ ] **Throughput Metrics:**
  * Gauge: `cow_perf_orders_per_second`
  * Gauge: `cow_perf_target_rate`
  * Gauge: `cow_perf_actual_rate`
- [ ] **Resource Metrics:**
  * Gauge: `cow_perf_container_cpu_percent{container}`
  * Gauge: `cow_perf_container_memory_bytes{container}`
  * Gauge: `cow_perf_container_network_rx_bytes{container}`
  * Gauge: `cow_perf_container_network_tx_bytes{container}`

### 3. Test Metadata Metrics

**Subtasks:**

- [ ] Info metric: `cow_perf_test_info{test_id, scenario, git_commit, duration}`
- [ ] Gauge: `cow_perf_test_start_timestamp`
- [ ] Gauge: `cow_perf_test_duration_seconds`
- [ ] Gauge: `cow_perf_num_traders`
- [ ] Gauge: `cow_perf_test_progress_percent`

### 4. Trader Metrics

**Subtasks:**

- [ ] Counter: `cow_perf_trader_orders_submitted{trader_address}`
- [ ] Counter: `cow_perf_trader_orders_filled{trader_address}`
- [ ] Gauge: `cow_perf_traders_active`

### 5. Scenario-Specific Metrics

**Subtasks:**

- [ ] Label all metrics with `scenario` name
- [ ] Support custom metrics for specific scenarios
- [ ] Gauge: `cow_perf_scenario_progress`

### 6. Baseline Comparison Metrics

**Subtasks:**

- [ ] Gauge: `cow_perf_baseline_comparison_percent{metric, baseline_id}`
- [ ] Gauge: `cow_perf_regression_detected{severity}`
- [ ] Counter: `cow_perf_regressions_total{severity}`

### 7. Metrics Registry and Management

**Subtasks:**

- [ ] Implement `PrometheusExporter` class
- [ ] Create metrics registry
- [ ] Support metric registration
- [ ] Implement metric update methods
- [ ] Handle concurrent metric updates safely
- [ ] Support metric reset between test runs

### 8. Integration with Metrics Collection Framework

**Subtasks:**

- [ ] Hook into `OrderLifecycleTracker` to export order metrics
- [ ] Hook into `APIMetrics` to export API metrics
- [ ] Hook into `ResourceMonitor` to export resource metrics
- [ ] Update metrics in real-time as events occur
- [ ] Batch metric updates for efficiency

### 9. HTTP Server for Metrics Exposition

**Subtasks:**

- [ ] Implement HTTP server on configurable port
- [ ] Expose `/metrics` endpoint
- [ ] Return metrics in Prometheus text format
- [ ] Support Prometheus scraping
- [ ] Implement health check endpoint `/health`

### 10. Compatibility with Existing Dashboards

**Subtasks:**

- [ ] Review metrics used in `latency_dashboard.json`:
  - Auction overhead metrics (`*auction_overhead_time`, `*auction_overhead_count`)
  - Runloop metrics (`gp_v2_autopilot_runloop_*`)
  - Driver metrics (`driver_auction_preprocessing_*`, `driver_remaining_solve_time_*`)
- [ ] Review metrics used in `main_dashboard.json`:
  - API metrics (throughput, response times, status codes)
  - Order metrics (in auction, filtered)
  - Database metrics
  - RPC metrics
- [ ] Ensure performance test metrics use compatible naming and labels
- [ ] Add `test_run_id` and `scenario` labels to enable filtering
- [ ] Document how to distinguish perf test metrics from production metrics

### 11. Docker Integration

**Subtasks:**

- [ ] Document Prometheus service configuration
- [ ] Provide Prometheus scrape configuration
- [ ] Ensure metrics accessible from Prometheus container
- [ ] Test with docker-compose setup

## Implementation Details

### Prometheus Exporter Architecture

```python
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    start_http_server,
    generate_latest,
)

class PrometheusExporter:
    def __init__(self, port: int = 9090, registry: Optional[CollectorRegistry] = None):
        self.port = port
        self.registry = registry or CollectorRegistry()
        self.server = None

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize all Prometheus metrics"""
        # Order counters
        self.orders_created = Counter(
            'cow_perf_orders_created_total',
            'Total number of orders created',
            ['scenario', 'order_type'],
            registry=self.registry,
        )

        self.orders_submitted = Counter(
            'cow_perf_orders_submitted_total',
            'Total number of orders submitted',
            ['scenario', 'order_type'],
            registry=self.registry,
        )

        self.orders_filled = Counter(
            'cow_perf_orders_filled_total',
            'Total number of orders filled',
            ['scenario', 'order_type'],
            registry=self.registry,
        )

        # Latency histograms
        self.submission_latency = Histogram(
            'cow_perf_submission_latency_seconds',
            'Order submission latency',
            ['scenario'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
            registry=self.registry,
        )

        self.settlement_latency = Histogram(
            'cow_perf_settlement_latency_seconds',
            'Order settlement latency',
            ['scenario'],
            buckets=[10, 30, 60, 120, 300, 600],
            registry=self.registry,
        )

        # API metrics
        self.api_requests = Counter(
            'cow_perf_api_requests_total',
            'Total API requests',
            ['endpoint', 'method', 'status'],
            registry=self.registry,
        )

        self.api_response_time = Histogram(
            'cow_perf_api_response_time_seconds',
            'API response time',
            ['endpoint', 'method'],
            buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
            registry=self.registry,
        )

        # Throughput gauges
        self.orders_per_second = Gauge(
            'cow_perf_orders_per_second',
            'Current orders per second',
            ['scenario'],
            registry=self.registry,
        )

        # Resource gauges
        self.container_cpu = Gauge(
            'cow_perf_container_cpu_percent',
            'Container CPU usage percentage',
            ['container'],
            registry=self.registry,
        )

        self.container_memory = Gauge(
            'cow_perf_container_memory_bytes',
            'Container memory usage in bytes',
            ['container'],
            registry=self.registry,
        )

        # Test metadata
        self.test_info = Info(
            'cow_perf_test',
            'Performance test information',
            registry=self.registry,
        )

    def start(self):
        """Start HTTP server for metrics exposition"""
        try:
            start_http_server(self.port, registry=self.registry)
            logger.info(f"Prometheus exporter started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus exporter: {e}")
            raise

    def record_order_created(self, scenario: str, order_type: str):
        """Record order creation"""
        self.orders_created.labels(scenario=scenario, order_type=order_type).inc()

    def record_order_submitted(self, scenario: str, order_type: str):
        """Record order submission"""
        self.orders_submitted.labels(scenario=scenario, order_type=order_type).inc()

    def record_submission_latency(self, scenario: str, latency_seconds: float):
        """Record submission latency"""
        self.submission_latency.labels(scenario=scenario).observe(latency_seconds)

    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status: int,
        response_time: float,
    ):
        """Record API request"""
        self.api_requests.labels(
            endpoint=endpoint,
            method=method,
            status=str(status),
        ).inc()

        self.api_response_time.labels(
            endpoint=endpoint,
            method=method,
        ).observe(response_time)

    def update_orders_per_second(self, scenario: str, rate: float):
        """Update orders per second gauge"""
        self.orders_per_second.labels(scenario=scenario).set(rate)

    def update_resource_metrics(self, container: str, cpu_percent: float, memory_bytes: int):
        """Update resource metrics"""
        self.container_cpu.labels(container=container).set(cpu_percent)
        self.container_memory.labels(container=container).set(memory_bytes)

    def set_test_info(self, test_id: str, scenario: str, git_commit: str, duration: int):
        """Set test information"""
        self.test_info.info({
            'test_id': test_id,
            'scenario': scenario,
            'git_commit': git_commit,
            'duration': str(duration),
        })
```

### Integration with Metrics Collector

```python
class MetricsCollector:
    def __init__(
        self,
        prometheus_exporter: Optional[PrometheusExporter] = None,
    ):
        self.prometheus = prometheus_exporter
        # ... other collectors

    async def on_order_created(self, order_uid: str, scenario: str, order_type: str):
        """Handle order creation event"""
        # Update internal metrics
        # ...

        # Export to Prometheus
        if self.prometheus:
            self.prometheus.record_order_created(scenario, order_type)

    async def on_order_submitted(
        self,
        order_uid: str,
        scenario: str,
        order_type: str,
        latency: float,
    ):
        """Handle order submission event"""
        # Update internal metrics
        # ...

        # Export to Prometheus
        if self.prometheus:
            self.prometheus.record_order_submitted(scenario, order_type)
            self.prometheus.record_submission_latency(scenario, latency)
```

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'cow-performance-testing'
    scrape_interval: 5s
    static_configs:
      - targets: ['performance-test:9090']
        labels:
          environment: 'playground'
          service: 'performance-testing'
```

## Acceptance Criteria

- [ ] Prometheus exporter exposes all core metrics
- [ ] Metrics HTTP server starts successfully
- [ ] Metrics accessible at `/metrics` endpoint
- [ ] Metrics format valid for Prometheus scraping
- [ ] Real-time metric updates during test execution
- [ ] Integration with existing Prometheus/Grafana stack
- [ ] Metrics include appropriate labels for filtering
- [ ] Histogram buckets appropriate for metric ranges
- [ ] Docker-compatible configuration
- [ ] Type hints throughout the codebase
- [ ] Unit tests for metric recording
- [ ] Integration tests with Prometheus server

## Testing Requirements

### Unit Tests

* Test metric initialization
* Test metric recording methods
* Test label handling
* Mock Prometheus client

### Integration Tests

* Start exporter and verify HTTP server running
* Submit test requests and verify metrics updated
* Scrape `/metrics` endpoint and validate format
* Test with actual Prometheus instance

## Technical Notes

* Use `prometheus-client` Python library (official client)
* Choose appropriate metric types:
  * Counter for cumulative values (orders submitted)
  * Gauge for current values (active traders)
  * Histogram for distributions (latency)
  * Info for metadata
* Use descriptive metric names following Prometheus conventions
* Include appropriate labels for filtering and grouping
* Choose histogram buckets based on expected value ranges (match existing dashboards where possible)
* Consider cardinality when using labels (avoid high-cardinality labels)
* Implement proper metric cleanup between test runs
* Use separate registry for testing to avoid conflicts
* **Prefix performance test metrics with** `cow_perf_` to distinguish from production metrics
* Add `test_run_id` and `scenario` labels to all perf test metrics
* Reuse existing histogram bucket sizes from CoW Protocol metrics where applicable

## Performance Considerations

* Metric updates should add minimal overhead
* Use efficient label management
* Batch metric updates when possible
* Limit cardinality of labels
* Consider sampling for high-frequency metrics

## Docker Integration

```yaml
# docker-compose.yml
services:
  performance-test:
    build: .
    ports:
      - "9090:9090"  # Prometheus metrics
    environment:
      - PROMETHEUS_PORT=9090

  prometheus:
    image: prom/prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
```

## Related Issues

* Depends on: m2-issue-06-metrics-collection-framework
* Blocks: m3-issue-11-grafana-dashboards
* Related: m5-issue-16-fork-mode-integration (Prometheus in docker-compose)

---

## Planning Notes (M3 Planning — 2026-02-05)

### Current State Analysis

**What already exists:**

1. **Basic Prometheus text output** (`cli/output.py`):
   - `format_metrics_prometheus_text()` generates static text exposition format
   - Only ~10 basic metrics (all gauges): `cow_perf_orders_total`, `cow_perf_orders_per_second`, `cow_perf_avg_order_latency_ms`, etc.
   - **Limitation**: One-shot export at test end, not a real-time scraping endpoint

2. **Rich metrics infrastructure** (from M2):
   - `MetricsStore` - Thread-safe storage with callbacks (`metrics/store.py`)
   - `MetricsEventStream` - Real-time event streaming (`metrics/streaming.py`)
   - `PercentileStats`, `OrderAggregateMetrics`, `APIAggregateMetrics`, `ResourceAggregateMetrics` (`metrics/aggregator.py`)
   - Detailed `OrderMetadata` with 6+ timestamps for lifecycle tracking (`metrics/models.py`)

3. **Docker infrastructure** (`docker-compose.yml`):
   - Prometheus service on port 9090 with `profile: monitoring`
   - `configs/prometheus.yml` already scrapes CoW services (orderbook:9586, autopilot:9589, driver, solver)
   - Grafana service on port 3000 with provisioned datasource

### Adjustments & Clarifications

1. **Port conflict**: The ticket proposes port 9090, but Prometheus itself uses 9090. **Use port 9091** for the performance test exporter to avoid conflicts.

2. **Integration approach**: Hook into `MetricsEventStream` (already has callback infrastructure) rather than polling `MetricsStore`. This provides real-time metric updates.

3. **Metric registration timing**: Metrics should be created at exporter initialization, updated via callbacks from `MetricsEventStream`, and served via HTTP.

4. **PoC dashboards reference**: The ticket references `latency_dashboard.json` and `main_dashboard.json` from a PoC. The PoC is available via PR #17 on bleu/cowprotocol-services. See [thoughts/research/poc-evaluation.md](../research/poc-evaluation.md) for complete PoC analysis and [thoughts/tasks/COW-591-implementation-phases.md](../tasks/COW-591-implementation-phases.md) for how the PoC metrics inform our design. The compatibility section means we should:
   - Use consistent naming conventions (`cow_perf_` prefix)
   - Use similar histogram bucket ranges where applicable
   - Support `scenario` and `test_run_id` labels for filtering

5. **Implementation phases** (full scope, ordered by complexity):
   - **Phase 1** (implement first): Order counters, latency histograms, throughput gauges, test info — these provide core visibility
   - **Phase 2** (implement second): Per-trader metrics, API metrics, resource metrics, baseline comparison metrics — these complete the deliverable

   **Note**: All metrics listed in this ticket are grant deliverables. The phasing is for implementation order only, not scope reduction. See `thoughts/tasks/COW-591-implementation-phases.md` for the detailed breakdown.

### Dependencies

- **Add to pyproject.toml**: `prometheus-client = "^0.20.0"`

### Recommended Implementation Order

1. `src/cow_performance/prometheus/__init__.py` - Module setup
2. `src/cow_performance/prometheus/exporter.py` - `PrometheusExporter` class with HTTP server
3. `src/cow_performance/prometheus/metrics.py` - Metric definitions (Counter, Histogram, Gauge, Info)
4. Integration with `MetricsEventStream` via callbacks
5. CLI flag `--prometheus-port` to enable exporter during test runs
6. Update `configs/prometheus.yml` to scrape the new exporter

### Acceptance Criteria (Full Scope)

All metrics listed in this ticket are grant deliverables. Implementation order:

**Phase 1** (implement first):
- [ ] `/metrics` endpoint accessible during test runs
- [ ] Core order metrics (counters for created/submitted/filled/failed/expired)
- [ ] Latency histograms with appropriate buckets (submission, orderbook, settlement, lifecycle)
- [ ] Throughput gauges (orders_per_second, target_rate, actual_rate)
- [ ] Test metadata info metric

**Phase 2** (implement after Phase 1):
- [ ] Per-trader metrics (with cardinality management - see notes in `COW-591-implementation-phases.md`)
- [ ] API performance metrics (requests_total, response_time, errors by endpoint)
- [ ] Resource metrics (CPU, memory, network per container)
- [ ] Baseline comparison metrics (comparison_percent, regression_detected)

**Note on cardinality**: Per-trader metrics should use bounded label values or sampling to avoid cardinality explosion. Document the approach in implementation.
