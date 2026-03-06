# COW-610: Collection - Lifecycle, API & Resource Monitoring Implementation Plan

## Overview

Implement the core metrics collection components that feed data into the foundation models (COW-609). This includes:
1. **InstrumentedOrderbookClient** - HTTP client wrapper with timing instrumentation
2. **OrderLifecycleTracker** - Enhanced order tracking with real API polling
3. **ResourceMonitor** - Docker container stats collection

## Current State Analysis

### What Exists

- **Foundation models** (`metrics/models.py:154-302`): `APIMetrics`, `ResourceSample`, `ResourceMetrics` are ready
- **MetricsStore** (`metrics/store.py`): Has `add_api_metric()`, `add_resource_sample()` with thread-safety
- **OrderbookClient** (`api/orderbook_client.py:13-184`): Uses aiohttp, creates sessions per request, **no timing instrumentation**
- **OrderTracker** (`load_generation/order_tracker.py:15-287`): Has `poll_order_status()` that's a **mock** - doesn't call API
- **Docker SDK**: Listed as dependency (`pyproject.toml:28`) but unused
- **Container services** in docker-compose.yml: `chain`, `orderbook`, `autopilot`, `driver`, `baseline`, `watch-tower`

### Key Discoveries

- `OrderbookClient.get_order()` (`api/orderbook_client.py:62-81`) returns order details including status
- `OrderTracker.poll_order_status()` (`order_tracker.py:119-145`) is marked as mock implementation
- CoW API order statuses from OpenAPI spec: `"presignaturePending"`, `"open"`, `"fulfilled"`, `"cancelled"`, `"expired"`
- Docker Compose uses default naming (e.g., `cow-performance-testing-suite-orderbook-1`)
- `TraderSimulator._submit_standard_order()` (`trader_simulator.py:212-263`) is the key integration point

## Desired End State

After this plan is complete:

1. **InstrumentedOrderbookClient** wraps `OrderbookClient` with timing and metrics
2. **OrderTracker.poll_order_status()** calls real API and maps status correctly
3. **ResourceMonitor** collects Docker stats from all CoW Protocol containers
4. All metrics flow into `MetricsStore` automatically
5. Unit tests for all new components
6. Integration with existing `TraderSimulator` and `run.py`

### Verification

```bash
# All tests pass
poetry run pytest tests/unit/test_instrumented_client.py tests/unit/test_order_lifecycle.py tests/unit/test_resource_monitor.py -v

# Linting passes
poetry run ruff check src/cow_performance/

# Type checking passes
poetry run mypy src/cow_performance/

# Existing tests still pass
poetry run pytest tests/unit/ -v
```

## What We're NOT Doing

- **COW-611 scope**: Metrics aggregation, percentiles, real-time streaming, CLI integration
- **Prometheus exporters**: Part of M3 milestone
- **Settlement detection on-chain**: Complex feature, deferred to later iteration
- **Connection pooling metrics**: Nice-to-have, not required for initial implementation
- **Retry logic instrumentation**: `OrderbookClient.max_retries` exists but isn't used; we won't implement it

## Implementation Approach

We'll implement in 4 phases, each resulting in a working, testable increment:

1. **Phase 1**: Instrumented HTTP Client Wrapper
2. **Phase 2**: Order Lifecycle Tracking (enhance OrderTracker with real API polling)
3. **Phase 3**: ResourceMonitor with Docker SDK
4. **Phase 4**: Integration and Testing

---

## Phase 1: Instrumented HTTP Client Wrapper

### Overview

Create `InstrumentedOrderbookClient` that wraps `OrderbookClient` to capture timing metrics for all API calls without modifying the original class.

### Changes Required

#### 1. Create instrumented client module

**File**: `src/cow_performance/api/instrumented_client.py`

