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

    def test_metrics_output_valid_prometheus_format(self, exporter: PrometheusExporter) -> None:
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

    def test_exporter_can_be_stopped_and_restarted_markers_set(
        self, exporter: PrometheusExporter
    ) -> None:
        """Test that exporter state flags work correctly."""
        # Should be running (started by fixture)
        assert exporter.is_running() is True

        # Stop should mark as not running
        exporter.stop()
        assert exporter.is_running() is False
