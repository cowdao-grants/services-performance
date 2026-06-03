"""Unit tests for order lifecycle tracking and status mapping."""

from unittest.mock import AsyncMock

import pytest

from cow_performance.load_generation.order_tracker import OrderTracker
from cow_performance.load_generation.status_mapping import (
    COW_API_STATUS_MAPPING,
    is_api_status_terminal,
    map_api_status_to_order_status,
)
from cow_performance.metrics import MetricsStore, OrderStatus


class TestStatusMapping:
    """Tests for status mapping utilities."""

    def test_map_open_status(self):
        """Test mapping 'open' status."""
        assert map_api_status_to_order_status("open") == OrderStatus.OPEN

    def test_map_fulfilled_status(self):
        """Test mapping 'fulfilled' status."""
        assert map_api_status_to_order_status("fulfilled") == OrderStatus.FILLED

    def test_map_cancelled_status(self):
        """Test mapping 'cancelled' status."""
        assert map_api_status_to_order_status("cancelled") == OrderStatus.CANCELLED

    def test_map_expired_status(self):
        """Test mapping 'expired' status."""
        assert map_api_status_to_order_status("expired") == OrderStatus.EXPIRED

    def test_map_presignature_pending_status(self):
        """Test mapping 'presignaturePending' status."""
        assert map_api_status_to_order_status("presignaturePending") == OrderStatus.SUBMITTED

    def test_map_unknown_status_raises(self):
        """Test that unknown status raises ValueError."""
        with pytest.raises(ValueError, match="Unknown API status"):
            map_api_status_to_order_status("invalid_status")

    def test_is_terminal_fulfilled(self):
        """Test fulfilled is terminal."""
        assert is_api_status_terminal("fulfilled") is True

    def test_is_terminal_cancelled(self):
        """Test cancelled is terminal."""
        assert is_api_status_terminal("cancelled") is True

    def test_is_terminal_expired(self):
        """Test expired is terminal."""
        assert is_api_status_terminal("expired") is True

    def test_is_not_terminal_open(self):
        """Test open is not terminal."""
        assert is_api_status_terminal("open") is False

    def test_is_not_terminal_presignature(self):
        """Test presignaturePending is not terminal."""
        assert is_api_status_terminal("presignaturePending") is False

    def test_all_statuses_have_mapping(self):
        """Test that all expected statuses have mappings."""
        expected_statuses = {"presignaturePending", "open", "fulfilled", "cancelled", "expired"}
        assert set(COW_API_STATUS_MAPPING.keys()) == expected_statuses