```python
"""
Instrumented HTTP client wrapper for API timing metrics.

Wraps OrderbookClient to capture request timing, status codes, and payload sizes
for performance analysis.
"""

import time
from typing import Any

from cow_performance.api.orderbook_client import OrderbookClient
from cow_performance.metrics import APIMetrics, MetricsStore


class InstrumentedOrderbookClient:
    """
    Wrapper around OrderbookClient that records timing metrics.

    All API calls are timed and recorded to a MetricsStore for performance analysis.
    The wrapper maintains the same interface as OrderbookClient.

    Example:
        store = MetricsStore()
        client = InstrumentedOrderbookClient(
            base_url="http://localhost:8080",
            metrics_store=store,
        )
        # Use exactly like OrderbookClient
        result = await client.submit_order(signed_order)
    """

    def __init__(
        self,
        base_url: str,
        metrics_store: MetricsStore,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the instrumented client.

        Args:
            base_url: Base URL of the orderbook API
            metrics_store: Store for recording metrics
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts (passed to underlying client)
        """
        self._client = OrderbookClient(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._metrics_store = metrics_store

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self._client.base_url

    async def _record_metric(
        self,
        endpoint: str,
        method: str,
        start_time: float,
        status_code: int,
        payload_size: int = 0,
        response_size: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Record an API metric to the store."""
        duration = time.perf_counter() - start_time
        metric = APIMetrics(
            endpoint=endpoint,
            method=method,
            timestamp=time.time(),
            duration=duration,
            status_code=status_code,
            payload_size=payload_size,
            response_size=response_size,
            error_message=error_message,
        )
        async with self._metrics_store.lock:
            self._metrics_store.add_api_metric(metric)

    async def submit_order(self, signed_order: dict[str, Any]) -> dict[str, Any]:
        """
        Submit a signed order with timing instrumentation.

        Args:
            signed_order: Complete signed order with all required fields

        Returns:
            Response from the orderbook containing order UID and status
        """
        import json

        endpoint = "/api/v1/orders"
        method = "POST"
        payload_size = len(json.dumps(signed_order))
        start_time = time.perf_counter()

        try:
            result = await self._client.submit_order(signed_order)
            response_size = len(json.dumps(result))
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=201,  # Created
                payload_size=payload_size,
                response_size=response_size,
            )
            return result
        except Exception as e:
            # Extract status code from exception if available
            status_code = 500
            if hasattr(e, "status"):
                status_code = e.status
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=status_code,
                payload_size=payload_size,
                error_message=str(e),
            )
            raise

    async def get_order(self, order_uid: str) -> dict[str, Any]:
        """
        Get order details with timing instrumentation.

        Args:
            order_uid: The unique order identifier

        Returns:
            Order details including status, amounts, and metadata
        """
        import json

        endpoint = f"/api/v1/orders/{order_uid}"
        method = "GET"
        start_time = time.perf_counter()

        try:
            result = await self._client.get_order(order_uid)
            response_size = len(json.dumps(result))
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=200,
                response_size=response_size,
            )
            return result
        except Exception as e:
            status_code = 500
            if hasattr(e, "status"):
                status_code = e.status
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=status_code,
                error_message=str(e),
            )
            raise

    async def get_trades(self, order_uid: str) -> list[dict[str, Any]]:
        """
        Get trades for an order with timing instrumentation.

        Args:
            order_uid: The unique order identifier

        Returns:
            List of trades associated with the order
        """
        import json

        endpoint = f"/api/v1/orders/{order_uid}/trades"
        method = "GET"
        start_time = time.perf_counter()

        try:
            result = await self._client.get_trades(order_uid)
            response_size = len(json.dumps(result))
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=200,
                response_size=response_size,
            )
            return result
        except Exception as e:
            status_code = 500
            if hasattr(e, "status"):
                status_code = e.status
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=status_code,
                error_message=str(e),
            )
            raise

    async def upload_app_data(
        self, app_data_hash: str, app_data_doc: str | dict[str, Any]
    ) -> dict[str, Any]:
        """
        Upload appData document with timing instrumentation.

        Args:
            app_data_hash: 32-byte hash of the appData document
            app_data_doc: Full appData JSON document

        Returns:
            Response from the orderbook
        """
        import json

        endpoint = f"/api/v1/app_data/{app_data_hash}"
        method = "PUT"
        payload_size = len(json.dumps(app_data_doc) if isinstance(app_data_doc, dict) else app_data_doc)
        start_time = time.perf_counter()

        try:
            result = await self._client.upload_app_data(app_data_hash, app_data_doc)
            response_size = len(json.dumps(result)) if result else 0
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=200,
                payload_size=payload_size,
                response_size=response_size,
            )
            return result
        except Exception as e:
            status_code = 500
            if hasattr(e, "status"):
                status_code = e.status
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=status_code,
                payload_size=payload_size,
                error_message=str(e),
            )
            raise

    async def get_version(self) -> dict[str, Any]:
        """
        Get API version with timing instrumentation.

        Returns:
            Version information from the orderbook API
        """
        import json

        endpoint = "/api/v1/version"
        method = "GET"
        start_time = time.perf_counter()

        try:
            result = await self._client.get_version()
            response_size = len(json.dumps(result))
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=200,
                response_size=response_size,
            )
            return result
        except Exception as e:
            status_code = 500
            if hasattr(e, "status"):
                status_code = e.status
            await self._record_metric(
                endpoint=endpoint,
                method=method,
                start_time=start_time,
                status_code=status_code,
                error_message=str(e),
            )
            raise

    async def check_health(self) -> bool:
        """
        Check if the orderbook API is healthy.

        Note: This method does NOT record metrics to avoid noise from health checks.

        Returns:
            True if the API is healthy, False otherwise
        """
        return await self._client.check_health()
```

#### 2. Update api module exports

**File**: `src/cow_performance/api/__init__.py`

Add new export:
```python
from cow_performance.api.instrumented_client import InstrumentedOrderbookClient
from cow_performance.api.orderbook_client import OrderbookClient

__all__ = [
    "OrderbookClient",
    "InstrumentedOrderbookClient",
]
```

#### 3. Create unit tests

**File**: `tests/unit/test_instrumented_client.py`

