"""Configuration system for the CoW Performance Testing Suite.

This module provides configuration management using pydantic-settings with support
for YAML files and environment variables.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NetworkConfig(BaseSettings):
    """Network configuration for blockchain connection."""

    model_config = SettingsConfigDict(env_prefix="COW_NETWORK_")

    chain_id: int = Field(default=1, description="Chain ID (1=Mainnet, 100=Gnosis)")
    rpc_url: str = Field(
        default="https://eth.llamarpc.com",
        description="RPC endpoint URL",
    )
    settlement_contract: str = Field(
        default="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        description="CoW Protocol settlement contract address",
    )
    composable_cow_contract: str = Field(
        default="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
        description="ComposableCow contract address for conditional orders",
    )
    vault_relayer: str = Field(
        default="0xC92E8bdf79f0507f65a392b0ab4667716BFE0110",
        description="VaultRelayer contract address for token approvals",
    )


class WalletConfig(BaseSettings):
    """Wallet configuration for trader accounts."""

    model_config = SettingsConfigDict(env_prefix="COW_WALLET_")

    # Wallet generation/specification
    generate_count: int = Field(
        default=0,
        ge=0,
        description="Number of new wallets to generate (0 = use default trader pool)",
    )
    private_keys: list[str] = Field(
        default_factory=list,
        description="List of private keys to use (hex strings with 0x prefix)",
    )

    # Funding configuration (requires Anvil fork mode)
    funding_enabled: bool = Field(
        default=False,
        description="Enable automatic wallet funding (requires Anvil RPC with fork mode)",
    )
    eth_balance: float = Field(
        default=10.0,
        gt=0.0,
        description="ETH balance to fund each wallet with (in ETH)",
    )
    token_balances: dict[str, float] = Field(
        default_factory=lambda: {"WETH": 10.0, "DAI": 10000.0},
        description="Token balances to fund (symbol: amount). Supported: WETH, DAI, USDC",
    )

    @field_validator("private_keys")
    @classmethod
    def validate_private_keys(cls, v: list[str]) -> list[str]:
        """Validate that private keys are valid hex strings."""
        for key in v:
            if not key.startswith("0x"):
                raise ValueError(f"Private key must start with 0x: {key[:10]}...")
            if len(key) != 66:  # 0x + 64 hex chars
                raise ValueError(f"Private key must be 66 characters (0x + 64 hex): {key[:10]}...")
        return v


class APIConfig(BaseSettings):
    """API configuration for orderbook interaction."""

    model_config = SettingsConfigDict(env_prefix="COW_API_")

    base_url: str = Field(
        default="http://localhost:8080",
        description="Base URL for CoW Protocol API",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts",
    )


class OutputConfig(BaseSettings):
    """Output formatting configuration."""

    model_config = SettingsConfigDict(env_prefix="COW_OUTPUT_")

    format: str = Field(
        default="json",
        description="Output format: json, table, csv, prometheus",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output",
    )
    save_results: bool = Field(
        default=False,
        description="Save results to file",
    )
    results_dir: Path = Field(
        default=Path(".cow-perf") / "results",
        description="Directory to save results",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate output format."""
        allowed = ["json", "table", "csv", "prometheus"]
        if v not in allowed:
            raise ValueError(f"Output format must be one of: {', '.join(allowed)}")
        return v


class OrderCleanupConfig(BaseSettings):
    """Configuration for order cleanup behavior."""

    model_config = SettingsConfigDict(env_prefix="COW_ORDER_CLEANUP_")

    enabled: bool = Field(
        default=True,
        description="Enable automatic order cleanup/cancellation",
    )
    max_open_orders_per_wallet: int = Field(
        default=50,
        ge=1,
        description="Maximum open orders per wallet before cleanup triggers",
    )
    cleanup_batch_size: int = Field(
        default=10,
        ge=1,
        description="Number of orders to cancel in each cleanup batch",
    )
    cleanup_strategy: str = Field(
        default="oldest_first",
        description="Cleanup strategy: 'oldest_first', 'random', or 'all'",
    )
    check_interval: float = Field(
        default=5.0,
        gt=0.0,
        description="Interval (seconds) to check order count and trigger cleanup",
    )

    @field_validator("cleanup_strategy")
    @classmethod
    def validate_cleanup_strategy(cls, v: str) -> str:
        """Validate cleanup strategy."""
        allowed = ["oldest_first", "random", "all"]
        if v not in allowed:
            raise ValueError(f"Cleanup strategy must be one of: {', '.join(allowed)}")
        return v


