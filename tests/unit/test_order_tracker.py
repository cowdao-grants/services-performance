"""
Unit tests for order tracking and lifecycle monitoring.

Tests order status tracking, metrics calculation, and lifecycle transitions.
"""

import asyncio
import time

import pytest

from cow_performance.load_generation import OrderStatus, OrderTracker


class TestOrderMetadata:
    """Tests for OrderMetadata lifecycle tracking."""

    @pytest.fixture
    def order_tracker(self):
        """Create order tracker fixture."""
        return OrderTracker()

    def test_track_order_creates_metadata(self, order_tracker):
        """Test that tracking an order creates metadata."""
        order_uid = "0x1234"
        owner = "0xabcd"

        metadata = order_tracker.track_order(order_uid, owner)

        assert metadata is not None
        assert metadata.order_uid == order_uid
        assert metadata.owner == owner
        assert metadata.current_status == OrderStatus.CREATED

    def test_get_order_returns_metadata(self, order_tracker):
        """Test getting tracked order metadata."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xabcd")

        metadata = order_tracker.get_order(order_uid)

        assert metadata is not None
        assert metadata.order_uid == order_uid

    def test_get_order_returns_none_for_untracked(self, order_tracker):
        """Test getting untracked order returns None."""
        metadata = order_tracker.get_order("0x9999")
        assert metadata is None

    def test_update_order_status(self, order_tracker):
        """Test updating order status."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xabcd")

        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        metadata = order_tracker.get_order(order_uid)
        assert metadata.current_status == OrderStatus.SUBMITTED

        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
        metadata = order_tracker.get_order(order_uid)
        assert metadata.current_status == OrderStatus.ACCEPTED

    def test_status_history_tracks_transitions(self, order_tracker):
        """Test that status history tracks all transitions."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xabcd")

        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        metadata = order_tracker.get_order(order_uid)
        assert len(metadata.status_history) == 3
        assert metadata.status_history[0][1] == OrderStatus.SUBMITTED
        assert metadata.status_history[1][1] == OrderStatus.ACCEPTED
        assert metadata.status_history[2][1] == OrderStatus.FILLED

    def test_time_to_submit_calculation(self, order_tracker):
        """Test time to submit calculation."""
        order_uid = "0x1234"
        metadata = order_tracker.track_order(order_uid, "0xabcd")

        time.sleep(0.1)
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        time_to_submit = metadata.get_time_to_submit()
        assert time_to_submit is not None
        assert time_to_submit > 0
        assert time_to_submit < 1.0  # Should be less than 1 second

    def test_time_to_accept_calculation(self, order_tracker):
        """Test time to accept calculation."""
        order_uid = "0x1234"
        metadata = order_tracker.track_order(order_uid, "0xabcd")

        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        time.sleep(0.1)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)

        time_to_accept = metadata.get_time_to_accept()
        assert time_to_accept is not None
        assert time_to_accept > 0

    def test_time_to_fill_calculation(self, order_tracker):
        """Test time to fill calculation."""
        order_uid = "0x1234"
        metadata = order_tracker.track_order(order_uid, "0xabcd")

        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
        time.sleep(0.1)
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        time_to_fill = metadata.get_time_to_fill()
        assert time_to_fill is not None
        assert time_to_fill > 0

    def test_total_lifecycle_time_calculation(self, order_tracker):
        """Test total lifecycle time calculation."""
        order_uid = "0x1234"
        metadata = order_tracker.track_order(order_uid, "0xabcd")

        time.sleep(0.1)
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        lifecycle_time = metadata.get_total_lifecycle_time()
        assert lifecycle_time is not None
        assert lifecycle_time > 0

    def test_is_terminal_state(self, order_tracker):
        """Test terminal state detection."""
        order_uid = "0x1234"
        metadata = order_tracker.track_order(order_uid, "0xabcd")

        # Non-terminal states
        assert not metadata.is_terminal_state()
        order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
        assert not metadata.is_terminal_state()
        order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
        assert not metadata.is_terminal_state()

        # Terminal state
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)
        assert metadata.is_terminal_state()


class TestOrderTracker:
    """Tests for OrderTracker class."""

    @pytest.fixture
    def order_tracker(self):
        """Create order tracker fixture."""
        return OrderTracker(poll_interval=0.1, max_poll_attempts=5)

    def test_track_multiple_orders(self, order_tracker):
        """Test tracking multiple orders."""
        order_tracker.track_order("0x1111", "0xaaaa")
        order_tracker.track_order("0x2222", "0xbbbb")
        order_tracker.track_order("0x3333", "0xcccc")

        all_orders = order_tracker.get_all_orders()
        assert len(all_orders) == 3

    def test_get_metrics_with_no_orders(self, order_tracker):
        """Test metrics calculation with no orders."""
        metrics = order_tracker.get_metrics()

        assert metrics.total_orders == 0
        assert metrics.orders_filled == 0

    def test_get_metrics_with_orders(self, order_tracker):
        """Test metrics calculation with orders."""
        # Create some orders in different states
        order_tracker.track_order("0x1111", "0xaaaa")
        order_tracker.update_order_status("0x1111", OrderStatus.SUBMITTED)
        order_tracker.update_order_status("0x1111", OrderStatus.ACCEPTED)
        order_tracker.update_order_status("0x1111", OrderStatus.FILLED)

        order_tracker.track_order("0x2222", "0xbbbb")
        order_tracker.update_order_status("0x2222", OrderStatus.SUBMITTED)
        order_tracker.update_order_status("0x2222", OrderStatus.ACCEPTED)

        order_tracker.track_order("0x3333", "0xcccc")
        order_tracker.update_order_status("0x3333", OrderStatus.FAILED)

        metrics = order_tracker.get_metrics()

        assert metrics.total_orders == 3
        assert metrics.orders_filled == 1
        assert metrics.orders_accepted == 1
        assert metrics.orders_failed == 1

    def test_metrics_average_times(self, order_tracker):
        """Test that metrics calculate average times correctly."""
        # Create order with known delays
        order_tracker.track_order("0x1111", "0xaaaa")
        time.sleep(0.1)
        order_tracker.update_order_status("0x1111", OrderStatus.SUBMITTED)
        time.sleep(0.1)
        order_tracker.update_order_status("0x1111", OrderStatus.ACCEPTED)
        time.sleep(0.1)
        order_tracker.update_order_status("0x1111", OrderStatus.FILLED)

        metrics = order_tracker.get_metrics()

        assert metrics.avg_time_to_submit > 0
        assert metrics.avg_time_to_accept > 0
        assert metrics.avg_time_to_fill > 0
        assert metrics.avg_total_lifecycle_time > 0

    @pytest.mark.asyncio
    async def test_monitor_order_until_terminal(self, order_tracker):
        """Test monitoring order until terminal state."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xaaaa")

        # Simulate order progression in background
        async def update_order():
            await asyncio.sleep(0.2)
            order_tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)
            await asyncio.sleep(0.2)
            order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
            await asyncio.sleep(0.2)
            order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        # Start monitoring and updating concurrently
        update_task = asyncio.create_task(update_order())
        metadata = await order_tracker.monitor_order(order_uid)

        await update_task

        assert metadata.current_status == OrderStatus.FILLED
        assert metadata.is_terminal_state()

    @pytest.mark.asyncio
    async def test_monitor_order_max_attempts(self, order_tracker):
        """Test that monitoring stops after max attempts."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xaaaa")

        # Don't update status, should timeout after max_poll_attempts
        metadata = await order_tracker.monitor_order(order_uid)

        # Should remain in CREATED status (not marked as FAILED)
        # The orchestrator's settlement wait will continue monitoring
        assert metadata.current_status == OrderStatus.CREATED
        assert metadata.error_message is None

    @pytest.mark.asyncio
    async def test_start_monitoring_in_background(self, order_tracker):
        """Test starting monitoring in background."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xaaaa")

        task = order_tracker.start_monitoring(order_uid)
        assert task is not None
        assert not task.done()

        # Mark as filled to complete monitoring
        order_tracker.update_order_status(order_uid, OrderStatus.FILLED)

        # Wait for monitoring to complete
        await asyncio.sleep(0.3)
        assert task.done()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, order_tracker):
        """Test stopping monitoring."""
        order_uid = "0x1234"
        order_tracker.track_order(order_uid, "0xaaaa")

        task = order_tracker.start_monitoring(order_uid)
        await asyncio.sleep(0.1)

        await order_tracker.stop_monitoring(order_uid)
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_stop_all_monitoring(self, order_tracker):
        """Test stopping all monitoring tasks."""
        # Start monitoring multiple orders
        for i in range(3):
            order_uid = f"0x{i:04x}"
            order_tracker.track_order(order_uid, "0xaaaa")
            order_tracker.start_monitoring(order_uid)

        await asyncio.sleep(0.1)

        # Stop all
        await order_tracker.stop_all_monitoring()

        # All should be stopped
        assert len(order_tracker._polling_tasks) == 0
