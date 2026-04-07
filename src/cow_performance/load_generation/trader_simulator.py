"""
Trader simulation for realistic user behavior patterns.

This module provides trader simulation with configurable behavior patterns,
supporting market and limit orders.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .order_factory import OrderFactory
from .order_signer import OrderSigner
from .order_tracker import OrderStatus, OrderTracker
from .trader_account import TraderAccount


class TradingPattern(StrEnum):
    """Trading behavior patterns for simulation."""

    CONSTANT_RATE = "constant_rate"  # Fixed interval between orders
    RANDOM_INTERVAL = "random_interval"  # Random intervals within a range
    BURST = "burst"  # Bursts of activity followed by quiet periods
    TIME_BASED = "time_based"  # More active during certain periods
    RAMP_UP = "ramp_up"  # Gradually increase submission rate
    RAMP_DOWN = "ramp_down"  # Gradually decrease submission rate
    SPIKE = "spike"  # Sudden bursts with recovery periods
    POISSON = "poisson"  # Poisson distribution for realistic random intervals


@dataclass
class TraderBehaviorConfig:
    """
    Configuration for trader behavior simulation.

    Controls trading patterns, order preferences, and timing parameters.
    """

    pattern: TradingPattern = TradingPattern.CONSTANT_RATE

    # Order submission rate (orders per minute)
    base_rate: float = 6.0

    # Order type distribution (sum should be 1.0)
    market_order_ratio: float = 0.5
    limit_order_ratio: float = 0.5

    # Random interval pattern parameters (seconds)
    min_interval: float = 5.0
    max_interval: float = 30.0

    # Burst pattern parameters
    burst_size: int = 5  # Orders per burst
    burst_interval: float = 2.0  # Seconds between orders in burst
    quiet_period: float = 60.0  # Seconds between bursts

    # Time-based pattern parameters
    active_hours: list[int] | None = None  # Hours when more active (0-23)
    active_multiplier: float = 2.0  # Rate multiplier during active hours

    # Order size preferences (multipliers for template amounts)
    min_size_multiplier: float = 0.5
    max_size_multiplier: float = 2.0

    # Think time (delay between decision and action, seconds)
    min_think_time: float = 0.5
    max_think_time: float = 2.0

    # Ramp pattern parameters (for RAMP_UP and RAMP_DOWN)
    ramp_start_rate: float | None = None  # Orders per minute at start
    ramp_target_rate: float | None = None  # Orders per minute at end
    ramp_duration: float = 300.0  # Duration in seconds (default 5 minutes)
    ramp_curve: str = "linear"  # "linear" or "exponential"

    # Spike pattern parameters
    spike_normal_rate: float | None = None  # Normal orders per minute
    spike_burst_rate: float | None = None  # Burst orders per minute
    spike_duration: float = 30.0  # Duration of spike in seconds
    spike_recovery_time: float = 60.0  # Time between spikes

    # Poisson pattern parameters
    poisson_lambda: float | None = None  # Events per minute (rate parameter)

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        total_ratio = (
            self.market_order_ratio
            + self.limit_order_ratio
        )
        if not 0.99 <= total_ratio <= 1.01:  # Allow small floating point errors
            raise ValueError(f"Order type ratios must sum to 1.0, got {total_ratio}")

        if self.base_rate <= 0:
            raise ValueError("base_rate must be positive")

        # Validate ramp parameters
        if self.pattern in (TradingPattern.RAMP_UP, TradingPattern.RAMP_DOWN):
            if self.ramp_start_rate is None:
                raise ValueError(f"{self.pattern} requires ramp_start_rate")
            if self.ramp_target_rate is None:
                raise ValueError(f"{self.pattern} requires ramp_target_rate")
            if self.ramp_start_rate <= 0 or self.ramp_target_rate <= 0:
                raise ValueError("Ramp rates must be positive")
            if self.ramp_duration <= 0:
                raise ValueError("Ramp duration must be positive")
            if self.ramp_curve not in ("linear", "exponential"):
                raise ValueError("ramp_curve must be 'linear' or 'exponential'")

        # Validate spike parameters
        if self.pattern == TradingPattern.SPIKE:
            if self.spike_normal_rate is None or self.spike_burst_rate is None:
                raise ValueError("SPIKE pattern requires spike_normal_rate and spike_burst_rate")
            if self.spike_normal_rate <= 0 or self.spike_burst_rate <= 0:
                raise ValueError("Spike rates must be positive")
            if self.spike_burst_rate <= self.spike_normal_rate:
                raise ValueError("spike_burst_rate must be greater than spike_normal_rate")
            if self.spike_duration <= 0:
                raise ValueError("spike_duration must be positive")

        # Validate poisson parameters
        if self.pattern == TradingPattern.POISSON:
            if self.poisson_lambda is None:
                raise ValueError("POISSON pattern requires poisson_lambda")
            if self.poisson_lambda <= 0:
                raise ValueError("poisson_lambda must be positive")


class TraderSimulator:
    """
    Simulates individual trader behavior with configurable patterns.

    Generates and submits market and limit orders according to configured
    behavior patterns.
    """

    def __init__(
        self,
        trader: TraderAccount,
        order_factory: OrderFactory,
        order_signer: OrderSigner,
        order_tracker: OrderTracker,
        behavior_config: TraderBehaviorConfig,
        api_client: Any | None = None,
        order_cleanup_config: Any | None = None,
        orchestrator: Any | None = None,
    ):
        """
        Initialize trader simulator.

        Args:
            trader: The trader account to simulate
            order_factory: Factory for generating standard orders
            order_signer: Signer for standard orders
            order_tracker: Tracker for monitoring order lifecycle
            behavior_config: Configuration for trading behavior
            api_client: Optional API client for order submission
            order_cleanup_config: Optional configuration for order cleanup behavior
            orchestrator: Optional orchestrator for rate limiting coordination
        """
        self.trader = trader
        self.order_factory = order_factory
        self.order_signer = order_signer
        self.order_tracker = order_tracker
        self.behavior_config = behavior_config
        self.api_client = api_client
        self.order_cleanup_config = order_cleanup_config
        self.orchestrator = orchestrator

        self._running = False
        self._task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None

    def _get_order_interval(self) -> float:
        """
        Calculate the next order interval based on behavior pattern.

        Returns:
            Seconds until next order
        """
        config = self.behavior_config
        base_interval = 60.0 / config.base_rate  # Convert rate to interval

        if config.pattern == TradingPattern.CONSTANT_RATE:
            return base_interval

        elif config.pattern == TradingPattern.RANDOM_INTERVAL:
            return random.uniform(config.min_interval, config.max_interval)

        elif config.pattern == TradingPattern.BURST:
            # Handled separately in _burst_pattern_loop
            return base_interval

        elif config.pattern == TradingPattern.TIME_BASED:
            current_hour = time.localtime().tm_hour
            if config.active_hours and current_hour in config.active_hours:
                return base_interval / config.active_multiplier
            return base_interval

        return base_interval

    def _select_order_type(self) -> str:
        """
        Select order type based on configured distribution.

        Returns:
            Order type: 'market' or 'limit'
        """
        config = self.behavior_config
        rand = random.random()

        cumulative = 0.0
        for order_type, ratio in [
            ("market", config.market_order_ratio),
            ("limit", config.limit_order_ratio),
        ]:
            cumulative += ratio
            if rand <= cumulative:
                return order_type

        return "market"  # Fallback

    async def _apply_think_time(self) -> None:
        """Apply random think time before action."""
        think_time = random.uniform(
            self.behavior_config.min_think_time,
            self.behavior_config.max_think_time,
        )
        await asyncio.sleep(think_time)

    async def _cleanup_loop(self) -> None:
        """Background loop to check and cleanup old orders."""
        if not self.order_cleanup_config or not self.order_cleanup_config.enabled:
            return

        if self.api_client is None:
            return

        while self._running:
            try:
                # Check current order count
                open_count = await self.api_client.get_open_order_count(self.trader.address)

                if open_count >= self.order_cleanup_config.max_open_orders_per_wallet:
                    print(
                        f"Trader {self.trader.address[:8]}... has {open_count} open orders, "
                        f"triggering cleanup..."
                    )
                    await self._cleanup_orders()

            except Exception as e:
                print(f"Error in cleanup loop: {e}")

            await asyncio.sleep(self.order_cleanup_config.check_interval)

    async def _cleanup_orders(self) -> None:
        """Cancel oldest orders to stay under limit."""
        if not self.order_cleanup_config:
            return

        if self.api_client is None:
            return

        config = self.order_cleanup_config

        # Get all orders for this wallet
        all_orders = await self.api_client.get_account_orders(
            self.trader.address,
            limit=1000,
        )

        # Filter to open orders only
        open_orders = [o for o in all_orders if o.get("status") == "open"]

        # Sort by creation time (oldest first)
        if config.cleanup_strategy == "oldest_first":
            open_orders.sort(key=lambda o: o.get("creationDate", ""))
        elif config.cleanup_strategy == "random":
            random.shuffle(open_orders)

        # Select orders to cancel
        orders_to_cancel = open_orders[: config.cleanup_batch_size]
        order_uids = [o["uid"] for o in orders_to_cancel]

        if not order_uids:
            return

        # Sign cancellation
        from .order_signer import sign_order_cancellations

        signature = sign_order_cancellations(
            order_uids=order_uids,
            trader_account=self.trader.get_account(),
            chain_id=self.order_factory.chain_id,
            settlement_contract=self.order_factory.settlement_contract,
        )

        # Cancel orders
        await self.api_client.cancel_orders(
            order_uids=order_uids,
            signature=signature,
            signing_scheme="eip712",
        )

        print(f"Trader {self.trader.address[:8]}... cancelled {len(order_uids)} orders")

    async def _generate_and_submit_order(self) -> None:
        """Generate and submit a single order based on behavior configuration."""
        # Check rate limits if orchestrator available
        if self.orchestrator is not None:
            allowed = await self.orchestrator.request_submission_permission(self.trader.address)
            if not allowed:
                # Rate limited, wait a bit and return
                await asyncio.sleep(0.1)
                return

        order_type = self._select_order_type()

        # Apply think time
        await self._apply_think_time()

        try:
            await self._submit_standard_order(order_type)
        except Exception as e:
            # Quote or submission failed - skip this order and continue
            # This matches production behavior: if quote fails, user must try again
            print(f"Skipping {order_type} order: {e}")

    async def _submit_standard_order(self, order_type: str) -> None:
        """
        Generate and submit a standard order (market or limit).

        Args:
            order_type: Either 'market' or 'limit'

        Raises:
            Exception: If quote fails or order submission fails
        """
        # Generate order using factory (already signed)
        # This will raise an exception if quote fails - caller should handle it
        try:
            if order_type == "market":
                signed_order = await self.order_factory.create_market_order(
                    trader_account=self.trader.get_account()
                )
            else:
                signed_order = await self.order_factory.create_limit_order(
                    trader_account=self.trader.get_account()
                )
        except Exception as e:
            # Quote failed - skip this order and let caller retry with different parameters
            raise RuntimeError(f"Quote failed for {order_type} order: {e}") from e

        # Track order with temporary UID first (for pre-submission tracking)
        temp_uid = f"pending_{int(time.time() * 1000)}"
        self.order_tracker.track_order(
            order_uid=temp_uid,
            owner=self.trader.address,
            sell_token=signed_order.sellToken,
            buy_token=signed_order.buyToken,
            sell_amount=signed_order.sellAmount,
            buy_amount=signed_order.buyAmount,
            order_type=order_type,
            valid_to=signed_order.validTo,
        )

        # Update status to submitted
        self.order_tracker.update_order_status(temp_uid, OrderStatus.SUBMITTED)

        # Submit to API
        order_uid = temp_uid  # Default to temp UID for dry-run mode
        if self.api_client is not None:
            try:
                # Submit order to orderbook API and get real UID from response
                response = await self.api_client.submit_order(
                    signed_order.model_dump(by_alias=True)
                )
                # Extract real UID from response (API returns UID as string directly or in dict)
                if isinstance(response, str):
                    real_uid = response
                else:
                    real_uid = response.get("uid") or response.get("order_uid") or response
                # Update tracker with real UID
                if real_uid and real_uid != temp_uid:
                    self.order_tracker.update_order_uid(temp_uid, real_uid)
                    order_uid = real_uid
                self.order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)
            except Exception as e:
                # Mark as failed if submission fails
                self.order_tracker.update_order_status(temp_uid, OrderStatus.FAILED)
                # Re-raise to let orchestrator handle it
                raise RuntimeError(f"Failed to submit order: {e}") from e
        else:
            # Dry-run mode: use mock UID
            order_uid = f"0x{'0' * 56}{int(time.time())}"
            self.order_tracker.track_order(
                order_uid=order_uid,
                owner=self.trader.address,
                sell_token=signed_order.sellToken,
                buy_token=signed_order.buyToken,
                sell_amount=signed_order.sellAmount,
                buy_amount=signed_order.buyAmount,
                order_type=order_type,
                valid_to=signed_order.validTo,
            )
            self.order_tracker.update_order_status(order_uid, OrderStatus.ACCEPTED)

        # Increment trader stats
        self.trader.increment_orders_submitted()

        # Start monitoring in background with real UID
        self.order_tracker.start_monitoring(order_uid, self.api_client)

    async def _constant_rate_loop(self, duration: float) -> None:
        """Run trading loop with constant rate pattern."""
        end_time = time.time() + duration

        # Spread out first submission across one full interval so all traders
        # don't hit the orderbook simultaneously (thundering-herd at t=0).
        initial_jitter = random.uniform(0, self._get_order_interval())
        await asyncio.sleep(min(initial_jitter, end_time - time.time()))

        while self._running and time.time() < end_time:
            await self._generate_and_submit_order()
            interval = self._get_order_interval()
            await asyncio.sleep(interval)

    async def _random_interval_loop(self, duration: float) -> None:
        """Run trading loop with random interval pattern."""
        # Same as constant rate, but _get_order_interval returns random values
        await self._constant_rate_loop(duration)

    async def _burst_pattern_loop(self, duration: float) -> None:
        """Run trading loop with burst pattern."""
        end_time = time.time() + duration
        config = self.behavior_config

        while self._running and time.time() < end_time:
            # Generate burst
            for _ in range(config.burst_size):
                if not self._running or time.time() >= end_time:
                    break
                await self._generate_and_submit_order()
                await asyncio.sleep(config.burst_interval)

            # Quiet period
            await asyncio.sleep(config.quiet_period)

    async def _time_based_loop(self, duration: float) -> None:
        """Run trading loop with time-based pattern."""
        # Same as constant rate, but _get_order_interval adjusts based on time
        await self._constant_rate_loop(duration)

    async def _ramp_up_loop(self, duration: float) -> None:
        """Run trading loop with ramp-up pattern."""
        end_time = time.time() + duration
        config = self.behavior_config
        start_time = time.time()
        ramp_end_time = start_time + config.ramp_duration

        # Type narrowing: these are guaranteed not None after validation
        assert config.ramp_start_rate is not None
        assert config.ramp_target_rate is not None

        while self._running and time.time() < end_time:
            current_time = time.time()

            # Calculate current rate based on progress
            if current_time < ramp_end_time:
                progress = (current_time - start_time) / config.ramp_duration

                if config.ramp_curve == "linear":
                    # Linear interpolation
                    current_rate = (
                        config.ramp_start_rate
                        + (config.ramp_target_rate - config.ramp_start_rate) * progress
                    )
                else:  # exponential
                    # Exponential curve
                    current_rate = config.ramp_start_rate * (
                        (config.ramp_target_rate / config.ramp_start_rate) ** progress
                    )
            else:
                # After ramp completes, use target rate
                current_rate = config.ramp_target_rate

            await self._generate_and_submit_order()

            # Calculate interval from rate (orders per minute)
            interval = 60.0 / current_rate
            await asyncio.sleep(interval)

    async def _ramp_down_loop(self, duration: float) -> None:
        """Run trading loop with ramp-down pattern."""
        end_time = time.time() + duration
        config = self.behavior_config
        start_time = time.time()
        ramp_end_time = start_time + config.ramp_duration

        # Type narrowing: these are guaranteed not None after validation
        assert config.ramp_start_rate is not None
        assert config.ramp_target_rate is not None

        while self._running and time.time() < end_time:
            current_time = time.time()

            if current_time < ramp_end_time:
                progress = (current_time - start_time) / config.ramp_duration

                if config.ramp_curve == "linear":
                    # Start high, end low
                    current_rate = (
                        config.ramp_start_rate
                        - (config.ramp_start_rate - config.ramp_target_rate) * progress
                    )
                else:  # exponential
                    current_rate = config.ramp_start_rate * (
                        (config.ramp_target_rate / config.ramp_start_rate) ** progress
                    )
            else:
                current_rate = config.ramp_target_rate

            await self._generate_and_submit_order()

            interval = 60.0 / current_rate
            await asyncio.sleep(interval)

    async def _spike_loop(self, duration: float) -> None:
        """Run trading loop with spike pattern."""
        end_time = time.time() + duration
        config = self.behavior_config

        # Type narrowing: these are guaranteed not None after validation
        assert config.spike_normal_rate is not None
        assert config.spike_burst_rate is not None

        while self._running and time.time() < end_time:
            # Normal rate period
            spike_start = time.time() + config.spike_recovery_time

            while self._running and time.time() < min(spike_start, end_time):
                await self._generate_and_submit_order()
                interval = 60.0 / config.spike_normal_rate
                await asyncio.sleep(interval)

            if time.time() >= end_time:
                break

            # Spike period
            spike_end = time.time() + config.spike_duration

            while self._running and time.time() < min(spike_end, end_time):
                await self._generate_and_submit_order()
                interval = 60.0 / config.spike_burst_rate
                await asyncio.sleep(interval)

    async def _poisson_loop(self, duration: float) -> None:
        """Run trading loop with Poisson distribution for intervals."""
        import numpy as np

        end_time = time.time() + duration
        config = self.behavior_config

        # Type narrowing: this is guaranteed not None after validation
        assert config.poisson_lambda is not None

        # Convert lambda from events per minute to events per second
        lambda_per_second = config.poisson_lambda / 60.0

        while self._running and time.time() < end_time:
            await self._generate_and_submit_order()

            # Generate Poisson-distributed interval
            # Inter-arrival times follow exponential distribution
            interval = np.random.exponential(1.0 / lambda_per_second)

            await asyncio.sleep(interval)

    async def run(self, duration: float) -> None:
        """
        Run trader simulation for specified duration.

        Args:
            duration: Duration to run simulation in seconds
        """
        self._running = True

        # Start cleanup loop if enabled
        if self.order_cleanup_config and self.order_cleanup_config.enabled and self.api_client:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        try:
            if self.behavior_config.pattern == TradingPattern.CONSTANT_RATE:
                await self._constant_rate_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.RANDOM_INTERVAL:
                await self._random_interval_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.BURST:
                await self._burst_pattern_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.TIME_BASED:
                await self._time_based_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.RAMP_UP:
                await self._ramp_up_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.RAMP_DOWN:
                await self._ramp_down_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.SPIKE:
                await self._spike_loop(duration)
            elif self.behavior_config.pattern == TradingPattern.POISSON:
                await self._poisson_loop(duration)
        finally:
            self._running = False
            # Cancel cleanup task
            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass

    def start(self, duration: float) -> asyncio.Task:
        """
        Start trader simulation in background.

        Args:
            duration: Duration to run simulation in seconds

        Returns:
            The asyncio Task for the simulation
        """
        self._task = asyncio.create_task(self.run(duration))
        return self._task

    async def stop(self) -> None:
        """Stop the trader simulation gracefully."""
        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

    def is_running(self) -> bool:
        """
        Check if trader is currently running.

        Returns:
            True if running, False otherwise
        """
        return self._running