class PerformanceTestConfig(BaseSettings):
    """Main configuration for performance testing."""

    model_config = SettingsConfigDict(
        env_prefix="COW_",
        case_sensitive=False,
        extra="allow",  # Allow extra fields like name, description, tags from scenarios
    )

    # Nested configurations
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    wallet: WalletConfig = Field(default_factory=WalletConfig)
    order_cleanup: OrderCleanupConfig = Field(default_factory=OrderCleanupConfig)

    # Scenario metadata (optional, for scenario files)
    name: str | None = Field(default=None, description="Scenario name")
    description: str | None = Field(default=None, description="Scenario description")
    tags: list[str] | None = Field(default=None, description="Scenario tags")
    version: str | None = Field(default=None, description="Scenario version")

    # Default test parameters (support both old and new field names)
    default_trader_count: int = Field(
        default=10,
        ge=1,
        description="Default number of concurrent traders",
    )
    default_duration: int = Field(
        default=60,
        ge=1,
        description="Default test duration in seconds",
    )

    # Aliases for scenario compatibility
    num_traders: int | None = Field(default=None, ge=1, description="Number of concurrent traders (alias for default_trader_count)")
    duration: int | None = Field(default=None, ge=1, description="Test duration in seconds (alias for default_duration)")
    default_startup_interval: float = Field(
        default=0.1,
        ge=0.0,
        description="Default interval between trader startups",
    )

    # Prometheus metrics export
    prometheus_port: int | None = Field(
        default=9091,
        description="Port for Prometheus metrics exporter (None or 0 to disable)",
    )

    # Trading pattern configuration
    trading_pattern: str = Field(
        default="constant_rate",
        description="Trading pattern: constant_rate, random_interval, burst, time_based, ramp_up, ramp_down, spike, poisson",
    )
    base_rate: float = Field(
        default=60.0,
        gt=0.0,
        description="Base order submission rate (orders per minute)",
    )

    # Random interval pattern parameters
    min_interval: float = Field(
        default=5.0,
        gt=0.0,
        description="Minimum interval between orders (seconds, for random_interval pattern)",
    )
    max_interval: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum interval between orders (seconds, for random_interval pattern)",
    )

    # Burst pattern parameters
    burst_size: int = Field(
        default=5,
        ge=1,
        description="Number of orders per burst (for burst pattern)",
    )
    burst_interval: float = Field(
        default=2.0,
        gt=0.0,
        description="Seconds between orders in burst (for burst pattern)",
    )
    quiet_period: float = Field(
        default=60.0,
        gt=0.0,
        description="Seconds between bursts (for burst pattern)",
    )

    # Time-based pattern parameters
    active_hours: list[int] | None = Field(
        default=None,
        description="Hours when more active (0-23, for time_based pattern)",
    )
    active_multiplier: float = Field(
        default=2.0,
        gt=0.0,
        description="Rate multiplier during active hours (for time_based pattern)",
    )

    # Ramp pattern parameters
    ramp_start_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Starting rate for ramp pattern (orders per minute)",
    )
    ramp_target_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Target rate for ramp pattern (orders per minute)",
    )
    ramp_duration: float = Field(
        default=300.0,
        gt=0.0,
        description="Duration of ramp in seconds (for ramp_up/ramp_down patterns)",
    )
    ramp_curve: str = Field(
        default="linear",
        description="Ramp curve type: linear or exponential (for ramp_up/ramp_down patterns)",
    )

    # Spike pattern parameters
    spike_normal_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Normal rate for spike pattern (orders per minute)",
    )
    spike_burst_rate: float | None = Field(
        default=None,
        gt=0.0,
        description="Burst rate for spike pattern (orders per minute)",
    )
    spike_duration: float = Field(
        default=30.0,
        gt=0.0,
        description="Duration of spike in seconds (for spike pattern)",
    )
    spike_recovery_time: float = Field(
        default=60.0,
        gt=0.0,
        description="Time between spikes in seconds (for spike pattern)",
    )

    # Poisson pattern parameters
    poisson_lambda: float | None = Field(
        default=None,
        gt=0.0,
        description="Lambda parameter for Poisson distribution (events per minute)",
    )

    # Rate limiting configuration
    enable_global_rate_limit: bool = Field(
        default=False,
        description="Enable global rate limiting across all traders",
    )
    max_orders_global_per_second: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum orders per second globally",
    )
    max_orders_global_per_minute: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum orders per minute globally",
    )

    enable_per_trader_rate_limit: bool = Field(
        default=False,
        description="Enable per-trader rate limiting",
    )
    max_orders_per_trader_per_second: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum orders per second per trader",
    )
    max_orders_per_trader_per_minute: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum orders per minute per trader",
    )

    rate_limit_burst_allowance: float = Field(
        default=1.5,
        gt=0.0,
        description="Burst allowance multiplier for rate limiting (e.g., 1.5 = 50% burst)",
    )

    # Order type ratios (defaults that sum to 1.0)
    market_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    limit_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    twap_order_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    stop_loss_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    good_after_time_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)

    # Order amount configuration (in token units)
    min_order_amount: float = Field(
        default=0.1,
        gt=0.0,
        description="Minimum order amount in token units (ETH, DAI, etc.)",
    )
    max_order_amount: float = Field(
        default=10.0,
        gt=0.0,
        description="Maximum order amount in token units (ETH, DAI, etc.)",
    )

    @field_validator("trading_pattern")
    @classmethod
    def validate_trading_pattern(cls, v: str) -> str:
        """Validate trading pattern."""
        allowed = [
            "constant_rate",
            "random_interval",
            "burst",
            "time_based",
            "ramp_up",
            "ramp_down",
            "spike",
            "poisson",
        ]
        if v not in allowed:
            raise ValueError(f"Trading pattern must be one of: {', '.join(allowed)}")
        return v

    @field_validator("ramp_curve")
    @classmethod
    def validate_ramp_curve(cls, v: str) -> str:
        """Validate ramp curve type."""
        allowed = ["linear", "exponential"]
        if v not in allowed:
            raise ValueError(f"Ramp curve must be one of: {', '.join(allowed)}")
        return v

    @field_validator(
        "market_order_ratio",
        "limit_order_ratio",
        "twap_order_ratio",
        "stop_loss_order_ratio",
        "good_after_time_order_ratio",
    )
    @classmethod
    def validate_ratio(cls, v: float) -> float:
        """Validate that ratio is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Ratio must be between 0.0 and 1.0")
        return v

    def validate_ratio_sum(self) -> None:
        """Validate that all order type ratios sum to 1.0."""
        total = (
            self.market_order_ratio
            + self.limit_order_ratio
            + self.twap_order_ratio
            + self.stop_loss_order_ratio
            + self.good_after_time_order_ratio
        )
        if abs(total - 1.0) > 0.001:  # Allow for floating point precision
            raise ValueError(
                f"Order type ratios must sum to 1.0, got {total}. "
                f"Adjust the ratios in your configuration."
            )

    @model_validator(mode="before")
    @classmethod
    def map_scenario_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Map scenario field names to config field names for compatibility.

        This allows scenarios to use 'num_traders' and 'duration' while the config
        internally uses 'default_trader_count' and 'default_duration'.
        """
        if isinstance(values, dict):
            # Map num_traders -> default_trader_count
            if "num_traders" in values and "default_trader_count" not in values:
                values["default_trader_count"] = values["num_traders"]

            # Map duration -> default_duration
            if "duration" in values and "default_duration" not in values:
                values["default_duration"] = values["duration"]

        return values


