"""Unit tests for real-time metrics streaming."""

import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricEvent,
    MetricEventType,
    MetricsEventStream,
    MetricsStore,
    OrderMetadata,
    RollingMetricsSummary,
)


class TestMetricsEventStream:
    """Tests for MetricsEventStream class."""

    @pytest.fixture
    def store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def stream(self, store):
        """Create an event stream fixture."""
        return MetricsEventStream(store, buffer_size=100)

    @pytest.mark.asyncio
    async def test_stream_start_stop(self, stream):
        """Test starting and stopping stream."""
        assert not stream.is_running()

        await stream.start()
        assert stream.is_running()

        await stream.stop()
        assert not stream.is_running()

    @pytest.mark.asyncio
    async def test_stream_context_manager(self, store):
        """Test stream as async context manager."""
        stream = MetricsEventStream(store)

        async with stream:
            assert stream.is_running()

        assert not stream.is_running()

    @pytest.mark.asyncio
    async def test_stream_receives_order_events(self, store, stream):
        """Test that stream receives order events."""
        await stream.start()

        # Add order to store (triggers callback)
        store.add_order(
            OrderMetadata(
                order_uid="0x1234",
                owner="0xowner",
                creation_time=time.time(),
            )
        )

        # Get event with timeout
        event = await stream.get_event(timeout=1.0)

        assert event is not None
        assert event.event_type == MetricEventType.ORDER
        assert event.data.order_uid == "0x1234"

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_receives_api_events(self, store, stream):
        """Test that stream receives API events."""
        await stream.start()

        # Add API metric to store
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=time.time(),
                duration=0.1,
                status_code=201,
            )
        )

        event = await stream.get_event(timeout=1.0)

        assert event is not None
        assert event.event_type == MetricEventType.API
        assert event.data.endpoint == "/api/v1/orders"

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_iteration(self, store, stream):
        """Test async iteration over stream."""
        await stream.start()

        # Add multiple events
        for i in range(5):
            store.add_order(
                OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                )
            )

        # Collect events
        events = []
        for _ in range(5):
            event = await stream.get_event(timeout=1.0)
            if event:
                events.append(event)

        assert len(events) == 5

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_buffer_overflow(self, store):
        """Test that buffer overflow drops oldest events."""
        stream = MetricsEventStream(store, buffer_size=5)
        await stream.start()

        # Add more events than buffer size
        for i in range(10):
            store.add_order(
                OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                )
            )

        # Should have dropped oldest events
        assert stream.pending_count <= 5

        await stream.stop()

    @pytest.mark.asyncio
    async def test_stream_timeout(self, store, stream):
        """Test get_event with timeout."""
        await stream.start()

        # Don't add any events - should timeout
        event = await stream.get_event(timeout=0.1)

        assert event is None

        await stream.stop()


class TestRollingMetricsSummary:
    """Tests for RollingMetricsSummary class."""

    def test_add_order_event(self):
        """Test adding order events to rolling summary."""
        summary = RollingMetricsSummary(window_size=10)

        for i in range(5):
            event = MetricEvent(
                event_type=MetricEventType.ORDER,
                data=OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        assert summary.get_recent_order_count() == 5

    def test_add_api_event_success_rate(self):
        """Test API success rate calculation."""
        summary = RollingMetricsSummary(window_size=10)

        # Add 8 successful, 2 failed
        for i in range(10):
            event = MetricEvent(
                event_type=MetricEventType.API,
                data=APIMetrics(
                    endpoint="/test",
                    method="GET",
                    timestamp=time.time(),
                    duration=0.1,
                    status_code=200 if i < 8 else 500,
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        assert summary.get_recent_api_success_rate() == 0.8

    def test_rolling_window_drops_old_events(self):
        """Test that rolling window drops old events."""
        summary = RollingMetricsSummary(window_size=5)

        for i in range(10):
            event = MetricEvent(
                event_type=MetricEventType.ORDER,
                data=OrderMetadata(
                    order_uid=f"0x{i:064x}",
                    owner="0xowner",
                    creation_time=time.time(),
                ),
                timestamp=time.time(),
            )
            summary.add_event(event)

        # Should only have last 5
        assert summary.get_recent_order_count() == 5

    def test_get_summary(self):
        """Test getting full summary."""
        summary = RollingMetricsSummary()

        # Add some events
        summary.add_event(
            MetricEvent(
                event_type=MetricEventType.ORDER,
                data=OrderMetadata(order_uid="0x1", owner="0x", creation_time=time.time()),
                timestamp=time.time(),
            )
        )
        summary.add_event(
            MetricEvent(
                event_type=MetricEventType.API,
                data=APIMetrics(
                    endpoint="/test",
                    method="GET",
                    timestamp=time.time(),
                    duration=0.1,
                    status_code=200,
                ),
                timestamp=time.time(),
            )
        )

        result = summary.get_summary()

        assert "recent_orders" in result
        assert "recent_api_count" in result
        assert "recent_api_success_rate" in result
        assert result["recent_orders"] == 1
        assert result["recent_api_count"] == 1
