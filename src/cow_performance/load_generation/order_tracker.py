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

from .status_mapping import map_api_status_to_order_status

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
        max_poll_attempts: int = 180,
        metrics_store: MetricsStore | None = None,
    ):
        """
        Initialize the order tracker.

        Args:
            poll_interval: Seconds between status polls (default 5.0)
            max_poll_attempts: Maximum number of poll attempts before giving up (default 180)
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
        order_type: str = "unknown",
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
            order_type: Type of order (market, limit, twap, stop_loss, good_after_time)

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
            order_type=order_type,
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

    def update_order_uid(self, old_uid: str, new_uid: str) -> None:
        """
        Replace a temporary UID with the real UID from API response.

        Args:
            old_uid: The temporary/pending UID
            new_uid: The real UID from the orderbook API
        """
        if old_uid in self._orders:
            order = self._orders.pop(old_uid)
            order.order_uid = new_uid
            self._orders[new_uid] = order

            # Also update in metrics store if present
            if self._metrics_store:
                self._metrics_store.update_order_uid(old_uid, new_uid)

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

        # Notify metrics store to trigger Prometheus exporter callbacks
        if self._metrics_store is not None:
            self._metrics_store.add_order(metadata)

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

            logger.debug(f"Order {order_uid[:10]}... status: {api_status} -> {new_status.value}")

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
                logger.debug(
                    f"Order {order_uid[:10]}... reached terminal state: "
                    f"{metadata.current_status.value}"
                )
                break

            # Poll status if we have an API client
            if api_client is not None:
                await self.poll_order_status(order_uid, api_client)

            await asyncio.sleep(self.poll_interval)
            attempts += 1

        # If we hit max attempts, stop monitoring but don't mark as failed
        # The orchestrator's settlement wait period will continue monitoring
        # and will determine the final status
        metadata = self.get_order(order_uid)
        if metadata and not metadata.is_terminal_state():
            # Calculate detailed timeout information
            age_seconds = time.time() - metadata.creation_time
            status = metadata.current_status.value

            # Build lifecycle progress string
            lifecycle_stages = []
            if metadata.submission_time:
                lifecycle_stages.append("submitted")
            if metadata.acceptance_time:
                lifecycle_stages.append("accepted")
            if metadata.first_fill_time:
                lifecycle_stages.append("partially_filled")

            lifecycle_str = " → ".join(lifecycle_stages) if lifecycle_stages else "created only"

            # Token pair info (truncate addresses for readability)
            sell_token = metadata.sell_token[-8:] if metadata.sell_token else "unknown"
            buy_token = metadata.buy_token[-8:] if metadata.buy_token else "unknown"

            logger.warning(
                f"Order {order_uid[:10]}... timed out after {attempts} poll attempts "
                f"(status={status}, age={age_seconds:.1f}s, "
                f"pair={sell_token}→{buy_token}, lifecycle=[{lifecycle_str}])"
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

        # Count orders by status and type
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

            # Count by order type
            order_type = order.order_type
            if order_type == "market":
                metrics.market_orders += 1
            elif order_type == "limit":
                metrics.limit_orders += 1
            elif order_type == "twap":
                metrics.twap_orders += 1
            elif order_type == "stop_loss":
                metrics.stop_loss_orders += 1
            elif order_type == "good_after_time":
                metrics.good_after_time_orders += 1

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