```python
"""Unit tests for InstrumentedOrderbookClient."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cow_performance.api.instrumented_client import InstrumentedOrderbookClient
from cow_performance.metrics import MetricsStore


class TestInstrumentedOrderbookClient:
    """Tests for InstrumentedOrderbookClient."""

    @pytest.fixture
    def metrics_store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def client(self, metrics_store):
        """Create an instrumented client fixture."""
        return InstrumentedOrderbookClient(
            base_url="http://localhost:8080",
            metrics_store=metrics_store,
        )

    @pytest.mark.asyncio
    async def test_submit_order_records_metrics(self, client, metrics_store):
        """Test that submit_order records API metrics."""
        signed_order = {"sellToken": "0x1", "buyToken": "0x2"}
        mock_response = {"uid": "0x123"}

        with patch.object(
            client._client, "submit_order", new_callable=AsyncMock
        ) as mock_submit:
            mock_submit.return_value = mock_response
            result = await client.submit_order(signed_order)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics("/api/v1/orders")
        assert len(metrics) == 1
        assert metrics[0].method == "POST"
        assert metrics[0].status_code == 201
        assert metrics[0].duration > 0

    @pytest.mark.asyncio
    async def test_submit_order_records_error_metrics(self, client, metrics_store):
        """Test that failed submit_order records error metrics."""
        import aiohttp

        signed_order = {"sellToken": "0x1", "buyToken": "0x2"}

        mock_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=400,
            message="Bad request",
        )

        with patch.object(
            client._client, "submit_order", new_callable=AsyncMock
        ) as mock_submit:
            mock_submit.side_effect = mock_error

            with pytest.raises(aiohttp.ClientResponseError):
                await client.submit_order(signed_order)

        metrics = metrics_store.get_api_metrics("/api/v1/orders")
        assert len(metrics) == 1
        assert metrics[0].status_code == 400
        assert metrics[0].error_message is not None

    @pytest.mark.asyncio
    async def test_get_order_records_metrics(self, client, metrics_store):
        """Test that get_order records API metrics."""
        order_uid = "0x1234"
        mock_response = {"uid": order_uid, "status": "open"}

        with patch.object(
            client._client, "get_order", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_order(order_uid)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics(f"/api/v1/orders/{order_uid}")
        assert len(metrics) == 1
        assert metrics[0].method == "GET"
        assert metrics[0].status_code == 200

    @pytest.mark.asyncio
    async def test_get_trades_records_metrics(self, client, metrics_store):
        """Test that get_trades records API metrics."""
        order_uid = "0x1234"
        mock_response = [{"txHash": "0xabc"}]

        with patch.object(
            client._client, "get_trades", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_trades(order_uid)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics(f"/api/v1/orders/{order_uid}/trades")
        assert len(metrics) == 1
        assert metrics[0].method == "GET"

    @pytest.mark.asyncio
    async def test_check_health_does_not_record_metrics(self, client, metrics_store):
        """Test that check_health does NOT record metrics."""
        with patch.object(
            client._client, "check_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True
            result = await client.check_health()

        assert result is True
        # No metrics should be recorded for health checks
        assert len(metrics_store.get_api_metrics()) == 0

    @pytest.mark.asyncio
    async def test_timing_precision(self, client, metrics_store):
        """Test that timing uses perf_counter for precision."""
        import asyncio

        order_uid = "0x1234"
        mock_response = {"uid": order_uid, "status": "open"}

        async def slow_response():
            await asyncio.sleep(0.1)  # 100ms delay
            return mock_response

        with patch.object(
            client._client, "get_order", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = slow_response
            await client.get_order(order_uid)

        metrics = metrics_store.get_api_metrics()
        assert len(metrics) == 1
        # Should be at least 100ms
        assert metrics[0].duration >= 0.1
        # But not unreasonably long
        assert metrics[0].duration < 0.5
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_instrumented_client.py -v` passes
- [x] `poetry run ruff check src/cow_performance/api/instrumented_client.py`
- [x] `poetry run mypy src/cow_performance/api/instrumented_client.py`
- [x] Import works: `from cow_performance.api import InstrumentedOrderbookClient`

#### Manual Verification

- [x] All `OrderbookClient` methods are wrapped
- [x] Metrics include correct endpoint paths
- [x] Timing precision is acceptable (sub-millisecond)

### Commit

After Phase 1, create a commit:
```
feat(api): add InstrumentedOrderbookClient for API timing metrics

Add HTTP client wrapper that records timing metrics for all API calls:
- Wraps OrderbookClient methods with timing instrumentation
- Records APIMetrics to MetricsStore for each request
- Uses time.perf_counter() for high-precision timing
- Health checks excluded from metrics to reduce noise

Part of COW-610: Collection - Lifecycle, API & Resource Monitoring
```

---

## Phase 2: Order Lifecycle Tracking

### Overview

Enhance `OrderTracker` to implement real API polling and proper status mapping. Replace the mock implementation with actual API calls.

### Changes Required

#### 1. Add status mapping utility

**File**: `src/cow_performance/load_generation/status_mapping.py`

```python
"""
Status mapping utilities for CoW Protocol order states.

Maps between CoW API status strings and internal OrderStatus enum values.
"""

from cow_performance.metrics import OrderStatus


# CoW API status values (from OpenAPI spec)
# https://api.cow.fi/docs/#/default/get_api_v1_orders__UID_
COW_API_STATUS_MAPPING: dict[str, OrderStatus] = {
    "presignaturePending": OrderStatus.SUBMITTED,
    "open": OrderStatus.OPEN,
    "fulfilled": OrderStatus.FILLED,
    "cancelled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
}


def map_api_status_to_order_status(api_status: str) -> OrderStatus:
    """
    Map CoW API status string to OrderStatus enum.

    Args:
        api_status: Status string from CoW API response

    Returns:
        Corresponding OrderStatus enum value

    Raises:
        ValueError: If the API status is unknown
    """
    status = COW_API_STATUS_MAPPING.get(api_status)
    if status is None:
        raise ValueError(f"Unknown API status: {api_status}")
    return status


def is_api_status_terminal(api_status: str) -> bool:
    """
    Check if an API status represents a terminal state.

    Args:
        api_status: Status string from CoW API response

    Returns:
        True if the status is terminal (no more updates expected)
    """
    terminal_statuses = {"fulfilled", "cancelled", "expired"}
    return api_status in terminal_statuses
```

#### 2. Update OrderTracker with real API polling

**File**: `src/cow_performance/load_generation/order_tracker.py`

Replace the `poll_order_status` method and add MetricsStore integration:

```python
"""
Order tracking and lifecycle monitoring for CoW Protocol orders.

This module provides functionality to track order states, monitor lifecycle
transitions, and calculate order metrics for performance analysis.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from cow_performance.metrics import MetricsStore, OrderMetadata, OrderMetrics, OrderStatus

from .status_mapping import is_api_status_terminal, map_api_status_to_order_status

if TYPE_CHECKING:
    from cow_performance.api import InstrumentedOrderbookClient

logger = logging.getLogger(__name__)


class OrderTracker:
    """
    Tracks order lifecycle and monitors status changes.

    This class maintains order metadata, polls order status from the API,
    and calculates performance metrics for load testing analysis.
    """

    def __init__(
        self,
        poll_interval: float = 5.0,
        max_poll_attempts: int = 60,
        metrics_store: MetricsStore | None = None,
    ):
        """
        Initialize the order tracker.

        Args:
            poll_interval: Seconds between status polls (default 5.0)
            max_poll_attempts: Maximum number of poll attempts before giving up (default 60)
            metrics_store: Optional MetricsStore for persisting order metrics
        """
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts
        self._metrics_store = metrics_store
        self._orders: dict[str, OrderMetadata] = {}
        self._polling_tasks: dict[str, asyncio.Task[OrderMetadata]] = {}

    def track_order(
        self,
        order_uid: str,
        owner: str,
        sell_token: str = "",
        buy_token: str = "",
        sell_amount: str = "0",
        buy_amount: str = "0",
    ) -> OrderMetadata:
        """
        Start tracking a new order.

        Args:
            order_uid: Unique identifier for the order
            owner: Address of the order owner
            sell_token: Address of sell token
            buy_token: Address of buy token
            sell_amount: Amount being sold
            buy_amount: Amount being bought

        Returns:
            The OrderMetadata instance for this order
        """
        metadata = OrderMetadata(
            order_uid=order_uid,
            owner=owner,
            creation_time=time.time(),
            sell_token=sell_token,
            buy_token=buy_token,
            sell_amount=sell_amount,
            buy_amount=buy_amount,
        )
        self._orders[order_uid] = metadata

        # Also add to MetricsStore if available
        if self._metrics_store is not None:
            # Note: We don't acquire lock here as this is typically called
            # from a single context. Lock will be acquired on updates.
            self._metrics_store.add_order(metadata)

        return metadata

    def get_order(self, order_uid: str) -> OrderMetadata | None:
        """
        Get metadata for a tracked order.

        Args:
            order_uid: The order UID to retrieve

        Returns:
            OrderMetadata if found, None otherwise
        """
        return self._orders.get(order_uid)

    def get_all_orders(self) -> list[OrderMetadata]:
        """
        Get all tracked orders.

        Returns:
            List of all OrderMetadata instances
        """
        return list(self._orders.values())

    def update_order_status(
        self,
        order_uid: str,
        new_status: OrderStatus,
        filled_amount: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Update the status of a tracked order.

        Args:
            order_uid: The order UID to update
            new_status: The new status
            filled_amount: Optional filled amount for partial/full fills
            error_message: Optional error message for failed orders
        """
        if order_uid not in self._orders:
            return

        metadata = self._orders[order_uid]
        metadata.update_status(new_status)

        if filled_amount is not None:
            metadata.filled_amount = filled_amount
        if error_message is not None:
            metadata.error_message = error_message

    async def poll_order_status(
        self,
        order_uid: str,
        api_client: "InstrumentedOrderbookClient | Any",
    ) -> OrderStatus:
        """
        Poll order status from the orderbook API.

        Fetches current order state from the API and updates internal tracking.

        Args:
            order_uid: The order UID to poll
            api_client: The API client to use for polling (InstrumentedOrderbookClient)

        Returns:
            The current order status
        """
        metadata = self.get_order(order_uid)
        if metadata is None:
            return OrderStatus.FAILED

        try:
            # Call the real API
            response = await api_client.get_order(order_uid)

            # Extract status from response
            api_status = response.get("status", "")

            # Map to our enum
            new_status = map_api_status_to_order_status(api_status)

            # Extract filled amount if available
            filled_amount = response.get("executedSellAmount")

            # Update our tracking
            self.update_order_status(
                order_uid,
                new_status,
                filled_amount=filled_amount,
            )

            logger.debug(
                f"Order {order_uid[:10]}... status: {api_status} -> {new_status.value}"
            )

            return new_status

        except ValueError as e:
            # Unknown status - log but don't fail
            logger.warning(f"Unknown status for order {order_uid}: {e}")
            return metadata.current_status

        except Exception as e:
            # API error - log and return current status
            logger.warning(f"Failed to poll order {order_uid}: {e}")
            return metadata.current_status

    async def monitor_order(
        self,
        order_uid: str,
        api_client: "InstrumentedOrderbookClient | Any | None" = None,
    ) -> OrderMetadata:
        """
        Monitor an order until it reaches a terminal state.

        Polls the order status at regular intervals and updates metadata
        until the order is filled, expired, cancelled, or failed.

        Args:
            order_uid: The order UID to monitor
            api_client: Optional API client for polling (required for real monitoring)

        Returns:
            The final OrderMetadata
        """
        attempts = 0

        while attempts < self.max_poll_attempts:
            metadata = self.get_order(order_uid)
            if metadata is None:
                break

            if metadata.is_terminal_state():
                logger.debug(f"Order {order_uid[:10]}... reached terminal state: {metadata.current_status.value}")
                break

            # Poll status if we have an API client
            if api_client is not None:
                await self.poll_order_status(order_uid, api_client)

            await asyncio.sleep(self.poll_interval)
            attempts += 1

        # If we hit max attempts, mark as failed
        metadata = self.get_order(order_uid)
        if metadata and not metadata.is_terminal_state():
            logger.warning(f"Order {order_uid[:10]}... timed out after {attempts} poll attempts")
            self.update_order_status(
                order_uid,
                OrderStatus.FAILED,
                error_message="Max poll attempts exceeded",
            )

        return metadata or OrderMetadata(
            order_uid=order_uid,
            owner="",
            creation_time=time.time(),
        )

    def start_monitoring(
        self, order_uid: str, api_client: "InstrumentedOrderbookClient | Any | None" = None
    ) -> asyncio.Task[OrderMetadata]:
        """
        Start monitoring an order in the background.

        Args:
            order_uid: The order UID to monitor
            api_client: Optional API client for polling

        Returns:
            The asyncio Task for monitoring
        """
        task = asyncio.create_task(self.monitor_order(order_uid, api_client))
        self._polling_tasks[order_uid] = task
        return task

    async def stop_monitoring(self, order_uid: str) -> None:
        """
        Stop monitoring an order.

        Args:
            order_uid: The order UID to stop monitoring
        """
        if order_uid in self._polling_tasks:
            task = self._polling_tasks[order_uid]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._polling_tasks[order_uid]

    async def stop_all_monitoring(self) -> None:
        """Stop monitoring all orders."""
        for order_uid in list(self._polling_tasks.keys()):
            await self.stop_monitoring(order_uid)

    def get_metrics(self) -> OrderMetrics:
        """
        Calculate aggregated metrics for all tracked orders.

        Returns:
            OrderMetrics with summary statistics
        """
        orders = self.get_all_orders()
        metrics = OrderMetrics(total_orders=len(orders))

        if not orders:
            return metrics

        # Count orders by status
        for order in orders:
            status = order.current_status
            if status == OrderStatus.CREATED:
                metrics.orders_created += 1
            elif status == OrderStatus.SUBMITTED:
                metrics.orders_submitted += 1
            elif status in (OrderStatus.ACCEPTED, OrderStatus.OPEN):
                metrics.orders_accepted += 1
            elif status == OrderStatus.FILLED:
                metrics.orders_filled += 1
            elif status == OrderStatus.PARTIALLY_FILLED:
                metrics.orders_partially_filled += 1
            elif status == OrderStatus.EXPIRED:
                metrics.orders_expired += 1
            elif status == OrderStatus.CANCELLED:
                metrics.orders_cancelled += 1
            elif status == OrderStatus.FAILED:
                metrics.orders_failed += 1

        # Calculate average times
        times_to_submit = [t for order in orders if (t := order.get_time_to_submit()) is not None]
        times_to_accept = [t for order in orders if (t := order.get_time_to_accept()) is not None]
        times_to_fill = [t for order in orders if (t := order.get_time_to_fill()) is not None]
        total_lifecycle_times = [
            t for order in orders if (t := order.get_total_lifecycle_time()) is not None
        ]

        if times_to_submit:
            metrics.avg_time_to_submit = sum(times_to_submit) / len(times_to_submit)
        if times_to_accept:
            metrics.avg_time_to_accept = sum(times_to_accept) / len(times_to_accept)
        if times_to_fill:
            metrics.avg_time_to_fill = sum(times_to_fill) / len(times_to_fill)
        if total_lifecycle_times:
            metrics.avg_total_lifecycle_time = sum(total_lifecycle_times) / len(
                total_lifecycle_times
            )

        return metrics
```

