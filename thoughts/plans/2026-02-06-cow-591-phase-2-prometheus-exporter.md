# COW-591 Phase 2: Extended Prometheus Metrics Implementation Plan

## Overview

Implement the remaining Prometheus metrics for COW-591: per-trader metrics, API performance metrics, resource metrics, and baseline comparison metrics. This completes the full grant deliverable for Prometheus exporters.

**Ticket**: [COW-591-prometheus-exporters.md](../tickets/COW-591-prometheus-exporters.md)
**Phase Reference**: [COW-591-implementation-phases.md](../tasks/COW-591-implementation-phases.md)
**Phase 1 Plan**: [2026-02-05-cow-591-phase-1-prometheus-exporter.md](./2026-02-05-cow-591-phase-1-prometheus-exporter.md)
**Enables**: COW-593 (Grafana Dashboards) depends on these metrics

---

## Current State Analysis

### What Phase 1 Implemented

1. **MetricsRegistry** (`src/cow_performance/prometheus/metrics.py`):
   - Order counters: `orders_created`, `orders_submitted`, `orders_filled`, `orders_failed`, `orders_expired`, `orders_active`
   - Latency histograms: `submission_latency`, `orderbook_latency`, `settlement_latency`, `order_lifecycle`
   - Throughput gauges: `orders_per_second`, `target_rate`, `actual_rate`
   - Test metadata: `test_info`, `test_start_timestamp`, `test_duration_seconds`, `num_traders`, `test_progress_percent`

2. **PrometheusExporter** (`src/cow_performance/prometheus/exporter.py`):
   - HTTP server on configurable port (default 9091)
   - MetricsStore callback integration for `metric_type == "order"`
   - Comment at line 116: `# API and resource metrics will be handled in Phase 2`

3. **CLI Integration** (`src/cow_performance/cli/commands/run.py`):
   - `--prometheus-port` flag enables exporter during test runs

### Existing Infrastructure for Phase 2

1. **API Metrics** (`src/cow_performance/metrics/models.py:154-179`):
   - `APIMetrics` dataclass with: `endpoint`, `method`, `timestamp`, `duration`, `status_code`, `error_message`
   - MetricsStore callback emits `("api", metric)` on each API call

2. **Resource Metrics** (`src/cow_performance/metrics/models.py:183-248`):
   - `ResourceSample` dataclass with: `cpu_percent`, `memory_bytes`, `network_rx_bytes`, `network_tx_bytes`
   - MetricsStore callback emits `("resource", sample)` on each sample

3. **Baseline Comparison** (`src/cow_performance/comparison/`):
   - `ComparisonResult` with `metric_comparisons`, `regressions`, severity counts
   - `MetricComparison` with `percent_change`, `regression_severity`

4. **Trader Tracking**:
   - `OrderMetadata.owner` contains trader Ethereum address
   - Default 10 traders per test (configurable)

---

## Desired End State

After this plan is complete:

1. **MetricsRegistry** has all Phase 2 metrics:
   - API metrics: `api_requests_total`, `api_response_time_seconds`, `api_errors_total`
   - Resource metrics: `container_cpu_percent`, `container_memory_bytes`, `container_network_rx_bytes`, `container_network_tx_bytes`
   - Per-trader metrics: `trader_orders_submitted`, `trader_orders_filled`, `traders_active`
   - Baseline comparison metrics: `baseline_comparison_percent`, `regression_detected`, `regressions_total`

2. **PrometheusExporter** handles all callback types:
   - `metric_type == "api"` → updates API metrics
   - `metric_type == "resource"` → updates resource metrics
   - Order callbacks also update per-trader metrics

3. **Baseline comparison metrics** can be populated after a comparison is run

### Verification

```bash
# Start a test with Prometheus exporter
cow-perf run --prometheus-port 9091 --duration 60

# Verify Phase 2 metrics
curl http://localhost:9091/metrics | grep -E "cow_perf_(api|container|trader|baseline|regression)"

# Expected output includes:
# cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"}
# cow_perf_container_cpu_percent{container="orderbook"}
# cow_perf_trader_orders_submitted{trader_index="0"}
# cow_perf_traders_active
```

---

## What We're NOT Doing

- Grafana dashboard creation (COW-593 - separate ticket)
- Alerting rules (COW-598 - separate ticket)
- Docker Compose changes for exporter service
- Changes to MetricsStore callback system (already works)

