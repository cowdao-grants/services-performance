"""
Unit tests for trading pattern configuration validation.

Tests parameter validation and configuration requirements for all trading patterns:
- RAMP_UP (linear and exponential)
- RAMP_DOWN (linear and exponential)
- SPIKE (burst cycles)
- POISSON (statistical properties)
- CONSTANT_RATE

Note: Timing and statistical properties are validated through integration tests
with real orderbook submissions (see configs/scenarios/). These unit tests focus
on configuration validation to ensure patterns are configured correctly.
"""

import pytest

from cow_performance.load_generation.trader_simulator import (
    TraderBehaviorConfig,
    TradingPattern,
)


class TestRampUpConfiguration:
    """Test RAMP_UP configuration validation."""

    def test_ramp_up_requires_start_and_target_rates(self) -> None:
        """Test that RAMP_UP requires ramp_start_rate and ramp_target_rate."""
        with pytest.raises(ValueError, match="ramp_start_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_UP,
                ramp_target_rate=60.0,
                # Missing ramp_start_rate
            )

        with pytest.raises(ValueError, match="ramp_target_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_UP,
                ramp_start_rate=6.0,
                # Missing ramp_target_rate
            )

    def test_ramp_up_requires_positive_rates(self) -> None:
        """Test that RAMP_UP requires positive rates."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_UP,
                ramp_start_rate=0.0,  # Invalid
                ramp_target_rate=60.0,
            )

        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_UP,
                ramp_start_rate=6.0,
                ramp_target_rate=-10.0,  # Invalid
            )

    def test_ramp_up_accepts_valid_configuration(self) -> None:
        """Test that RAMP_UP accepts valid configuration."""
        # Linear ramp
        config = TraderBehaviorConfig(
            pattern=TradingPattern.RAMP_UP,
            ramp_start_rate=6.0,
            ramp_target_rate=60.0,
            ramp_duration=300.0,
            ramp_curve="linear",
        )
        assert config.pattern == TradingPattern.RAMP_UP
        assert config.ramp_start_rate == 6.0
        assert config.ramp_target_rate == 60.0
        assert config.ramp_curve == "linear"

        # Exponential ramp
        config2 = TraderBehaviorConfig(
            pattern=TradingPattern.RAMP_UP,
            ramp_start_rate=1.0,
            ramp_target_rate=120.0,
            ramp_duration=150.0,
            ramp_curve="exponential",
        )
        assert config2.ramp_curve == "exponential"


class TestRampDownConfiguration:
    """Test RAMP_DOWN configuration validation."""

    def test_ramp_down_requires_start_and_target_rates(self) -> None:
        """Test that RAMP_DOWN requires ramp_start_rate and ramp_target_rate."""
        with pytest.raises(ValueError, match="ramp_start_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_DOWN,
                ramp_target_rate=6.0,
                # Missing ramp_start_rate
            )

        with pytest.raises(ValueError, match="ramp_target_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_DOWN,
                ramp_start_rate=60.0,
                # Missing ramp_target_rate
            )

    def test_ramp_down_requires_positive_rates(self) -> None:
        """Test that RAMP_DOWN requires positive rates."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.RAMP_DOWN,
                ramp_start_rate=60.0,
                ramp_target_rate=0.0,  # Invalid
            )

    def test_ramp_down_accepts_valid_configuration(self) -> None:
        """Test that RAMP_DOWN accepts valid configuration."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.RAMP_DOWN,
            ramp_start_rate=60.0,
            ramp_target_rate=6.0,
            ramp_duration=300.0,
            ramp_curve="exponential",
        )
        assert config.pattern == TradingPattern.RAMP_DOWN
        assert config.ramp_start_rate == 60.0
        assert config.ramp_target_rate == 6.0


class TestSpikeConfiguration:
    """Test SPIKE configuration validation."""

    def test_spike_requires_normal_and_burst_rates(self) -> None:
        """Test that SPIKE requires spike_normal_rate and spike_burst_rate."""
        with pytest.raises(ValueError, match="spike_normal_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.SPIKE,
                spike_burst_rate=60.0,
                # Missing spike_normal_rate
            )

        with pytest.raises(ValueError, match="spike_burst_rate"):
            TraderBehaviorConfig(
                pattern=TradingPattern.SPIKE,
                spike_normal_rate=10.0,
                # Missing spike_burst_rate
            )

    def test_spike_burst_must_be_greater_than_normal(self) -> None:
        """Test that spike_burst_rate must be greater than spike_normal_rate."""
        with pytest.raises(ValueError, match="must be greater"):
            TraderBehaviorConfig(
                pattern=TradingPattern.SPIKE,
                spike_normal_rate=60.0,
                spike_burst_rate=30.0,  # Lower than normal - invalid
            )

    def test_spike_requires_positive_rates(self) -> None:
        """Test that SPIKE requires positive rates."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.SPIKE,
                spike_normal_rate=0.0,  # Invalid
                spike_burst_rate=60.0,
            )

    def test_spike_requires_positive_durations(self) -> None:
        """Test that SPIKE requires positive durations."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.SPIKE,
                spike_normal_rate=10.0,
                spike_burst_rate=60.0,
                spike_duration=0.0,  # Invalid
            )

    def test_spike_accepts_valid_configuration(self) -> None:
        """Test that SPIKE accepts valid configuration."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.SPIKE,
            spike_normal_rate=10.0,
            spike_burst_rate=100.0,
            spike_duration=15.0,
            spike_recovery_time=60.0,
        )
        assert config.pattern == TradingPattern.SPIKE
        assert config.spike_normal_rate == 10.0
        assert config.spike_burst_rate == 100.0