#### 3. Update load_generation module exports

**File**: `src/cow_performance/load_generation/__init__.py`

Add new exports:
```python
from cow_performance.load_generation.status_mapping import (
    map_api_status_to_order_status,
    is_api_status_terminal,
    COW_API_STATUS_MAPPING,
)
```

#### 4. Create unit tests

**File**: `tests/unit/test_order_lifecycle.py`

```python
"""Unit tests for order lifecycle tracking and status mapping."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

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
        """Test monitoring times out and marks as failed."""
        order_uid = "0x1234"
        tracker.track_order(order_uid, owner="0xowner")
        tracker.update_order_status(order_uid, OrderStatus.SUBMITTED)

        mock_client = AsyncMock()
        mock_client.get_order.return_value = {"uid": order_uid, "status": "open"}

        metadata = await tracker.monitor_order(order_uid, mock_client)

        assert metadata.current_status == OrderStatus.FAILED
        assert metadata.error_message == "Max poll attempts exceeded"

    def test_track_order_adds_to_store(self, tracker_with_store):
        """Test that tracking adds order to MetricsStore."""
        tracker, store = tracker_with_store
        order_uid = "0x1234"

        tracker.track_order(order_uid, owner="0xowner")

        stored_order = store.get_order(order_uid)
        assert stored_order is not None
        assert stored_order.order_uid == order_uid
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_order_lifecycle.py -v` passes
- [x] `poetry run ruff check src/cow_performance/load_generation/`
- [x] `poetry run mypy src/cow_performance/load_generation/`
- [x] Existing tests pass: `poetry run pytest tests/unit/test_order_tracker.py -v`

#### Manual Verification

- [x] Status mapping covers all CoW API statuses
- [x] API errors are handled gracefully (no crashes)
- [x] Terminal states correctly stop monitoring

### Commit

After Phase 2, create a commit:
```
feat(tracking): implement real API polling in OrderTracker

Replace mock implementation with actual orderbook API polling:
- Add status_mapping.py for CoW API status -> OrderStatus conversion
- Implement poll_order_status() with real API calls
- Add MetricsStore integration for order persistence
- Add logging for status transitions and errors

Supports status values: open, fulfilled, cancelled, expired, presignaturePending

Part of COW-610: Collection - Lifecycle, API & Resource Monitoring
```

---

## Phase 3: ResourceMonitor with Docker SDK

### Overview

Implement `ResourceMonitor` class that collects container stats from Docker and stores them in `MetricsStore`.

### Changes Required

#### 1. Create ResourceMonitor module

**File**: `src/cow_performance/monitoring/__init__.py`

```python
"""
Resource monitoring for CoW Protocol performance testing.

Provides Docker container monitoring and resource utilization tracking.
"""

from cow_performance.monitoring.resource_monitor import (
    ResourceMonitor,
    ResourceMonitorConfig,
)

__all__ = [
    "ResourceMonitor",
    "ResourceMonitorConfig",
]
```

**File**: `src/cow_performance/monitoring/resource_monitor.py`

