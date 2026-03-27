"""
Background task to check for expired orders and update metrics.

Since we cannot modify the CoW Protocol orderbook service code, we track
expiration ourselves by periodically checking order valid_to timestamps.
"""

import asyncio
import logging
import time

from .models import OrderStatus
from .store import MetricsStore

logger = logging.getLogger(__name__)


class ExpirationChecker:
    """
    Periodically checks for expired orders and updates metrics.

    This background task monitors all tracked orders and marks them as
    expired when their valid_to timestamp passes. This allows the
    performance testing suite to track order expiration without modifying
    the orderbook service code.
    """

    def __init__(self, metrics_store: MetricsStore, check_interval: float = 5.0):
        """
        Initialize expiration checker.

        Args:
            metrics_store: Store containing all order metadata
            check_interval: How often to check for expirations in seconds (default: 5.0)
        """
        self.metrics_store = metrics_store
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start background expiration checking."""
        if self._running:
            logger.warning("ExpirationChecker already running")
            return

        logger.info(f"Starting ExpirationChecker (check_interval={self.check_interval}s)")
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info(f"ExpirationChecker started (check_interval={self.check_interval}s)")

    async def stop(self) -> None:
        """Stop background expiration checking."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("ExpirationChecker stopped")

    async def _check_loop(self) -> None:
        """Main loop that checks for expired orders."""
        while self._running:
            try:
                await self._check_expired_orders()
            except Exception as e:
                logger.error(f"Error checking expired orders: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _check_expired_orders(self) -> None:
        """Check all orders and mark expired ones."""
        current_time = int(time.time())
        expired_count = 0
        checked_count = 0
        orders_without_valid_to = 0

        async with self.metrics_store.lock:
            logger.info(
                f"ExpirationChecker: Checking {len(self.metrics_store._orders)} orders (current_time={current_time})"
            )
            for order_uid, metadata in self.metrics_store._orders.items():
                checked_count += 1

                # Skip if valid_to not set (shouldn't happen, but be defensive)
                if metadata.valid_to is None:
                    orders_without_valid_to += 1
                    logger.warning(f"Order {order_uid[:10]}... has no valid_to set!")
                    continue

                logger.debug(
                    f"Order {order_uid[:10]}... valid_to={metadata.valid_to}, status={metadata.current_status}, expired={metadata.valid_to < current_time}"
                )

                # Skip if already marked as expired
                if metadata.current_status == OrderStatus.EXPIRED:
                    continue

                # Skip if already in terminal state (filled/cancelled/failed)
                if metadata.current_status in {
                    OrderStatus.FILLED,
                    OrderStatus.CANCELLED,
                    OrderStatus.FAILED,
                }:
                    continue

                # Check if order has expired
                if metadata.valid_to < current_time:
                    # Mark as expired using update_status to track history
                    metadata.update_status(OrderStatus.EXPIRED)
                    # Trigger MetricsStore callbacks (for Prometheus updates)
                    self.metrics_store.add_order(metadata)
                    expired_count += 1

                    logger.info(
                        f"Order {order_uid[:10]}... expired "
                        f"(valid_to={metadata.valid_to}, now={current_time})"
                    )

        if expired_count > 0:
            logger.info(f"Marked {expired_count} order(s) as expired")

        if orders_without_valid_to > 0:
            logger.warning(
                f"Found {orders_without_valid_to}/{checked_count} orders without valid_to set"
            )
