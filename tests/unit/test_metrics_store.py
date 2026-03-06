"""Unit tests for MetricsStore."""

import asyncio
import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricsStore,
    MetricsStoreConfig,
    OrderMetadata,
    OrderStatus,
    ResourceSample,
)


class TestMetricsStore:
    """Tests for MetricsStore class."""

    @pytest.fixture
    def store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def small_store(self):
        """Create a store with small limits for testing bounds."""
        config = MetricsStoreConfig(
            max_orders=3,
            max_api_metrics_per_endpoint=3,
            max_resource_samples_per_container=3,
        )
        return MetricsStore(config)

    def test_add_and_get_order(self, store):
        """Test adding and retrieving orders."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )

        store.add_order(metadata)
        retrieved = store.get_order("0x1234")

        assert retrieved is not None
        assert retrieved.order_uid == "0x1234"

    def test_get_nonexistent_order(self, store):
        """Test getting a nonexistent order returns None."""
        assert store.get_order("0x9999") is None

    def test_get_all_orders(self, store):
        """Test getting all orders."""
        for i in range(5):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            store.add_order(metadata)

        orders = store.get_all_orders()
        assert len(orders) == 5

    def test_get_orders_by_status(self, store):
        """Test filtering orders by status."""
        for i in range(3):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            store.add_order(metadata)

        # Update some to different statuses
        store.get_order("0x0000").update_status(OrderStatus.FILLED)
        store.get_order("0x0001").update_status(OrderStatus.FILLED)

        filled = store.get_orders_by_status("filled")
        assert len(filled) == 2

    def test_get_orders_by_owner(self, store):
        """Test filtering orders by owner."""
        store.add_order(
            OrderMetadata(
                order_uid="0x0001",
                owner="0xaaaa",
                creation_time=time.time(),
            )
        )
        store.add_order(
            OrderMetadata(
                order_uid="0x0002",
                owner="0xbbbb",
                creation_time=time.time(),
            )
        )
        store.add_order(
            OrderMetadata(
                order_uid="0x0003",
                owner="0xaaaa",
                creation_time=time.time(),
            )
        )

        owner_a_orders = store.get_orders_by_owner("0xaaaa")
        assert len(owner_a_orders) == 2

    def test_orders_bounded_by_max(self, small_store):
        """Test that orders are bounded by max_orders config."""
        for i in range(5):
            metadata = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
            )
            small_store.add_order(metadata)

        # Should only have 3 (the limit)
        orders = small_store.get_all_orders()
        assert len(orders) == 3

        # First orders should be removed
        assert small_store.get_order("0x0000") is None
        assert small_store.get_order("0x0001") is None
        # Later orders should exist
        assert small_store.get_order("0x0004") is not None

    def test_add_and_get_api_metrics(self, store):
        """Test adding and retrieving API metrics."""
        metric = APIMetrics(
            endpoint="/api/v1/orders",
            method="POST",
            timestamp=time.time(),
            duration=0.150,
            status_code=201,
        )

        store.add_api_metric(metric)
        metrics = store.get_api_metrics("/api/v1/orders")

        assert len(metrics) == 1
        assert metrics[0].endpoint == "/api/v1/orders"

    def test_get_api_metrics_all_endpoints(self, store):
        """Test getting metrics from all endpoints."""
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=time.time(),
                duration=0.1,
                status_code=201,
            )
        )
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/orders/status",
                method="GET",
                timestamp=time.time(),
                duration=0.05,
                status_code=200,
            )
        )

        all_metrics = store.get_api_metrics()
        assert len(all_metrics) == 2

    def test_api_metrics_bounded(self, small_store):
        """Test that API metrics are bounded per endpoint."""
        for _i in range(5):
            metric = APIMetrics(
                endpoint="/api/test",
                method="GET",
                timestamp=time.time(),
                duration=0.1,
                status_code=200,
            )
            small_store.add_api_metric(metric)

        metrics = small_store.get_api_metrics("/api/test")
        assert len(metrics) == 3  # bounded to max

    def test_add_resource_sample(self, store):
        """Test adding resource samples."""
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=25.0,
            memory_bytes=100_000_000,
            memory_limit_bytes=1_000_000_000,
        )

        store.add_resource_sample("test-container", sample)
        metrics = store.get_resource_metrics("test-container")

        assert "test-container" in metrics
        assert len(metrics["test-container"].samples) == 1

    def test_resource_samples_bounded(self, small_store):
        """Test that resource samples are bounded per container."""
        for i in range(5):
            sample = ResourceSample(
                timestamp=time.time(),
                cpu_percent=float(i * 10),
                memory_bytes=100_000_000,
                memory_limit_bytes=1_000_000_000,
            )
            small_store.add_resource_sample("test-container", sample)

        metrics = small_store.get_resource_metrics("test-container")
        assert len(metrics["test-container"].samples) == 3  # bounded

    def test_clear_store(self, store):
        """Test clearing the store."""
        store.add_order(
            OrderMetadata(
                order_uid="0x1234",
                owner="0xabcd",
                creation_time=time.time(),
            )
        )
        store.add_api_metric(
            APIMetrics(
                endpoint="/test",
                method="GET",
                timestamp=time.time(),
                duration=0.1,
                status_code=200,
            )
        )

        store.clear()

        assert len(store.get_all_orders()) == 0
        assert len(store.get_api_metrics()) == 0

    def test_summary(self, store):
        """Test getting store summary."""
        store.add_order(
            OrderMetadata(
                order_uid="0x1234",
                owner="0xabcd",
                creation_time=time.time(),
            )
        )
        store.add_api_metric(
            APIMetrics(
                endpoint="/test",
                method="GET",
                timestamp=time.time(),
                duration=0.1,
                status_code=200,
            )
        )

        summary = store.summary()

        assert summary["orders"] == 1
        assert summary["api_metrics_total"] == 1

    @pytest.mark.asyncio
    async def test_thread_safe_concurrent_writes(self, store):
        """Test concurrent writes are thread-safe."""

        async def add_orders(start_idx: int, count: int):
            for i in range(count):
                async with store.lock:
                    store.add_order(
                        OrderMetadata(
                            order_uid=f"0x{start_idx + i:04x}",
                            owner="0xabcd",
                            creation_time=time.time(),
                        )
                    )
                await asyncio.sleep(0.001)

        # Run multiple concurrent tasks
        await asyncio.gather(
            add_orders(0, 10),
            add_orders(100, 10),
            add_orders(200, 10),
        )

        orders = store.get_all_orders()
        assert len(orders) == 30

    def test_callback_registration(self, store):
        """Test callback registration and notification."""
        received = []

        def callback(metric_type: str, metric: object):
            received.append((metric_type, metric))

        store.register_callback(callback)

        store.add_order(
            OrderMetadata(
                order_uid="0x1234",
                owner="0xabcd",
                creation_time=time.time(),
            )
        )

        assert len(received) == 1
        assert received[0][0] == "order"

        store.unregister_callback(callback)

        store.add_order(
            OrderMetadata(
                order_uid="0x5678",
                owner="0xabcd",
                creation_time=time.time(),
            )
        )

        # Should still be 1 after unregistering
        assert len(received) == 1

    def test_callback_error_does_not_affect_metrics(self, store):
        """Test that callback errors don't affect metrics collection."""

        def bad_callback(metric_type: str, metric: object):
            raise ValueError("Intentional error")

        store.register_callback(bad_callback)

        # Should not raise even though callback throws
        store.add_order(
            OrderMetadata(
                order_uid="0x1234",
                owner="0xabcd",
                creation_time=time.time(),
            )
        )

        # Order should still be stored
        assert store.get_order("0x1234") is not None

    def test_get_api_endpoints(self, store):
        """Test getting list of API endpoints."""
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=time.time(),
                duration=0.1,
                status_code=201,
            )
        )
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/quotes",
                method="GET",
                timestamp=time.time(),
                duration=0.05,
                status_code=200,
            )
        )

        endpoints = store.get_api_endpoints()
        assert len(endpoints) == 2
        assert "/api/v1/orders" in endpoints
        assert "/api/v1/quotes" in endpoints

    def test_get_container_names(self, store):
        """Test getting list of container names."""
        store.add_resource_sample(
            "container-a",
            ResourceSample(
                timestamp=time.time(),
                cpu_percent=10.0,
                memory_bytes=100_000_000,
                memory_limit_bytes=1_000_000_000,
            ),
        )
        store.add_resource_sample(
            "container-b",
            ResourceSample(
                timestamp=time.time(),
                cpu_percent=20.0,
                memory_bytes=200_000_000,
                memory_limit_bytes=1_000_000_000,
            ),
        )

        names = store.get_container_names()
        assert len(names) == 2
        assert "container-a" in names
        assert "container-b" in names
