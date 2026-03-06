"""Unit tests for Prometheus metrics registry."""

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
        assert (
            'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0'
            in output
        )

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
        assert 'cow_perf_trader_orders_submitted_total{trader_index="0"} 2.0' in output
        assert 'cow_perf_trader_orders_submitted_total{trader_index="1"} 1.0' in output

    def test_regression_detection_gauge(self) -> None:
        """Test regression detection gauge with severity labels."""
        metrics = MetricsRegistry()
        metrics.regression_detected.labels(severity="critical").set(1)
        metrics.regression_detected.labels(severity="major").set(2)
        metrics.regression_detected.labels(severity="minor").set(3)

        output = generate_latest(metrics.registry).decode()
        assert 'cow_perf_regression_detected{severity="critical"} 1.0' in output
        assert 'cow_perf_regression_detected{severity="major"} 2.0' in output
        assert 'cow_perf_regression_detected{severity="minor"} 3.0' in output