class TestOrderTrackerPolling:
    """Tests for OrderTracker API polling."""

    @pytest.fixture
    def tracker(self):
        """Create an order tracker fixture."""
        return OrderTracker(poll_interval=0.1, max_poll_attempts=5)

    @pytest.fixture
    def tracker_with_store(self):
        """Create an order tracker with MetricsStore."""
        store = MetricsStore()
        tracker = OrderTracker(poll_interval=0.1, max_poll_attempts=5, metrics_store=store)
        return tracker, store

    @pytest.mark.asyncio
    async def test_poll_order_status_success(self, tracker):
        """Test successful status polling."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {
            "uid": order_uid,
            "status": "open",
            "executedSellAmount": "0",
        }

        status = await tracker.poll_order_status(order_uid, mock_client)

        assert status == OrderStatus.OPEN
        mock_client.get_order.assert_called_once_with(order_uid)

    @pytest.mark.asyncio
    async def test_poll_order_status_fulfilled(self, tracker):
        """Test polling when order is fulfilled."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner", sell_amount="1000")

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {
            "uid": order_uid,
            "status": "fulfilled",
            "executedSellAmount": "1000",
        }

        status = await tracker.poll_order_status(order_uid, mock_client)

        assert status == OrderStatus.FILLED
        metadata = tracker.get_order(order_uid)
        assert metadata.filled_amount == "1000"

    @pytest.mark.asyncio
    async def test_poll_order_status_api_error(self, tracker):
        """Test polling handles API errors gracefully."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        mock_client = AsyncMock()
        mock_client.get_order.side_effect = Exception("Network error")

        status = await tracker.poll_order_status(order_uid, mock_client)

        # Should return current status on error
        assert status == OrderStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_poll_order_status_unknown_status(self, tracker):
        """Test polling handles unknown status gracefully."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.OPEN)

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {
            "uid": order_uid,
            "status": "unknownStatus",
        }

        status = await tracker.poll_order_status(order_uid, mock_client)

        # Should return current status on unknown status
        assert status == OrderStatus.OPEN

    @pytest.mark.asyncio
    async def test_poll_nonexistent_order(self, tracker):
        """Test polling a non-existent order."""
        mock_client = AsyncMock()

        status = await tracker.poll_order_status("nonexistent", mock_client)

        assert status == OrderStatus.FAILED
        mock_client.get_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_order_until_terminal(self, tracker):
        """Test monitoring stops at terminal state."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        call_count = 0

        async def mock_get_order(uid):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"uid": uid, "status": "open"}
            return {"uid": uid, "status": "fulfilled"}

        mock_client = AsyncMock()
        mock_client.get_order = mock_get_order

        metadata = await tracker.monitor_order(order_uid, mock_client)

        assert metadata.current_status == OrderStatus.FILLED
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_monitor_order_timeout(self, tracker):
        """Test monitoring stops after max attempts without marking as failed."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {"uid": order_uid, "status": "open"}

        metadata = await tracker.monitor_order(order_uid, mock_client)

        # Timeout does not mark as FAILED; last polled status (OPEN) is returned
        assert metadata.current_status == OrderStatus.OPEN
        assert metadata.error_message is None

    @pytest.mark.asyncio
    async def test_monitor_order_without_client(self, tracker):
        """Test monitoring without API client (no polling)."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        # Mark as filled immediately
        tracker.update_order_status(order_uid, OrderStatus.FILLED)

        metadata = await tracker.monitor_order(order_uid, api_client=None)

        assert metadata.current_status == OrderStatus.FILLED

    def test_track_order_adds_to_store(self, tracker_with_store):
        """Test that tracking adds order to MetricsStore."""
        tracker, store = tracker_with_store
        order_uid = "0x1234"

        tracker.track_order(order_uid, owner="0xowner")

        stored_order = store.get_order(order_uid)
        assert stored_order is not None
        assert stored_order.order_uid == order_uid

    def test_track_order_with_all_params(self, tracker):
        """Test tracking with all parameters."""
        order_uid = "0x1234"
        metadata = tracker.track_order(
            order_uid=order_uid,
            owner="0xowner",
            sell_token="0xsell",
            buy_token="0xbuy",
            sell_amount="1000",
            buy_amount="500",
        )

        assert metadata.order_uid == order_uid
        assert metadata.owner == "0xowner"
        assert metadata.sell_token == "0xsell"
        assert metadata.buy_token == "0xbuy"
        assert metadata.sell_amount == "1000"
        assert metadata.buy_amount == "500"

    def test_get_metrics(self, tracker):
        """Test getting aggregated metrics."""
        # Track some orders with different statuses
        tracker.track_order("0x1", owner="0xowner")
        tracker.update_order_status("0x1", OrderStatus.FILLED)

        tracker.track_order("0x2", owner="0xowner")
        tracker.update_order_status("0x2", OrderStatus.EXPIRED)

        tracker.track_order("0x3", owner="0xowner")
        # Keep as created

        metrics = tracker.get_metrics()

        assert metrics.total_orders == 3
        assert metrics.orders_filled == 1
        assert metrics.orders_expired == 1
        assert metrics.orders_created == 1


class TestOrderUIDTracking:
    """Tests for order UID update functionality."""

    @pytest.fixture
    def tracker(self):
        """Create an order tracker fixture."""
        return OrderTracker(poll_interval=0.1, max_poll_attempts=5)

    @pytest.fixture
    def tracker_with_store(self):
        """Create an order tracker with MetricsStore."""
        store = MetricsStore()
        tracker = OrderTracker(poll_interval=0.1, max_poll_attempts=5, metrics_store=store)
        return tracker, store

    def test_update_order_uid_in_tracker(self, tracker):
        """Test updating order UID in tracker."""
        old_uid = "pending_123456"
        new_uid = "0xreal_uid_from_api"

        tracker.track_order(old_uid, owner="0xowner")
        tracker.update_order_status(old_uid, OrderStatus.SUBMITTED)

        # Update the UID
        tracker.update_order_uid(old_uid, new_uid)

        # Old UID should no longer exist
        assert tracker.get_order(old_uid) is None

        # New UID should have the order
        metadata = tracker.get_order(new_uid)
        assert metadata is not None
        assert metadata.order_uid == new_uid
        assert metadata.owner == "0xowner"
        assert metadata.current_status == OrderStatus.SUBMITTED

    def test_update_order_uid_preserves_status_history(self, tracker):
        """Test that UID update preserves status history."""
        old_uid = "pending_123456"
        new_uid = "0xreal_uid"

        tracker.track_order(old_uid, owner="0xowner")
        tracker.update_order_status(old_uid, OrderStatus.SUBMITTED)
        tracker.update_order_status(old_uid, OrderStatus.ACCEPTED)

        tracker.update_order_uid(old_uid, new_uid)

        metadata = tracker.get_order(new_uid)
        assert len(metadata.status_history) == 2
        assert metadata.current_status == OrderStatus.ACCEPTED

    def test_update_order_uid_nonexistent(self, tracker):
        """Test updating non-existent UID does nothing."""
        tracker.update_order_uid("nonexistent", "new_uid")
        # Should not raise, and new_uid shouldn't exist
        assert tracker.get_order("new_uid") is None

    def test_update_order_uid_syncs_to_metrics_store(self, tracker_with_store):
        """Test that UID update syncs to MetricsStore."""
        tracker, store = tracker_with_store
        old_uid = "pending_123456"
        new_uid = "0xreal_uid_from_api"

        tracker.track_order(old_uid, owner="0xowner")

        # Verify initial state in store
        assert store.get_order(old_uid) is not None

        # Update UID
        tracker.update_order_uid(old_uid, new_uid)

        # Store should have new UID, not old
        assert store.get_order(old_uid) is None
        stored_order = store.get_order(new_uid)
        assert stored_order is not None
        assert stored_order.order_uid == new_uid

    @pytest.mark.asyncio
    async def test_monitoring_uses_updated_uid(self, tracker):
        """Test that monitoring continues with updated UID."""
        old_uid = "pending_123456"
        new_uid = "0xreal_uid_from_api"

        tracker.track_order(old_uid, owner="0xowner")
        tracker.update_order_uid(old_uid, new_uid)
        tracker.update_order_status(new_uid, OrderStatus.SUBMITTED)

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {
            "uid": new_uid,
            "status": "fulfilled",
        }

        status = await tracker.poll_order_status(new_uid, mock_client)

        assert status == OrderStatus.FILLED
        mock_client.get_order.assert_called_once_with(new_uid)


class TestMetricsStoreUIDUpdate:
    """Tests for MetricsStore UID update functionality."""

    def test_update_order_uid_in_store(self):
        """Test updating order UID in MetricsStore."""
        from cow_performance.metrics.models import OrderMetadata

        store = MetricsStore()
        old_uid = "pending_123"
        new_uid = "0xreal_uid"

        metadata = OrderMetadata(
            order_uid=old_uid,
            owner="0xowner",
            creation_time=1234567890.0,
        )
        store.add_order(metadata)

        # Update UID
        store.update_order_uid(old_uid, new_uid)

        # Old UID gone, new UID present
        assert store.get_order(old_uid) is None
        stored = store.get_order(new_uid)
        assert stored is not None
        assert stored.order_uid == new_uid
        assert stored.owner == "0xowner"

    def test_update_order_uid_nonexistent_in_store(self):
        """Test updating non-existent UID in store does nothing."""
        store = MetricsStore()
        store.update_order_uid("nonexistent", "new_uid")
        assert store.get_order("new_uid") is None


class TestOrderTrackerMonitoringTasks:
    """Tests for background monitoring tasks."""

    @pytest.fixture
    def tracker(self):
        """Create an order tracker fixture."""
        return OrderTracker(poll_interval=0.01, max_poll_attempts=3)

    @pytest.mark.asyncio
    async def test_start_monitoring(self, tracker):
        """Test starting background monitoring."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.FILLED)  # Terminal immediately

        mock_client = AsyncMock()

        task = tracker.start_monitoring(order_uid, mock_client)

        # Wait for task to complete
        metadata = await task

        assert metadata.current_status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, tracker):
        """Test stopping background monitoring."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {"uid": order_uid, "status": "open"}

        tracker.start_monitoring(order_uid, mock_client)

        # Stop immediately
        await tracker.stop_monitoring(order_uid)

        assert order_uid not in tracker._polling_tasks

    @pytest.mark.asyncio
    async def test_stop_all_monitoring(self, tracker):
        """Test stopping all background monitoring."""
        tracker.track_order("0x1", owner="0xowner")
        tracker.track_order("0x2", owner="0xowner")

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {"uid": "0x", "status": "open"}

        tracker.start_monitoring("0x1", mock_client)
        tracker.start_monitoring("0x2", mock_client)

        await tracker.stop_all_monitoring()

        assert len(tracker._polling_tasks) == 0