---

## Implementation Approach

1. **Add metrics incrementally** - API, then resource, then per-trader, then baseline
2. **Extend existing callback handler** - `_on_metric_update()` already has structure for multiple types
3. **Use trader index for cardinality management** - Not full addresses (bounded to num_traders)
4. **Baseline metrics are "push" style** - Populated explicitly after comparison, not via callback

---

## Phase 1: Add API Metrics

### Overview

Add Prometheus metrics for API request tracking. The infrastructure already exists - `InstrumentedOrderbookClient` records `APIMetrics` to `MetricsStore`, which emits `("api", metric)` callbacks.

### Changes Required

#### 1. Extend MetricsRegistry

**File**: `src/cow_performance/prometheus/metrics.py`

Add new initialization method after `_init_test_metadata()`:

```python
def _init_api_metrics(self) -> None:
    """Initialize API performance metrics."""
    self.api_requests_total = Counter(
        "cow_perf_api_requests_total",
        "Total API requests",
        ["endpoint", "method", "status"],
        registry=self.registry,
    )
    self.api_response_time = Histogram(
        "cow_perf_api_response_time_seconds",
        "API response time distribution",
        ["endpoint", "method"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        registry=self.registry,
    )
    self.api_errors_total = Counter(
        "cow_perf_api_errors_total",
        "Total API errors by type",
        ["endpoint", "error_type"],
        registry=self.registry,
    )
```

Call this method in `__init__()`:

```python
def __init__(self, registry: CollectorRegistry | None = None):
    self.registry = registry or CollectorRegistry()
    self._init_order_metrics()
    self._init_latency_metrics()
    self._init_throughput_metrics()
    self._init_test_metadata()
    self._init_api_metrics()  # Add this line
```

#### 2. Extend PrometheusExporter Callback

**File**: `src/cow_performance/prometheus/exporter.py`

Add import at top:

```python
from cow_performance.metrics.models import APIMetrics, OrderMetadata, OrderStatus
```

Update `_on_metric_update()` method to handle API metrics:

```python
def _on_metric_update(self, metric_type: str, metric: object) -> None:
    """
    Callback for MetricsStore updates.

    Maps incoming metrics to Prometheus metrics based on type.
    """
    try:
        if metric_type == "order" and isinstance(metric, OrderMetadata):
            self._update_order_metrics(metric)
        elif metric_type == "api" and isinstance(metric, APIMetrics):
            self._update_api_metrics(metric)
        # Resource metrics will be handled next
    except Exception as e:
        logger.warning("Error updating Prometheus metric: %s", e)
```

Add new method for API metrics:

```python
def _update_api_metrics(self, api_metric: APIMetrics) -> None:
    """Update API-related Prometheus metrics from APIMetrics."""
    endpoint = api_metric.endpoint
    method = api_metric.method
    status = str(api_metric.status_code)

    # Increment request counter
    self._metrics.api_requests_total.labels(
        endpoint=endpoint,
        method=method,
        status=status,
    ).inc()

    # Record response time
    self._metrics.api_response_time.labels(
        endpoint=endpoint,
        method=method,
    ).observe(api_metric.duration)

    # Track errors (non-2xx responses)
    if not api_metric.is_success:
        error_type = self._classify_api_error(api_metric)
        self._metrics.api_errors_total.labels(
            endpoint=endpoint,
            error_type=error_type,
        ).inc()

def _classify_api_error(self, api_metric: APIMetrics) -> str:
    """Classify API error by type."""
    status = api_metric.status_code
    if 400 <= status < 500:
        return "client_error"
    elif 500 <= status < 600:
        return "server_error"
    elif api_metric.error_message:
        if "timeout" in api_metric.error_message.lower():
            return "timeout"
        elif "connection" in api_metric.error_message.lower():
            return "connection_error"
    return "unknown"
```

#### 3. Add Manual Recording Methods

**File**: `src/cow_performance/prometheus/exporter.py`

Add after existing manual methods:

```python
# --- API Recording Methods ---

def record_api_request(
    self,
    endpoint: str,
    method: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record an API request."""
    self._metrics.api_requests_total.labels(
        endpoint=endpoint,
        method=method,
        status=str(status_code),
    ).inc()
    self._metrics.api_response_time.labels(
        endpoint=endpoint,
        method=method,
    ).observe(duration_seconds)

def record_api_error(self, endpoint: str, error_type: str) -> None:
    """Record an API error."""
    self._metrics.api_errors_total.labels(
        endpoint=endpoint,
        error_type=error_type,
    ).inc()
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/` passes
- [x] `poetry run ruff check src/cow_performance/prometheus/` passes

