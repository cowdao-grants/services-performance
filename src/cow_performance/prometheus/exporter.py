"""Prometheus HTTP exporter for CoW Protocol performance testing metrics.

Exposes metrics at /metrics endpoint for Prometheus scraping.
Integrates with MetricsStore via callbacks for real-time updates.
"""

import logging
import platform
import time
from typing import TYPE_CHECKING

from prometheus_client import CollectorRegistry, start_http_server

from cow_performance import __version__
from cow_performance.comparison.models import ComparisonResult
from cow_performance.metrics.models import APIMetrics, OrderMetadata, OrderStatus, ResourceSample
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
        self._store: MetricsStore | None = None
        self._active_orders: set[str] = set()

        # Trader tracking (Phase 2)
        self._trader_address_to_index: dict[str, str] = {}
        self._active_traders: set[str] = set()  # Set of trader indices with active orders
        self._orders_by_trader: dict[str, set[str]] = {}  # trader_index -> set of order_uids

    @property
    def registry(self) -> CollectorRegistry:
        """Get the Prometheus CollectorRegistry."""
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
            elif metric_type == "api" and isinstance(metric, APIMetrics):
                self._update_api_metrics(metric)
            elif metric_type == "resource":
                self._update_resource_metrics(metric)
            elif metric_type == "uid_rename" and isinstance(metric, tuple) and len(metric) == 2:
                self._rename_order_uid(str(metric[0]), str(metric[1]))
        except Exception as e:
            logger.warning("Error updating Prometheus metric: %s", e)

    def _update_order_metrics(self, order: OrderMetadata) -> None:
        """Update order-related Prometheus metrics from OrderMetadata."""
        status = order.current_status
        scenario = self.scenario

        # Get or assign trader index for per-trader tracking
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
            self._metrics.orders_submitted.labels(scenario=scenario).inc()

            # Record submission latency if available
            latency = order.get_time_to_submit()
            if latency is not None:
                self._metrics.submission_latency.labels(scenario=scenario).observe(latency)

        elif status in (OrderStatus.ACCEPTED, OrderStatus.OPEN):
            # Record orderbook acceptance latency (submission → acceptance)
            latency = order.get_time_to_accept()
            if latency is not None:
                self._metrics.orderbook_latency.labels(scenario=scenario).observe(latency)

            # Record total acceptance latency (creation → acceptance)
            if order.acceptance_time is not None and order.creation_time is not None:
                total_to_accept = order.acceptance_time - order.creation_time
                if total_to_accept >= 0:
                    self._metrics.order_acceptance_latency.labels(scenario=scenario).observe(
                        total_to_accept
                    )

        elif status == OrderStatus.FILLED:
            self._metrics.orders_filled.labels(scenario=scenario).inc()
            self._active_orders.discard(order.order_uid)

            # Update per-trader tracking
            self._metrics.trader_orders_filled.labels(trader_index=trader_index).inc()
            self._remove_order_from_trader(trader_index, order.order_uid)

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
            self._remove_order_from_trader(trader_index, order.order_uid)

        elif status == OrderStatus.EXPIRED:
            print(
                f"EXPIRED: order_uid={order.order_uid[:10]}..., was_in_active={order.order_uid in self._active_orders}, active_before={len(self._active_orders)}"
            )
            self._metrics.orders_expired.labels(scenario=scenario).inc()
            self._active_orders.discard(order.order_uid)
            print(f"EXPIRED: active_after={len(self._active_orders)}")
            self._remove_order_from_trader(trader_index, order.order_uid)

        elif status == OrderStatus.CANCELLED:
            # Cancelled orders are tracked but not counted as failed
            self._active_orders.discard(order.order_uid)
            self._remove_order_from_trader(trader_index, order.order_uid)

        # Update active orders gauge
        self._metrics.orders_active.labels(scenario=scenario).set(len(self._active_orders))

    def _rename_order_uid(self, old_uid: str, new_uid: str) -> None:
        """Update internal UID references after a temp→real UID swap."""
        if old_uid in self._active_orders:
            self._active_orders.discard(old_uid)
            self._active_orders.add(new_uid)

        for order_set in self._orders_by_trader.values():
            if old_uid in order_set:
                order_set.discard(old_uid)
                order_set.add(new_uid)
                break

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

    def _update_resource_metrics(self, metric: object) -> None:
        """Update resource-related Prometheus metrics.

        Note: MetricsStore emits (container_name, sample) tuple for resource metrics.
        """
        # Handle tuple format from MetricsStore.add_resource_sample callback
        if isinstance(metric, tuple) and len(metric) == 2:
            container_name, sample = metric
            if isinstance(sample, ResourceSample):
                self._metrics.container_cpu_percent.labels(container=container_name).set(
                    sample.cpu_percent
                )
                self._metrics.container_memory_bytes.labels(container=container_name).set(
                    sample.memory_bytes
                )
                self._metrics.container_memory_percent.labels(container=container_name).set(
                    sample.memory_percent
                )
                self._metrics.container_network_rx_bytes.labels(container=container_name).set(
                    sample.network_rx_bytes
                )
                self._metrics.container_network_tx_bytes.labels(container=container_name).set(
                    sample.network_tx_bytes
                )
                self._metrics.container_disk_read_bytes.labels(container=container_name).set(
                    sample.block_read_bytes
                )
                self._metrics.container_disk_write_bytes.labels(container=container_name).set(
                    sample.block_write_bytes
                )
                self._metrics.container_disk_usage_bytes.labels(container=container_name).set(
                    sample.disk_usage_bytes
                )

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

    # --- API Recording Methods (Phase 2) ---

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

    # --- Resource Recording Methods (Phase 2) ---

    def update_container_resources(
        self,
        container: str,
        cpu_percent: float,
        memory_bytes: int,
        network_rx_bytes: int = 0,
        network_tx_bytes: int = 0,
        memory_percent: float | None = None,
        disk_read_bytes: int = 0,
        disk_write_bytes: int = 0,
        disk_usage_bytes: int = 0,
    ) -> None:
        """Update resource metrics for a container."""
        self._metrics.container_cpu_percent.labels(container=container).set(cpu_percent)
        self._metrics.container_memory_bytes.labels(container=container).set(memory_bytes)
        if memory_percent is not None:
            self._metrics.container_memory_percent.labels(container=container).set(memory_percent)
        self._metrics.container_network_rx_bytes.labels(container=container).set(network_rx_bytes)
        self._metrics.container_network_tx_bytes.labels(container=container).set(network_tx_bytes)
        self._metrics.container_disk_read_bytes.labels(container=container).set(disk_read_bytes)
        self._metrics.container_disk_write_bytes.labels(container=container).set(disk_write_bytes)
        self._metrics.container_disk_usage_bytes.labels(container=container).set(disk_usage_bytes)

    # --- Trader Recording Methods (Phase 2) ---

    def record_trader_order_submitted(self, trader_index: int) -> None:
        """Record an order submission for a trader."""
        self._metrics.trader_orders_submitted.labels(trader_index=str(trader_index)).inc()

    def record_trader_order_filled(self, trader_index: int) -> None:
        """Record an order fill for a trader."""
        self._metrics.trader_orders_filled.labels(trader_index=str(trader_index)).inc()

    def set_active_traders(self, count: int) -> None:
        """Set the count of active traders."""
        self._metrics.traders_active.set(count)

    # --- Baseline Comparison Methods (Phase 2) ---

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
            ).set(
                comparison.percent_change * 100
            )  # Convert to percentage

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

    # --- Scaling Experiment Methods ---

    def record_scaling_phase(self, order_count_target: int) -> None:
        """Record the target order count for the current scaling phase."""
        self._metrics.scaling_phase_order_count.labels(scenario=self.scenario).set(
            order_count_target
        )

    def record_complexity_slope(self, metric_name: str, slope: float) -> None:
        """Record the power-law slope from complexity analysis for a given metric."""
        self._metrics.scaling_complexity_slope.labels(
            scenario=self.scenario, metric=metric_name
        ).set(slope)

    def record_rss_snapshot(self, container: str, snapshot: str, rss_bytes: int) -> None:
        """Record a container RSS memory snapshot for a scaling phase.

        Args:
            container: Docker container name.
            snapshot: Either "before" or "after" (relative to the test step).
            rss_bytes: RSS memory in bytes at the time of capture.
        """
        self._metrics.container_rss_snapshot_bytes.labels(
            scenario=self.scenario, container=container, snapshot=snapshot
        ).set(rss_bytes)
