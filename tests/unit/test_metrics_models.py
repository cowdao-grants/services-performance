"""Unit tests for metrics data models."""

import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    OrderMetadata,
    OrderStatus,
    ResourceMetrics,
    ResourceSample,
    TestRunMetrics,
)


class TestOrderMetadata:
    """Tests for OrderMetadata model."""

    def test_create_order_metadata(self):
        """Test creating order metadata."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        assert metadata.order_uid == "0x1234"
        assert metadata.owner == "0xabcd"
        assert metadata.current_status == OrderStatus.CREATED

    def test_update_status_records_history(self):
        """Test that status updates are recorded in history."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        metadata.update_status(OrderStatus.SUBMITTED)
        metadata.update_status(OrderStatus.ACCEPTED)
        metadata.update_status(OrderStatus.FILLED)

        assert len(metadata.status_history) == 3
        assert metadata.current_status == OrderStatus.FILLED

    def test_lifecycle_times_calculated(self):
        """Test lifecycle time calculations."""
        base_time = time.time()
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=base_time,
        )

        metadata.update_status(OrderStatus.SUBMITTED, base_time + 0.1)
        metadata.update_status(OrderStatus.ACCEPTED, base_time + 0.2)
        metadata.update_status(OrderStatus.FILLED, base_time + 0.5)

        assert metadata.get_time_to_submit() == pytest.approx(0.1, rel=0.01)
        assert metadata.get_time_to_accept() == pytest.approx(0.1, rel=0.01)
        assert metadata.get_time_to_fill() == pytest.approx(0.3, rel=0.01)
        assert metadata.get_total_lifecycle_time() == pytest.approx(0.5, rel=0.01)

    def test_is_terminal_state(self):
        """Test terminal state detection."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        assert not metadata.is_terminal_state()

        metadata.update_status(OrderStatus.FILLED)
        assert metadata.is_terminal_state()


class TestAPIMetrics:
    """Tests for APIMetrics model."""

    def test_create_api_metrics(self):
        """Test creating API metrics."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.150,
            status_code=201,
            payload_size=512,
        )

        assert metric.endpoint == "/api/v1/orders"
        assert metric.method == "POST"
        assert metric.duration == 0.150

    def test_duration_ms_property(self):
        """Test duration_ms calculation."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="GET",
            timestamp=time.time(),
            duration=0.150,
            status_code=200,
        )

        assert metric.duration_ms == 150.0

    def test_is_success_property(self):
        """Test is_success detection."""
        success = APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=200,
        )
        assert success.is_success

        created = APIMetrics(
            endpoint="/test",
            method="POST",
            timestamp=time.time(),
            duration=0.1,
            status_code=201,
        )
        assert created.is_success

        error = APIMetrics(
            endpoint="/test",
            method="GET",
            timestamp=time.time(),
            duration=0.1,
            status_code=500,
        )
        assert not error.is_success


class TestResourceMetrics:
    """Tests for ResourceSample and ResourceMetrics."""

    def test_resource_sample_memory_percent(self):
        """Test memory percentage calculation."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_bytes=500_000_000,  # 500MB
            memory_limit_bytes=1_000_000_000,  # 1GB
        )

        assert sample.memory_percent == 50.0

    def test_resource_sample_zero_limit(self):
        """Test memory percent with zero limit."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=50.0,
            memory_bytes=500_000_000,
            memory_limit_bytes=0,
        )

        assert sample.memory_percent == 0.0

    def test_resource_metrics_aggregation(self):
        """Test resource metrics aggregation."""
        metrics = ResourceMetrics(container_name="test-container")

        metrics.add_sample(
            ResourceSample(
                timestamp=time.time(),
                cpu_percent=20.0,
                memory_bytes=100_000_000,
                memory_limit_bytes=1_000_000_000,
            )
        )
        metrics.add_sample(
            ResourceSample(
                timestamp=time.time(),
                cpu_percent=40.0,
                memory_bytes=200_000_000,
                memory_limit_bytes=1_000_000_000,
            )
        )

        assert metrics.avg_cpu_percent == 30.0
        assert metrics.max_cpu_percent == 40.0
        assert metrics.max_memory_bytes == 200_000_000


class TestTestRunMetrics:
    """Tests for TestRunMetrics model."""

    def test_create_test_run_metrics(self):
        """Test creating test run metrics."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            num_traders=10,
            duration_seconds=60.0,
        )

        assert metrics.test_id == "test-001"
        assert metrics.num_traders == 10

    def test_test_duration_property(self):
        """Test test_duration calculation."""
        start = time.time()
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=start,
            end_time=start + 60.0,
        )

        assert metrics.test_duration == 60.0

    def test_success_rate_property(self):
        """Test success rate calculation."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            orders_submitted=100,
            orders_filled=80,
        )

        assert metrics.success_rate == 0.8

    def test_success_rate_zero_submitted(self):
        """Test success rate with zero orders."""
        metrics = TestRunMetrics(
            test_id="test-001",
            start_time=time.time(),
            orders_submitted=0,
            orders_filled=0,
        )

        assert metrics.success_rate == 0.0