```python
"""
Docker container resource monitoring.

Collects CPU, memory, network, and I/O metrics from Docker containers
for performance analysis during load testing.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

import docker
from docker.errors import NotFound as ContainerNotFound
from docker.models.containers import Container

from cow_performance.metrics import MetricsStore, ResourceSample

logger = logging.getLogger(__name__)


# Default CoW Protocol services to monitor
DEFAULT_SERVICE_PATTERNS = [
    "orderbook",
    "autopilot",
    "driver",
    "baseline",
    "chain",
]


@dataclass
class ResourceMonitorConfig:
    """Configuration for ResourceMonitor."""

    # Service name patterns to match containers
    service_patterns: list[str] = field(default_factory=lambda: DEFAULT_SERVICE_PATTERNS.copy())

    # Sampling interval in seconds
    sample_interval: float = 5.0

    # Docker socket URL (None for default)
    docker_url: str | None = None


class ResourceMonitor:
    """
    Monitors Docker container resource utilization.

    Collects CPU, memory, network I/O, and block I/O metrics from containers
    matching configured service patterns and stores them in MetricsStore.

    Example:
        store = MetricsStore()
        monitor = ResourceMonitor(store)
        await monitor.start()
        # ... run tests ...
        await monitor.stop()
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        config: ResourceMonitorConfig | None = None,
    ):
        """
        Initialize the resource monitor.

        Args:
            metrics_store: Store for recording resource metrics
            config: Optional configuration (uses defaults if not provided)
        """
        self._metrics_store = metrics_store
        self._config = config or ResourceMonitorConfig()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._docker_client: docker.DockerClient | None = None
        self._containers: dict[str, Container] = {}

    def _get_docker_client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._docker_client is None:
            if self._config.docker_url:
                self._docker_client = docker.DockerClient(base_url=self._config.docker_url)
            else:
                self._docker_client = docker.from_env()
        return self._docker_client

    def _discover_containers(self) -> dict[str, Container]:
        """
        Discover containers matching service patterns.

        Returns:
            Dict mapping container names to Container objects
        """
        client = self._get_docker_client()
        containers: dict[str, Container] = {}

        for container in client.containers.list():
            name = container.name
            # Check if container name matches any service pattern
            for pattern in self._config.service_patterns:
                if pattern in name:
                    containers[name] = container
                    logger.debug(f"Discovered container: {name} (matched pattern: {pattern})")
                    break

        return containers

    def _calculate_cpu_percent(self, stats: dict) -> float:
        """
        Calculate CPU percentage from Docker stats.

        Uses the same formula as `docker stats` command.

        Args:
            stats: Docker container stats dict

        Returns:
            CPU usage percentage (0-100+, can exceed 100% with multiple cores)
        """
        try:
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            # Get CPU deltas
            cpu_delta = (
                cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            )
            system_delta = (
                cpu_stats.get("system_cpu_usage", 0)
                - precpu_stats.get("system_cpu_usage", 0)
            )

            if system_delta > 0 and cpu_delta > 0:
                # Number of CPUs
                num_cpus = cpu_stats.get("online_cpus", 1)
                if num_cpus == 0:
                    num_cpus = len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [1]))

                return (cpu_delta / system_delta) * num_cpus * 100.0

            return 0.0
        except (KeyError, TypeError, ZeroDivisionError):
            return 0.0

    def _extract_network_stats(self, stats: dict) -> tuple[int, int]:
        """
        Extract network I/O from Docker stats.

        Args:
            stats: Docker container stats dict

        Returns:
            Tuple of (rx_bytes, tx_bytes)
        """
        try:
            networks = stats.get("networks", {})
            rx_bytes = 0
            tx_bytes = 0

            for _, network_stats in networks.items():
                rx_bytes += network_stats.get("rx_bytes", 0)
                tx_bytes += network_stats.get("tx_bytes", 0)

            return rx_bytes, tx_bytes
        except (KeyError, TypeError):
            return 0, 0

    def _extract_block_io_stats(self, stats: dict) -> tuple[int, int]:
        """
        Extract block I/O from Docker stats.

        Args:
            stats: Docker container stats dict

        Returns:
            Tuple of (read_bytes, write_bytes)
        """
        try:
            blkio_stats = stats.get("blkio_stats", {})
            io_service_bytes = blkio_stats.get("io_service_bytes_recursive", []) or []

            read_bytes = 0
            write_bytes = 0

            for entry in io_service_bytes:
                op = entry.get("op", "").lower()
                value = entry.get("value", 0)
                if op == "read":
                    read_bytes += value
                elif op == "write":
                    write_bytes += value

            return read_bytes, write_bytes
        except (KeyError, TypeError):
            return 0, 0

    async def _collect_sample(self, container_name: str, container: Container) -> ResourceSample | None:
        """
        Collect a single resource sample from a container.

        Args:
            container_name: Name of the container
            container: Docker Container object

        Returns:
            ResourceSample if successful, None if collection failed
        """
        try:
            # Get stats (non-streaming for single snapshot)
            stats = container.stats(stream=False)

            # Extract metrics
            cpu_percent = self._calculate_cpu_percent(stats)

            memory_stats = stats.get("memory_stats", {})
            memory_bytes = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 0)

            rx_bytes, tx_bytes = self._extract_network_stats(stats)
            read_bytes, write_bytes = self._extract_block_io_stats(stats)

            return ResourceSample(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_bytes=memory_bytes,
                memory_limit_bytes=memory_limit,
                network_rx_bytes=rx_bytes,
                network_tx_bytes=tx_bytes,
                block_read_bytes=read_bytes,
                block_write_bytes=write_bytes,
            )
        except ContainerNotFound:
            logger.warning(f"Container {container_name} not found, removing from monitoring")
            return None
        except Exception as e:
            logger.warning(f"Failed to collect stats from {container_name}: {e}")
            return None

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that collects samples at configured intervals."""
        logger.info(
            f"Starting resource monitoring with {len(self._containers)} containers, "
            f"interval={self._config.sample_interval}s"
        )

        while self._running:
            # Refresh container list periodically (containers may restart)
            self._containers = self._discover_containers()

            # Collect samples from all containers
            for container_name, container in list(self._containers.items()):
                sample = await self._collect_sample(container_name, container)

                if sample is not None:
                    async with self._metrics_store.lock:
                        self._metrics_store.add_resource_sample(container_name, sample)
                else:
                    # Remove container from monitoring if collection failed
                    self._containers.pop(container_name, None)

            # Wait for next sample interval
            await asyncio.sleep(self._config.sample_interval)

    async def start(self) -> None:
        """
        Start the resource monitor.

        Discovers containers and begins collecting samples in the background.
        """
        if self._running:
            logger.warning("ResourceMonitor is already running")
            return

        # Discover containers
        self._containers = self._discover_containers()
        logger.info(f"Discovered {len(self._containers)} containers to monitor: {list(self._containers.keys())}")

        if not self._containers:
            logger.warning(
                f"No containers found matching patterns: {self._config.service_patterns}. "
                "Resource monitoring will be disabled."
            )
            return

        # Start monitoring loop
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop the resource monitor gracefully."""
        if not self._running:
            return

        logger.info("Stopping resource monitor...")
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        # Clean up Docker client
        if self._docker_client:
            self._docker_client.close()
            self._docker_client = None

        self._containers.clear()
        logger.info("Resource monitor stopped")

    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._running

    def get_monitored_containers(self) -> list[str]:
        """Get list of currently monitored container names."""
        return list(self._containers.keys())
```

