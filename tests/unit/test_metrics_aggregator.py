"""Unit tests for MetricsAggregator."""

import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricsAggregator,
    MetricsStore,
    OrderMetadata,
    OrderStatus,
    PercentileStats,
    ResourceSample,
)


class TestPercentileStats:
    """Tests for PercentileStats class."""

    def test_from_empty_values(self):
        """Test percentile stats from empty list."""
        stats = PercentileStats.from_values([])
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.p50 == 0.0

    def test_from_single_value(self):
        """Test percentile stats from single value."""
        stats = PercentileStats.from_values([100.0])
        assert stats.count == 1
        assert stats.mean == 100.0
        assert stats.min == 100.0
        assert stats.max == 100.0
        assert stats.p50 == 100.0

    def test_from_multiple_values(self):
        """Test percentile stats from multiple values."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        stats = PercentileStats.from_values(values)

        assert stats.count == 10
        assert stats.min == 10.0
        assert stats.max == 100.0
        assert stats.mean == 55.0
        assert stats.p50 == pytest.approx(55.0, rel=0.1)
        assert stats.p90 == pytest.approx(91.0, rel=0.1)
        assert stats.p95 == pytest.approx(95.5, rel=0.1)
        assert stats.p99 == pytest.approx(99.1, rel=0.1)


class TestMetricsAggregator:
    """Tests for MetricsAggregator class."""

    @pytest.fixture
    def store_with_orders(self):
        """Create a store with sample orders."""
        store = MetricsStore()
        base_time = time.time()

        # Add orders with various statuses and timings
        for i in range(10):
            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner=f"0x{i % 3:040x}",  # 3 different owners
                creation_time=base_time + i * 0.1,
                sell_token="0xsell",
                buy_token="0xbuy",
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i * 0.1 + 0.01)
            order.update_status(OrderStatus.ACCEPTED, base_time + i * 0.1 + 0.02)

            # Vary the outcomes
            if i < 7:
                order.update_status(OrderStatus.FILLED, base_time + i * 0.1 + 0.1 + i * 0.01)
            elif i == 7:
                order.update_status(OrderStatus.EXPIRED, base_time + i * 0.1 + 0.5)
            elif i == 8:
                order.update_status(OrderStatus.CANCELLED, base_time + i * 0.1 + 0.3)
            else:
                order.update_status(OrderStatus.FAILED, base_time + i * 0.1 + 0.05)

            store.add_order(order)

        return store

    @pytest.fixture
    def store_with_api_metrics(self):
        """Create a store with sample API metrics."""
        store = MetricsStore()
        base_time = time.time()

        for i in range(100):
            metric = APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=base_time + i * 0.1,
                duration=0.05 + (i % 10) * 0.01,  # 50-140ms
                status_code=201 if i < 90 else 500,  # 90% success rate
            )
            store.add_api_metric(metric)

        return store

    def test_aggregate_orders_empty(self):
        """Test aggregating empty order list."""
        store = MetricsStore()
        aggregator = MetricsAggregator(store)

        metrics = aggregator.aggregate_orders()

        assert metrics.total_orders == 0
        assert metrics.success_rate == 0.0
        assert metrics.time_to_submit.count == 0

    def test_aggregate_orders_with_data(self, store_with_orders):
        """Test aggregating orders with data."""
        aggregator = MetricsAggregator(store_with_orders)

        metrics = aggregator.aggregate_orders()

        assert metrics.total_orders == 10
        assert metrics.orders_filled == 7
        assert metrics.orders_expired == 1
        assert metrics.orders_cancelled == 1
        assert metrics.orders_failed == 1
        assert metrics.success_rate == pytest.approx(0.7, rel=0.01)
        assert metrics.time_to_submit.count > 0
        assert metrics.time_to_fill.count == 7  # Only filled orders have fill time

    def test_aggregate_api_metrics_empty(self):
        """Test aggregating empty API metrics."""
        store = MetricsStore()
        aggregator = MetricsAggregator(store)

        metrics = aggregator.aggregate_api_metrics()

        assert metrics.total_requests == 0
        assert metrics.success_rate == 0.0

    def test_aggregate_api_metrics_with_data(self, store_with_api_metrics):
        """Test aggregating API metrics with data."""
        aggregator = MetricsAggregator(store_with_api_metrics)

        metrics = aggregator.aggregate_api_metrics()

        assert metrics.total_requests == 100
        assert metrics.successful_requests == 90
        assert metrics.failed_requests == 10
        assert metrics.success_rate == 0.9
        assert metrics.response_time.count == 100
        assert metrics.response_time.p50 > 0
        assert metrics.response_time.p95 > metrics.response_time.p50
        assert 201 in metrics.status_code_counts
        assert 500 in metrics.status_code_counts

    def test_aggregate_api_metrics_by_endpoint(self, store_with_api_metrics):
        """Test filtering API metrics by endpoint."""
        aggregator = MetricsAggregator(store_with_api_metrics)

        # Add metrics for another endpoint
        for _i in range(10):
            store_with_api_metrics.add_api_metric(
                APIMetrics(
                    endpoint="/api/v1/version",
                    method="GET",
                    timestamp=time.time(),
                    duration=0.01,
                    status_code=200,
                )
            )

        metrics = aggregator.aggregate_api_metrics(endpoint="/api/v1/orders")
        assert metrics.total_requests == 100  # Only /api/v1/orders

    def test_aggregate_resource_metrics(self):
        """Test aggregating resource metrics."""
        store = MetricsStore()

        for i in range(50):
            sample = ResourceSample(
                timestamp=time.time(),
                cpu_percent=20.0 + i * 0.5,  # 20-45%
                memory_bytes=100_000_000 + i * 1_000_000,
                memory_limit_bytes=1_000_000_000,
            )
            store.add_resource_sample("orderbook", sample)

        aggregator = MetricsAggregator(store)
        metrics = aggregator.aggregate_resource_metrics()

        assert "orderbook" in metrics
        orderbook_metrics = metrics["orderbook"]
        assert orderbook_metrics.sample_count == 50
        assert orderbook_metrics.cpu_percent.count == 50
        assert orderbook_metrics.cpu_percent.min == pytest.approx(20.0, rel=0.01)
        assert orderbook_metrics.cpu_percent.max == pytest.approx(44.5, rel=0.01)

    def test_get_summary(self, store_with_orders):
        """Test getting comprehensive summary."""
        # Use store with orders
        aggregator = MetricsAggregator(store_with_orders)
        summary = aggregator.get_summary()

        assert "orders" in summary
        assert "api" in summary
        assert "resources" in summary


class TestMetricsAggregatorGrouping:
    """Tests for MetricsAggregator grouping methods."""

    @pytest.fixture
    def store_with_diverse_orders(self):
        """Create a store with orders from multiple owners and token pairs."""
        store = MetricsStore()
        base_time = time.time()

        owners = ["0xAAA", "0xBBB", "0xCCC"]
        token_pairs = [
            ("0xWETH", "0xUSDC"),
            ("0xWETH", "0xDAI"),
            ("0xUSDC", "0xDAI"),
        ]

        for i in range(30):
            owner = owners[i % 3]
            sell_token, buy_token = token_pairs[i % 3]

            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner=owner,
                creation_time=base_time + i * 0.5,  # 0.5s apart
                sell_token=sell_token,
                buy_token=buy_token,
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i * 0.5 + 0.01)
            order.update_status(OrderStatus.FILLED, base_time + i * 0.5 + 0.1)
            store.add_order(order)

        return store

    def test_aggregate_orders_by_owner(self, store_with_diverse_orders):
        """Test grouping orders by owner."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        by_owner = aggregator.aggregate_orders_by_owner()

        assert len(by_owner) == 3
        assert "0xAAA" in by_owner
        assert "0xBBB" in by_owner
        assert "0xCCC" in by_owner

        # Each owner should have 10 orders
        for metrics in by_owner.values():
            assert metrics.total_orders == 10

    def test_aggregate_orders_by_token_pair(self, store_with_diverse_orders):
        """Test grouping orders by token pair."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        by_pair = aggregator.aggregate_orders_by_token_pair()

        assert len(by_pair) == 3
        assert "0xWETH->0xUSDC" in by_pair
        assert "0xWETH->0xDAI" in by_pair
        assert "0xUSDC->0xDAI" in by_pair

    def test_aggregate_orders_by_time_window(self, store_with_diverse_orders):
        """Test grouping orders by time windows."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        windows = aggregator.aggregate_orders_by_time_window(window_seconds=5.0)

        # With 30 orders 0.5s apart (15s total), we should have ~3 windows of 5s each
        assert len(windows) >= 3

        # Each window should have metrics
        for start, end, metrics in windows:
            assert end - start == 5.0
            assert metrics.total_orders > 0

    def test_aggregate_api_metrics_by_endpoint(self):
        """Test grouping API metrics by endpoint."""
        store = MetricsStore()

        # Add metrics for different endpoints
        for endpoint in ["/api/v1/orders", "/api/v1/version", "/api/v1/trades"]:
            for _ in range(10):
                store.add_api_metric(
                    APIMetrics(
                        endpoint=endpoint,
                        method="GET",
                        timestamp=time.time(),
                        duration=0.1,
                        status_code=200,
                    )
                )

        aggregator = MetricsAggregator(store)
        by_endpoint = aggregator.aggregate_api_metrics_by_endpoint()

        assert len(by_endpoint) == 3
        for metrics in by_endpoint.values():
            assert metrics.total_requests == 10

    def test_calculate_throughput(self, store_with_diverse_orders):
        """Test throughput calculation."""
        aggregator = MetricsAggregator(store_with_diverse_orders)
        throughput = aggregator.calculate_throughput()

        assert "orders_per_second" in throughput
        assert "api_requests_per_second" in throughput
        # 30 orders over ~15s = ~2 orders/second
        assert throughput["orders_per_second"] > 1.0
