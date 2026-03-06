"""HTTP client for CoW Protocol Orderbook API.

This module provides an async client for interacting with the CoW Protocol
orderbook API, supporting order submission, status queries, and appData uploads.
"""

import json
from typing import Any

import aiohttp


class OrderbookClient:
    """Async client for CoW Protocol Orderbook API.

    Provides methods for submitting orders, querying order status, and uploading
    appData documents to the orderbook service.
    """

    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        """Initialize the orderbook client.

        Args:
            base_url: Base URL of the orderbook API (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries

    async def submit_order(self, signed_order: dict[str, Any]) -> dict[str, Any]:
        """Submit a signed order to the orderbook.

        Args:
            signed_order: Complete signed order with all required fields

        Returns:
            Response from the orderbook containing order UID and status

        Raises:
            aiohttp.ClientError: If the request fails
            aiohttp.ClientResponseError: If the server returns an error status
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/v1/orders",
                json=signed_order,
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Order submission failed: {error_text}",
                        headers=response.headers,
                    )
                result: dict[str, Any] = await response.json()
                return result

    async def get_order(self, order_uid: str) -> dict[str, Any]:
        """Get order details by UID.

        Args:
            order_uid: The unique order identifier

        Returns:
            Order details including status, amounts, and metadata

        Raises:
            aiohttp.ClientError: If the request fails
            aiohttp.ClientResponseError: If the order is not found or server error
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.base_url}/api/v1/orders/{order_uid}",
            ) as response:
                response.raise_for_status()
                result: dict[str, Any] = await response.json()
                return result

    async def get_quote(
        self,
        sell_token: str,
        buy_token: str,
        sell_amount: str,
        from_address: str,
        kind: str = "sell",
        app_data: str | None = None,
    ) -> dict[str, Any]:
        """Get a quote for an order with realistic pricing and surplus.

        The quote includes market price with slippage/surplus to ensure
        orders are profitable for solvers.

        Args:
            sell_token: Address of token to sell
            buy_token: Address of token to buy
            sell_amount: Amount to sell in wei (as string)
            from_address: Trader address
            kind: Order kind ("sell" or "buy")
            app_data: Optional appData hash to include in quote request

        Returns:
            Quote response with buyAmount, feeAmount, etc.

        Raises:
            aiohttp.ClientError: If request fails
        """
        quote_request = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmountBeforeFee": sell_amount,
            "from": from_address,
            "kind": kind,
            "priceQuality": "optimal",  # Get best available price
        }

        # Include appData if provided - ensures quote matches order parameters
        if app_data:
            quote_request["appData"] = app_data

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/v1/quote",
                json=quote_request,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise aiohttp.ClientError(
                        f"Quote request failed: {response.status}, message='{error_text}'"
                    )
                result: dict[str, Any] = await response.json()
                return result

    async def get_trades(self, order_uid: str) -> list[dict[str, Any]]:
        """Get trades for an order.

        Args:
            order_uid: The unique order identifier

        Returns:
            List of trades associated with the order. Empty list if no trades found.

        Raises:
            aiohttp.ClientError: If the request fails
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.base_url}/api/v1/orders/{order_uid}/trades",
            ) as response:
                if response.status == 404:
                    return []
                response.raise_for_status()
                result: list[dict[str, Any]] = await response.json()
                return result

    async def upload_app_data(
        self, app_data_hash: str, app_data_doc: str | dict[str, Any]
    ) -> dict[str, Any]:
        """Upload appData document to the orderbook.

        This is required before submitting orders with custom appData (e.g., hooks).

        Args:
            app_data_hash: 32-byte hash of the appData document (with 0x prefix)
            app_data_doc: Full appData JSON document (as string or dict)

        Returns:
            Response from the orderbook (typically empty on success)

        Raises:
            aiohttp.ClientError: If the request fails
            aiohttp.ClientResponseError: If the server returns an error status
        """
        # Parse app_data_doc to dict if it's a string
        if isinstance(app_data_doc, str):
            app_data_doc = json.loads(app_data_doc)

        # Strip 0x prefix for the URL path
        hash_without_prefix = app_data_hash[2:] if app_data_hash.startswith("0x") else app_data_hash

        # The API expects the appData wrapped in a "fullAppData" field
        # IMPORTANT: Use consistent serialization to match hash computation
        request_body = {
            "fullAppData": json.dumps(app_data_doc, separators=(",", ":"), sort_keys=True)
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.put(
                f"{self.base_url}/api/v1/app_data/{hash_without_prefix}",
                json=request_body,
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"AppData upload failed: {error_text}",
                        headers=response.headers,
                    )
                # API may return empty response on success
                text = await response.text()
                if text:
                    result: dict[str, Any] = await response.json()
                    return result
                return {}

    async def get_version(self) -> dict[str, Any]:
        """Get the API version information.

        Useful for health checks and API compatibility verification.

        Returns:
            Version information from the orderbook API

        Raises:
            aiohttp.ClientError: If the request fails
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.base_url}/api/v1/version",
            ) as response:
                response.raise_for_status()
                result: dict[str, Any] = await response.json()
                return result

    async def check_health(self) -> bool:
        """Check if the orderbook API is healthy and responding.

        Returns:
            True if the API is healthy, False otherwise
        """
        try:
            await self.get_version()
            return True
        except Exception:
            return False

    async def cancel_orders(
        self,
        order_uids: list[str],
        signature: str,
        signing_scheme: str = "eip712",
    ) -> dict[str, Any]:
        """Cancel multiple orders in a single request (batch cancellation).

        Args:
            order_uids: List of order UIDs to cancel
            signature: EIP-712 signature of OrderCancellations message
            signing_scheme: Signing scheme (default: "eip712")

        Returns:
            Response from orderbook

        Raises:
            aiohttp.ClientResponseError: If cancellation fails
        """
        request_body = {
            "orderUids": order_uids,
            "signature": signature,
            "signingScheme": signing_scheme,
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.delete(
                f"{self.base_url}/api/v1/orders",
                json=request_body,
            ) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Order cancellation failed: {error_text}",
                        headers=response.headers,
                    )
                result: dict[str, Any] = await response.json()
                return result

    async def get_account_orders(
        self,
        owner: str,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get orders for an account with pagination.

        Args:
            owner: Ethereum address of order owner
            offset: Pagination offset (default: 0)
            limit: Max orders to return (default: 1000, max: 1000)

        Returns:
            List of orders for the account

        Raises:
            aiohttp.ClientResponseError: If request fails
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.base_url}/api/v1/account/{owner}/orders",
                params={"offset": offset, "limit": limit},
            ) as response:
                response.raise_for_status()
                result: list[dict[str, Any]] = await response.json()
                return result

    async def get_open_order_count(self, owner: str) -> int:
        """Get count of open orders for an account.

        Args:
            owner: Ethereum address of order owner

        Returns:
            Number of open orders
        """
        orders = await self.get_account_orders(owner, limit=1000)
        open_orders = [o for o in orders if o.get("status") == "open"]
        return len(open_orders)

    async def upload_app_data_with_retry(
        self,
        app_data_hash: str,
        app_data_doc: str | dict[str, Any],
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Upload appData with automatic retry on failure.

        Args:
            app_data_hash: 32-byte hash of appData document
            app_data_doc: Full appData JSON document
            max_retries: Maximum retry attempts

        Returns:
            Response from orderbook

        Raises:
            aiohttp.ClientResponseError: If all retries fail
        """
        import asyncio

        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.upload_app_data(app_data_hash, app_data_doc)
            except aiohttp.ClientResponseError as e:
                last_error = e
                # Only retry on transient errors (5xx) or 409 Conflict (already exists)
                if e.status == 409:
                    # AppData already exists, this is OK
                    return {}
                if e.status not in (500, 502, 503, 504):
                    raise

                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    print(
                        f"AppData upload failed (attempt {attempt + 1}), "
                        f"retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

        if last_error:
            raise last_error
        return {}
