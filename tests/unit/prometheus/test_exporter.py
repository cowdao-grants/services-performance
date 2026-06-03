"""Unit tests for Prometheus exporter."""

import time

from prometheus_client import generate_latest

from cow_performance.metrics.models import APIMetrics, OrderMetadata, OrderStatus
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

        # Should not raise - these will be handled by specific handlers now
        exporter._on_metric_update("unknown_type", {"some": "data"})

        # Counters should still be at default
        output = generate_latest(exporter.registry).decode()
        # No increments should have happened
        assert "cow_perf_orders_created_total" in output


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
        assert (
            'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0'
            in output
        )

    def test_record_api_error(self) -> None:
        """Test API error recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_api_error(endpoint="/api/v1/orders", error_type="server_error")

        output = generate_latest(exporter.registry).decode()
        assert (
            'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="server_error"} 1.0'
            in output
        )

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
        assert 'cow_perf_container_memory_bytes{container="orderbook"} 5.36870912e+08' in output

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

    def test_trader_orders_submitted_tracking(self) -> None:
        """Test per-trader order submission tracking."""
        exporter = PrometheusExporter(scenario="test")

        # Create orders from same trader
        order1 = OrderMetadata(
            order_uid="order-1",
            owner="0xAAA",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        order2 = OrderMetadata(
            order_uid="order-2",
            owner="0xAAA",
            creation_time=1001.0,
            current_status=OrderStatus.CREATED,
        )

        exporter._on_metric_update("order", order1)
        exporter._on_metric_update("order", order2)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_trader_orders_submitted_total{trader_index="0"} 2.0' in output

    def test_trader_orders_filled_tracking(self) -> None:
        """Test per-trader order fill tracking."""
        exporter = PrometheusExporter(scenario="test")

        # Create and fill an order
        order = OrderMetadata(
            order_uid="order-1",
            owner="0xAAA",
            creation_time=1000.0,
            current_status=OrderStatus.CREATED,
        )
        exporter._on_metric_update("order", order)

        order.current_status = OrderStatus.FILLED
        order.completion_time = 1030.0
        exporter._on_metric_update("order", order)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_trader_orders_filled_total{trader_index="0"} 1.0' in output

    def test_set_regression_counts(self) -> None:
        """Test regression count setting."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_regression_counts(critical=1, major=2, minor=3)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_regression_detected{severity="critical"} 1.0' in output
        assert 'cow_perf_regression_detected{severity="major"} 2.0' in output
        assert 'cow_perf_regression_detected{severity="minor"} 3.0' in output

    def test_set_baseline_comparison(self) -> None:
        """Test baseline comparison metric setting."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_baseline_comparison(
            metric_name="avg_latency",
            baseline_id="baseline-123",
            percent_change=15.5,
        )

        output = generate_latest(exporter.registry).decode()
        assert (
            'cow_perf_baseline_comparison_percent{baseline_id="baseline-123",metric="avg_latency"} 15.5'
            in output
        )

    def test_record_trader_order_submitted(self) -> None:
        """Test manual trader order submission recording."""
        exporter = PrometheusExporter(scenario="test")
        exporter.record_trader_order_submitted(trader_index=0)
        exporter.record_trader_order_submitted(trader_index=0)
        exporter.record_trader_order_submitted(trader_index=1)

        output = generate_latest(exporter.registry).decode()
        assert 'cow_perf_trader_orders_submitted_total{trader_index="0"} 2.0' in output
        assert 'cow_perf_trader_orders_submitted_total{trader_index="1"} 1.0' in output

    def test_set_active_traders(self) -> None:
        """Test active traders gauge setting."""
        exporter = PrometheusExporter(scenario="test")
        exporter.set_active_traders(5)

        output = generate_latest(exporter.registry).decode()
        assert "cow_perf_traders_active 5.0" in output


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
        assert (
            'cow_perf_api_requests_total{endpoint="/api/v1/orders",method="POST",status="200"} 1.0'
            in output
        )

    def test_callback_classifies_client_errors(self) -> None:
        """Test that 4xx responses are classified as client errors."""
        exporter = PrometheusExporter(scenario="test")

        api_metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.1,
            status_code=400,
            error_message="Bad request",
        )
        exporter._on_metric_update("api", api_metric)

        output = generate_latest(exporter.registry).decode()
        assert (
            'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="client_error"} 1.0'
            in output
        )

    def test_callback_classifies_server_errors(self) -> None:
        """Test that 5xx responses are classified as server errors."""
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
        assert (
            'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="server_error"} 1.0'
            in output
        )

    def test_callback_classifies_timeout_errors(self) -> None:
        """Test that timeout errors are classified correctly."""
        exporter = PrometheusExporter(scenario="test")

        api_metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=30.0,
            status_code=0,
            error_message="Connection timeout",
        )
        exporter._on_metric_update("api", api_metric)

        output = generate_latest(exporter.registry).decode()
        assert (
            'cow_perf_api_errors_total{endpoint="/api/v1/orders",error_type="timeout"} 1.0'
            in output
        )

    def test_callback_records_response_time(self) -> None:
        """Test that API response times are recorded."""
        exporter = PrometheusExporter(scenario="test")

        api_metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.15,
            status_code=200,
        )
        exporter._on_metric_update("api", api_metric)

        output = generate_latest(exporter.registry).decode()
        assert "cow_perf_api_response_time_seconds_sum" in output
        assert "cow_perf_api_response_time_seconds_count" in output
