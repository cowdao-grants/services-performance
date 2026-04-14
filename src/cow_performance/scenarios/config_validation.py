"""Enhanced configuration validation with warnings and semantic checks.

This module provides multi-level validation for scenario configurations:
- Schema validation (handled by Pydantic)
- Semantic validation (logical consistency)
- Reference validation (token addresses, etc.)
- Warning system (performance concerns, best practices)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from cow_performance.cli.commands.scenarios import ScenarioConfig

try:
    from web3 import Web3

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False


@dataclass
class ValidationError:
    """Represents a blocking validation error."""

    field: str
    message: str
    context: str | None = None
    suggestion: str | None = None
    error_type: str = "error"  # error, schema, semantic, reference

    def __str__(self) -> str:
        """Format error as string."""
        parts = [f"Field: {self.field}", f"Error: {self.message}"]
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.suggestion:
            parts.append(f"Fix: {self.suggestion}")
        return "\n".join(parts)


@dataclass
class ValidationWarning:
    """Represents a non-blocking validation warning."""

    field: str
    message: str
    recommendation: str
    warning_type: str = "performance"  # performance, best-practice, resource

    def __str__(self) -> str:
        """Format warning as string."""
        return (
            f"Field: {self.field}\nWarning: {self.message}\nRecommendation: {self.recommendation}"
        )


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def display(self, console: Console) -> None:
        """Display validation result with rich formatting.

        Args:
            console: Rich console for output
        """
        if self.has_errors:
            console.print("\n❌ [bold red]Configuration Validation Failed[/bold red]\n")

            for idx, error in enumerate(self.errors, 1):
                # Create error panel
                error_text = Text()
                error_text.append("Field: ", style="bold")
                error_text.append(f"{error.field}\n", style="cyan")
                error_text.append("Type: ", style="bold")
                error_text.append(f"{error.error_type}\n\n", style="yellow")
                error_text.append(f"Problem: {error.message}\n", style="red")

                if error.context:
                    error_text.append(f"\nContext: {error.context}\n", style="dim")

                if error.suggestion:
                    error_text.append(f"\n💡 Fix: {error.suggestion}", style="green")

                panel = Panel(
                    error_text,
                    title=f"Error {idx}/{len(self.errors)}",
                    border_style="red",
                    expand=False,
                )
                console.print(panel)

        if self.has_warnings:
            console.print("\n⚠️  [bold yellow]Configuration Warnings[/bold yellow]\n")

            # Create warnings table
            table = Table(show_header=True, header_style="bold yellow", expand=True)
            table.add_column("Field", style="cyan")
            table.add_column("Warning", style="yellow")
            table.add_column("Recommendation", style="green")

            for warning in self.warnings:
                table.add_row(
                    warning.field,
                    warning.message,
                    warning.recommendation,
                )

            console.print(table)

        if not self.has_errors and not self.has_warnings:
            console.print("✅ [bold green]Configuration validation passed![/bold green]")


class ConfigValidator:
    """Enhanced configuration validator with semantic checks and warnings."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationWarning] = []

    def validate(self, config: ScenarioConfig) -> ConfigValidationResult:
        """Validate scenario configuration.

        Args:
            config: ScenarioConfig instance to validate

        Returns:
            ConfigValidationResult with errors and warnings
        """
        # Reset state
        self.errors.clear()
        self.warnings.clear()

        # Run validation checks
        self._validate_trader_config(config)
        self._validate_duration(config)
        self._validate_trading_pattern(config)
        self._validate_order_ratios(config)
        self._validate_metadata_consistency(config)
        self._validate_success_criteria(config)

        # Return result
        return ConfigValidationResult(
            valid=len(self.errors) == 0,
            errors=self.errors.copy(),
            warnings=self.warnings.copy(),
        )

    def _validate_trader_config(self, config: ScenarioConfig) -> None:
        """Validate trader configuration.

        Args:
            config: ScenarioConfig instance
        """
        # Check for excessive number of traders
        if config.num_traders > 100:
            self.warnings.append(
                ValidationWarning(
                    field="num_traders",
                    message=f"Very high number of traders: {config.num_traders}",
                    recommendation="Ensure your infrastructure can handle this load. "
                    "Consider starting with fewer traders and ramping up.",
                    warning_type="performance",
                )
            )

        # Check if traders is reasonable for duration
        if config.num_traders > 50 and config.duration < 60:
            self.warnings.append(
                ValidationWarning(
                    field="num_traders / duration",
                    message=f"{config.num_traders} traders in only {config.duration}s may cause startup overhead",
                    recommendation="Consider increasing duration or reducing traders for more stable results.",
                    warning_type="performance",
                )
            )

        # Check startup interval
        if config.startup_interval < 0.05 and config.num_traders > 20:
            self.warnings.append(
                ValidationWarning(
                    field="startup_interval",
                    message=f"Very short startup interval ({config.startup_interval}s) with many traders",
                    recommendation="Consider increasing startup_interval to avoid overwhelming the system during startup.",
                    warning_type="performance",
                )
            )

    def _validate_duration(self, config: ScenarioConfig) -> None:
        """Validate test duration.

        Args:
            config: ScenarioConfig instance
        """
        # Warn about very short tests
        if config.duration < 30:
            self.warnings.append(
                ValidationWarning(
                    field="duration",
                    message=f"Very short test duration: {config.duration}s",
                    recommendation="Tests shorter than 30s may not produce reliable metrics. "
                    "Consider increasing to at least 60s.",
                    warning_type="best-practice",
                )
            )

        # Warn about very long tests
        if config.duration > 3600:
            self.warnings.append(
                ValidationWarning(
                    field="duration",
                    message=f"Very long test duration: {config.duration}s ({config.duration // 60} minutes)",
                    recommendation="Ensure you have sufficient time and resources. "
                    "Long tests may accumulate disk usage and require cleanup.",
                    warning_type="resource",
                )
            )

    def _validate_trading_pattern(self, config: ScenarioConfig) -> None:
        """Validate trading pattern configuration.

        Args:
            config: ScenarioConfig instance
        """
        # Warn about very high rates
        if config.trading_pattern == "constant_rate" and config.base_rate > 1000:
            self.warnings.append(
                ValidationWarning(
                    field="base_rate",
                    message=f"Very high trading rate: {config.base_rate} orders/min ({config.base_rate / 60:.1f} orders/sec)",
                    recommendation="Ensure your infrastructure can handle this load. "
                    "Monitor solver and orderbook performance closely.",
                    warning_type="performance",
                )
            )

        # Validate burst pattern
        if config.trading_pattern == "burst":
            if config.burst_size and config.burst_size > 100:
                self.warnings.append(
                    ValidationWarning(
                        field="burst_size",
                        message=f"Very large burst size: {config.burst_size} orders",
                        recommendation="Large bursts may overwhelm the system. "
                        "Consider breaking into smaller bursts.",
                        warning_type="performance",
                    )
                )

            if config.burst_interval and config.burst_interval < 0.01:
                self.warnings.append(
                    ValidationWarning(
                        field="burst_interval",
                        message=f"Very short burst interval: {config.burst_interval}s",
                        recommendation="Extremely short intervals may cause contention. "
                        "Consider increasing to at least 0.05s.",
                        warning_type="performance",
                    )
                )

        # Validate random interval pattern
        if config.trading_pattern == "random_interval":
            if config.min_interval is not None and config.max_interval is not None:
                interval_range = config.max_interval - config.min_interval
                if interval_range < 0.1:
                    self.warnings.append(
                        ValidationWarning(
                            field="min_interval / max_interval",
                            message=f"Very narrow interval range: {interval_range}s",
                            recommendation="Consider widening the range for more realistic random behavior.",
                            warning_type="best-practice",
                        )
                    )

    def _validate_order_ratios(self, config: ScenarioConfig) -> None:
        """Validate order type ratios.

        Args:
            config: ScenarioConfig instance
        """
        # Check if all ratios are zero (edge case)
        total = config.market_order_ratio + config.limit_order_ratio

        if total == 0:
            self.errors.append(
                ValidationError(
                    field="order_ratios",
                    message="All order type ratios are zero",
                    context="At least one order type must have a non-zero ratio",
                    suggestion="Set at least one order type ratio to a value greater than 0. "
                    "Common: market_order_ratio=0.7, limit_order_ratio=0.3",
                    error_type="semantic",
                )
            )

        # Warn if only one order type is used
        non_zero_ratios = sum(
            1
            for ratio in [
                config.market_order_ratio,
                config.limit_order_ratio,
            ]
            if ratio > 0
        )

        if non_zero_ratios == 1:
            self.warnings.append(
                ValidationWarning(
                    field="order_ratios",
                    message="Only one order type is used",
                    recommendation="Consider using multiple order types for more realistic testing.",
                    warning_type="best-practice",
                )
            )

    def _validate_metadata_consistency(self, config: ScenarioConfig) -> None:
        """Validate metadata consistency with configuration.

        Args:
            config: ScenarioConfig instance
        """
        if config.metadata is None:
            return

        # Check expected duration matches actual duration
        if config.metadata.expected_duration_seconds is not None:
            if config.metadata.expected_duration_seconds != config.duration:
                self.warnings.append(
                    ValidationWarning(
                        field="metadata.expected_duration_seconds",
                        message=f"Expected duration ({config.metadata.expected_duration_seconds}s) "
                        f"doesn't match actual duration ({config.duration}s)",
                        recommendation="Update metadata.expected_duration_seconds to match duration, "
                        "or adjust duration to match expectations.",
                        warning_type="best-practice",
                    )
                )

        # Estimate expected orders and compare
        if config.metadata.expected_orders is not None:
            # Rough estimate: num_traders * duration * base_rate / 60
            if config.trading_pattern == "constant_rate":
                estimated_orders = int(config.num_traders * config.duration * config.base_rate / 60)
                # Allow 50% variance
                if abs(config.metadata.expected_orders - estimated_orders) > estimated_orders * 0.5:
                    self.warnings.append(
                        ValidationWarning(
                            field="metadata.expected_orders",
                            message=f"Expected orders ({config.metadata.expected_orders}) "
                            f"differs significantly from estimated ({estimated_orders})",
                            recommendation=f"Verify expected_orders or adjust test parameters. "
                            f"Estimated: {estimated_orders} orders",
                            warning_type="best-practice",
                        )
                    )

        # Check resource requirements
        if config.metadata.resources:
            resources = config.metadata.resources

            # Warn if high load but low resources
            if config.num_traders > 50:
                if resources.recommended_memory_gb and resources.recommended_memory_gb < 8:
                    self.warnings.append(
                        ValidationWarning(
                            field="metadata.resources.recommended_memory_gb",
                            message=f"High trader count ({config.num_traders}) but low recommended memory ({resources.recommended_memory_gb}GB)",
                            recommendation="Consider increasing recommended_memory_gb to at least 8GB for high-load scenarios.",
                            warning_type="resource",
                        )
                    )

                if resources.recommended_cpu_cores and resources.recommended_cpu_cores < 4:
                    self.warnings.append(
                        ValidationWarning(
                            field="metadata.resources.recommended_cpu_cores",
                            message=f"High trader count ({config.num_traders}) but low recommended CPU ({resources.recommended_cpu_cores} cores)",
                            recommendation="Consider increasing recommended_cpu_cores to at least 4 for high-load scenarios.",
                            warning_type="resource",
                        )
                    )

    def _validate_success_criteria(self, config: ScenarioConfig) -> None:
        """Validate success criteria values.

        Args:
            config: ScenarioConfig instance
        """
        if config.success_criteria is None:
            return

        criteria = config.success_criteria

        # Check if min_success_rate is too lenient
        if criteria.min_success_rate is not None and criteria.min_success_rate < 0.5:
            self.warnings.append(
                ValidationWarning(
                    field="success_criteria.min_success_rate",
                    message=f"Low minimum success rate: {criteria.min_success_rate * 100}%",
                    recommendation="Success rate below 50% may indicate systemic issues. "
                    "Consider setting at least 0.70 (70%).",
                    warning_type="best-practice",
                )
            )

        # Check if max_error_rate is too lenient
        if criteria.max_error_rate is not None and criteria.max_error_rate > 0.5:
            self.warnings.append(
                ValidationWarning(
                    field="success_criteria.max_error_rate",
                    message=f"High maximum error rate: {criteria.max_error_rate * 100}%",
                    recommendation="Error rate above 50% may indicate systemic issues. "
                    "Consider setting at most 0.30 (30%).",
                    warning_type="best-practice",
                )
            )

        # Check if latency is too lenient
        if criteria.max_p95_latency_seconds is not None and criteria.max_p95_latency_seconds > 30:
            self.warnings.append(
                ValidationWarning(
                    field="success_criteria.max_p95_latency_seconds",
                    message=f"High maximum P95 latency: {criteria.max_p95_latency_seconds}s",
                    recommendation="P95 latency above 30s may indicate performance issues. "
                    "Consider setting lower thresholds for better responsiveness.",
                    warning_type="performance",
                )
            )


def validate_token_address(address: str) -> tuple[bool, str | None]:
    """Validate Ethereum address format.

    Args:
        address: Ethereum address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not WEB3_AVAILABLE:
        # If Web3 is not available, do basic validation
        if not address.startswith("0x") or len(address) != 42:
            return False, "Invalid address format (must start with 0x and be 42 characters)"
        return True, None

    # Check if it's a valid checksum address
    if not Web3.is_checksum_address(address):
        if Web3.is_address(address):
            # Valid address but wrong checksum
            checksum_address = Web3.to_checksum_address(address)
            return False, f"Invalid checksum. Use: {checksum_address}"
        else:
            return False, "Invalid Ethereum address format"

    return True, None
