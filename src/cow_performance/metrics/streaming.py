"""
Real-time metrics streaming for live monitoring.

Provides async event stream for metrics updates using MetricsStore callbacks.
"""

import asyncio
import logging
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cow_performance.metrics.store import MetricsStore

logger = logging.getLogger(__name__)


class MetricEventType(StrEnum):
    """Types of metric events."""

    ORDER = "order"
    API = "api"
    RESOURCE = "resource"


@dataclass
class MetricEvent:
    """A single metric event for streaming."""

    event_type: MetricEventType
    data: Any
    timestamp: float


class MetricsEventStream:
    """
    Async event stream for real-time metrics monitoring.

    Uses MetricsStore callbacks to stream metrics updates as async events.
    Can be used with async for loops for live monitoring.

    Example:
        store = MetricsStore()
        stream = MetricsEventStream(store)

        async with stream:
            async for event in stream:
                print(f"New {event.event_type}: {event.data}")
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        buffer_size: int = 1000,
    ):
        """
        Initialize the event stream.

        Args:
            metrics_store: The metrics store to stream from
            buffer_size: Maximum number of events to buffer
        """
        self._store = metrics_store
        self._buffer_size = buffer_size
        self._queue: asyncio.Queue[MetricEvent | None] = asyncio.Queue(maxsize=buffer_size)
        self._running = False

    def _callback(self, metric_type: str, metric: object) -> None:
        """
        Callback for MetricsStore updates.

        Converts metrics to events and adds to queue.
        """
        try:
            event = MetricEvent(
                event_type=MetricEventType(metric_type),
                data=metric,
                timestamp=time.time(),
            )

            # Non-blocking put - drop oldest if full
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event and add new one
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

        except Exception as e:
            logger.warning(f"Error in metrics stream callback: {e}")

    async def start(self) -> None:
        """Start streaming metrics events."""
        if self._running:
            return

        self._running = True
        self._store.register_callback(self._callback)
        logger.debug("MetricsEventStream started")

    async def stop(self) -> None:
        """Stop streaming and signal completion."""
        if not self._running:
            return

        self._running = False
        self._store.unregister_callback(self._callback)

        # Signal end of stream
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        logger.debug("MetricsEventStream stopped")

    async def __aenter__(self) -> "MetricsEventStream":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.stop()

    def __aiter__(self) -> AsyncIterator[MetricEvent]:
        """Return async iterator."""
        return self

    async def __anext__(self) -> MetricEvent:
        """Get next event from stream."""
        if not self._running:
            raise StopAsyncIteration

        event = await self._queue.get()

        if event is None:
            raise StopAsyncIteration

        return event

    async def get_event(self, timeout: float | None = None) -> MetricEvent | None:
        """
        Get next event with optional timeout.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            MetricEvent or None if timeout/stopped
        """
        try:
            if timeout is not None:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            else:
                event = await self._queue.get()

            return event

        except TimeoutError:
            return None

    def is_running(self) -> bool:
        """Check if stream is currently running."""
        return self._running

    @property
    def pending_count(self) -> int:
        """Get number of pending events in queue."""
        return self._queue.qsize()


class RollingMetricsSummary:
    """
    Maintains a rolling summary of recent metrics.

    Useful for real-time dashboards showing recent performance.
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize rolling summary.

        Args:
            window_size: Number of recent events to track
        """
        self._window_size = window_size
        self._order_events: deque[MetricEvent] = deque(maxlen=window_size)
        self._api_events: deque[MetricEvent] = deque(maxlen=window_size)
        self._resource_events: deque[MetricEvent] = deque(maxlen=window_size)

    def add_event(self, event: MetricEvent) -> None:
        """Add an event to the rolling window."""
        if event.event_type == MetricEventType.ORDER:
            self._order_events.append(event)
        elif event.event_type == MetricEventType.API:
            self._api_events.append(event)
        elif event.event_type == MetricEventType.RESOURCE:
            self._resource_events.append(event)

    def get_recent_order_count(self) -> int:
        """Get count of orders in the rolling window."""
        return len(self._order_events)

    def get_recent_api_success_rate(self) -> float:
        """Get API success rate in the rolling window."""
        if not self._api_events:
            return 0.0

        successes = sum(
            1 for e in self._api_events if hasattr(e.data, "is_success") and e.data.is_success
        )
        return successes / len(self._api_events)

    def get_recent_avg_api_response_time(self) -> float:
        """Get average API response time in the rolling window (ms)."""
        if not self._api_events:
            return 0.0

        durations = [e.data.duration_ms for e in self._api_events if hasattr(e.data, "duration_ms")]

        if not durations:
            return 0.0

        return float(sum(durations)) / len(durations)

    def get_summary(self) -> dict[str, Any]:
        """Get current rolling summary."""
        return {
            "recent_orders": self.get_recent_order_count(),
            "recent_api_count": len(self._api_events),
            "recent_api_success_rate": self.get_recent_api_success_rate(),
            "recent_avg_api_response_ms": self.get_recent_avg_api_response_time(),
            "recent_resource_samples": len(self._resource_events),
        }
