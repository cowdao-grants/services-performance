"""Integration tests for metrics collection pipeline."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from cow_performance.api import InstrumentedOrderbookClient
from cow_performance.load_generation.order_tracker import OrderTracker
from cow_performance.metrics import MetricsStore, OrderStatus


class TestMetricsCollectionPipeline:
    """Tests for the complete metrics collection pipeline."""

    @pytest.fixture
    def metrics_store(self):
        """Create a shared metrics store."""
        return MetricsStore()

    @pytest.fixture
    def order_tracker(self, metrics_store):
        """Create an order tracker with metrics store."""
        return OrderTracker(
            poll_interval=0.1,
            max_poll_attempts=5,
            metrics_store=metrics_store,
        )

    @pytest.fixture
    def instrumented_client(self, metrics_store):
        """Create an instrumented client with metrics store."""
        return InstrumentedOrderbookClient(
            base_url="http://localhost:8080",
            metrics_store=metrics_store,
        )

    @pytest.mark.asyncio
    async def test_order_lifecycle_with_api_metrics(
        self, metrics_store, order_tracker, instrumented_client
    ):
        """Test that order tracking and API metrics work together."""
        order_uid = "0x1234567890abcdef"

        # Track order creation
        order_tracker.track_order(
            order_uid=order_uid,
            owner="0xowner",
            sell_token="0xsell",
            buy_token="0xbuy",
            sell_amount="1000",
            buy_amount="500",
        )

        # Mock API responses
        with patch.object(
            instrumented_client._client, "submit_order", new_callable=AsyncMock
        ) as mock_submit:
            mock_submit.return_value = {"uid": order_uid}

            # Submit order (records API metrics)
            await instrumented_client.submit_order({"test": "order"})

        # Update order status
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)

        # Mock status polling
        with patch.object(
            instrumented_client._client, "get_order", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"uid": order_uid, "status": "fulfilled"}

            # Poll status (records API metrics)
            await order_tracker.poll_order_status(order_uid, instrumented_client)

        # Verify both order and API metrics are stored
        stored_order = metrics_store.get_order(order_uid)
        assert stored_order is not None
        assert stored_order.current_status == OrderStatus.FILLED

        api_metrics = metrics_store.get_api_metrics()
        assert len(api_metrics) == 2  # submit + get_order

        # Verify summary
        summary = metrics_store.summary()
        assert summary["orders"] == 1
        assert summary["api_metrics_total"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_order_tracking(self, metrics_store, order_tracker):
        """Test tracking multiple orders concurrently."""
        num_orders = 10

        async def track_and_update(order_num: int) -> None:
            order_uid = f"0x{order_num:064x}"
            order_tracker.track_order(order_uid, owner=f"0xowner{order_num}")
            order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
            await asyncio.sleep(0.01)  # Small delay
            order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        # Track multiple orders concurrently
        await asyncio.gather(*[track_and_update(i) for i in range(num_orders)])

        # Verify all orders tracked
        assert len(order_tracker.get_all_orders()) == num_orders
        assert metrics_store.summary()["orders"] == num_orders

        # Verify all reached terminal state
        filled = [
            o for o in order_tracker.get_all_orders() if o.current_status == OrderStatus.FILLED
        ]
        assert len(filled) == num_orders

    @pytest.mark.asyncio
    async def test_api_error_handling_with_metrics(self, metrics_store, instrumented_client):
        """Test that API errors are properly recorded in metrics."""
        from unittest.mock import MagicMock

        import aiohttp

        # Mock a failing API call with proper request_info
        mock_request_info = MagicMock()
        mock_request_info.real_url = "http://localhost:8080/api/v1/orders/0x1234"
        mock_error = aiohttp.ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
            message="Internal server error",
        )

        with patch.object(
            instrumented_client._client, "get_order", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = mock_error

            with pytest.raises(aiohttp.ClientResponseError):
                await instrumented_client.get_order("0x1234")

        # Verify error was recorded in metrics
        metrics = metrics_store.get_api_metrics()
        assert len(metrics) == 1
        assert metrics[0].status_code == 500
        assert metrics[0].error_message is not None

    @pytest.mark.asyncio
    async def test_order_lifecycle_timing(self, metrics_store, order_tracker):
        """Test that order lifecycle timing is captured correctly."""
        order_uid = "0x1234"

        # Track order at creation time
        metadata = order_tracker.track_order(order_uid, owner="0xowner")

        # Simulate time passing and status updates
        await asyncio.sleep(0.05)
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        await asyncio.sleep(0.05)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)

        await asyncio.sleep(0.05)
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        # Verify timing data was captured
        metadata = order_tracker.get_order(order_uid)
        assert metadata is not None
        assert metadata.submission_time is not None
        assert metadata.acceptance_time is not None
        assert metadata.first_fill_time is not None
        assert metadata.completion_time is not None

        # Verify time calculations work
        assert metadata.get_time_to_submit() > 0
        assert metadata.get_time_to_accept() > 0
        assert metadata.get_time_to_fill() > 0
        assert metadata.get_total_lifecycle_time() > 0

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, metrics_store, order_tracker):
        """Test that metrics are properly aggregated."""
        # Create orders with different outcomes
        orders = [
            ("0x1", OrderStatus.FILLED),
            ("0x2", OrderStatus.FILLED),
            ("0x3", OrderStatus.EXPIRED),
            ("0x4", OrderStatus.CANCELLED),
            ("0x5", OrderStatus.FAILED),
        ]

        for uid, final_status in orders:
            order_tracker.track_order(uid, owner="0xowner")
            order_tracker.update_order_status(uid, OrderStatus.SUBMITTED)
            order_tracker.update_order_status(uid, final_status)

        # Get aggregated metrics
        metrics = order_tracker.get_metrics()

        assert metrics.total_orders == 5
        assert metrics.orders_filled == 2
        assert metrics.orders_expired == 1
        assert metrics.orders_cancelled == 1
        assert metrics.orders_failed == 1

    @pytest.mark.asyncio
    async def test_full_pipeline_with_polling(
        self, metrics_store, order_tracker, instrumented_client
    ):
        """Test the full pipeline with background polling."""
        order_uid = "0x1234"

        # Track order
        order_tracker.track_order(order_uid, owner="0xowner")
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        # Mock API to return open first, then fulfilled
        call_count = 0

        async def mock_get_order(uid):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"uid": uid, "status": "open"}
            return {"uid": uid, "status": "fulfilled"}

        with patch.object(
            instrumented_client._client, "get_order", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = mock_get_order

            # Monitor until completion
            metadata = await order_tracker.monitor_order(order_uid, instrumented_client)

        # Verify order reached terminal state
        assert metadata.current_status == OrderStatus.FILLED

        # Verify API metrics were recorded for each poll
        api_metrics = metrics_store.get_api_metrics()
        assert len(api_metrics) == call_count

    @pytest.mark.asyncio
    async def test_store_isolation(self):
        """Test that different stores don't interfere with each other."""
        store1 = MetricsStore()
        store2 = MetricsStore()

        tracker1 = OrderTracker(metrics_store=store1)
        tracker2 = OrderTracker(metrics_store=store2)

        tracker1.track_order("0x1", owner="owner1")
        tracker2.track_order("0x2", owner="owner2")

        assert store1.summary()["orders"] == 1
        assert store2.summary()["orders"] == 1
        assert store1.get_order("0x1") is not None
        assert store1.get_order("0x2") is None
        assert store2.get_order("0x1") is None
        assert store2.get_order("0x2") is not None
