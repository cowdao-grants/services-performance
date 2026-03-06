# COW-591 Phase 1: Prometheus Exporter Implementation Plan

## Overview

Implement a real-time Prometheus HTTP exporter for the CoW Protocol performance testing suite. This exporter will expose metrics at a `/metrics` endpoint that Prometheus can scrape during test execution, enabling live monitoring and visualization in Grafana.

**Ticket**: [COW-591-prometheus-exporters.md](../tickets/COW-591-prometheus-exporters.md)
**Phase Reference**: [COW-591-implementation-phases.md](../tasks/COW-591-implementation-phases.md)
**PoC Evaluation**: [poc-evaluation.md](../research/poc-evaluation.md)

---

## Current State Analysis

### What Already Exists

1. **MetricsStore Callback System** (`src/cow_performance/metrics/store.py:269-298`):
   - `register_callback(callback)` - Registers a callback for metric updates
   - `unregister_callback(callback)` - Removes a callback
   - `_notify_callbacks(metric_type, metric)` - Invokes callbacks on each metric update
   - Callbacks receive `(metric_type: str, metric: object)` where `metric_type` is `"order"`, `"api"`, or `"resource"`

2. **OrderMetadata Model** (`src/cow_performance/metrics/models.py:27-126`):
   - Timestamps: `creation_time`, `submission_time`, `acceptance_time`, `first_fill_time`, `completion_time`
   - Status: `current_status` (OrderStatus enum)
   - Helper methods: `get_time_to_submit()`, `get_time_to_accept()`, `get_time_to_fill()`, `get_total_lifecycle_time()`
   - **Note**: No `order_type` field exists - order type must be inferred or tracked separately

3. **OrderStatus Enum** (`src/cow_performance/metrics/models.py:13-24`):
   - `CREATED`, `SUBMITTED`, `ACCEPTED`, `OPEN`, `FILLED`, `PARTIALLY_FILLED`, `EXPIRED`, `CANCELLED`, `FAILED`

4. **prometheus-client Dependency** (`pyproject.toml:26`):
   - Already installed: `prometheus-client = "^0.19.0"`

5. **Static Prometheus Output** (`src/cow_performance/cli/output.py:72-91`):
   - `format_metrics_prometheus_text()` generates one-shot text format at test end
   - Not suitable for real-time scraping

6. **Prometheus Scrape Config** (`configs/prometheus.yml`):
   - Scrapes CoW services (orderbook, autopilot, driver, baseline)
   - Does not include performance test exporter

### Key Discoveries

- `MetricsStore` is instantiated at `src/cow_performance/cli/commands/run.py:294`
- The callback system was designed for COW-611 streaming but works perfectly for Prometheus
- `__version__` is available from `src/cow_performance/__init__.py:6`
- OrderMetadata does NOT have an `order_type` field - we'll use a default label value

---

## Desired End State

After this plan is complete:

1. A new `src/cow_performance/prometheus/` module exists with:
   - `MetricsRegistry` class defining all Phase 1 Prometheus metrics
   - `PrometheusExporter` class with HTTP server and MetricsStore integration

2. Running `cow-perf run --prometheus-port 9091` starts an HTTP server exposing metrics at `http://localhost:9091/metrics`

3. Prometheus can scrape the endpoint and receive real-time metrics updates during test execution

4. All Phase 1 metrics are exposed:
   - Order counters (created, submitted, filled, failed, expired, active)
   - Latency histograms (submission, orderbook, settlement, lifecycle)
   - Throughput gauges (orders_per_second, target_rate, actual_rate)
   - Test metadata (test_info, start_timestamp, duration, num_traders, progress)

### Verification

```bash
# Start a test with Prometheus exporter
cow-perf run --prometheus-port 9091 --duration 60

# In another terminal, verify metrics
curl http://localhost:9091/metrics | grep cow_perf_

# Expected output includes:
# cow_perf_orders_created_total
# cow_perf_orders_submitted_total
# cow_perf_submission_latency_seconds_bucket
# cow_perf_test_info
```

---

## What We're NOT Doing

Phase 2 items (deferred to separate implementation):
- Per-trader metrics (`cow_perf_trader_orders_submitted`, `cow_perf_trader_orders_filled`)
- API performance metrics (`cow_perf_api_requests_total`, `cow_perf_api_response_time_seconds`)
- Resource metrics (`cow_perf_container_cpu_percent`, `cow_perf_container_memory_bytes`)
- Baseline comparison metrics (`cow_perf_baseline_comparison_percent`, `cow_perf_regression_detected`)

Not in scope:
- Grafana dashboard creation (COW-593)
- Alerting rules (COW-598)
- Docker Compose changes for the exporter service

---

## Implementation Approach

1. **Separate metrics definitions from exporter logic** for testability
2. **Use a custom CollectorRegistry** to avoid conflicts with the default registry during testing
3. **Hook into MetricsStore callbacks** for real-time updates (no polling)
4. **Run HTTP server in daemon thread** to avoid blocking test execution
5. **Use port 9091** (not 9090) to avoid conflict with Prometheus server itself

