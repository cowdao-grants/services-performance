"""
Orchestration for managing multiple concurrent trader simulations.

This module provides coordination of multiple trader simulators with graceful
startup/shutdown, error handling, and performance monitoring.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .conditional_order_factory import ConditionalOrderFactory
from .order_factory import OrderFactory
from .order_signer import ConditionalOrderSigner, OrderSigner
from .order_tracker import OrderTracker
from .trader_account import TraderPool
from .trader_simulator import TraderBehaviorConfig, TraderSimulator


@dataclass
class OrchestrationConfig:
    """
    Configuration for trader orchestration.

    Controls the number of concurrent traders, timing, and error handling behavior.
    """

    num_traders: int = 10
    duration: float = 60.0  # Simulation duration in seconds
    startup_interval: float = 0.5  # Seconds between starting each trader
    restart_on_failure: bool = True  # Restart traders on failure
    max_restarts_per_trader: int = 3  # Maximum restart attempts
    graceful_shutdown_timeout: float = 10.0  # Timeout for graceful shutdown
    settlement_wait_time: float = (
        300.0  # Seconds to wait after test for orders to settle (default 5 min)
    )


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Per-trader rate limiting
    enable_per_trader_limit: bool = False
    max_orders_per_trader_per_second: float | None = None
    max_orders_per_trader_per_minute: float | None = None

    # Global rate limiting
    enable_global_limit: bool = False
    max_orders_global_per_second: float | None = None
    max_orders_global_per_minute: float | None = None

    # Algorithm settings
    algorithm: str = "token_bucket"  # "token_bucket" or "leaky_bucket"
    burst_allowance: float = 1.5  # Allow burst up to 1.5x the rate

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.enable_per_trader_limit:
            if (
                self.max_orders_per_trader_per_second is None
                and self.max_orders_per_trader_per_minute is None
            ):
                raise ValueError("Per-trader rate limit enabled but no limit specified")

        if self.enable_global_limit:
            if (
                self.max_orders_global_per_second is None
                and self.max_orders_global_per_minute is None
            ):
                raise ValueError("Global rate limit enabled but no limit specified")

        if self.algorithm not in ("token_bucket", "leaky_bucket"):
            raise ValueError(f"Unknown rate limit algorithm: {self.algorithm}")


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        rate_per_second: float,
        burst_allowance: float = 1.5,
    ):
        """
        Initialize rate limiter.

        Args:
            rate_per_second: Maximum sustained rate (operations per second)
            burst_allowance: Multiplier for burst capacity (e.g., 1.5 = 50% burst)
        """
        self.rate_per_second = rate_per_second
        self.capacity = rate_per_second * burst_allowance
        self.tokens = self.capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False if rate limit exceeded
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
            self.last_update = now

            # Try to acquire
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        """
        Wait until tokens are available.

        Args:
            tokens: Number of tokens to acquire
        """
        while True:
            if await self.acquire(tokens):
                return

            # Calculate wait time
            wait_time = tokens / self.rate_per_second
            await asyncio.sleep(wait_time)


class TraderOrchestrator:
    """
    Orchestrates multiple concurrent trader simulations.

    Manages trader lifecycle, handles failures, and provides coordinated
    startup and shutdown for load testing scenarios.
    """

    def __init__(
        self,
        trader_pool: TraderPool,
        order_factory: OrderFactory,
        conditional_order_factory: ConditionalOrderFactory,
        order_signer: OrderSigner,
        conditional_order_signer: ConditionalOrderSigner,
        order_tracker: OrderTracker,
        default_behavior_config: TraderBehaviorConfig,
        orchestration_config: OrchestrationConfig,
        api_client: Any | None = None,
        order_cleanup_config: Any | None = None,
        rate_limit_config: RateLimitConfig | None = None,
    ):
        """
        Initialize the trader orchestrator.

        Args:
            trader_pool: Pool of trader accounts
            order_factory: Factory for standard orders
            conditional_order_factory: Factory for conditional orders
            order_signer: Signer for standard orders
            conditional_order_signer: Signer for conditional orders
            order_tracker: Shared order tracker for all traders
            default_behavior_config: Default behavior configuration for traders
            orchestration_config: Configuration for orchestration
            api_client: Optional API client for order submission
            order_cleanup_config: Optional configuration for order cleanup behavior
            rate_limit_config: Optional configuration for rate limiting
        """
        self.trader_pool = trader_pool
        self.order_factory = order_factory
        self.conditional_order_factory = conditional_order_factory
        self.order_signer = order_signer
        self.conditional_order_signer = conditional_order_signer
        self.order_tracker = order_tracker
        self.default_behavior_config = default_behavior_config
        self.orchestration_config = orchestration_config
        self.api_client = api_client
        self.order_cleanup_config = order_cleanup_config
        self.rate_limit_config = rate_limit_config or RateLimitConfig()

        self.simulators: list[TraderSimulator] = []
        self.tasks: list[asyncio.Task] = []
        self.restart_counts: dict[int, int] = {}
        self._running = False
        self._start_time: float = 0.0

        # Initialize rate limiters
        self._global_limiter: RateLimiter | None = None
        self._per_trader_limiters: dict[str, RateLimiter] = {}
        self._rate_limit_hits = {
            "per_trader": 0,
            "global": 0,
        }

        if self.rate_limit_config.enable_global_limit:
            rate = self._calculate_rate_per_second(
                self.rate_limit_config.max_orders_global_per_second,
                self.rate_limit_config.max_orders_global_per_minute,
            )
            self._global_limiter = RateLimiter(
                rate_per_second=rate,
                burst_allowance=self.rate_limit_config.burst_allowance,
            )

    def _calculate_rate_per_second(
        self,
        per_second: float | None,
        per_minute: float | None,
    ) -> float:
        """Calculate rate per second from config."""
        if per_second is not None:
            return per_second
        elif per_minute is not None:
            return per_minute / 60.0
        else:
            raise ValueError("No rate specified")

    def _get_or_create_trader_limiter(self, trader_address: str) -> RateLimiter | None:
        """Get or create rate limiter for trader."""
        if not self.rate_limit_config.enable_per_trader_limit:
            return None

        if trader_address not in self._per_trader_limiters:
            rate = self._calculate_rate_per_second(
                self.rate_limit_config.max_orders_per_trader_per_second,
                self.rate_limit_config.max_orders_per_trader_per_minute,
            )
            self._per_trader_limiters[trader_address] = RateLimiter(
                rate_per_second=rate,
                burst_allowance=self.rate_limit_config.burst_allowance,
            )

        return self._per_trader_limiters[trader_address]

    async def request_submission_permission(self, trader_address: str) -> bool:
        """
        Request permission to submit an order.

        Checks both global and per-trader rate limits.

        Args:
            trader_address: Address of the trader requesting permission

        Returns:
            True if submission allowed, False if rate limited
        """
        # Check per-trader limit first
        if self.rate_limit_config.enable_per_trader_limit:
            trader_limiter = self._get_or_create_trader_limiter(trader_address)
            if trader_limiter and not await trader_limiter.acquire():
                self._rate_limit_hits["per_trader"] += 1
                return False

        # Check global limit
        if self.rate_limit_config.enable_global_limit and self._global_limiter:
            if not await self._global_limiter.acquire():
                self._rate_limit_hits["global"] += 1
                return False

        return True

    def _create_simulator(self, trader_index: int) -> TraderSimulator:
        """
        Create a trader simulator for the given trader index.

        Args:
            trader_index: Index of trader in the pool

        Returns:
            A configured TraderSimulator instance
        """
        trader = self.trader_pool.get_trader(trader_index)

        # Could customize behavior per trader here
        behavior_config = self.default_behavior_config

        return TraderSimulator(
            trader=trader,
            order_factory=self.order_factory,
            conditional_order_factory=self.conditional_order_factory,
            order_signer=self.order_signer,
            conditional_order_signer=self.conditional_order_signer,
            order_tracker=self.order_tracker,
            behavior_config=behavior_config,
            api_client=self.api_client,
            order_cleanup_config=self.order_cleanup_config,
            orchestrator=self,
        )

    async def _run_trader_with_restart(
        self,
        trader_index: int,
        duration: float,
    ) -> None:
        """
        Run a trader with automatic restart on failure.

        Args:
            trader_index: Index of the trader to run
            duration: Duration to run the trader
        """
        self.restart_counts[trader_index] = 0

        while self._running:
            # Check if we've exceeded max restarts
            if (
                self.orchestration_config.restart_on_failure
                and self.restart_counts[trader_index]
                >= self.orchestration_config.max_restarts_per_trader
            ):
                print(
                    f"Trader {trader_index} exceeded max restarts "
                    f"({self.orchestration_config.max_restarts_per_trader}), stopping"
                )
                break

            # Calculate remaining duration
            elapsed = time.time() - self._start_time
            remaining = duration - elapsed
            if remaining <= 0:
                break

            try:
                # Create and run simulator
                simulator = self._create_simulator(trader_index)
                await simulator.run(remaining)

                # If we complete successfully, we're done
                break

            except Exception as e:
                print(f"Trader {trader_index} failed with error: {e}")

                if not self.orchestration_config.restart_on_failure:
                    break

                # Increment restart count and retry
                self.restart_counts[trader_index] += 1
                print(
                    f"Restarting trader {trader_index} "
                    f"(attempt {self.restart_counts[trader_index]})"
                )

                # Small delay before restart
                await asyncio.sleep(1.0)

    async def _upload_app_data(self) -> None:
        """Upload appData documents for market and limit order classification."""
        if self.api_client is None:
            # Skip upload in dry-run mode
            return

        try:
            print("Uploading appData documents for order classification...")

            # Upload market order appData
            await self.api_client.upload_app_data_with_retry(
                app_data_hash=self.order_factory.market_app_data_hash,
                app_data_doc=self.order_factory.market_app_data_doc,
            )

            # Upload limit order appData
            await self.api_client.upload_app_data_with_retry(
                app_data_hash=self.order_factory.limit_app_data_hash,
                app_data_doc=self.order_factory.limit_app_data_doc,
            )

            print("AppData documents uploaded successfully")

        except Exception as e:
            print(f"Warning: Failed to upload appData documents: {e}")
            print("Continuing with simulation - orders may not be classified correctly")

    async def _wait_for_settlements(self, wait_time: float) -> None:
        """
        Wait for pending orders to settle after test completes.

        Continues monitoring order status during the wait period to detect
        fills, expirations, and other terminal states.

        Args:
            wait_time: Seconds to wait for settlements
        """
        if self.api_client is None:
            return

        # Get all non-terminal orders
        all_orders = self.order_tracker.get_all_orders()
        pending_orders = [o for o in all_orders if not o.is_terminal_state()]

        if not pending_orders:
            print("No pending orders to monitor")
            return

        # Show initial status breakdown
        status_counts: dict[str, int] = {}
        for o in pending_orders:
            status = o.current_status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        status_str = ", ".join(f"{v} {k}" for k, v in sorted(status_counts.items()))

        print(f"Monitoring {len(pending_orders)} pending orders [{status_str}]...")

        # Monitor orders with polling
        start_time = time.time()
        poll_interval = 10.0  # Poll every 10 seconds during settlement
        last_filled_count = 0

        while time.time() - start_time < wait_time:
            # Poll all pending orders
            for order in pending_orders:
                if order.is_terminal_state():
                    continue

                try:
                    # Poll status from API
                    # Update will happen inside poll_order_status if status changed
                    await self.order_tracker.poll_order_status(
                        order.order_uid,
                        self.api_client,
                    )
                except Exception:
                    # Continue monitoring even if one order fails
                    continue

            # Update pending list and show progress
            all_orders = self.order_tracker.get_all_orders()
            pending_orders = [o for o in all_orders if not o.is_terminal_state()]
            filled_orders = [o for o in all_orders if o.current_status.value == "filled"]
            expired_orders = [o for o in all_orders if o.current_status.value == "expired"]
            failed_orders = [o for o in all_orders if o.current_status.value == "failed"]

            filled_count = len(filled_orders)
            if filled_count > last_filled_count:
                # Build status breakdown for pending orders
                loop_status_counts: dict[str, int] = {}
                for o in pending_orders:
                    status = o.current_status.value
                    loop_status_counts[status] = loop_status_counts.get(status, 0) + 1

                status_str = ", ".join(f"{v} {k}" for k, v in sorted(loop_status_counts.items()))
                terminal_str = ""
                if expired_orders or failed_orders:
                    terminal_str = f" | {len(expired_orders)} expired, {len(failed_orders)} failed"

                print(
                    f"  Progress: {filled_count} filled, "
                    f"{len(pending_orders)} pending [{status_str}]{terminal_str} "
                    f"({int(time.time() - start_time)}s elapsed)"
                )
                last_filled_count = filled_count

            # If all orders are settled, we can exit early
            if not pending_orders:
                print("All orders settled!")
                break

            # Wait before next poll
            await asyncio.sleep(poll_interval)

        # Final summary with detailed breakdown
        final_orders = self.order_tracker.get_all_orders()
        filled = len([o for o in final_orders if o.current_status.value == "filled"])
        expired = len([o for o in final_orders if o.current_status.value == "expired"])
        failed = len([o for o in final_orders if o.current_status.value == "failed"])
        cancelled = len([o for o in final_orders if o.current_status.value == "cancelled"])
        still_pending = [o for o in final_orders if not o.is_terminal_state()]

        # Build pending breakdown
        pending_str = ""
        if still_pending:
            final_status_counts: dict[str, int] = {}
            for o in still_pending:
                status = o.current_status.value
                final_status_counts[status] = final_status_counts.get(status, 0) + 1
            pending_str = f" (pending breakdown: {final_status_counts})"

        print(
            f"Settlement wait completed: {filled} filled, {expired} expired, "
            f"{failed} failed, {cancelled} cancelled, {len(still_pending)} still pending{pending_str}"
        )

    async def run(self) -> None:
        """
        Run the orchestrated trader simulation.

        Starts all traders with staggered timing and runs for the configured duration.
        """
        self._running = True
        self._start_time = time.time()

        config = self.orchestration_config
        num_traders = min(config.num_traders, self.trader_pool.get_pool_size())

        # Upload appData documents before starting traders
        await self._upload_app_data()

        print(f"Starting {num_traders} traders...")

        try:
            # Start traders with staggered timing
            for i in range(num_traders):
                if not self._running:
                    break

                task = asyncio.create_task(self._run_trader_with_restart(i, config.duration))
                self.tasks.append(task)

                # Stagger startup
                if i < num_traders - 1:
                    await asyncio.sleep(config.startup_interval)

            print(f"All {len(self.tasks)} traders started")

            # Wait for all traders to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)

            print("All traders completed")

            # Wait for pending orders to settle
            if config.settlement_wait_time > 0 and self.api_client is not None:
                print(
                    f"\nWaiting {config.settlement_wait_time:.0f} seconds for "
                    "pending orders to settle..."
                )
                await self._wait_for_settlements(config.settlement_wait_time)
                print("Settlement monitoring completed")

        finally:
            self._running = False

    async def start(self) -> asyncio.Task:
        """
        Start orchestration in background.

        Returns:
            The asyncio Task for the orchestration
        """
        return asyncio.create_task(self.run())

    async def stop(self) -> None:
        """
        Stop all traders gracefully.

        Attempts to stop all traders within the configured timeout,
        then cancels any remaining tasks.
        """
        print("Stopping all traders...")
        self._running = False

        # Stop all simulators
        for simulator in self.simulators:
            try:
                await asyncio.wait_for(
                    simulator.stop(),
                    timeout=self.orchestration_config.graceful_shutdown_timeout,
                )
            except TimeoutError:
                print("Timeout stopping simulator, forcing cancellation")

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellations to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)

        # Stop order tracking
        await self.order_tracker.stop_all_monitoring()

        print("All traders stopped")

    def get_status(self) -> dict[str, Any]:
        """
        Get current orchestration status.

        Returns:
            Dictionary with status information
        """
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0

        return {
            "running": self._running,
            "num_traders": len(self.tasks),
            "elapsed_time": elapsed,
            "total_orders_submitted": self.trader_pool.get_total_orders_submitted(),
            "restart_counts": self.restart_counts.copy(),
            "order_metrics": self.order_tracker.get_metrics(),
        }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive metrics from the simulation.

        Returns:
            Dictionary with detailed metrics
        """
        status = self.get_status()
        order_metrics = self.order_tracker.get_metrics()

        return {
            "orchestration": {
                "num_traders": len(self.tasks),
                "elapsed_time": status["elapsed_time"],
                "total_restarts": sum(self.restart_counts.values()),
            },
            "orders": {
                "total_submitted": self.trader_pool.get_total_orders_submitted(),
                "total_tracked": order_metrics.total_orders,
                # Current states
                "orders_open": order_metrics.orders_accepted,  # Includes both ACCEPTED and OPEN status
                # Terminal states
                "orders_filled": order_metrics.orders_filled,
                "orders_failed": order_metrics.orders_failed,
                "orders_expired": order_metrics.orders_expired,
                "orders_cancelled": order_metrics.orders_cancelled,
                "orders_partially_filled": order_metrics.orders_partially_filled,
                # Order types
                "market_orders": order_metrics.market_orders,
                "limit_orders": order_metrics.limit_orders,
                "twap_orders": order_metrics.twap_orders,
                "stop_loss_orders": order_metrics.stop_loss_orders,
                "good_after_time_orders": order_metrics.good_after_time_orders,
            },
            "performance": {
                "orders_per_second": (
                    self.trader_pool.get_total_orders_submitted() / status["elapsed_time"]
                    if status["elapsed_time"] > 0
                    else 0.0
                ),
                "avg_time_to_submit": order_metrics.avg_time_to_submit,
                "avg_time_to_accept": order_metrics.avg_time_to_accept,
                "avg_time_to_fill": order_metrics.avg_time_to_fill,
                "avg_total_lifecycle_time": order_metrics.avg_total_lifecycle_time,
            },
            "rate_limiting": {
                "per_trader_hits": self._rate_limit_hits["per_trader"],
                "global_hits": self._rate_limit_hits["global"],
                "total_hits": (
                    self._rate_limit_hits["per_trader"] + self._rate_limit_hits["global"]
                ),
            },
        }