def find_config_file() -> Path | None:
    """Find the configuration file.

    Search order:
    1. ./.cow-perf.yml (current directory)
    2. ~/.cow-perf.yml (home directory)

    Returns:
        Path to config file if found, None otherwise
    """
    # Check current directory
    local_config = Path(".cow-perf.yml")
    if local_config.exists():
        return local_config

    # Check home directory
    home_config = Path.home() / ".cow-perf.yml"
    if home_config.exists():
        return home_config

    return None


def load_config_from_yaml(config_path: Path) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with configuration values

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    if config_data is None:
        return {}

    if not isinstance(config_data, dict):
        raise ValueError(f"Configuration file must contain a YAML object, got {type(config_data)}")

    return config_data


def load_config(config_path: Path | None = None) -> PerformanceTestConfig:
    """Load configuration from file and environment variables.

    Args:
        config_path: Optional path to config file. If None, searches for config file.

    Returns:
        Loaded configuration object

    Raises:
        FileNotFoundError: If specified config file doesn't exist
        ValueError: If configuration is invalid
    """
    # Find config file if not specified
    if config_path is None:
        config_path = find_config_file()

    # Load from YAML if config file exists
    if config_path is not None:
        yaml_config = load_config_from_yaml(config_path)
    else:
        yaml_config = {}

    # Create config (environment variables will override YAML values)
    config = PerformanceTestConfig(**yaml_config)

    # Validate ratio sum
    config.validate_ratio_sum()

    return config