---

## Phase 1: Create Module Structure

### Overview

Create the `src/cow_performance/prometheus/` module with proper exports.

### Changes Required

#### 1. Create Module Directory

**File**: `src/cow_performance/prometheus/__init__.py`

```python
"""Prometheus metrics exporter for CoW Protocol performance testing."""

from cow_performance.prometheus.exporter import PrometheusExporter
from cow_performance.prometheus.metrics import MetricsRegistry

__all__ = ["PrometheusExporter", "MetricsRegistry"]
```

#### 2. Create Empty Test Directories

**Files**:
- `tests/unit/prometheus/__init__.py`
- `tests/integration/__init__.py` (if doesn't exist)

### Success Criteria

- [x] Directory structure exists as specified

---

## Phase 2: Implement MetricsRegistry

### Overview

Define all Phase 1 Prometheus metrics in a dedicated class. Using a class allows dependency injection of the registry for testing.

### Changes Required

#### 1. Create Metrics Definitions

**File**: `src/cow_performance/prometheus/metrics.py`

```python
"""Prometheus metric definitions for CoW Protocol performance testing.

All metrics are prefixed with `cow_perf_` to distinguish from production metrics.
Uses a custom CollectorRegistry to avoid conflicts during testing.
"""

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
)


class MetricsRegistry:
    """
    Registry of Prometheus metrics for performance testing.

    Uses a custom CollectorRegistry to avoid conflicts with the default registry.
    All metrics are prefixed with `cow_perf_` as per naming convention.

    Example:
        registry = MetricsRegistry()
        registry.orders_created.labels(scenario="stress").inc()
    """

    def __init__(self, registry: CollectorRegistry | None = None):
        """
        Initialize the metrics registry.

        Args:
            registry: Optional custom registry. Creates new one if not provided.
        """
        self.registry = registry or CollectorRegistry()
        self._init_order_metrics()
        self._init_latency_metrics()
        self._init_throughput_metrics()
        self._init_test_metadata()

    def _init_order_metrics(self) -> None:
        """Initialize order-related counters and gauges."""
        # Counters for order lifecycle events
        self.orders_created = Counter(
            "cow_perf_orders_created_total",
            "Total number of orders created",
            ["scenario"],
            registry=self.registry,
        )
        self.orders_submitted = Counter(
            "cow_perf_orders_submitted_total",
            "Total number of orders submitted to API",
            ["scenario"],
            registry=self.registry,
        )
        self.orders_filled = Counter(
            "cow_perf_orders_filled_total",
            "Total number of orders successfully filled",
            ["scenario"],
            registry=self.registry,
        )
        self.orders_failed = Counter(
            "cow_perf_orders_failed_total",
            "Total number of orders that failed",
            ["scenario"],
            registry=self.registry,
        )
        self.orders_expired = Counter(
            "cow_perf_orders_expired_total",
            "Total number of orders that expired",
            ["scenario"],
            registry=self.registry,
        )

        # Gauge for active orders
        self.orders_active = Gauge(
            "cow_perf_orders_active",
            "Currently active (non-terminal) orders",
            ["scenario"],
            registry=self.registry,
        )

    def _init_latency_metrics(self) -> None:
        """Initialize latency histograms with appropriate buckets."""
        # Submission latency (fast operation: creation to submission)
        self.submission_latency = Histogram(
            "cow_perf_submission_latency_seconds",
            "Time from order creation to API submission",
            ["scenario"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
            registry=self.registry,
        )

        # Orderbook acceptance latency (submission to acceptance)
        self.orderbook_latency = Histogram(
            "cow_perf_orderbook_latency_seconds",
            "Time from submission to orderbook acceptance",
            ["scenario"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
            registry=self.registry,
        )

        # Settlement latency (slow operation: acceptance to fill)
        self.settlement_latency = Histogram(
            "cow_perf_settlement_latency_seconds",
            "Time from acceptance to order fill",
            ["scenario"],
            buckets=[10, 30, 60, 120, 300, 600],
            registry=self.registry,
        )

        # Full lifecycle (creation to completion)
        self.order_lifecycle = Histogram(
            "cow_perf_order_lifecycle_seconds",
            "Total order lifecycle duration (creation to completion)",
            ["scenario"],
            buckets=[10, 30, 60, 120, 300, 600, 900],
            registry=self.registry,
        )

    def _init_throughput_metrics(self) -> None:
        """Initialize throughput gauges."""
        self.orders_per_second = Gauge(
            "cow_perf_orders_per_second",
            "Current order submission rate",
            ["scenario"],
            registry=self.registry,
        )
        self.target_rate = Gauge(
            "cow_perf_target_rate",
            "Configured target submission rate",
            ["scenario"],
            registry=self.registry,
        )
        self.actual_rate = Gauge(
            "cow_perf_actual_rate",
            "Measured actual submission rate",
            ["scenario"],
            registry=self.registry,
        )

    def _init_test_metadata(self) -> None:
        """Initialize test metadata metrics."""
        self.test_info = Info(
            "cow_perf_test",
            "Performance test information",
            registry=self.registry,
        )
        self.test_start_timestamp = Gauge(
            "cow_perf_test_start_timestamp",
            "Test start Unix timestamp",
            ["scenario"],
            registry=self.registry,
        )
        self.test_duration_seconds = Gauge(
            "cow_perf_test_duration_seconds",
            "Configured test duration in seconds",
            ["scenario"],
            registry=self.registry,
        )
        self.num_traders = Gauge(
            "cow_perf_num_traders",
            "Number of simulated traders",
            ["scenario"],
            registry=self.registry,
        )
        self.test_progress_percent = Gauge(
            "cow_perf_test_progress_percent",
            "Test completion percentage (0-100)",
            ["scenario"],
            registry=self.registry,
        )
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/metrics.py` passes

---

## Phase 3: Implement PrometheusExporter

### Overview

Implement the main exporter class with HTTP server and MetricsStore callback integration.

### Changes Required

#### 1. Create Exporter Class

**File**: `src/cow_performance/prometheus/exporter.py`

```python
"""Prometheus HTTP exporter for CoW Protocol performance testing metrics.

Exposes metrics at /metrics endpoint for Prometheus scraping.
Integrates with MetricsStore via callbacks for real-time updates.
"""

import logging
import platform
import time
from typing import TYPE_CHECKING

from prometheus_client import start_http_server

from cow_performance import __version__
from cow_performance.metrics.models import OrderMetadata, OrderStatus
from cow_performance.prometheus.metrics import MetricsRegistry

if TYPE_CHECKING:
    from cow_performance.metrics.store import MetricsStore

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Prometheus HTTP exporter for performance testing.

    Exposes metrics at /metrics endpoint for Prometheus scraping.
    Integrates with MetricsStore via callbacks for real-time updates.

    Example:
        exporter = PrometheusExporter(port=9091, scenario="stress-test")
        exporter.start()

        # Register with MetricsStore for real-time updates
        exporter.register_with_store(metrics_store)

        # ... run tests ...

        exporter.stop()
    """

    DEFAULT_PORT = 9091

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        scenario: str = "default",
    ):
        """
        Initialize the Prometheus exporter.

        Args:
            port: Port for HTTP server (default: 9091)
            scenario: Scenario name for metric labels
        """
        self.port = port
        self.scenario = scenario
        self._metrics = MetricsRegistry()
        self._running = False
        self._store: "MetricsStore | None" = None
        self._active_orders: set[str] = set()

    @property
    def registry(self) -> "CollectorRegistry":
        """Get the Prometheus CollectorRegistry."""
        from prometheus_client import CollectorRegistry

        return self._metrics.registry

    def start(self) -> None:
        """Start the HTTP server for metrics exposition."""
        if self._running:
            logger.warning("Prometheus exporter already running on port %d", self.port)
            return

        try:
            start_http_server(self.port, registry=self._metrics.registry)
            self._running = True
            logger.info("Prometheus exporter started on port %d", self.port)
        except OSError as e:
            logger.error("Failed to start Prometheus exporter on port %d: %s", self.port, e)
            raise

    def stop(self) -> None:
        """Stop the exporter and unregister callbacks."""
        if not self._running:
            return

        # Unregister from MetricsStore if registered
        if self._store is not None:
            self._store.unregister_callback(self._on_metric_update)
            self._store = None

        self._running = False
        logger.info("Prometheus exporter stopped")

    def register_with_store(self, store: "MetricsStore") -> None:
        """
        Register with MetricsStore for real-time metric updates.

        Args:
            store: The MetricsStore to receive updates from
        """
        self._store = store
        store.register_callback(self._on_metric_update)
        logger.debug("Prometheus exporter registered with MetricsStore")

    def _on_metric_update(self, metric_type: str, metric: object) -> None:
        """
        Callback for MetricsStore updates.

        Maps incoming metrics to Prometheus metrics based on type.
        """
        try:
            if metric_type == "order" and isinstance(metric, OrderMetadata):
                self._update_order_metrics(metric)
            # API and resource metrics will be handled in Phase 2
        except Exception as e:
            logger.warning("Error updating Prometheus metric: %s", e)

    def _update_order_metrics(self, order: OrderMetadata) -> None:
        """Update order-related Prometheus metrics from OrderMetadata."""
        status = order.current_status
        scenario = self.scenario

        # Track active orders
        if status == OrderStatus.CREATED:
            self._metrics.orders_created.labels(scenario=scenario).inc()
            self._active_orders.add(order.order_uid)

        elif status == OrderStatus.SUBMITTED:
            self._metrics.orders_submitted.labels(scenario=scenario).inc()

            # Record submission latency if available
            latency = order.get_time_to_submit()
            if latency is not None:
                self._metrics.submission_latency.labels(scenario=scenario).observe(latency)

        elif status in (OrderStatus.ACCEPTED, OrderStatus.OPEN):
            # Record orderbook acceptance latency
            latency = order.get_time_to_accept()
            if latency is not None:
                self._metrics.orderbook_latency.labels(scenario=scenario).observe(latency)

        elif status == OrderStatus.FILLED:
            self._metrics.orders_filled.labels(scenario=scenario).inc()
            self._active_orders.discard(order.order_uid)

            # Record settlement latency (acceptance to fill)
            latency = order.get_time_to_fill()
            if latency is not None:
                self._metrics.settlement_latency.labels(scenario=scenario).observe(latency)

            # Record full lifecycle
            lifecycle = order.get_total_lifecycle_time()
            if lifecycle is not None:
                self._metrics.order_lifecycle.labels(scenario=scenario).observe(lifecycle)

        elif status == OrderStatus.FAILED:
            self._metrics.orders_failed.labels(scenario=scenario).inc()
            self._active_orders.discard(order.order_uid)

        elif status == OrderStatus.EXPIRED:
            self._metrics.orders_expired.labels(scenario=scenario).inc()
            self._active_orders.discard(order.order_uid)

        elif status == OrderStatus.CANCELLED:
            # Cancelled orders are tracked but not counted as failed
            self._active_orders.discard(order.order_uid)

        # Update active orders gauge
        self._metrics.orders_active.labels(scenario=scenario).set(len(self._active_orders))

    # --- Manual Recording Methods (for direct updates) ---

    def record_order_created(self) -> None:
        """Record an order creation event."""
        self._metrics.orders_created.labels(scenario=self.scenario).inc()

    def record_order_submitted(self, latency_seconds: float | None = None) -> None:
        """Record an order submission with optional latency."""
        self._metrics.orders_submitted.labels(scenario=self.scenario).inc()
        if latency_seconds is not None:
            self._metrics.submission_latency.labels(scenario=self.scenario).observe(latency_seconds)

    def record_order_filled(
        self,
        settlement_latency: float | None = None,
        lifecycle_latency: float | None = None,
    ) -> None:
        """Record an order fill with optional latencies."""
        self._metrics.orders_filled.labels(scenario=self.scenario).inc()
        if settlement_latency is not None:
            self._metrics.settlement_latency.labels(scenario=self.scenario).observe(
                settlement_latency
            )
        if lifecycle_latency is not None:
            self._metrics.order_lifecycle.labels(scenario=self.scenario).observe(lifecycle_latency)

    def record_order_failed(self) -> None:
        """Record an order failure."""
        self._metrics.orders_failed.labels(scenario=self.scenario).inc()

    def record_order_expired(self) -> None:
        """Record an order expiration."""
        self._metrics.orders_expired.labels(scenario=self.scenario).inc()

    def update_active_orders(self, count: int) -> None:
        """Update the active orders gauge."""
        self._metrics.orders_active.labels(scenario=self.scenario).set(count)

    def update_throughput(
        self,
        orders_per_second: float,
        target_rate: float | None = None,
        actual_rate: float | None = None,
    ) -> None:
        """Update throughput gauges."""
        self._metrics.orders_per_second.labels(scenario=self.scenario).set(orders_per_second)
        if target_rate is not None:
            self._metrics.target_rate.labels(scenario=self.scenario).set(target_rate)
        if actual_rate is not None:
            self._metrics.actual_rate.labels(scenario=self.scenario).set(actual_rate)

    def set_test_info(
        self,
        test_id: str,
        git_commit: str = "",
        duration: int = 0,
    ) -> None:
        """Set test metadata info metric."""
        self._metrics.test_info.info(
            {
                "test_id": test_id,
                "scenario": self.scenario,
                "git_commit": git_commit,
                "duration": str(duration),
                "python_version": platform.python_version(),
                "platform": platform.system(),
                "cow_perf_version": __version__,
            }
        )

    def set_test_start(self, timestamp: float | None = None) -> None:
        """Set test start timestamp."""
        ts = timestamp or time.time()
        self._metrics.test_start_timestamp.labels(scenario=self.scenario).set(ts)

    def set_test_duration(self, duration_seconds: int) -> None:
        """Set configured test duration."""
        self._metrics.test_duration_seconds.labels(scenario=self.scenario).set(duration_seconds)

    def set_num_traders(self, count: int) -> None:
        """Set number of simulated traders."""
        self._metrics.num_traders.labels(scenario=self.scenario).set(count)

    def update_progress(self, percent: float) -> None:
        """Update test progress percentage (0-100)."""
        self._metrics.test_progress_percent.labels(scenario=self.scenario).set(percent)

    def is_running(self) -> bool:
        """Check if exporter is running."""
        return self._running
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/exporter.py` passes

---

## Phase 4: Add CLI Integration

### Overview

Add `--prometheus-port` flag to the run command and integrate the exporter into the test execution flow.

### Changes Required

#### 1. Update Run Command

**File**: `src/cow_performance/cli/commands/run.py`

**Change 1**: Add import at top of file (after line 29):

```python
from cow_performance.prometheus import PrometheusExporter
```

**Change 2**: Update `run_performance_test` function signature (line 68-75) to add parameter:

```python
async def run_performance_test(
    config: PerformanceTestConfig,
    traders: int | None = None,
    duration: int | None = None,
    settlement_wait: int | None = None,
    verbose: bool = False,
    dry_run: bool = False,
    prometheus_port: int | None = None,  # Add this parameter
) -> dict[str, Any]:
```

**Change 3**: After MetricsStore creation (after line 294), add exporter setup:

```python
    # Create shared metrics store for all components
    metrics_store = MetricsStore()

    # Start Prometheus exporter if port specified
    prometheus_exporter: PrometheusExporter | None = None
    if prometheus_port is not None:
        prometheus_exporter = PrometheusExporter(
            port=prometheus_port,
            scenario=config.trading_pattern,  # Use trading pattern as scenario name
        )
        prometheus_exporter.start()
        prometheus_exporter.register_with_store(metrics_store)

        # Set initial test metadata
        prometheus_exporter.set_test_duration(test_duration)
        prometheus_exporter.set_num_traders(num_traders)
        prometheus_exporter.set_test_start()

        if verbose:
            console.print(f"[cyan]Prometheus Exporter:[/cyan] http://localhost:{prometheus_port}/metrics")
            console.print()
```

**Change 4**: Update the finally block (around line 438) to stop the exporter:

```python
    finally:
        # Stop resource monitoring
        if resource_monitor:
            await resource_monitor.stop()

        # Stop Prometheus exporter
        if prometheus_exporter:
            prometheus_exporter.stop()
```

**Change 5**: Update `run_command` function signature (line 502) to add parameter:

```python
def run_command(
    config: PerformanceTestConfig,
    traders: int | None = None,
    duration: int | None = None,
    settlement_wait: int | None = None,
    output_format: str | None = None,
    save_results: bool = False,
    output_file: str | None = None,
    verbose: bool = False,
    dry_run: bool = False,
    prometheus_port: int | None = None,  # Add this parameter
) -> None:
```

**Change 6**: Pass prometheus_port to run_performance_test (around line 536):

```python
        metrics = asyncio.run(
            run_performance_test(
                config=config,
                traders=traders,
                duration=duration,
                settlement_wait=settlement_wait,
                verbose=use_verbose,
                dry_run=dry_run,
                prometheus_port=prometheus_port,  # Add this
            )
        )
```

#### 2. Update CLI Main

**File**: `src/cow_performance/cli/main.py`

Add `--prometheus-port` option to the run command. Find the `run` function and add the option:

```python
    prometheus_port: Optional[int] = typer.Option(
        None,
        "--prometheus-port",
        help="Port for Prometheus metrics exporter (enables exporter when set)",
    ),
```

Pass it to `run_command`:

```python
    run_command(
        config=config,
        traders=traders,
        duration=duration,
        settlement_wait=settlement_wait,
        output_format=output_format,
        save_results=save,
        output_file=output,
        verbose=verbose,
        dry_run=dry_run,
        prometheus_port=prometheus_port,  # Add this
    )
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/cli/` passes

---

## Phase 5: Update Prometheus Configuration

### Overview

Add scrape target for the performance test exporter to the Prometheus configuration.

### Changes Required

#### 1. Update Prometheus Config

**File**: `configs/prometheus.yml`

Add new scrape job after the baseline job (around line 60):

```yaml
  # CoW Performance Test Suite metrics
  # Note: Only active during test runs with --prometheus-port flag
  - job_name: "cow-performance-test"
    scrape_interval: 5s
    static_configs:
      - targets: ["host.docker.internal:9091"]
        labels:
          service: "performance-test"
          component: "cow-perf"
    # Fail gracefully if exporter not running
    scrape_timeout: 5s
```

**Note**: Use `host.docker.internal` for Docker-to-host communication on macOS/Windows. For Linux, use the host's IP or `172.17.0.1` (docker0 bridge).

### Success Criteria

- [x] YAML syntax is valid: `python -c "import yaml; yaml.safe_load(open('configs/prometheus.yml'))"`

---

## Phase 6: Write Tests

### Overview

Write unit tests for MetricsRegistry and PrometheusExporter, plus an integration test for the HTTP endpoint.

### Changes Required

#### 1. Unit Tests for MetricsRegistry

**File**: `tests/unit/prometheus/__init__.py`

```python
"""Unit tests for Prometheus metrics module."""
```

**File**: `tests/unit/prometheus/test_metrics.py`

```python
"""Unit tests for Prometheus metrics registry."""

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from cow_performance.prometheus.metrics import MetricsRegistry


class TestMetricsRegistry:
    """Tests for MetricsRegistry class."""

    def test_creates_custom_registry(self) -> None:
        """Test that MetricsRegistry creates a custom registry."""
        metrics = MetricsRegistry()
        assert metrics.registry is not None
        assert isinstance(metrics.registry, CollectorRegistry)

    def test_uses_provided_registry(self) -> None:
        """Test that MetricsRegistry uses provided registry."""
        custom_registry = CollectorRegistry()
        metrics = MetricsRegistry(registry=custom_registry)
        assert metrics.registry is custom_registry

    def test_order_counters_exist(self) -> None:
        """Test that all order counters are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_orders_created_total" in output
        assert "cow_perf_orders_submitted_total" in output
        assert "cow_perf_orders_filled_total" in output
        assert "cow_perf_orders_failed_total" in output
        assert "cow_perf_orders_expired_total" in output

    def test_order_active_gauge_exists(self) -> None:
        """Test that active orders gauge is registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()
        assert "cow_perf_orders_active" in output

    def test_latency_histograms_exist(self) -> None:
        """Test that all latency histograms are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_submission_latency_seconds" in output
        assert "cow_perf_orderbook_latency_seconds" in output
        assert "cow_perf_settlement_latency_seconds" in output
        assert "cow_perf_order_lifecycle_seconds" in output

    def test_throughput_gauges_exist(self) -> None:
        """Test that all throughput gauges are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_orders_per_second" in output
        assert "cow_perf_target_rate" in output
        assert "cow_perf_actual_rate" in output

    def test_test_metadata_exists(self) -> None:
        """Test that test metadata metrics are registered."""
        metrics = MetricsRegistry()
        output = generate_latest(metrics.registry).decode()

        assert "cow_perf_test_info" in output
        assert "cow_perf_test_start_timestamp" in output
        assert "cow_perf_test_duration_seconds" in output
        assert "cow_perf_num_traders" in output
        assert "cow_perf_test_progress_percent" in output

    def test_counter_increments(self) -> None:
        """Test that counters can be incremented."""
        metrics = MetricsRegistry()
        metrics.orders_created.labels(scenario="test").inc()
        metrics.orders_created.labels(scenario="test").inc()

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_orders_created_total{scenario="test"} 2.0' in output

    def test_histogram_observation(self) -> None:
        """Test that histograms record observations."""
        metrics = MetricsRegistry()
        metrics.submission_latency.labels(scenario="test").observe(0.5)

        output = generate_latest(metrics.registry).decode()
        assert "cow_perf_submission_latency_seconds_bucket" in output
        assert "cow_perf_submission_latency_seconds_sum" in output
        assert "cow_perf_submission_latency_seconds_count" in output

    def test_gauge_set(self) -> None:
        """Test that gauges can be set."""
        metrics = MetricsRegistry()
        metrics.orders_active.labels(scenario="test").set(42)

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_orders_active{scenario="test"} 42.0' in output

    def test_info_metric(self) -> None:
        """Test that info metric can be set."""
        metrics = MetricsRegistry()
        metrics.test_info.info({"test_id": "abc123", "scenario": "stress"})

        output = generate_latest(metrics.registry).decode()
        assert "cow_perf_test_info" in output
        assert 'test_id="abc123"' in output
```

#### 2. Unit Tests for PrometheusExporter

**File**: `tests/unit/prometheus/test_exporter.py`

```python
"""Unit tests for Prometheus exporter."""

import pytest
from prometheus_client import generate_latest

from cow_performance.metrics.models import OrderMetadata, OrderStatus
from cow_performance.prometheus.exporter import PrometheusExporter


class TestPrometheusExporter:
    """Tests for PrometheusExporter class."""

    def test_default_port(self) -> None:
        """Test that default port is 9091."""
        exporter = PrometheusExporter()
        assert exporter.port == 9091

    def test_custom_port(self) -> None:
        """Test that custom port is used."""
        exporter = PrometheusExporter(port=9092)
        assert exporter.port == 9092

    def test_custom_scenario(self) -> None:
        """Test that custom scenario is used."""
        exporter = PrometheusExporter(scenario="stress-test")
        assert exporter.scenario == "stress-test"

    def test_is_running_initially_false(self) -> None:
        """Test that exporter is not running initially."""
        exporter = PrometheusExporter()
        assert exporter.is_running() is False

    def test_record_order_created(self) -> None:
        """Test manual order creation recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_order_created()

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_created_total{scenario="test"} 1.0' in output

    def test_record_order_submitted_with_latency(self) -> None:
        """Test order submission recording with latency."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_order_submitted(latency_seconds=0.25)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_submitted_total{scenario="test"} 1.0' in output
        assert "cow_perf_submission_latency_seconds_sum" in output

    def test_record_order_filled_with_latencies(self) -> None:
        """Test order fill recording with latencies."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_order_filled(settlement_latency=30.0, lifecycle_latency=60.0)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_filled_total{scenario="test"} 1.0' in output
        assert "cow_perf_settlement_latency_seconds_sum" in output
        assert "cow_perf_order_lifecycle_seconds_sum" in output

    def test_record_order_failed(self) -> None:
        """Test order failure recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_order_failed()

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_failed_total{scenario="test"} 1.0' in output

    def test_record_order_expired(self) -> None:
        """Test order expiration recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_order_expired()

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_expired_total{scenario="test"} 1.0' in output

    def test_update_active_orders(self) -> None:
        """Test active orders gauge update."""
        exporter = PrometheusExporter(scenario="test")
        exporter.update_active_orders(5)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_active{scenario="test"} 5.0' in output

    def test_update_throughput(self) -> None:
        """Test throughput gauges update."""
        exporter = PrometheusExporter(scenario="test")
        exporter.update_throughput(
            orders_per_second=10.5,
            target_rate=15.0,
            actual_rate=10.5,
        )

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_per_second{scenario="test"} 10.5' in output
        assert 'cow_perf_target_rate{scenario="test"} 15.0' in output
        assert 'cow_perf_actual_rate{scenario="test"} 10.5' in output

    def test_set_test_info(self) -> None:
        """Test test info metric."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_test_info(test_id="abc123", git_commit="deadbeef", duration=300)

        output = generate_latest(exporter.registry).decode()
        assert "cow_perf_test_info" in output
        assert 'test_id="abc123"' in output
        assert 'scenario="test"' in output

    def test_set_test_duration(self) -> None:
        """Test test duration gauge."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_test_duration(300)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_test_duration_seconds{scenario="test"} 300.0' in output

    def test_set_num_traders(self) -> None:
        """Test num traders gauge."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_num_traders(10)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_num_traders{scenario="test"} 10.0' in output

    def test_update_progress(self) -> None:
        """Test progress percentage gauge."""
        exporter = PrometheusExporter(scenario="test")
        exporter.update_progress(75.0)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_test_progress_percent{scenario="test"} 75.0' in output


class TestPrometheusExporterOrderCallback:
    """Tests for PrometheusExporter order callback handling."""

    def test_callback_handles_created_status(self) -> None:
        """Test callback increments counter for CREATED status."""
        exporter = PrometheusExporter(scenario="test")

        order = OrderMetadata(
            order_uid="order-1",
            owner="0x123",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        exporter._on_metric_update("order", order)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_created_total{scenario="test"} 1.0' in output
        assert 'cow_perf_orders_active{scenario="test"} 1.0' in output

    def test_callback_handles_submitted_status(self) -> None:
        """Test callback increments counter and records latency for SUBMITTED."""
        exporter = PrometheusExporter(scenario="test")

        order = OrderMetadata(
            order_uid="order-1",
            owner="0x123",
            creation_time=1000.0,
            submission_time=1000.5,
            current_status=OrderStatus.SUBMITTED,
        )
        exporter._on_metric_update("order", order)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_submitted_total{scenario="test"} 1.0' in output

    def test_callback_handles_filled_status(self) -> None:
        """Test callback increments counter and records latencies for FILLED."""
        exporter = PrometheusExporter(scenario="test")

        # First add as created to track in active orders
        order = OrderMetadata(
            order_uid="order-1",
            owner="0x123",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        exporter._on_metric_update("order", order)

        # Then update to filled
        order.submission_time = 1000.5
        order.acceptance_time = 1001.0
        order.first_fill_time = 1030.0
        order.completion_time = 1030.0
        order.current_status = OrderStatus.FILLED
        exporter._on_metric_update("order", order)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_filled_total{scenario="test"} 1.0' in output
        assert 'cow_perf_orders_active{scenario="test"} 0.0' in output

    def test_callback_handles_failed_status(self) -> None:
        """Test callback increments counter for FAILED status."""
        exporter = PrometheusExporter(scenario="test")

        # First add as created
        order = OrderMetadata(
            order_uid="order-1",
            owner="0x123",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        exporter._on_metric_update("order", order)

        # Then update to failed
        order.current_status = OrderStatus.FAILED
        exporter._on_metric_update("order", order)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_orders_failed_total{scenario="test"} 1.0' in output
        assert 'cow_perf_orders_active{scenario="test"} 0.0' in output

    def test_callback_ignores_non_order_metrics(self) -> None:
        """Test callback ignores non-order metric types."""
        exporter = PrometheusExporter(scenario="test")

        # Should not raise
        exporter._on_metric_update("api", {"some": "data"})
        exporter._on_metric_update("resource", {"some": "data"})

        # Counters should still be at default
        output = generate_latest(exporter.registry).decode()
        # No increments should have happened
        assert "cow_perf_orders_created_total" in output
```

#### 3. Integration Test

**File**: `tests/integration/test_prometheus_integration.py`

```python
"""Integration tests for Prometheus exporter HTTP endpoint."""

import socket
import time

import pytest
import requests

from cow_performance.prometheus.exporter import PrometheusExporter


def find_free_port() -> int:
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def exporter() -> PrometheusExporter:
    """Create and start an exporter for testing."""
    port = find_free_port()
    exp = PrometheusExporter(port=port, scenario="integration-test")
    exp.start()
    # Give server time to start
    time.sleep(0.1)
    yield exp
    exp.stop()


class TestPrometheusIntegration:
    """Integration tests for Prometheus HTTP endpoint."""

    def test_metrics_endpoint_accessible(self, exporter: PrometheusExporter) -> None:
        """Test that /metrics endpoint is accessible."""
        response = requests.get(f"http://localhost:{exporter.port}/metrics", timeout=5)
        assert response.status_code == 200
        assert "text/plain" in response.headers["Content-Type"]

    def test_metrics_output_valid_prometheus_format(
        self, exporter: PrometheusExporter
    ) -> None:
        """Test that output is valid Prometheus format."""
        response = requests.get(f"http://localhost:{exporter.port}/metrics", timeout=5)
        content = response.text

        # Check for HELP and TYPE comments
        assert "# HELP cow_perf_" in content
        assert "# TYPE cow_perf_" in content

        # Check for expected metric families
        assert "cow_perf_orders_created_total" in content
        assert "cow_perf_submission_latency_seconds" in content

    def test_metrics_update_reflected(self, exporter: PrometheusExporter) -> None:
        """Test that metric updates are reflected in output."""
        # Record some metrics
        exporter.record_order_created()
        exporter.record_order_submitted(latency_seconds=0.1)
        exporter.update_throughput(orders_per_second=5.0)

        # Fetch metrics
        response = requests.get(f"http://localhost:{exporter.port}/metrics", timeout=5)
        content = response.text

        # Verify updates
        assert 'cow_perf_orders_created_total{scenario="integration-test"} 1.0' in content
        assert 'cow_perf_orders_submitted_total{scenario="integration-test"} 1.0' in content
        assert 'cow_perf_orders_per_second{scenario="integration-test"} 5.0' in content

    def test_multiple_exporters_on_different_ports(self) -> None:
        """Test that multiple exporters can run on different ports."""
        port1 = find_free_port()
        port2 = find_free_port()

        exp1 = PrometheusExporter(port=port1, scenario="test1")
        exp2 = PrometheusExporter(port=port2, scenario="test2")

        try:
            exp1.start()
            exp2.start()
            time.sleep(0.1)

            # Both should be accessible
            resp1 = requests.get(f"http://localhost:{port1}/metrics", timeout=5)
            resp2 = requests.get(f"http://localhost:{port2}/metrics", timeout=5)

            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert 'scenario="test1"' in resp1.text
            assert 'scenario="test2"' in resp2.text
        finally:
            exp1.stop()
            exp2.stop()
```

### Success Criteria

#### Automated Verification
- [x] `poetry run black src/ tests/` passes
- [x] `poetry run ruff check src/ tests/` passes
- [x] `poetry run mypy src/` passes
- [x] `poetry run pytest` passes (all tests including new prometheus tests)

#### Manual Verification
- [x] `cow-perf run --help` shows `--prometheus-port` option
- [x] `cow-perf run --prometheus-port 9091 --dry-run` starts exporter and shows URL
- [x] `curl http://localhost:9091/metrics` returns valid Prometheus format with `cow_perf_*` metrics
- [ ] Prometheus UI shows `cow-performance-test` target (when docker-compose is running)

---

## Testing Strategy

### Unit Tests
- **MetricsRegistry**: Verify all metrics are registered with correct names and types
- **PrometheusExporter**: Test manual recording methods, callback handling, and state management

### Integration Tests
- **HTTP Server**: Verify `/metrics` endpoint accessibility and response format
- **Real-time Updates**: Confirm metric changes are reflected in scraped output

### Manual Testing Steps

1. **Start exporter with dry-run test**:
   ```bash
   cow-perf run --prometheus-port 9091 --dry-run --duration 10
   ```

2. **Verify metrics endpoint**:
   ```bash
   curl http://localhost:9091/metrics | grep cow_perf_
   ```

3. **Verify Prometheus can scrape** (requires docker-compose):
   ```bash
   docker compose up prometheus -d
   # Check targets: http://localhost:9090/targets
   ```

4. **Run actual test and observe metrics**:
   ```bash
   # Terminal 1: Start test with exporter
   cow-perf run --prometheus-port 9091 --duration 60

   # Terminal 2: Watch metrics update
   watch -n 2 'curl -s http://localhost:9091/metrics | grep -E "cow_perf_orders_(created|filled)_total"'
   ```

---

## Performance Considerations

- **Callback overhead**: MetricsStore callbacks are synchronous and brief; Prometheus metric updates are thread-safe and fast
- **Label cardinality**: Phase 1 uses only `scenario` label with bounded values
- **HTTP server**: Runs in daemon thread, non-blocking to test execution
- **Memory**: Prometheus client library handles metric storage efficiently

---

## References

- Original ticket: [COW-591-prometheus-exporters.md](../tickets/COW-591-prometheus-exporters.md)
- Implementation phases: [COW-591-implementation-phases.md](../tasks/COW-591-implementation-phases.md)
- PoC evaluation: [poc-evaluation.md](../research/poc-evaluation.md)
- prometheus-client docs: https://prometheus.github.io/client_python/
- Prometheus naming conventions: https://prometheus.io/docs/practices/naming/
