"""Unit tests for ExpirationChecker."""

import asyncio
import time

import pytest

from cow_performance.metrics import ExpirationChecker, MetricsStore, OrderMetadata, OrderStatus


class TestExpirationChecker:
    """Tests for ExpirationChecker background task."""

    @pytest.fixture
    def metrics_store(self):
        """Create a MetricsStore for testing."""
        return MetricsStore()

    @pytest.fixture
    def expiration_checker(self, metrics_store):
        """Create an ExpirationChecker with short check interval."""
        return ExpirationChecker(metrics_store, check_interval=0.1)  # 100ms for fast tests

    @pytest.mark.asyncio
    async def test_start_and_stop(self, expiration_checker):
        """Test starting and stopping the expiration checker."""
        assert not expiration_checker._running

        await expiration_checker.start()
        assert expiration_checker._running
        assert expiration_checker._task is not None

        await expiration_checker.stop()
        assert not expiration_checker._running

    @pytest.mark.asyncio
    async def test_marks_expired_orders(self, metrics_store, expiration_checker):
        """Test that orders past valid_to are marked as expired."""
        # Create order with valid_to in the past
        past_time = int(time.time()) - 10  # 10 seconds ago
        order = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=past_time,
        )
        order.update_status(OrderStatus.OPEN)
        metrics_store.add_order(order)

        # Start checker and wait for it to run
        await expiration_checker.start()
        await asyncio.sleep(0.3)  # Wait for multiple check cycles
        await expiration_checker.stop()

        # Check that order was marked as expired
        updated_order = metrics_store.get_order("0x1234")
        assert updated_order is not None
        assert updated_order.current_status == OrderStatus.EXPIRED
        assert updated_order.expiration_time is not None

    @pytest.mark.asyncio
    async def test_does_not_mark_future_orders(self, metrics_store, expiration_checker):
        """Test that orders with future valid_to are not marked as expired."""
        # Create order with valid_to in the future
        future_time = int(time.time()) + 3600  # 1 hour from now
        order = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=future_time,
        )
        order.update_status(OrderStatus.OPEN)
        metrics_store.add_order(order)

        # Start checker and wait
        await expiration_checker.start()
        await asyncio.sleep(0.3)
        await expiration_checker.stop()

        # Check that order is still open
        updated_order = metrics_store.get_order("0x1234")
        assert updated_order is not None
        assert updated_order.current_status == OrderStatus.OPEN

    @pytest.mark.asyncio
    async def test_does_not_mark_already_expired(self, metrics_store, expiration_checker):
        """Test that already-expired orders are not processed again."""
        past_time = int(time.time()) - 10
        order = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=past_time,
        )
        order.update_status(OrderStatus.EXPIRED)
        metrics_store.add_order(order)

        # Record original expiration_time
        original_expiration_time = order.expiration_time

        # Start checker and wait
        await expiration_checker.start()
        await asyncio.sleep(0.3)
        await expiration_checker.stop()

        # Check that expiration_time was not changed
        updated_order = metrics_store.get_order("0x1234")
        assert updated_order is not None
        assert updated_order.current_status == OrderStatus.EXPIRED
        assert updated_order.expiration_time == original_expiration_time

    @pytest.mark.asyncio
    async def test_does_not_mark_terminal_orders(self, metrics_store, expiration_checker):
        """Test that orders in terminal states (filled/cancelled/failed) are not marked as expired."""
        past_time = int(time.time()) - 10

        # Test with filled order
        filled_order = OrderMetadata(
            order_uid="0x_filled",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=past_time,
        )
        filled_order.update_status(OrderStatus.FILLED)
        metrics_store.add_order(filled_order)

        # Test with cancelled order
        cancelled_order = OrderMetadata(
            order_uid="0x_cancelled",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=past_time,
        )
        cancelled_order.update_status(OrderStatus.CANCELLED)
        metrics_store.add_order(cancelled_order)

        # Test with failed order
        failed_order = OrderMetadata(
            order_uid="0x_failed",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=past_time,
        )
        failed_order.update_status(OrderStatus.FAILED)
        metrics_store.add_order(failed_order)

        # Start checker and wait
        await expiration_checker.start()
        await asyncio.sleep(0.3)
        await expiration_checker.stop()

        # Check that orders are still in their original terminal states
        assert metrics_store.get_order("0x_filled").current_status == OrderStatus.FILLED
        assert metrics_store.get_order("0x_cancelled").current_status == OrderStatus.CANCELLED
        assert metrics_store.get_order("0x_failed").current_status == OrderStatus.FAILED

    @pytest.mark.asyncio
    async def test_handles_orders_without_valid_to(self, metrics_store, expiration_checker):
        """Test that orders without valid_to are not processed."""
        order = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
            valid_to=None,  # No expiration set
        )
        order.update_status(OrderStatus.OPEN)
        metrics_store.add_order(order)

        # Start checker and wait
        await expiration_checker.start()
        await asyncio.sleep(0.3)
        await expiration_checker.stop()

        # Check that order is still open
        updated_order = metrics_store.get_order("0x1234")
        assert updated_order is not None
        assert updated_order.current_status == OrderStatus.OPEN

    @pytest.mark.asyncio
    async def test_multiple_orders_expiration(self, metrics_store, expiration_checker):
        """Test that multiple orders can be marked as expired in one check."""
        past_time = int(time.time()) - 10

        # Create 3 expired orders
        for i in range(3):
            order = OrderMetadata(
                order_uid=f"0x{i:04x}",
                owner="0xabcd",
                creation_time=time.time(),
                valid_to=past_time,
            )
            order.update_status(OrderStatus.OPEN)
            metrics_store.add_order(order)

        # Start checker and wait
        await expiration_checker.start()
        await asyncio.sleep(0.3)
        await expiration_checker.stop()

        # Check that all orders were marked as expired
        for i in range(3):
            updated_order = metrics_store.get_order(f"0x{i:04x}")
            assert updated_order is not None
            assert updated_order.current_status == OrderStatus.EXPIRED


    @pytest.mark.asyncio
    async def test_double_start_warning(self, expiration_checker, caplog):
        """Test that starting an already-running checker logs a warning."""
        await expiration_checker.start()
        await expiration_checker.start()  # Second start should warn

        # Check for warning in logs
        assert any("already running" in record.message.lower() for record in caplog.records)

        await expiration_checker.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, expiration_checker):
        """Test that stopping a non-running checker is safe."""
        assert not expiration_checker._running
        await expiration_checker.stop()  # Should not raise
        assert not expiration_checker._running
