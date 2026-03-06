"""Integration tests for CLI live display."""

import asyncio
import time

import pytest

from cow_performance.cli.live_display import (
    LiveMetricsDisplay,
    create_performance_metrics_dict,
)
from cow_performance.metrics import (
    APIMetrics,
    MetricsStore,
    OrderMetadata,
    OrderStatus,
)


class TestLiveMetricsDisplay:
    """Tests for LiveMetricsDisplay."""

    @pytest.fixture
    def store_with_data(self):
        """Create a store with sample data."""
        store = MetricsStore()
        base_time = time.time()

        # Add orders
        for i in range(10):
            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner="0xowner",
                creation_time=base_time + i,
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i + 0.01)
            order.update_status(OrderStatus.FILLED, base_time + i + 0.1)
            store.add_order(order)

        # Add API metrics
        for i in range(20):
            store.add_api_metric(
                APIMetrics(
                    endpoint="/api/v1/orders",
                    method="POST",
                    timestamp=base_time + i * 0.5,
                    duration=0.05 + i * 0.005,
                    status_code=201,
                )
            )

        return store

    @pytest.mark.asyncio
    async def test_live_display_start_stop(self, store_with_data):
        """Test live display lifecycle."""
        display = LiveMetricsDisplay(store_with_data)

        await display.start()
        await asyncio.sleep(0.1)  # Let it run briefly
        await display.stop()

    @pytest.mark.asyncio
    async def test_live_display_update(self, store_with_data):
        """Test that display updates without errors."""
        display = LiveMetricsDisplay(store_with_data)

        layout = display.update()
        assert layout is not None

    def test_create_performance_metrics_dict(self, store_with_data):
        """Test performance metrics dict creation."""
        metrics = create_performance_metrics_dict(store_with_data, elapsed_seconds=10.0)

        assert "orders_per_second" in metrics
        assert "avg_order_latency_ms" in metrics
        assert "p50_latency_ms" in metrics
        assert "p95_latency_ms" in metrics
        assert "p99_latency_ms" in metrics
        assert "api_success_rate" in metrics

        # Verify percentiles are reasonable
        assert metrics["p50_latency_ms"] <= metrics["p95_latency_ms"]
        assert metrics["p95_latency_ms"] <= metrics["p99_latency_ms"]