---

## Phase 2: Add Resource Metrics

### Overview

Add Prometheus metrics for container resource monitoring. The `ResourceMonitor` already collects samples and emits `("resource", sample)` callbacks via MetricsStore.

### Changes Required

#### 1. Extend MetricsRegistry

**File**: `src/cow_performance/prometheus/metrics.py`

Add new initialization method:

```python
def _init_resource_metrics(self) -> None:
    """Initialize container resource metrics."""
    self.container_cpu_percent = Gauge(
        "cow_perf_container_cpu_percent",
        "Container CPU usage percentage",
        ["container"],
        registry=self.registry,
    )
    self.container_memory_bytes = Gauge(
        "cow_perf_container_memory_bytes",
        "Container memory usage in bytes",
        ["container"],
        registry=self.registry,
    )
    self.container_network_rx_bytes = Gauge(
        "cow_perf_container_network_rx_bytes",
        "Container network bytes received",
        ["container"],
        registry=self.registry,
    )
    self.container_network_tx_bytes = Gauge(
        "cow_perf_container_network_tx_bytes",
        "Container network bytes transmitted",
        ["container"],
        registry=self.registry,
    )
```

Call in `__init__()`:

```python
def __init__(self, registry: CollectorRegistry | None = None):
    self.registry = registry or CollectorRegistry()
    self._init_order_metrics()
    self._init_latency_metrics()
    self._init_throughput_metrics()
    self._init_test_metadata()
    self._init_api_metrics()
    self._init_resource_metrics()  # Add this line
```

#### 2. Extend PrometheusExporter Callback

**File**: `src/cow_performance/prometheus/exporter.py`

Add import:

```python
from cow_performance.metrics.models import APIMetrics, OrderMetadata, OrderStatus, ResourceSample
```

Update `_on_metric_update()`:

```python
def _on_metric_update(self, metric_type: str, metric: object) -> None:
    """
    Callback for MetricsStore updates.

    Maps incoming metrics to Prometheus metrics based on type.
    """
    try:
        if metric_type == "order" and isinstance(metric, OrderMetadata):
            self._update_order_metrics(metric)
        elif metric_type == "api" and isinstance(metric, APIMetrics):
            self._update_api_metrics(metric)
        elif metric_type == "resource":
            self._update_resource_metrics(metric)
    except Exception as e:
        logger.warning("Error updating Prometheus metric: %s", e)
```

Add new method:

```python
def _update_resource_metrics(self, metric: object) -> None:
    """Update resource-related Prometheus metrics.

    Note: MetricsStore emits (container_name, sample) tuple for resource metrics.
    """
    # Handle tuple format from MetricsStore.add_resource_sample callback
    if isinstance(metric, tuple) and len(metric) == 2:
        container_name, sample = metric
        if isinstance(sample, ResourceSample):
            self._metrics.container_cpu_percent.labels(
                container=container_name
            ).set(sample.cpu_percent)
            self._metrics.container_memory_bytes.labels(
                container=container_name
            ).set(sample.memory_bytes)
            self._metrics.container_network_rx_bytes.labels(
                container=container_name
            ).set(sample.network_rx_bytes)
            self._metrics.container_network_tx_bytes.labels(
                container=container_name
            ).set(sample.network_tx_bytes)
```

**Note**: Check how MetricsStore emits resource callbacks. Looking at `store.py:239`, it calls `_notify_callbacks("resource", sample)`. We need to verify if it passes just the sample or a tuple. If it's just the sample, we need the container name from somewhere.

#### 3. Verify MetricsStore Callback Format

**File**: `src/cow_performance/metrics/store.py`

Check line 239 - the callback receives `("resource", sample)` but `sample` is just `ResourceSample`, not including container_name.

**Fix needed**: Update the callback to pass container name. This requires a small change to MetricsStore:

**File**: `src/cow_performance/metrics/store.py`

Find `add_resource_sample()` method and update the callback notification:

```python
def add_resource_sample(self, container_name: str, sample: ResourceSample) -> None:
    """Add a resource sample for a container."""
    # ... existing code ...

    # Change this line:
    # self._notify_callbacks("resource", sample)
    # To include container_name:
    self._notify_callbacks("resource", (container_name, sample))
```