#### 2. Create unit tests

**File**: `tests/unit/test_resource_monitor.py`

```python
"""Unit tests for ResourceMonitor."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from cow_performance.metrics import MetricsStore
from cow_performance.monitoring.resource_monitor import (
    DEFAULT_SERVICE_PATTERNS,
    ResourceMonitor,
    ResourceMonitorConfig,
)


class TestResourceMonitorConfig:
    """Tests for ResourceMonitorConfig."""

    def test_default_service_patterns(self):
        """Test default service patterns."""
        config = ResourceMonitorConfig()
        assert "orderbook" in config.service_patterns
        assert "autopilot" in config.service_patterns
        assert "driver" in config.service_patterns
        assert "baseline" in config.service_patterns
        assert "chain" in config.service_patterns

    def test_custom_patterns(self):
        """Test custom service patterns."""
        config = ResourceMonitorConfig(service_patterns=["custom-service"])
        assert config.service_patterns == ["custom-service"]

    def test_default_sample_interval(self):
        """Test default sample interval."""
        config = ResourceMonitorConfig()
        assert config.sample_interval == 5.0


class TestResourceMonitor:
    """Tests for ResourceMonitor."""

    @pytest.fixture
    def metrics_store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def monitor(self, metrics_store):
        """Create a resource monitor fixture."""
        return ResourceMonitor(metrics_store)

    def test_calculate_cpu_percent(self, monitor):
        """Test CPU percentage calculation."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 10000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 900000000},
                "system_cpu_usage": 9000000000,
            },
        }

        cpu_percent = monitor._calculate_cpu_percent(stats)
        # (100M / 1000M) * 4 * 100 = 40%
        assert cpu_percent == pytest.approx(40.0, rel=0.1)

    def test_calculate_cpu_percent_no_delta(self, monitor):
        """Test CPU calculation with no delta."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000},
                "system_cpu_usage": 1000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000},
                "system_cpu_usage": 1000,
            },
        }

        cpu_percent = monitor._calculate_cpu_percent(stats)
        assert cpu_percent == 0.0

    def test_extract_network_stats(self, monitor):
        """Test network stats extraction."""
        stats = {
            "networks": {
                "eth0": {"rx_bytes": 1000, "tx_bytes": 500},
                "eth1": {"rx_bytes": 200, "tx_bytes": 100},
            }
        }

        rx, tx = monitor._extract_network_stats(stats)
        assert rx == 1200
        assert tx == 600

    def test_extract_network_stats_empty(self, monitor):
        """Test network stats with no networks."""
        stats = {"networks": {}}
        rx, tx = monitor._extract_network_stats(stats)
        assert rx == 0
        assert tx == 0

    def test_extract_block_io_stats(self, monitor):
        """Test block I/O stats extraction."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1000},
                    {"op": "Write", "value": 500},
                    {"op": "Read", "value": 200},
                ]
            }
        }

        read, write = monitor._extract_block_io_stats(stats)
        assert read == 1200
        assert write == 500

    def test_extract_block_io_stats_empty(self, monitor):
        """Test block I/O stats with no data."""
        stats = {"blkio_stats": {}}
        read, write = monitor._extract_block_io_stats(stats)
        assert read == 0
        assert write == 0

    def test_is_running_initially_false(self, monitor):
        """Test monitor is not running initially."""
        assert monitor.is_running() is False

    def test_get_monitored_containers_empty(self, monitor):
        """Test empty container list initially."""
        assert monitor.get_monitored_containers() == []


class TestResourceMonitorIntegration:
    """Integration tests for ResourceMonitor with mocked Docker."""

    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client."""
        mock_client = MagicMock()

        # Create mock containers
        mock_container = MagicMock()
        mock_container.name = "cow-perf-orderbook-1"
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 10000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 900000000},
                "system_cpu_usage": 9000000000,
            },
            "memory_stats": {
                "usage": 100000000,
                "limit": 1000000000,
            },
            "networks": {
                "eth0": {"rx_bytes": 1000, "tx_bytes": 500},
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1000},
                    {"op": "Write", "value": 500},
                ]
            },
        }

        mock_client.containers.list.return_value = [mock_container]

        return mock_client

    @pytest.mark.asyncio
    async def test_discover_containers(self, mock_docker_client):
        """Test container discovery."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            containers = monitor._discover_containers()

        assert len(containers) == 1
        assert "cow-perf-orderbook-1" in containers

    @pytest.mark.asyncio
    async def test_collect_sample(self, mock_docker_client):
        """Test sample collection from container."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        mock_container = mock_docker_client.containers.list()[0]

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            sample = await monitor._collect_sample("orderbook", mock_container)

        assert sample is not None
        assert sample.cpu_percent > 0
        assert sample.memory_bytes == 100000000
        assert sample.memory_limit_bytes == 1000000000
        assert sample.network_rx_bytes == 1000
        assert sample.network_tx_bytes == 500

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_docker_client):
        """Test start and stop lifecycle."""
        store = MetricsStore()
        config = ResourceMonitorConfig(sample_interval=0.1)
        monitor = ResourceMonitor(store, config)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            await monitor.start()
            assert monitor.is_running() is True

            # Let it collect a few samples
            await asyncio.sleep(0.25)

            await monitor.stop()
            assert monitor.is_running() is False

        # Should have collected samples
        metrics = store.get_resource_metrics()
        assert len(metrics) > 0

    @pytest.mark.asyncio
    async def test_no_containers_found(self):
        """Test behavior when no containers match patterns."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        mock_client = MagicMock()
        mock_client.containers.list.return_value = []

        with patch.object(monitor, "_get_docker_client", return_value=mock_client):
            await monitor.start()

        # Should not be running if no containers found
        assert monitor.is_running() is False
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_resource_monitor.py -v` passes
- [x] `poetry run ruff check src/cow_performance/monitoring/`
- [x] `poetry run mypy src/cow_performance/monitoring/`
- [x] Import works: `from cow_performance.monitoring import ResourceMonitor`

