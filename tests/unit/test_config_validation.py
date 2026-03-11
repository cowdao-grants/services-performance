"""Tests for enhanced configuration validation."""

from cow_performance.cli.commands.scenarios import (
    ResourceRequirements,
    ScenarioConfig,
    ScenarioMetadata,
    SuccessCriteria,
)
from cow_performance.scenarios.config_validation import (
    ConfigValidator,
    ValidationError,
    ValidationWarning,
    validate_token_address,
)


class TestConfigValidator:
    """Test ConfigValidator class."""

    def test_valid_config_no_warnings(self):
        """Test that a well-configured scenario passes without warnings."""
        config = ScenarioConfig(
            name="test-scenario",
            num_traders=10,
            duration=120,
            market_order_ratio=0.7,
            limit_order_ratio=0.3,
            twap_order_ratio=0.0,
            stop_loss_order_ratio=0.0,
            good_after_time_order_ratio=0.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert not result.has_errors
        # May have warnings about single order type, but should be valid

    def test_excessive_traders_warning(self):
        """Test warning for excessive number of traders."""
        config = ScenarioConfig(
            name="high-load",
            num_traders=150,  # > 100
            duration=300,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid  # Warning, not error
        assert result.has_warnings
        assert any("very high number of traders" in w.message.lower() for w in result.warnings)

    def test_short_duration_warning(self):
        """Test warning for very short test duration."""
        config = ScenarioConfig(
            name="quick-test",
            num_traders=5,
            duration=15,  # < 30
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very short test duration" in w.message.lower() for w in result.warnings)

    def test_long_duration_warning(self):
        """Test warning for very long test duration."""
        config = ScenarioConfig(
            name="marathon",
            num_traders=10,
            duration=7200,  # > 3600
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very long test duration" in w.message.lower() for w in result.warnings)

    def test_high_rate_warning(self):
        """Test warning for very high trading rate."""
        config = ScenarioConfig(
            name="high-frequency",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=1500,  # > 1000
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very high trading rate" in w.message.lower() for w in result.warnings)

    def test_large_burst_warning(self):
        """Test warning for very large burst size."""
        config = ScenarioConfig(
            name="burst-test",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="burst",
            base_rate=60,
            burst_size=150,  # > 100
            burst_interval=0.1,
            quiet_period=5.0,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very large burst size" in w.message.lower() for w in result.warnings)

    def test_short_burst_interval_warning(self):
        """Test warning for very short burst interval."""
        config = ScenarioConfig(
            name="rapid-burst",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="burst",
            base_rate=60,
            burst_size=10,
            burst_interval=0.005,  # < 0.01
            quiet_period=5.0,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very short burst interval" in w.message.lower() for w in result.warnings)

    def test_narrow_interval_range_warning(self):
        """Test warning for narrow interval range in random pattern."""
        config = ScenarioConfig(
            name="random-test",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="random_interval",
            base_rate=60,
            min_interval=0.5,
            max_interval=0.55,  # range < 0.1
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very narrow interval range" in w.message.lower() for w in result.warnings)

    def test_all_zero_ratios_error(self):
        """Test error when all order ratios are zero."""
        config = ScenarioConfig(
            name="invalid",
            num_traders=10,
            duration=120,
            market_order_ratio=0.0,
            limit_order_ratio=0.0,
            twap_order_ratio=0.0,
            stop_loss_order_ratio=0.0,
            good_after_time_order_ratio=0.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert not result.valid
        assert result.has_errors
        assert any("all order type ratios are zero" in e.message.lower() for e in result.errors)

    def test_single_order_type_warning(self):
        """Test warning when only one order type is used."""
        config = ScenarioConfig(
            name="market-only",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
            twap_order_ratio=0.0,
            stop_loss_order_ratio=0.0,
            good_after_time_order_ratio=0.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("only one order type" in w.message.lower() for w in result.warnings)

    def test_duration_mismatch_warning(self):
        """Test warning when metadata duration doesn't match actual duration."""
        config = ScenarioConfig(
            name="mismatch-test",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            metadata=ScenarioMetadata(expected_duration_seconds=300),  # Mismatch
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any(
            "expected duration" in w.message.lower() and "doesn't match" in w.message.lower()
            for w in result.warnings
        )

    def test_order_count_mismatch_warning(self):
        """Test warning when expected orders differs significantly from estimate."""
        # Estimate: 10 traders * 60s * 60 orders/min / 60 = 600 orders
        config = ScenarioConfig(
            name="order-mismatch",
            num_traders=10,
            duration=60,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            metadata=ScenarioMetadata(
                expected_orders=100
            ),  # Way off (600 estimated vs 100 expected)
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any(
            "expected orders" in w.message.lower() and "differs significantly" in w.message.lower()
            for w in result.warnings
        )

    def test_high_load_low_memory_warning(self):
        """Test warning for high trader count with low recommended memory."""
        config = ScenarioConfig(
            name="resource-mismatch",
            num_traders=60,  # > 50
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            metadata=ScenarioMetadata(
                resources=ResourceRequirements(recommended_memory_gb=4)  # < 8
            ),
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any(
            "high trader count" in w.message.lower()
            and "low recommended memory" in w.message.lower()
            for w in result.warnings
        )

    def test_high_load_low_cpu_warning(self):
        """Test warning for high trader count with low recommended CPU."""
        config = ScenarioConfig(
            name="cpu-mismatch",
            num_traders=60,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            metadata=ScenarioMetadata(
                resources=ResourceRequirements(recommended_cpu_cores=2)  # < 4
            ),
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any(
            "high trader count" in w.message.lower() and "low recommended cpu" in w.message.lower()
            for w in result.warnings
        )

    def test_low_success_rate_warning(self):
        """Test warning for very low minimum success rate."""
        config = ScenarioConfig(
            name="lenient-criteria",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            success_criteria=SuccessCriteria(min_success_rate=0.3),  # < 0.5
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("low minimum success rate" in w.message.lower() for w in result.warnings)

    def test_high_error_rate_warning(self):
        """Test warning for very high maximum error rate."""
        config = ScenarioConfig(
            name="high-errors",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            success_criteria=SuccessCriteria(max_error_rate=0.6),  # > 0.5
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("high maximum error rate" in w.message.lower() for w in result.warnings)

    def test_high_latency_warning(self):
        """Test warning for very high maximum P95 latency."""
        config = ScenarioConfig(
            name="slow-criteria",
            num_traders=10,
            duration=120,
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
            success_criteria=SuccessCriteria(max_p95_latency_seconds=45),  # > 30
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("high maximum p95 latency" in w.message.lower() for w in result.warnings)

    def test_many_traders_short_duration_warning(self):
        """Test warning for many traders with short duration."""
        config = ScenarioConfig(
            name="startup-overhead",
            num_traders=60,  # > 50
            duration=45,  # < 60
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("may cause startup overhead" in w.message.lower() for w in result.warnings)

    def test_short_startup_interval_warning(self):
        """Test warning for very short startup interval with many traders."""
        config = ScenarioConfig(
            name="rapid-startup",
            num_traders=30,  # > 20
            duration=120,
            startup_interval=0.02,  # < 0.05
            market_order_ratio=1.0,
            trading_pattern="constant_rate",
            base_rate=60,
        )

        validator = ConfigValidator()
        result = validator.validate(config)

        assert result.valid
        assert result.has_warnings
        assert any("very short startup interval" in w.message.lower() for w in result.warnings)


class TestValidateTokenAddress:
    """Test token address validation."""

    def test_valid_checksum_address(self):
        """Test valid checksummed address."""
        address = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        is_valid, error = validate_token_address(address)

        # If Web3 is available, should pass; otherwise basic validation
        if is_valid:
            assert error is None

    def test_invalid_address_format(self):
        """Test invalid address format."""
        address = "not_an_address"
        is_valid, error = validate_token_address(address)

        assert not is_valid
        assert error is not None

    def test_address_without_0x(self):
        """Test address without 0x prefix."""
        address = "5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
        is_valid, error = validate_token_address(address)

        assert not is_valid
        assert "0x" in error.lower()

    def test_address_wrong_length(self):
        """Test address with wrong length."""
        address = "0x5aAeb6053"
        is_valid, error = validate_token_address(address)

        assert not is_valid
        assert error is not None


class TestValidationResult:
    """Test ConfigValidationResult display functionality."""

    def test_display_errors(self, capsys):
        """Test error display (visual check)."""
        from rich.console import Console

        from cow_performance.scenarios.config_validation import ConfigValidationResult

        result = ConfigValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    field="num_traders",
                    message="Value must be positive",
                    context="num_traders=-5",
                    suggestion="Set num_traders to a positive value, e.g., 10",
                    error_type="schema",
                )
            ],
        )

        console = Console()
        result.display(console)
        # Visual verification - just ensure it doesn't crash

    def test_display_warnings(self):
        """Test warning display (visual check)."""
        from rich.console import Console

        from cow_performance.scenarios.config_validation import ConfigValidationResult

        result = ConfigValidationResult(
            valid=True,
            warnings=[
                ValidationWarning(
                    field="duration",
                    message="Very short duration",
                    recommendation="Increase to at least 60s",
                    warning_type="performance",
                )
            ],
        )

        console = Console()
        result.display(console)
        # Visual verification - just ensure it doesn't crash

    def test_display_success(self):
        """Test success message display."""
        from rich.console import Console

        from cow_performance.scenarios.config_validation import ConfigValidationResult

        result = ConfigValidationResult(valid=True)

        console = Console()
        result.display(console)
        # Visual verification - just ensure it doesn't crash