This is a minor interface change but necessary for Prometheus to know which container the sample belongs to.

#### 4. Add Manual Recording Methods

**File**: `src/cow_performance/prometheus/exporter.py`

```python
# --- Resource Recording Methods ---

def update_container_resources(
    self,
    container: str,
    cpu_percent: float,
    memory_bytes: int,
    network_rx_bytes: int = 0,
    network_tx_bytes: int = 0,
) -> None:
    """Update resource metrics for a container."""
    self._metrics.container_cpu_percent.labels(container=container).set(cpu_percent)
    self._metrics.container_memory_bytes.labels(container=container).set(memory_bytes)
    self._metrics.container_network_rx_bytes.labels(container=container).set(network_rx_bytes)
    self._metrics.container_network_tx_bytes.labels(container=container).set(network_tx_bytes)
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/` passes
- [x] `poetry run ruff check src/cow_performance/` passes

---

## Phase 3: Add Per-Trader Metrics

### Overview

Add Prometheus metrics for per-trader order tracking. To manage label cardinality, use trader index (0, 1, 2, ...) instead of full Ethereum addresses.

### Cardinality Management Strategy

**Approach**: Use trader index as label value instead of full address.

- Default tests have 10 traders → 10 label values
- Max reasonable tests might have 100 traders → 100 label values
- This keeps cardinality bounded and predictable

**Trade-off**: Loses direct address visibility, but:
- Address can be looked up from test logs if needed
- Index provides sufficient granularity for analysis
- Prometheus scraping remains efficient

### Changes Required

#### 1. Extend MetricsRegistry

**File**: `src/cow_performance/prometheus/metrics.py`

Add new initialization method:

```python
def _init_trader_metrics(self) -> None:
    """Initialize per-trader metrics.

    Note: Uses trader_index (0, 1, 2, ...) instead of full addresses
    to manage label cardinality. Default tests have ~10 traders.
    """
    self.trader_orders_submitted = Counter(
        "cow_perf_trader_orders_submitted",
        "Orders submitted per trader",
        ["trader_index"],
        registry=self.registry,
    )
    self.trader_orders_filled = Counter(
        "cow_perf_trader_orders_filled",
        "Orders filled per trader",
        ["trader_index"],
        registry=self.registry,
    )
    self.traders_active = Gauge(
        "cow_perf_traders_active",
        "Count of currently active traders",
        registry=self.registry,
    )
```

Call in `__init__()`:

```python
def __init__(self, registry: CollectorRegistry | None = None):
    self.registry = registry or CollectorRegistry()
    self._init_order_metrics()
    self._init_latency_metrics()
    self._init_throughput_metrics()
    self._init_test_metadata()
    self._init_api_metrics()
    self._init_resource_metrics()
    self._init_trader_metrics()  # Add this line
```

#### 2. Extend PrometheusExporter for Trader Tracking

**File**: `src/cow_performance/prometheus/exporter.py`

Add trader tracking state in `__init__()`:

```python
def __init__(
    self,
    port: int = DEFAULT_PORT,
    scenario: str = "default",
):
    self.port = port
    self.scenario = scenario
    self._metrics = MetricsRegistry()
    self._running = False
    self._store: MetricsStore | None = None
    self._active_orders: set[str] = set()

    # Trader tracking (Phase 2)
    self._trader_address_to_index: dict[str, str] = {}
    self._active_traders: set[str] = set()  # Set of trader indices with active orders
    self._orders_by_trader: dict[str, set[str]] = {}  # trader_index -> set of order_uids
```

Update `_update_order_metrics()` to also update trader metrics:

```python
def _update_order_metrics(self, order: OrderMetadata) -> None:
    """Update order-related Prometheus metrics from OrderMetadata."""
    status = order.current_status
    scenario = self.scenario

    # Get or assign trader index
    trader_index = self._get_trader_index(order.owner)

    # Track active orders
    if status == OrderStatus.CREATED:
        self._metrics.orders_created.labels(scenario=scenario).inc()
        self._active_orders.add(order.order_uid)

        # Update per-trader tracking
        self._metrics.trader_orders_submitted.labels(trader_index=trader_index).inc()
        if trader_index not in self._orders_by_trader:
            self._orders_by_trader[trader_index] = set()
        self._orders_by_trader[trader_index].add(order.order_uid)
        self._active_traders.add(trader_index)
        self._metrics.traders_active.set(len(self._active_traders))

    elif status == OrderStatus.SUBMITTED:
        # ... existing code unchanged ...

    elif status in (OrderStatus.ACCEPTED, OrderStatus.OPEN):
        # ... existing code unchanged ...

    elif status == OrderStatus.FILLED:
        self._metrics.orders_filled.labels(scenario=scenario).inc()
        self._active_orders.discard(order.order_uid)

        # Update per-trader tracking
        self._metrics.trader_orders_filled.labels(trader_index=trader_index).inc()
        self._remove_order_from_trader(trader_index, order.order_uid)

        # ... rest of existing code for latencies ...

    elif status == OrderStatus.FAILED:
        self._metrics.orders_failed.labels(scenario=scenario).inc()
        self._active_orders.discard(order.order_uid)
        self._remove_order_from_trader(trader_index, order.order_uid)

    elif status == OrderStatus.EXPIRED:
        self._metrics.orders_expired.labels(scenario=scenario).inc()
        self._active_orders.discard(order.order_uid)
        self._remove_order_from_trader(trader_index, order.order_uid)

    elif status == OrderStatus.CANCELLED:
        self._active_orders.discard(order.order_uid)
        self._remove_order_from_trader(trader_index, order.order_uid)

    # Update active orders gauge
    self._metrics.orders_active.labels(scenario=scenario).set(len(self._active_orders))
```

Add helper methods:

```python
def _get_trader_index(self, owner_address: str) -> str:
    """Get or assign a trader index for an address.

    Uses sequential indices (0, 1, 2, ...) to manage label cardinality.
    """
    if owner_address not in self._trader_address_to_index:
        index = len(self._trader_address_to_index)
        self._trader_address_to_index[owner_address] = str(index)
    return self._trader_address_to_index[owner_address]

def _remove_order_from_trader(self, trader_index: str, order_uid: str) -> None:
    """Remove an order from trader tracking and update active traders."""
    if trader_index in self._orders_by_trader:
        self._orders_by_trader[trader_index].discard(order_uid)
        # If trader has no more active orders, remove from active set
        if not self._orders_by_trader[trader_index]:
            self._active_traders.discard(trader_index)
            self._metrics.traders_active.set(len(self._active_traders))
```

#### 3. Add Manual Recording Methods

```python
# --- Trader Recording Methods ---

def record_trader_order_submitted(self, trader_index: int) -> None:
    """Record an order submission for a trader."""
    self._metrics.trader_orders_submitted.labels(trader_index=str(trader_index)).inc()

def record_trader_order_filled(self, trader_index: int) -> None:
    """Record an order fill for a trader."""
    self._metrics.trader_orders_filled.labels(trader_index=str(trader_index)).inc()

def set_active_traders(self, count: int) -> None:
    """Set the count of active traders."""
    self._metrics.traders_active.set(count)
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/` passes
- [x] `poetry run ruff check src/cow_performance/prometheus/` passes

---

## Phase 4: Add Baseline Comparison Metrics

### Overview

Add Prometheus metrics for baseline comparison results. These are "push" metrics - populated explicitly after a comparison is run, not via MetricsStore callbacks.

### Changes Required

#### 1. Extend MetricsRegistry

**File**: `src/cow_performance/prometheus/metrics.py`

Add new initialization method:

```python
def _init_comparison_metrics(self) -> None:
    """Initialize baseline comparison metrics."""
    self.baseline_comparison_percent = Gauge(
        "cow_perf_baseline_comparison_percent",
        "Percentage change from baseline (positive = increase)",
        ["metric", "baseline_id"],
        registry=self.registry,
    )
    self.regression_detected = Gauge(
        "cow_perf_regression_detected",
        "Count of detected regressions by severity",
        ["severity"],
        registry=self.registry,
    )
    self.regressions_total = Counter(
        "cow_perf_regressions_total",
        "Total regressions detected by severity",
        ["severity"],
        registry=self.registry,
    )
```

Call in `__init__()`:

```python
def __init__(self, registry: CollectorRegistry | None = None):
    self.registry = registry or CollectorRegistry()
    self._init_order_metrics()
    self._init_latency_metrics()
    self._init_throughput_metrics()
    self._init_test_metadata()
    self._init_api_metrics()
    self._init_resource_metrics()
    self._init_trader_metrics()
    self._init_comparison_metrics()  # Add this line
```