#### Manual Verification

- [x] With Docker running, monitor discovers CoW Protocol containers
- [x] CPU percentage calculation matches `docker stats` output
- [x] Samples are stored in MetricsStore correctly

### Commit

After Phase 3, create a commit:
```
feat(monitoring): add ResourceMonitor for Docker container stats

Implement Docker container resource monitoring:
- ResourceMonitor class with configurable service patterns
- CPU, memory, network I/O, and block I/O collection
- Service pattern matching for container discovery
- Background sampling at configurable intervals
- Integration with MetricsStore for persistence

Default monitoring: orderbook, autopilot, driver, baseline, chain

Part of COW-610: Collection - Lifecycle, API & Resource Monitoring
```

---

## Phase 4: Integration and Testing

### Overview

Integrate all components with the existing CLI and load generation system. Update `run.py` to use instrumented client and resource monitoring.

### Changes Required

#### 1. Update CLI run command

**File**: `src/cow_performance/cli/commands/run.py`

Update the `run_performance_test()` function to use new components:

```python
# Add imports at top
from cow_performance.api import InstrumentedOrderbookClient
from cow_performance.metrics import MetricsStore
from cow_performance.monitoring import ResourceMonitor, ResourceMonitorConfig

# In run_performance_test(), after config loading:

# Create shared metrics store
metrics_store = MetricsStore()

# Create order tracker with metrics store
order_tracker = OrderTracker(
    poll_interval=5.0,
    max_poll_attempts=12,
    metrics_store=metrics_store,
)

# Create API client (instrumented if not dry-run)
api_client = None
if not dry_run:
    api_client = InstrumentedOrderbookClient(
        base_url=config.api.base_url,
        metrics_store=metrics_store,
        timeout=config.api.timeout,
        max_retries=config.api.max_retries,
    )

# Create resource monitor (only if not dry-run)
resource_monitor = None
if not dry_run:
    resource_config = ResourceMonitorConfig(
        service_patterns=["orderbook", "autopilot", "driver", "baseline", "chain"],
        sample_interval=5.0,
    )
    resource_monitor = ResourceMonitor(metrics_store, resource_config)

# Start resource monitoring before test
if resource_monitor:
    await resource_monitor.start()

try:
    # ... existing test execution code ...
    pass
finally:
    # Stop resource monitoring after test
    if resource_monitor:
        await resource_monitor.stop()

    # Export metrics at end
    from cow_performance.metrics import save_metrics_to_file
    output_path = Path(f"test-results/perf-test-{test_id}.json")
    save_metrics_to_file(metrics_store, output_path, format="json")
```

#### 2. Create integration test

**File**: `tests/integration/test_metrics_collection.py`

```python
"""Integration tests for metrics collection pipeline."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

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
        filled = [o for o in order_tracker.get_all_orders() if o.current_status == OrderStatus.FILLED]
        assert len(filled) == num_orders
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/integration/test_metrics_collection.py -v` passes
- [x] `poetry run pytest tests/unit/ -v` passes (all existing tests)
- [x] `poetry run ruff check src/`
- [x] `poetry run mypy src/`
- [x] `poetry run black --check src/`

#### Manual Verification

- [ ] Run `poetry run cow-perf run --scenario configs/scenarios/test-funded-scenario.yml`
- [ ] Verify API metrics are captured in output
- [ ] Verify order lifecycle metrics show timing data
- [ ] If Docker is running, verify resource metrics are captured

#### CLI Integration (Basic Wiring)

- [x] Create shared MetricsStore in run.py
- [x] Use InstrumentedOrderbookClient when dry_run=False
- [x] Pass metrics_store to OrderTracker
- [x] Start/stop ResourceMonitor around test execution
- [x] Add metrics_store.summary() to returned metrics

### Commit

After Phase 4, create a commit:
```
feat: integrate metrics collection into CLI and load testing

Wire up all metrics collection components:
- Use InstrumentedOrderbookClient in run command
- Add MetricsStore to OrderTracker for persistence
- Start/stop ResourceMonitor around test execution
- Export metrics to JSON after test completion

This completes COW-610: Collection - Lifecycle, API & Resource Monitoring
```

---

## Testing Strategy

### Unit Tests

Located in `tests/unit/`:
- `test_instrumented_client.py`: API timing instrumentation
- `test_order_lifecycle.py`: Status mapping and polling
- `test_resource_monitor.py`: Docker stats collection

### Integration Tests

Located in `tests/integration/`:
- `test_metrics_collection.py`: End-to-end pipeline

### Manual Testing Steps

1. Start Docker services: `docker compose up -d`
2. Run performance test: `poetry run cow-perf run --dry-run`
3. Verify output in `test-results/` directory
4. Check metrics JSON for API timing, order lifecycle, and resource data

---

## References

- Original ticket: `thoughts/tickets/COW-610-collection-lifecycle-api-monitoring.md`
- Parent ticket: `thoughts/tickets/COW-587-metrics-collection-framework.md`
- Foundation plan: `thoughts/plans/2026-01-28-cow-609-foundation-data-models-storage.md`
- COW API spec: https://api.cow.fi/docs/
- Docker SDK docs: https://docker-py.readthedocs.io/