async def run_load_test(
    num_traders: int = 10,
    duration: float = 60.0,
    trader_pool: TraderPool | None = None,
    order_factory: OrderFactory | None = None,
    conditional_order_factory: ConditionalOrderFactory | None = None,
    order_signer: OrderSigner | None = None,
    conditional_order_signer: ConditionalOrderSigner | None = None,
    order_tracker: OrderTracker | None = None,
    behavior_config: TraderBehaviorConfig | None = None,
    orchestration_config: OrchestrationConfig | None = None,
    api_client: Any | None = None,
) -> dict[str, Any]:
    """
    Convenience function to run a complete load test.

    This function sets up and runs a load test with the specified parameters,
    providing a simple interface for common testing scenarios.

    Args:
        num_traders: Number of concurrent traders
        duration: Test duration in seconds
        trader_pool: Optional trader pool (creates default if None)
        order_factory: Optional order factory (creates default if None)
        conditional_order_factory: Optional conditional order factory (creates default if None)
        order_signer: Optional order signer (creates default if None)
        conditional_order_signer: Optional conditional order signer (creates default if None)
        order_tracker: Optional order tracker (creates default if None)
        behavior_config: Optional behavior config (uses default if None)
        orchestration_config: Optional orchestration config (uses default if None)
        api_client: Optional API client for order submission

    Returns:
        Dictionary with test results and metrics
    """
    # Create default components if not provided
    if trader_pool is None:
        trader_pool = TraderPool(num_traders=num_traders)

    if order_tracker is None:
        order_tracker = OrderTracker()

    if behavior_config is None:
        behavior_config = TraderBehaviorConfig()

    if orchestration_config is None:
        orchestration_config = OrchestrationConfig(
            num_traders=num_traders,
            duration=duration,
        )

    # Note: order_factory, conditional_order_factory, order_signer, and
    # conditional_order_signer would need to be created with proper
    # configuration (chain_id, contract addresses, etc.)
    # For now, we require them to be passed in or this function will fail

    if order_factory is None or order_signer is None:
        raise ValueError("order_factory and order_signer must be provided")

    if conditional_order_factory is None or conditional_order_signer is None:
        raise ValueError("conditional_order_factory and conditional_order_signer must be provided")

    # Create orchestrator
    orchestrator = TraderOrchestrator(
        trader_pool=trader_pool,
        order_factory=order_factory,
        conditional_order_factory=conditional_order_factory,
        order_signer=order_signer,
        conditional_order_signer=conditional_order_signer,
        order_tracker=order_tracker,
        default_behavior_config=behavior_config,
        orchestration_config=orchestration_config,
        api_client=api_client,
    )

    # Run the test
    await orchestrator.run()

    # Return metrics
    return orchestrator.get_metrics()