#### 2. Add Comparison Recording Methods to PrometheusExporter

**File**: `src/cow_performance/prometheus/exporter.py`

Add import:

```python
from cow_performance.comparison.models import ComparisonResult, RegressionSeverity
```

Add methods:

```python
# --- Baseline Comparison Methods ---

def record_comparison_result(self, result: ComparisonResult) -> None:
    """Record metrics from a baseline comparison result.

    This populates comparison metrics from a ComparisonResult object,
    typically called after running a baseline comparison.
    """
    baseline_id = result.baseline_id

    # Record percentage changes for each metric comparison
    for metric_name, comparison in result.metric_comparisons.items():
        self._metrics.baseline_comparison_percent.labels(
            metric=metric_name,
            baseline_id=baseline_id,
        ).set(comparison.percent_change * 100)  # Convert to percentage

    # Record regression counts by severity
    self._metrics.regression_detected.labels(severity="critical").set(result.critical_count)
    self._metrics.regression_detected.labels(severity="major").set(result.major_count)
    self._metrics.regression_detected.labels(severity="minor").set(result.minor_count)

    # Increment total regression counters
    for _ in range(result.critical_count):
        self._metrics.regressions_total.labels(severity="critical").inc()
    for _ in range(result.major_count):
        self._metrics.regressions_total.labels(severity="major").inc()
    for _ in range(result.minor_count):
        self._metrics.regressions_total.labels(severity="minor").inc()

def set_baseline_comparison(
    self,
    metric_name: str,
    baseline_id: str,
    percent_change: float,
) -> None:
    """Set a single baseline comparison metric."""
    self._metrics.baseline_comparison_percent.labels(
        metric=metric_name,
        baseline_id=baseline_id,
    ).set(percent_change)

def set_regression_counts(
    self,
    critical: int = 0,
    major: int = 0,
    minor: int = 0,
) -> None:
    """Set regression detection counts."""
    self._metrics.regression_detected.labels(severity="critical").set(critical)
    self._metrics.regression_detected.labels(severity="major").set(major)
    self._metrics.regression_detected.labels(severity="minor").set(minor)
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/` passes
- [x] `poetry run ruff check src/cow_performance/prometheus/` passes

---

## Phase 5: Update Module Exports

### Overview

Update `__init__.py` to export any new types needed by consumers.

### Changes Required

**File**: `src/cow_performance/prometheus/__init__.py`

```python
"""Prometheus metrics exporter for CoW Protocol performance testing."""

from cow_performance.prometheus.exporter import PrometheusExporter
from cow_performance.prometheus.metrics import MetricsRegistry

__all__ = ["PrometheusExporter", "MetricsRegistry"]
```

No changes needed - exports remain the same.

---

## Phase 6: Write Tests

### Overview

Add unit tests for all new Phase 2 metrics and update integration tests.

### Changes Required

#### 1. Update Unit Tests for MetricsRegistry

**File**: `tests/unit/prometheus/test_metrics.py`

Add tests for new metrics:

```python
class TestMetricsRegistryPhase2:
    """Tests for Phase 2 metrics in MetricsRegistry."""

    def test_api_metrics_exist(self) -> None:
        """Test that all API metrics are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_api_requests_total" in output
        assert "cow_perf_api_response_time_seconds" in output
        assert "cow_perf_api_errors_total" in output

    def test_resource_metrics_exist(self) -> None:
        """Test that all resource metrics are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_container_cpu_percent" in output
        assert "cow_perf_container_memory_bytes" in output
        assert "cow_perf_container_network_rx_bytes" in output
        assert "cow_perf_container_network_tx_bytes" in output

    def test_trader_metrics_exist(self) -> None:
        """Test that all per-trader metrics are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_trader_orders_submitted" in output
        assert "cow_perf_trader_orders_filled" in output
        assert "cow_perf_traders_active" in output

    def test_comparison_metrics_exist(self) -> None:
        """Test that all comparison metrics are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_baseline_comparison_percent" in output
        assert "cow_perf_regression_detected" in output
        assert "cow_perf_regressions_total" in output

    def test_api_request_counter(self) -> None:
        """Test API request counter with labels."""
        metrics = MetricsRegistry()
        metrics.api_requests_total.labels(
            endpoint="/api/v1/orders",
            method="POST",
            status="200",
        ).inc()

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0' in output

    def test_api_response_time_histogram(self) -> None:
        """Test API response time histogram."""
        metrics = MetricsRegistry()
        metrics.api_response_time.labels(
            endpoint="/api/v1/orders",
            method="POST",
        ).observe(0.15)

        output = generate_latest(metrics.registry).decode()
        assert "cow_perf_api_response_time_seconds_bucket" in output
        assert "cow_perf_api_response_time_seconds_sum" in output

    def test_container_resource_gauges(self) -> None:
        """Test container resource gauges."""
        metrics = MetricsRegistry()
        metrics.container_cpu_percent.labels(container="orderbook").set(45.5)
        metrics.container_memory_bytes.labels(container="orderbook").set(1024 * 1024 * 512)

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_container_cpu_percent{container="orderbook"} 45.5' in output
        assert 'cow_perf_container_memory_bytes{container="orderbook"}' in output

    def test_trader_counter_with_index(self) -> None:
        """Test per-trader counter using index."""
        metrics = MetricsRegistry()
        metrics.trader_orders_submitted.labels(trader_index="0").inc()
        metrics.trader_orders_submitted.labels(trader_index="0").inc()
        metrics.trader_orders_submitted.labels(trader_index="1").inc()

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_trader_orders_submitted{trader_index="0"} 2.0' in output
        assert 'cow_perf_trader_orders_submitted{trader_index="1"} 1.0' in output
```

#### 2. Update Unit Tests for PrometheusExporter

**File**: `tests/unit/prometheus/test_exporter.py`

Add tests for Phase 2 functionality:

```python
class TestPrometheusExporterPhase2:
    """Tests for Phase 2 exporter functionality."""

    def test_record_api_request(self) -> None:
        """Test API request recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_api_request(
            endpoint="/api/v1/orders",
            method="POST",
            status_code=200,
            duration_seconds=0.15,
        )

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0' in output

    def test_record_api_error(self) -> None:
        """Test API error recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_api_error(endpoint="/api/v1/orders", error_type="server_error")

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="server_error"} 1.0' in output

    def test_update_container_resources(self) -> None:
        """Test container resource updates."""
        exporter = PrometheusExporter(scenario="test")
        exporter.update_container_resources(
            container="orderbook",
            cpu_percent=45.5,
            memory_bytes=536870912,
            network_rx_bytes=1024000,
            network_tx_bytes=512000,
        )

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_container_cpu_percent{container="orderbook"} 45.5' in output
        assert 'cow_perf_container_memory_bytes{container="orderbook"} 536870912' in output

    def test_trader_index_assignment(self) -> None:
        """Test that trader addresses get sequential indices."""
        exporter = PrometheusExporter(scenario="test")

        # Simulate orders from different traders
        idx1 = exporter._get_trader_index("0xAAA")
        idx2 = exporter._get_trader_index("0xBBB")
        idx3 = exporter._get_trader_index("0xAAA")  # Same as first

        assert idx1 == "0"
        assert idx2 == "1"
        assert idx3 == "0"  # Same address gets same index

    def test_active_traders_tracking(self) -> None:
        """Test active traders gauge updates."""
        exporter = PrometheusExporter(scenario="test")

        # Create orders from two traders
        order1 = OrderMetadata(
            order_uid="order-1",
            owner="0xAAA",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        order2 = OrderMetadata(
            order_uid="order-2",
            owner="0xBBB",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )

        exporter._on_metric_update("order", order1)
        exporter._on_metric_update("order", order2)

        output = generate_latest(exporter.registry).decode()
        assert "cow_perf_traders_active 2.0" in output

        # Fill one order
        order1.current_status = OrderStatus.FILLED
        order1.completion_time = 1030.0
        exporter._on_metric_update("order", order1)

        output = generate_latest(exporter.registry).decode()
        assert "cow_perf_traders_active 1.0" in output

    def test_set_regression_counts(self) -> None:
        """Test regression count setting."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_regression_counts(critical=1, major=2, minor=3)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_regression_detected{severity="critical"} 1.0' in output
        assert 'cow_perf_regression_detected{severity="major"} 2.0' in output
        assert 'cow_perf_regression_detected{severity="minor"} 3.0' in output


class TestPrometheusExporterAPICallback:
    """Tests for API callback handling."""

    def test_callback_handles_api_metrics(self) -> None:
        """Test callback processes APIMetrics correctly."""
        exporter = PrometheusExporter(scenario="test")

        api_metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.25,
            status_code=200,
        )
        exporter._on_metric_update("api", api_metric)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0' in output

    def test_callback_classifies_errors(self) -> None:
        """Test that non-2xx responses are classified as errors."""
        exporter = PrometheusExporter(scenario="test")

        api_metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.5,
            status_code=500,
            error_message="Internal server error",
        )
        exporter._on_metric_update("api", api_metric)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="server_error"} 1.0' in output
```