def save_config_template(output_path: Path) -> None:
    """Save a template configuration file.

    Args:
        output_path: Path where to save the template
    """
    template = """# CoW Performance Testing Suite Configuration

# Network settings
network:
  chain_id: 1  # 1=Mainnet, 100=Gnosis Chain
  rpc_url: "https://eth.llamarpc.com"
  settlement_contract: "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
  composable_cow_contract: "0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74"
  vault_relayer: "0xC92E8bdf79f0507f65a392b0ab4667716BFE0110"

# API settings
api:
  base_url: "http://localhost:8080"
  timeout: 30
  max_retries: 3

# Output settings
output:
  format: "json"  # json, table, csv, prometheus
  verbose: false
  save_results: false
  results_dir: ".cow-perf/results"

# Wallet configuration for trader accounts
wallet:
  # Wallet generation/specification
  generate_count: 0  # Number of wallets to generate (0 = use default trader pool)
  private_keys: []   # List of private keys to use (hex with 0x prefix)
  # Example:
  # private_keys:
  #   - "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
  #   - "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"

  # Automatic funding (requires Anvil fork mode)
  funding_enabled: false  # Enable to fund wallets automatically
  eth_balance: 10.0       # ETH per wallet
  token_balances:         # Token amounts per wallet
    WETH: 10.0           # 10 WETH
    DAI: 10000.0         # 10,000 DAI
    USDC: 5000.0         # 5,000 USDC

# Default test parameters
default_trader_count: 10
default_duration: 60
default_startup_interval: 0.1

# Trading pattern configuration
# Available patterns: constant_rate, random_interval, burst, time_based,
#                     ramp_up, ramp_down, spike, poisson
trading_pattern: "constant_rate"
base_rate: 60.0  # Orders per minute

# Random interval pattern (for trading_pattern: random_interval)
min_interval: 5.0   # Minimum seconds between orders
max_interval: 30.0  # Maximum seconds between orders

# Burst pattern (for trading_pattern: burst)
burst_size: 5           # Orders per burst
burst_interval: 2.0     # Seconds between orders in burst
quiet_period: 60.0      # Seconds between bursts

# Time-based pattern (for trading_pattern: time_based)
# active_hours: [9, 10, 11, 12, 13, 14, 15, 16]  # Active during business hours
active_multiplier: 2.0  # Rate multiplier during active hours

# Ramp patterns (for trading_pattern: ramp_up or ramp_down)
# Gradually increase (ramp_up) or decrease (ramp_down) submission rate
# Example: Start at 6 orders/min, ramp up to 60 orders/min over 5 minutes
# ramp_start_rate: 6.0      # Orders per minute at start
# ramp_target_rate: 60.0    # Orders per minute at end
# ramp_duration: 300.0      # Duration in seconds (300s = 5 min)
# ramp_curve: "linear"      # "linear" or "exponential"

# Spike pattern (for trading_pattern: spike)
# Sudden bursts of activity followed by recovery periods
# Example: Normal 10 orders/min, spike to 100 orders/min for 30s, recover for 60s
# spike_normal_rate: 10.0   # Normal orders per minute
# spike_burst_rate: 100.0   # Burst orders per minute
# spike_duration: 30.0      # Duration of spike in seconds
# spike_recovery_time: 60.0 # Time between spikes in seconds

# Poisson pattern (for trading_pattern: poisson)
# Statistically realistic random intervals following Poisson distribution
# Example: Average 30 orders per minute with natural variation
# poisson_lambda: 30.0      # Events per minute (rate parameter)

# Rate limiting configuration
# Helps avoid API rate limits and simulate realistic load
enable_global_rate_limit: false
# max_orders_global_per_second: 10.0     # Global limit across all traders
# max_orders_global_per_minute: 600.0    # Alternative: per-minute limit

enable_per_trader_rate_limit: false
# max_orders_per_trader_per_second: 2.0  # Per-trader limit
# max_orders_per_trader_per_minute: 120.0 # Alternative: per-minute limit

rate_limit_burst_allowance: 1.5  # Allow bursts up to 1.5x sustained rate

# Order type ratios (must sum to 1.0)
market_order_ratio: 0.4
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.05
good_after_time_order_ratio: 0.05

# Order cleanup configuration
order_cleanup:
  enabled: true
  max_open_orders_per_wallet: 50
  cleanup_batch_size: 10
  cleanup_strategy: "oldest_first"
  check_interval: 5.0
"""

    with open(output_path, "w") as f:
        f.write(template)
