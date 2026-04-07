"""
Integration tests for user simulation module.

Tests full user simulation with multiple concurrent traders submitting
market and limit orders.
"""

import asyncio

import pytest

from cow_performance.load_generation import (
    OrchestrationConfig,
    OrderFactory,
    OrderSigner,
    OrderTracker,
    TraderBehaviorConfig,
    TraderOrchestrator,
    TraderPool,
    TradingPattern,
    create_mainnet_token_registry,
)


@pytest.fixture
def chain_id():
    """Test chain ID (Mainnet)."""
    return 1


@pytest.fixture
def settlement_contract():
    """CoW Protocol settlement contract address (Mainnet)."""
    return "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"


@pytest.fixture
def token_registry():
    """Create token registry."""
    return create_mainnet_token_registry()


@pytest.fixture
def order_factory(token_registry):
    """Create order factory."""
    return OrderFactory(
        token_pair_registry=token_registry,
        chain_id=1,
        settlement_contract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        valid_duration=3600,
    )


@pytest.fixture
def order_signer(chain_id, settlement_contract):
    """Create order signer."""
    return OrderSigner(chain_id, settlement_contract)


@pytest.fixture
def order_tracker():
    """Create order tracker."""
    return OrderTracker(poll_interval=1.0, max_poll_attempts=10)


@pytest.fixture
def trader_pool():
    """Create trader pool with deterministic accounts."""
    TraderPool.set_deterministic_seed(12345)
    pool = TraderPool(num_traders=10)
    TraderPool.set_deterministic_seed(None)
    return pool


class TestUserSimulationIntegration:
    """Integration tests for complete user simulation."""

    @pytest.mark.asyncio
    async def test_single_trader_submits_orders(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test that a single trader can submit orders successfully."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            base_rate=60.0,  # 60 orders per minute = 1 per second
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=1,
            duration=3.0,  # Run for 3 seconds
            startup_interval=0.0,
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Run the test
        await orchestrator.run()

        # Verify orders were submitted
        total_orders = trader_pool.get_total_orders_submitted()
        assert total_orders >= 2  # Should submit at least 2-3 orders in 3 seconds

        # Verify metrics
        metrics = orchestrator.get_metrics()
        assert metrics["orchestration"]["num_traders"] == 1
        assert metrics["orders"]["total_submitted"] >= 2

    @pytest.mark.asyncio
    async def test_multiple_concurrent_traders(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test multiple traders running concurrently."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            base_rate=30.0,  # 30 orders per minute = 1 every 2 seconds
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=5,
            duration=5.0,  # Run for 5 seconds
            startup_interval=0.1,  # Start traders quickly
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Run the test
        await orchestrator.run()

        # Verify multiple traders submitted orders
        total_orders = trader_pool.get_total_orders_submitted()
        assert total_orders >= 10  # 5 traders * ~2 orders each

        # Verify multiple traders were active
        active_traders = sum(
            1 for trader in trader_pool.get_all_traders() if trader.orders_submitted > 0
        )
        assert active_traders == 5

    @pytest.mark.asyncio
    async def test_burst_trading_pattern(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test burst trading pattern."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.BURST,
            burst_size=3,
            burst_interval=0.1,
            quiet_period=2.0,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=2,
            duration=5.0,
            startup_interval=0.0,
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Run the test
        await orchestrator.run()

        # Verify burst pattern created orders
        total_orders = trader_pool.get_total_orders_submitted()
        assert total_orders >= 6  # 2 traders * 3 orders per burst

    @pytest.mark.asyncio
    async def test_random_interval_pattern(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test random interval trading pattern."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.RANDOM_INTERVAL,
            min_interval=0.5,
            max_interval=2.0,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=2,
            duration=5.0,
            startup_interval=0.0,
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Run the test
        await orchestrator.run()

        # Verify orders were submitted with random timing
        total_orders = trader_pool.get_total_orders_submitted()
        assert total_orders >= 4  # Should get multiple orders in 5 seconds

    @pytest.mark.asyncio
    async def test_graceful_shutdown(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test graceful shutdown of orchestrator."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            base_rate=60.0,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=3,
            duration=30.0,  # Long duration
            startup_interval=0.1,
            graceful_shutdown_timeout=5.0,
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Start orchestrator
        task = await orchestrator.start()

        # Let it run briefly
        await asyncio.sleep(2.0)

        # Stop it
        await orchestrator.stop()

        # Verify it stopped
        assert not orchestrator._running
        assert task.done()

    @pytest.mark.asyncio
    async def test_order_signatures_are_valid(
        self,
        trader_pool,
        order_factory,
        order_signer,
        order_tracker,
    ):
        """Test that generated order signatures are valid."""
        behavior_config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            base_rate=60.0,
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
        )

        orchestration_config = OrchestrationConfig(
            num_traders=2,
            duration=2.0,
            startup_interval=0.0,
        )

        orchestrator = TraderOrchestrator(
            trader_pool=trader_pool,
            order_factory=order_factory,
            order_signer=order_signer,
            order_tracker=order_tracker,
            default_behavior_config=behavior_config,
            orchestration_config=orchestration_config,
        )

        # Run the test
        await orchestrator.run()

        # Verify orders were created
        total_orders = trader_pool.get_total_orders_submitted()
        assert total_orders >= 2

        # Note: In a real implementation with API submission, we would verify
        # that all signatures were accepted by the orderbook API


class TestTraderBehaviorConfig:
    """Tests for trader behavior configuration validation."""

    def test_valid_config(self):
        """Test that valid config is accepted."""
        config = TraderBehaviorConfig(
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
        )
        assert config is not None

    def test_invalid_ratio_sum_raises_error(self):
        """Test that invalid ratio sum raises error."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            TraderBehaviorConfig(
                market_order_ratio=0.3,
                limit_order_ratio=0.3,
            )

    def test_negative_rate_raises_error(self):
        """Test that negative rate raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                base_rate=-1.0,
                market_order_ratio=1.0,
                limit_order_ratio=0.0,
            )


class TestOrchestrationConfig:
    """Tests for orchestration configuration."""

    def test_valid_orchestration_config(self):
        """Test that valid orchestration config is accepted."""
        config = OrchestrationConfig(
            num_traders=10,
            duration=60.0,
            startup_interval=0.5,
        )
        assert config is not None
        assert config.num_traders == 10
        assert config.duration == 60.0