#### 3. Add import for time module

**File**: `tests/unit/prometheus/test_exporter.py`

Add at top:

```python
import time

from cow_performance.metrics.models import APIMetrics, OrderMetadata, OrderStatus
```

### Success Criteria

#### Automated Verification

- [x] `poetry run black src/ tests/` passes
- [x] `poetry run ruff check src/ tests/` passes
- [x] `poetry run mypy src/` passes
- [x] `poetry run pytest tests/unit/prometheus/` passes (all new tests)
- [x] `poetry run pytest` passes (full test suite)

#### Manual Verification

- [x] `cow-perf run --prometheus-port 9091 --dry-run` starts exporter
- [x] `curl http://localhost:9091/metrics | grep cow_perf_api_` shows API metrics
- [x] `curl http://localhost:9091/metrics | grep cow_perf_container_` shows resource metrics
- [x] `curl http://localhost:9091/metrics | grep cow_perf_trader_` shows trader metrics
- [x] `curl http://localhost:9091/metrics | grep cow_perf_baseline_` shows comparison metrics

---

## Testing Strategy

### Unit Tests

- **MetricsRegistry**: Verify all Phase 2 metrics are registered with correct names, types, and labels
- **PrometheusExporter**: Test manual recording methods, callback handling for API/resource types, trader index assignment

### Integration Tests

- **HTTP Server**: Verify new metrics appear in `/metrics` output
- **End-to-end**: Run a short test and verify API metrics are populated from actual API calls

### Manual Testing Steps

1. **Start test with Prometheus exporter**:
   ```bash
   cow-perf run --prometheus-port 9091 --duration 30
   ```

2. **In another terminal, verify metrics**:
   ```bash
   # API metrics
   curl -s http://localhost:9091/metrics | grep "cow_perf_api_"

   # Resource metrics (requires docker services running)
   curl -s http://localhost:9091/metrics | grep "cow_perf_container_"

   # Per-trader metrics
   curl -s http://localhost:9091/metrics | grep "cow_perf_trader_"
   ```

3. **Verify Prometheus can scrape** (requires docker-compose with monitoring profile):
   ```bash
   docker compose --profile monitoring up -d
   # Check http://localhost:9090/targets for cow-performance-test target
   ```

---

## Performance Considerations

- **API metrics**: Each API call triggers callback; Prometheus increments are O(1)
- **Resource metrics**: Sampled every 5s by ResourceMonitor; bounded by number of containers (~5)
- **Per-trader metrics**: Bounded by num_traders (default 10, max ~100); uses index not address
- **Baseline comparison**: Push-based, only called after explicit comparison; not high-frequency

---

## Summary of Files Modified

| File | Changes |
|------|---------|
| `src/cow_performance/prometheus/metrics.py` | Add 4 new `_init_*` methods for API, resource, trader, comparison metrics |
| `src/cow_performance/prometheus/exporter.py` | Add callback handlers, helper methods, manual recording methods |
| `src/cow_performance/metrics/store.py` | Update resource callback to include container_name (minor) |
| `tests/unit/prometheus/test_metrics.py` | Add `TestMetricsRegistryPhase2` class |
| `tests/unit/prometheus/test_exporter.py` | Add `TestPrometheusExporterPhase2`, `TestPrometheusExporterAPICallback` classes |

---

## References

- Original ticket: [COW-591-prometheus-exporters.md](../tickets/COW-591-prometheus-exporters.md)
- Implementation phases: [COW-591-implementation-phases.md](../tasks/COW-591-implementation-phases.md)
- Phase 1 plan: [2026-02-05-cow-591-phase-1-prometheus-exporter.md](./2026-02-05-cow-591-phase-1-prometheus-exporter.md)
- Enables: COW-593 (Grafana Dashboards)
- prometheus-client docs: https://prometheus.github.io/client_python/
