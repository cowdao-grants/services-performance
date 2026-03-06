"""
Instrumented HTTP client wrapper for API timing metrics.

Wraps OrderbookClient to capture request timing, status codes, and payload sizes
for performance analysis.
"""

import asyncio
import json
import time
from typing import Any

import aiohttp

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
        endpoint = f"/api/v1/app_data/{app_data_hash}"
        method = "PUT"
        payload_size = len(
            json.dumps(app_data_doc) if isinstance(app_data_doc, dict) else app_data_doc
        )
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

    async def upload_app_data_with_retry(
        self,
        app_data_hash: str,
        app_data_doc: str | dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Upload appData with automatic retry on failure (instrumented).

        Args:
            app_data_hash: 32-byte hash of appData document
            app_data_doc: Full appData JSON document
            max_retries: Maximum retry attempts

        Returns:
            Response from orderbook
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return await self.upload_app_data(app_data_hash, app_data_doc)
            except aiohttp.ClientResponseError as e:
                last_error = e
                if e.status == 409:
                    return {}
                if e.status not in (500, 502, 503, 504):
                    raise
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    print(
                        f"AppData upload failed (attempt {attempt + 1}), "
                        f"retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
        if last_error:
            raise last_error
        return {}

    async def get_version(self) -> dict[str, Any]:
        """
        Get API version with timing instrumentation.

        Returns:
            Version information from the orderbook API
        """
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

    async def get_open_order_count(self, owner: str) -> int:
        """Get count of open orders for an account (delegates to underlying client)."""
        return await self._client.get_open_order_count(owner)

    async def check_health(self) -> bool:
        """
        Check if the orderbook API is healthy.

        Note: This method does NOT record metrics to avoid noise from health checks.

        Returns:
            True if the API is healthy, False otherwise
        """
        return await self._client.check_health()
