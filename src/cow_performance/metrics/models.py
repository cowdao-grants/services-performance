"""
Data models for metrics collection in CoW Protocol performance testing.

This module defines the core data structures for capturing and tracking
performance metrics during load testing.
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class OrderStatus(StrEnum):
    """Order lifecycle states."""

    CREATED = "created"  # Order created locally, not yet submitted
    SUBMITTED = "submitted"  # Order submitted to API, awaiting confirmation
    ACCEPTED = "accepted"  # Order accepted by orderbook
    OPEN = "open"  # Order is active in the orderbook
    FILLED = "filled"  # Order fully filled
    PARTIALLY_FILLED = "partiallyFilled"  # Order partially filled
    EXPIRED = "expired"  # Order expired (past validTo)
    CANCELLED = "cancelled"  # Order cancelled by user
    FAILED = "failed"  # Order submission/processing failed


@dataclass
class OrderMetadata:
    """
    Metadata about an order for tracking and metrics.

    Tracks timestamps, status transitions, and order details for
    lifecycle analysis and performance monitoring.
    """

    order_uid: str
    owner: str
    creation_time: float
    submission_time: float | None = None
    acceptance_time: float | None = None
    first_fill_time: float | None = None
    completion_time: float | None = None
    expiration_time: float | None = None  # When order was detected as expired

    current_status: OrderStatus = OrderStatus.CREATED
    status_history: list[tuple[float, OrderStatus]] = field(default_factory=list)

    valid_to: int | None = None  # Unix timestamp when order expires

    sell_token: str = ""
    buy_token: str = ""
    sell_amount: str = "0"
    buy_amount: str = "0"

    filled_amount: str = "0"
    error_message: str | None = None
    order_type: str = "unknown"  # "market", "limit", "twap", "stop_loss", "good_after_time"

    def update_status(self, new_status: OrderStatus, timestamp: float | None = None) -> None:
        """
        Update order status and record the transition.

        Args:
            new_status: The new order status
            timestamp: Optional timestamp (uses current time if not provided)
        """
        if timestamp is None:
            timestamp = time.time()

        self.current_status = new_status
        self.status_history.append((timestamp, new_status))

        # Update lifecycle timestamps
        if new_status == OrderStatus.SUBMITTED and self.submission_time is None:
            self.submission_time = timestamp
        elif (
            new_status in (OrderStatus.ACCEPTED, OrderStatus.OPEN) and self.acceptance_time is None
        ):
            self.acceptance_time = timestamp

        # Handle fill time (can be both FILLED and completion)
        if (
            new_status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED)
            and self.first_fill_time is None
        ):
            self.first_fill_time = timestamp

        # Handle expiration time
        if new_status == OrderStatus.EXPIRED and self.expiration_time is None:
            self.expiration_time = timestamp

        # Handle completion (terminal states)
        if new_status in (
            OrderStatus.FILLED,
            OrderStatus.EXPIRED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
        ):
            if self.completion_time is None:
                self.completion_time = timestamp

    def get_time_to_submit(self) -> float | None:
        """Get time from creation to submission in seconds."""
        if self.submission_time is None:
            return None
        return self.submission_time - self.creation_time

    def get_time_to_accept(self) -> float | None:
        """Get time from submission to acceptance in seconds."""
        if self.submission_time is None or self.acceptance_time is None:
            return None
        return self.acceptance_time - self.submission_time

    def get_time_to_fill(self) -> float | None:
        """Get time from acceptance to first fill in seconds."""
        if self.acceptance_time is None or self.first_fill_time is None:
            return None
        return self.first_fill_time - self.acceptance_time

    def get_total_lifecycle_time(self) -> float | None:
        """Get total time from creation to completion in seconds."""
        if self.completion_time is None:
            return None
        return self.completion_time - self.creation_time

    def is_terminal_state(self) -> bool:
        """Check if order is in a terminal state (no more updates expected)."""
        return self.current_status in (
            OrderStatus.FILLED,
            OrderStatus.EXPIRED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED,
        )


@dataclass
class OrderMetrics:
    """
    Aggregated metrics for order tracking.

    Provides summary statistics for order lifecycle performance
    across multiple orders.
    """

    total_orders: int = 0
    orders_created: int = 0
    orders_submitted: int = 0
    orders_accepted: int = 0
    orders_filled: int = 0
    orders_partially_filled: int = 0
    orders_expired: int = 0
    orders_cancelled: int = 0
    orders_failed: int = 0

    # Order type counts
    market_orders: int = 0
    limit_orders: int = 0

    avg_time_to_submit: float = 0.0
    avg_time_to_accept: float = 0.0
    avg_time_to_fill: float = 0.0
    avg_total_lifecycle_time: float = 0.0


@dataclass
class APIMetrics:
    """
    Metrics for a single API request.

    Captures timing, status, and payload information for
    performance analysis of API interactions.
    """

    endpoint: str
    method: str  # GET, POST, PUT, DELETE
    timestamp: float  # When the request was made
    duration: float  # Response time in seconds
    status_code: int
    payload_size: int = 0  # Request payload size in bytes
    response_size: int = 0  # Response size in bytes
    error_message: str | None = None

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return self.duration * 1000

    @property
    def is_success(self) -> bool:
        """Check if request was successful (2xx status)."""
        return 200 <= self.status_code < 300


@dataclass
class ResourceSample:
    """
    A single resource utilization sample.

    Represents a point-in-time snapshot of container resource usage.
    """

    timestamp: float
    cpu_percent: float  # CPU usage percentage (0-100+)
    memory_bytes: int  # Current memory usage in bytes
    memory_limit_bytes: int  # Memory limit in bytes
    network_rx_bytes: int = 0  # Network bytes received
    network_tx_bytes: int = 0  # Network bytes transmitted
    block_read_bytes: int = 0  # Block I/O read
    block_write_bytes: int = 0  # Block I/O write
    disk_usage_bytes: int = 0  # Total disk space used by container

    @property
    def memory_percent(self) -> float:
        """Get memory usage as percentage of limit."""
        if self.memory_limit_bytes == 0:
            return 0.0
        return (self.memory_bytes / self.memory_limit_bytes) * 100


@dataclass
class ResourceMetrics:
    """
    Aggregated resource metrics for a container.

    Stores time-series samples and provides summary statistics.
    """

    container_name: str
    samples: list[ResourceSample] = field(default_factory=list)

    def add_sample(self, sample: ResourceSample) -> None:
        """Add a resource sample."""
        self.samples.append(sample)

    @property
    def avg_cpu_percent(self) -> float:
        """Get average CPU usage."""
        if not self.samples:
            return 0.0
        return sum(s.cpu_percent for s in self.samples) / len(self.samples)

    @property
    def max_cpu_percent(self) -> float:
        """Get maximum CPU usage."""
        if not self.samples:
            return 0.0
        return max(s.cpu_percent for s in self.samples)

    @property
    def avg_memory_percent(self) -> float:
        """Get average memory usage percentage."""
        if not self.samples:
            return 0.0
        return sum(s.memory_percent for s in self.samples) / len(self.samples)

    @property
    def max_memory_bytes(self) -> int:
        """Get maximum memory usage."""
        if not self.samples:
            return 0
        return max(s.memory_bytes for s in self.samples)


@dataclass
class TestRunMetrics:
    """
    Aggregate metrics for an entire test run.

    Combines order lifecycle, API, and resource metrics into
    a comprehensive test summary.
    """

    # Test identification
    test_id: str
    start_time: float
    end_time: float | None = None

    # Configuration snapshot
    num_traders: int = 0
    duration_seconds: float = 0.0

    # Order counts
    total_orders: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_failed: int = 0
    orders_expired: int = 0

    # Timing summaries (in seconds)
    avg_submission_latency: float = 0.0
    avg_time_to_fill: float = 0.0
    avg_total_lifecycle: float = 0.0

    # Throughput
    orders_per_second: float = 0.0

    # API summary
    total_api_calls: int = 0
    api_success_rate: float = 0.0
    avg_api_response_time: float = 0.0

    @property
    def test_duration(self) -> float | None:
        """Get actual test duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time

    @property
    def success_rate(self) -> float:
        """Get order success rate (filled / submitted)."""
        if self.orders_submitted == 0:
            return 0.0
        return self.orders_filled / self.orders_submitted