class TestPoissonConfiguration:
    """Test POISSON configuration validation."""

    def test_poisson_requires_lambda(self) -> None:
        """Test that POISSON requires poisson_lambda."""
        with pytest.raises(ValueError, match="poisson_lambda"):
            TraderBehaviorConfig(
                pattern=TradingPattern.POISSON,
                # Missing poisson_lambda
            )

    def test_poisson_lambda_must_be_positive(self) -> None:
        """Test that poisson_lambda must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            TraderBehaviorConfig(
                pattern=TradingPattern.POISSON,
                poisson_lambda=0.0,  # Invalid
            )

    def test_poisson_accepts_valid_configuration(self) -> None:
        """Test that POISSON accepts valid configuration."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.POISSON,
            poisson_lambda=30.0,
        )
        assert config.pattern == TradingPattern.POISSON
        assert config.poisson_lambda == 30.0


class TestConstantRateConfiguration:
    """Test CONSTANT_RATE configuration validation."""

    def test_constant_rate_accepts_default_configuration(self) -> None:
        """Test that CONSTANT_RATE works with default configuration."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
        )
        assert config.pattern == TradingPattern.CONSTANT_RATE
        assert config.base_rate == 6.0  # Default

    def test_constant_rate_accepts_custom_rate(self) -> None:
        """Test that CONSTANT_RATE accepts custom base_rate."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            base_rate=60.0,
        )
        assert config.base_rate == 60.0


class TestOrderTypeRatios:
    """Test order type ratio validation."""

    def test_order_type_ratios_must_sum_to_one(self) -> None:
        """Test that order type ratios must sum to approximately 1.0."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            TraderBehaviorConfig(
                pattern=TradingPattern.CONSTANT_RATE,
                market_order_ratio=0.5,
                limit_order_ratio=0.3,
                twap_order_ratio=0.0,
                stop_loss_order_ratio=0.0,
                good_after_time_order_ratio=0.0,
                # Sum is 0.8, not 1.0
            )

    def test_order_type_ratios_accept_valid_distribution(self) -> None:
        """Test that valid order type distributions are accepted."""
        config = TraderBehaviorConfig(
            pattern=TradingPattern.CONSTANT_RATE,
            market_order_ratio=0.4,
            limit_order_ratio=0.4,
            twap_order_ratio=0.1,
            stop_loss_order_ratio=0.05,
            good_after_time_order_ratio=0.05,
        )
        assert config.market_order_ratio == 0.4
        assert config.limit_order_ratio == 0.4
        total = (
            config.market_order_ratio
            + config.limit_order_ratio
            + config.twap_order_ratio
            + config.stop_loss_order_ratio
            + config.good_after_time_order_ratio
        )
        assert abs(total - 1.0) < 0.01  # Allow small floating point error
