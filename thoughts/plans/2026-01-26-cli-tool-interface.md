# M1-Issue-05: CLI Tool Interface Implementation Plan

## Overview

Implement a functional command-line interface (CLI) tool that provides an intuitive interface for running performance tests, managing configurations, and viewing real-time progress. The CLI will integrate with the existing load generation module (TraderOrchestrator) and provide structured output suitable for both automated reports and Prometheus/Grafana monitoring.

## Current State Analysis

### What Exists:
- Basic CLI skeleton at `src/cow_performance/cli/main.py:1-75` with Typer framework
- Placeholder commands: `version`, `run`, `scenarios`, `baselines`, `config`
- CLI entry point configured: `cow-perf` command in `pyproject.toml:55`
- Rich library installed and partially used for colored output
- Comprehensive load generation module ready for integration:
  - `TraderOrchestrator` for running multi-trader simulations
  - `OrderFactory` and `ConditionalOrderFactory` for order generation
  - `TraderPool` for managing multiple trader accounts
  - `OrderTracker` for metrics collection

### What's Missing:
- Actual implementation of CLI commands (currently just print placeholders)
- YAML-based configuration file support with validation
- Integration with TraderOrchestrator for running tests
- Real-time progress display during test execution
- Structured output formatting (JSON for automation, tables for humans)
- Graceful error handling and user feedback
- Configuration discovery and environment variable support

### Key Discoveries:

**1. TraderOrchestrator is ready** (`trader_orchestrator.py:45-382`):
- Async execution with `asyncio.gather()`
- Automatic trader restart on failure
- Staggered startup to prevent thundering herd
- Comprehensive metrics collection
- Graceful shutdown support

**2. Configuration pattern** (`trader_simulator.py:31-86`, `trader_orchestrator.py:21-35`):
- Existing configs use dataclasses with `__post_init__` validation
- `pydantic-settings` installed but not used yet
- Manual `os.getenv()` for environment variables

**3. Testing pattern** (`tests/unit/test_cli.py:1-47`):
- Uses `CliRunner` from `typer.testing`
- Simple assertions on exit code and stdout

## Desired End State

After this plan is complete:

1. **Working CLI Commands**:
   - `cow-perf run --scenario <path>` executes performance tests
   - `cow-perf scenarios validate <file>` validates scenario YAML
   - `cow-perf baselines save/list/show` manages baseline results
   - `cow-perf config show/init/validate` manages configuration
   - `cow-perf version` shows version and dependencies

2. **Configuration System**:
   - YAML configuration file support (`.cow-perf.yml`)
   - Configuration discovery (current dir → home dir → defaults)
   - Environment variable overrides for all settings
   - Pydantic validation with helpful error messages

3. **Structured Output**:
   - JSON format (primary) for automation/Prometheus
   - Human-readable Rich tables for terminal display
   - File output support (`--output results.json`)
   - Metrics compatible with Prometheus/Grafana

4. **User Experience**:
   - Real-time progress bars during test execution
   - Graceful Ctrl+C handling
   - Clear, actionable error messages
   - `--verbose` flag for detailed logs
   - `--dry-run` flag to validate without executing

### Verification:

**Automated:**
- `cow-perf version` returns exit code 0 and version string
- `cow-perf run` with valid config executes test and returns metrics
- `cow-perf config validate` catches invalid configuration
- All CLI tests pass: `pytest tests/unit/test_cli.py -v`
- Type checking passes: `mypy src/cow_performance/cli/`

**Manual:**
- Run `cow-perf run --scenario scenarios/light-load.yml` completes successfully
- Progress bar updates during execution
- Ctrl+C stops test gracefully
- JSON output can be parsed by jq
- Table output is readable in terminal

## What We're NOT Doing

**Out of scope for M1-05:**
- Scenario library implementation (deferred to M1-06)
- Baseline comparison and regression detection (deferred to M2-08)
- Built-in scenario templates (M1-06)
- Prometheus exporter integration (M3)
- Grafana dashboard creation (M3)
- Docker container packaging (later)
- CI/CD pipeline integration (later)

**Why these are out of scope:**
- Scenario library is explicitly M1-06's responsibility
- Baseline comparison is M2-08's scope
- Monitoring integration is M3's scope
- Focus M1-05 on core CLI functionality and configuration

## Implementation Approach

**Strategy:**
1. Start with configuration system (foundation for everything else)
2. Implement `run` command next (highest priority, core functionality)
3. Add scenario validation (prepare for M1-06)
4. Implement basic baseline management (foundation for M2-08)
5. Polish error handling and output formatting
6. Comprehensive testing throughout

**Technical decisions:**
- Use `pydantic-settings` for configuration (already installed, type-safe)
- YAML only (not JSON/TOML) to reduce complexity
- JSON as primary output format (Prometheus-compatible)
- Rich tables as secondary format (human-friendly)
- `asyncio.run()` to bridge sync CLI and async TraderOrchestrator

---

## Phase 1: Configuration System

### Overview

Create a YAML-based configuration system using pydantic-settings that supports file discovery, environment variable overrides, and comprehensive validation.

### Changes Required:

#### 1. Configuration Schema (`src/cow_performance/cli/config.py` - NEW FILE)

**File**: `src/cow_performance/cli/config.py`
**Changes**: Create new configuration module

```python
"""Configuration management for CoW Performance Testing Suite."""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from web3 import Web3


class NetworkConfig(BaseSettings):
    """Network and blockchain configuration."""

    model_config = SettingsConfigDict(
        env_prefix="COW_",
        env_file=".env",
        case_sensitive=False,
    )

    eth_rpc_url: str = Field(
        default="http://localhost:8545",
        description="Ethereum RPC endpoint URL"
    )
    chain_id: int = Field(
        default=1,
        description="Chain ID (1=Ethereum, 100=Gnosis)"
    )
    settlement_contract: str = Field(
        default="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
        description="CoW Protocol settlement contract address"
    )
    composable_cow_contract: str = Field(
        default="0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
        description="ComposableCow contract address"
    )

    @field_validator("settlement_contract", "composable_cow_contract")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)


class APIConfig(BaseSettings):
    """API endpoint configuration."""

    model_config = SettingsConfigDict(
        env_prefix="COW_",
        env_file=".env",
        case_sensitive=False,
    )

    orderbook_api_url: str = Field(
        default="http://localhost:8080",
        description="CoW Protocol orderbook API URL"
    )
    autopilot_api_url: str = Field(
        default="http://localhost:9000",
        description="Autopilot API URL"
    )


class PerformanceTestConfig(BaseSettings):
    """Main configuration for performance testing."""

    model_config = SettingsConfigDict(
        env_prefix="COW_",
        env_file=".env",
        case_sensitive=False,
        yaml_file="cow-perf.yml",  # Will load if exists
    )

    # Nested configs
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    # Test configuration
    default_trader_count: int = Field(
        default=10,
        description="Default number of concurrent traders"
    )
    default_duration: int = Field(
        default=60,
        description="Default test duration in seconds"
    )
    default_startup_interval: float = Field(
        default=0.5,
        description="Seconds between trader startups"
    )

    # Output configuration
    output_dir: Path = Field(
        default=Path("results"),
        description="Directory for test results"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v_upper


def find_config_file() -> Path | None:
    """
    Find configuration file in standard locations.

    Search order:
    1. ./.cow-perf.yml (current directory)
    2. ~/.cow-perf.yml (home directory)

    Returns:
        Path to config file or None if not found
    """
    locations = [
        Path.cwd() / ".cow-perf.yml",
        Path.home() / ".cow-perf.yml",
    ]

    for path in locations:
        if path.exists():
            return path

    return None


def load_config(config_file: Path | None = None) -> PerformanceTestConfig:
    """
    Load configuration from file and environment.

    Args:
        config_file: Optional path to config file. If None, searches standard locations.

    Returns:
        Validated configuration

    Raises:
        FileNotFoundError: If specified config file doesn't exist
        ValueError: If configuration is invalid
    """
    if config_file is None:
        config_file = find_config_file()

    if config_file is not None:
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        # Load YAML and merge with env vars
        import yaml
        with open(config_file) as f:
            config_data = yaml.safe_load(f) or {}

        return PerformanceTestConfig(**config_data)

    # No config file, use defaults + env vars
    return PerformanceTestConfig()


def create_default_config_file(path: Path) -> None:
    """
    Create a default configuration file.

    Args:
        path: Path where to create the config file
    """
    import yaml

    default_config = {
        "network": {
            "eth_rpc_url": "http://localhost:8545",
            "chain_id": 1,
            "settlement_contract": "0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
            "composable_cow_contract": "0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74",
        },
        "api": {
            "orderbook_api_url": "http://localhost:8080",
            "autopilot_api_url": "http://localhost:9000",
        },
        "default_trader_count": 10,
        "default_duration": 60,
        "default_startup_interval": 0.5,
        "output_dir": "results",
        "log_level": "INFO",
    }

    with open(path, "w") as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
```

#### 2. Config Commands (`src/cow_performance/cli/main.py`)

**File**: `src/cow_performance/cli/main.py`
**Changes**: Implement config subcommands

```python
# Add to imports
from .config import (
    PerformanceTestConfig,
    create_default_config_file,
    find_config_file,
    load_config,
)

@app.command()
def config(
    action: str = typer.Argument(..., help="Action: show, init, or validate"),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Config file path"
    ),
) -> None:
    """Manage configuration.

    Actions:
        show - Display current configuration
        init - Create default configuration file
        validate - Validate configuration file
    """
    if action == "show":
        try:
            cfg = load_config(Path(config_file) if config_file else None)
            console.print("[bold green]Current Configuration:[/bold green]\n")

            # Display as YAML for readability
            import yaml
            config_dict = cfg.model_dump()
            console.print(yaml.dump(config_dict, default_flow_style=False))
        except Exception as e:
            console.print(f"[red]Error loading config:[/red] {e}")
            raise typer.Exit(1)

    elif action == "init":
        path = Path(config_file) if config_file else Path.cwd() / ".cow-perf.yml"

        if path.exists():
            console.print(f"[yellow]Warning:[/yellow] Config file already exists: {path}")
            overwrite = typer.confirm("Overwrite?")
            if not overwrite:
                console.print("Cancelled")
                return

        try:
            create_default_config_file(path)
            console.print(f"[green]✓[/green] Created config file: {path}")
        except Exception as e:
            console.print(f"[red]Error creating config:[/red] {e}")
            raise typer.Exit(1)

    elif action == "validate":
        if not config_file:
            console.print("[red]Error:[/red] --config required for validate")
            raise typer.Exit(1)

        path = Path(config_file)
        try:
            load_config(path)
            console.print(f"[green]✓[/green] Configuration valid: {path}")
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] Config file not found: {path}")
            raise typer.Exit(2)
        except Exception as e:
            console.print(f"[red]Validation Error:[/red] {e}")
            raise typer.Exit(3)

    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Valid actions: show, init, validate")
        raise typer.Exit(1)
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_config.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/config.py`
- [ ] Linting passes: `ruff check src/cow_performance/cli/config.py`
- [ ] Config can be loaded from YAML file
- [ ] Environment variables override file config
- [ ] Invalid config raises clear validation errors

#### Manual Verification:
- [ ] Run `cow-perf config init` creates `.cow-perf.yml`
- [ ] Run `cow-perf config show` displays current config
- [ ] Run `cow-perf config validate invalid.yml` shows helpful error
- [ ] Set `COW_CHAIN_ID=100` and verify it overrides file config
- [ ] Invalid address in config shows clear validation error

---

## Phase 2: Run Command Implementation

### Overview

Implement the `run` command to execute performance tests by integrating with TraderOrchestrator. Include real-time progress display, graceful shutdown, and structured output.

### Changes Required:

#### 1. Run Command Core (`src/cow_performance/cli/commands/run.py` - NEW FILE)

**File**: `src/cow_performance/cli/commands/run.py`
**Changes**: Create run command module

```python
"""Run command implementation."""

import asyncio
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from cow_performance.load_generation import (
    ConditionalOrderFactory,
    ConditionalOrderSigner,
    OrderFactory,
    OrderSigner,
    OrderTracker,
    OrchestrationConfig,
    TraderBehaviorConfig,
    TraderOrchestrator,
    TraderPool,
    TradingPattern,
    create_mainnet_token_registry,
)
from ..config import PerformanceTestConfig, load_config

console = Console()


class GracefulShutdown:
    """Handle graceful shutdown on Ctrl+C."""

    def __init__(self) -> None:
        self.shutdown_requested = False
        self.orchestrator: TraderOrchestrator | None = None

    def request_shutdown(self, signum: int, frame: Any) -> None:
        """Signal handler for graceful shutdown."""
        if not self.shutdown_requested:
            console.print("\n[yellow]Shutdown requested... stopping traders gracefully[/yellow]")
            self.shutdown_requested = True

            if self.orchestrator:
                # Trigger async shutdown
                asyncio.create_task(self.orchestrator.stop())
        else:
            console.print("\n[red]Force shutdown[/red]")
            sys.exit(1)


async def run_performance_test(
    scenario_config: dict[str, Any],
    app_config: PerformanceTestConfig,
    duration: int | None = None,
    traders: int | None = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run a performance test.

    Args:
        scenario_config: Scenario configuration from YAML
        app_config: Application configuration
        duration: Override duration in seconds
        traders: Override number of traders
        verbose: Enable verbose output
        dry_run: Validate without executing

    Returns:
        Test metrics dictionary
    """
    # Extract scenario parameters with overrides
    num_traders = traders or scenario_config.get("num_traders", app_config.default_trader_count)
    test_duration = duration or scenario_config.get("duration", app_config.default_duration)
    startup_interval = scenario_config.get("startup_interval", app_config.default_startup_interval)

    if verbose:
        console.print(f"[dim]Configuration:[/dim]")
        console.print(f"[dim]  Traders: {num_traders}[/dim]")
        console.print(f"[dim]  Duration: {test_duration}s[/dim]")
        console.print(f"[dim]  API: {app_config.api.orderbook_api_url}[/dim]")

    if dry_run:
        console.print("[yellow]Dry run mode - validation only[/yellow]")
        return {"status": "dry_run", "valid": True}

    # Create components
    token_registry = create_mainnet_token_registry()
    trader_pool = TraderPool(num_traders=num_traders)

    order_factory = OrderFactory(
        token_pair_registry=token_registry,
        chain_id=app_config.network.chain_id,
        settlement_contract=app_config.network.settlement_contract,
    )

    # For now, use a dummy safe address (will be improved in future)
    dummy_safe = "0x0000000000000000000000000000000000000001"
    conditional_order_factory = ConditionalOrderFactory(
        token_pair_registry=token_registry,
        chain_id=app_config.network.chain_id,
        safe_wallet_address=dummy_safe,
    )

    order_signer = OrderSigner(
        chain_id=app_config.network.chain_id,
        settlement_contract=app_config.network.settlement_contract,
    )

    conditional_order_signer = ConditionalOrderSigner(
        chain_id=app_config.network.chain_id,
        composable_cow_contract=app_config.network.composable_cow_contract,
    )

    order_tracker = OrderTracker(
        poll_interval=5.0,
        max_poll_attempts=60,
    )

    # Create behavior config from scenario
    behavior_config = TraderBehaviorConfig(
        pattern=TradingPattern.CONSTANT_RATE,
        base_rate=scenario_config.get("orders_per_minute", 6.0),
        market_order_ratio=scenario_config.get("market_order_ratio", 0.4),
        limit_order_ratio=scenario_config.get("limit_order_ratio", 0.4),
        twap_order_ratio=scenario_config.get("twap_order_ratio", 0.1),
        stop_loss_order_ratio=scenario_config.get("stop_loss_order_ratio", 0.05),
        good_after_time_order_ratio=scenario_config.get("good_after_time_order_ratio", 0.05),
    )

    orchestration_config = OrchestrationConfig(
        num_traders=num_traders,
        duration=float(test_duration),
        startup_interval=startup_interval,
        restart_on_failure=True,
        max_restarts_per_trader=3,
    )

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
    )

    # Setup graceful shutdown
    shutdown_handler = GracefulShutdown()
    shutdown_handler.orchestrator = orchestrator
    signal.signal(signal.SIGINT, shutdown_handler.request_shutdown)

    # Display progress
    console.print(f"\n[bold green]Starting performance test...[/bold green]")
    console.print(f"[dim]Traders: {num_traders} | Duration: {test_duration}s | Pattern: CONSTANT_RATE[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running test...", total=test_duration)

        # Run test in background
        test_task = asyncio.create_task(orchestrator.run())

        # Update progress
        start_time = time.time()
        while not test_task.done():
            elapsed = time.time() - start_time
            progress.update(task, completed=min(elapsed, test_duration))

            if shutdown_handler.shutdown_requested:
                break

            await asyncio.sleep(0.5)

        # Wait for completion
        try:
            await test_task
        except asyncio.CancelledError:
            pass

        progress.update(task, completed=test_duration, description="[green]Test complete")

    # Get metrics
    metrics = orchestrator.get_metrics()
    return metrics


def display_results_table(metrics: dict[str, Any]) -> None:
    """Display test results as a formatted table."""
    table = Table(title="Performance Test Results", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    # Orchestration metrics
    orch = metrics["orchestration"]
    table.add_row("Traders", str(orch["num_traders"]))
    table.add_row("Duration", f"{orch['elapsed_time']:.2f}s")
    table.add_row("Restarts", str(orch["total_restarts"]))

    # Order metrics
    orders = metrics["orders"]
    table.add_row("", "")  # Separator
    table.add_row("Total Submitted", str(orders["total_submitted"]))
    table.add_row("Orders Filled", str(orders["orders_filled"]))
    table.add_row("Orders Failed", str(orders["orders_failed"]))
    table.add_row("Orders Expired", str(orders["orders_expired"]))

    # Performance metrics
    perf = metrics["performance"]
    table.add_row("", "")  # Separator
    table.add_row("Orders/Second", f"{perf['orders_per_second']:.2f}")

    if perf.get("avg_time_to_fill"):
        table.add_row("Avg Time to Fill", f"{perf['avg_time_to_fill']:.2f}s")

    console.print("\n")
    console.print(table)
    console.print("\n")


def save_results(metrics: dict[str, Any], output_path: Path) -> None:
    """Save test results to file."""
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)

    console.print(f"[green]✓[/green] Results saved to: {output_path}")
```

#### 2. Update Main CLI (`src/cow_performance/cli/main.py`)

**File**: `src/cow_performance/cli/main.py`
**Changes**: Replace run command placeholder

```python
from .commands.run import run_performance_test, display_results_table, save_results

@app.command()
def run(
    scenario: str = typer.Argument(..., help="Scenario name or path to YAML file"),
    duration: Optional[int] = typer.Option(
        None, "--duration", "-d", help="Override scenario duration (seconds)"
    ),
    traders: Optional[int] = typer.Option(
        None, "--traders", "-t", help="Override number of concurrent traders"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for results (JSON)"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Config file path"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate without executing"
    ),
) -> None:
    """Run a performance test scenario."""
    import asyncio
    from pathlib import Path

    try:
        # Load application config
        app_config = load_config(Path(config_file) if config_file else None)

        # Load scenario config
        scenario_path = Path(scenario)
        if not scenario_path.exists():
            console.print(f"[red]Error:[/red] Scenario file not found: {scenario}")
            raise typer.Exit(2)

        with open(scenario_path) as f:
            scenario_config = yaml.safe_load(f)

        if not scenario_config:
            console.print(f"[red]Error:[/red] Empty scenario file: {scenario}")
            raise typer.Exit(3)

        # Run test
        metrics = asyncio.run(run_performance_test(
            scenario_config=scenario_config,
            app_config=app_config,
            duration=duration,
            traders=traders,
            verbose=verbose,
            dry_run=dry_run,
        ))

        # Display results
        if not dry_run:
            display_results_table(metrics)

        # Save to file if requested
        if output:
            save_results(metrics, Path(output))

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(2)
    except ValueError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(3)
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        raise typer.Exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        console.print(f"[red]Unexpected Error:[/red] {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_cli_run.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/commands/run.py`
- [ ] Linting passes: `ruff check src/cow_performance/cli/commands/`
- [ ] Run command executes with valid scenario
- [ ] Invalid scenario file returns exit code 2
- [ ] Metrics structure matches expected format

#### Manual Verification:
- [ ] Run `cow-perf run scenario.yml` completes successfully
- [ ] Progress bar updates every 0.5 seconds
- [ ] Press Ctrl+C gracefully stops test
- [ ] Second Ctrl+C force quits
- [ ] `--output results.json` creates valid JSON file
- [ ] `--verbose` shows detailed configuration
- [ ] `--dry-run` validates without executing
- [ ] Results table displays correctly in terminal

---

## Phase 3: Scenario Management Foundation

### Overview

Implement basic scenario file validation and loading to prepare for M1-06's full scenario library implementation.

### Changes Required:

#### 1. Scenario Validation (`src/cow_performance/cli/commands/scenarios.py` - NEW FILE)

**File**: `src/cow_performance/cli/commands/scenarios.py`
**Changes**: Create scenario management module

```python
"""Scenario management commands."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator
from rich.console import Console

console = Console()


class ScenarioConfig(BaseModel):
    """Schema for scenario configuration files."""

    name: str = Field(..., description="Scenario name")
    description: str = Field(..., description="Scenario description")

    # Test parameters
    num_traders: int = Field(default=10, ge=1, description="Number of concurrent traders")
    duration: int = Field(default=60, ge=1, description="Test duration in seconds")
    startup_interval: float = Field(default=0.5, ge=0.0, description="Startup interval")

    # Order type distribution
    orders_per_minute: float = Field(default=6.0, gt=0.0, description="Order rate")
    market_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    limit_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    twap_order_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    stop_loss_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    good_after_time_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)

    @field_validator("market_order_ratio", "limit_order_ratio", "twap_order_ratio",
                     "stop_loss_order_ratio", "good_after_time_order_ratio")
    @classmethod
    def validate_ratio_sum(cls, v: float, info: Any) -> float:
        """Validate that order type ratios sum to 1.0."""
        # This validator runs after all fields are set
        if hasattr(info, 'data'):
            values = info.data
            total = (
                values.get("market_order_ratio", 0) +
                values.get("limit_order_ratio", 0) +
                values.get("twap_order_ratio", 0) +
                values.get("stop_loss_order_ratio", 0) +
                values.get("good_after_time_order_ratio", 0)
            )
            if not 0.99 <= total <= 1.01:  # Allow small floating point error
                raise ValueError(f"Order type ratios must sum to 1.0, got {total}")
        return v


def validate_scenario_file(scenario_path: Path) -> tuple[bool, list[str]]:
    """
    Validate a scenario file.

    Args:
        scenario_path: Path to scenario YAML file

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check file exists
    if not scenario_path.exists():
        return False, [f"File not found: {scenario_path}"]

    # Check file extension
    if scenario_path.suffix not in [".yml", ".yaml"]:
        errors.append(f"Invalid file extension: {scenario_path.suffix}. Expected .yml or .yaml")

    # Parse YAML
    try:
        with open(scenario_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, [f"Invalid YAML: {e}"]

    if not data:
        return False, ["Empty scenario file"]

    # Validate against schema
    try:
        ScenarioConfig(**data)
    except Exception as e:
        errors.append(f"Validation error: {e}")

    return len(errors) == 0, errors


def list_scenarios(scenarios_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    List available scenario files.

    Args:
        scenarios_dir: Directory to search for scenarios. If None, uses default.

    Returns:
        List of scenario metadata
    """
    if scenarios_dir is None:
        # Default locations to search
        scenarios_dir = Path.cwd() / "scenarios"

    if not scenarios_dir.exists():
        return []

    scenarios = []
    for path in scenarios_dir.glob("*.{yml,yaml}"):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            scenarios.append({
                "path": str(path),
                "name": data.get("name", path.stem),
                "description": data.get("description", "No description"),
            })
        except Exception:
            # Skip invalid files
            continue

    return scenarios
```

#### 2. Update Main CLI (`src/cow_performance/cli/main.py`)

**File**: `src/cow_performance/cli/main.py`
**Changes**: Replace scenarios command

```python
from .commands.scenarios import validate_scenario_file, list_scenarios

@app.command()
def scenarios(
    action: str = typer.Argument("list", help="Action: list, validate"),
    scenario_file: Optional[str] = typer.Argument(None, help="Scenario file to validate"),
) -> None:
    """Manage test scenarios.

    Actions:
        list - List available scenarios
        validate - Validate a scenario file
    """
    if action == "list":
        scenarios_list = list_scenarios()

        if not scenarios_list:
            console.print("[yellow]No scenarios found in ./scenarios/[/yellow]")
            console.print("\n[dim]Create scenarios in ./scenarios/ directory[/dim]")
            return

        console.print("[bold green]Available Scenarios:[/bold green]\n")
        for scenario in scenarios_list:
            console.print(f"  [cyan]{scenario['name']}[/cyan]")
            console.print(f"    Path: {scenario['path']}")
            console.print(f"    {scenario['description']}\n")

    elif action == "validate":
        if not scenario_file:
            console.print("[red]Error:[/red] scenario file required for validate")
            raise typer.Exit(1)

        path = Path(scenario_file)
        is_valid, errors = validate_scenario_file(path)

        if is_valid:
            console.print(f"[green]✓[/green] Scenario valid: {path}")
        else:
            console.print(f"[red]✗[/red] Scenario invalid: {path}\n")
            for error in errors:
                console.print(f"  [red]•[/red] {error}")
            raise typer.Exit(3)

    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Valid actions: list, validate")
        raise typer.Exit(1)
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_cli_scenarios.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/commands/scenarios.py`
- [ ] ScenarioConfig validates order ratio sums
- [ ] Invalid YAML file returns proper error
- [ ] Missing required fields caught by validation

#### Manual Verification:
- [ ] Run `cow-perf scenarios list` shows scenarios in `./scenarios/`
- [ ] Run `cow-perf scenarios validate valid.yml` succeeds
- [ ] Run `cow-perf scenarios validate invalid.yml` shows specific errors
- [ ] Validation error messages are clear and actionable
- [ ] Order ratio sum validation works (rejects 0.5 + 0.5 + 0.5)

---

## Phase 4: Baseline System Basics

### Overview

Implement basic baseline management (save/list/show) to establish the foundation for M2-08's comparison and regression detection features.

### Changes Required:

#### 1. Baseline Storage (`src/cow_performance/cli/commands/baselines.py` - NEW FILE)

**File**: `src/cow_performance/cli/commands/baselines.py`
**Changes**: Create baseline management module

```python
"""Baseline management commands."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()

BASELINES_DIR = Path.home() / ".cow-perf" / "baselines"


def ensure_baselines_dir() -> Path:
    """Ensure baselines directory exists."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    return BASELINES_DIR


def save_baseline(name: str, metrics: dict[str, Any]) -> Path:
    """
    Save test results as a baseline.

    Args:
        name: Baseline name
        metrics: Test metrics to save

    Returns:
        Path to saved baseline file
    """
    baselines_dir = ensure_baselines_dir()

    # Add metadata
    baseline_data = {
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
    }

    # Save to file
    baseline_file = baselines_dir / f"{name}.json"
    with open(baseline_file, "w") as f:
        json.dump(baseline_data, f, indent=2)

    return baseline_file


def load_baseline(name: str) -> dict[str, Any] | None:
    """
    Load a baseline by name.

    Args:
        name: Baseline name

    Returns:
        Baseline data or None if not found
    """
    baseline_file = BASELINES_DIR / f"{name}.json"

    if not baseline_file.exists():
        return None

    with open(baseline_file) as f:
        return json.load(f)


def list_baselines() -> list[dict[str, Any]]:
    """
    List all saved baselines.

    Returns:
        List of baseline metadata
    """
    if not BASELINES_DIR.exists():
        return []

    baselines = []
    for path in BASELINES_DIR.glob("*.json"):
        try:
            with open(path) as f:
                data = json.load(f)

            baselines.append({
                "name": data.get("name", path.stem),
                "timestamp": data.get("timestamp", "Unknown"),
                "path": str(path),
            })
        except Exception:
            continue

    return sorted(baselines, key=lambda x: x["timestamp"], reverse=True)


def display_baseline(baseline_data: dict[str, Any]) -> None:
    """Display baseline details."""
    console.print(f"\n[bold cyan]Baseline: {baseline_data['name']}[/bold cyan]")
    console.print(f"[dim]Saved: {baseline_data['timestamp']}[/dim]\n")

    metrics = baseline_data["metrics"]

    # Create table
    table = Table(show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    # Orchestration
    orch = metrics["orchestration"]
    table.add_row("Traders", str(orch["num_traders"]))
    table.add_row("Duration", f"{orch['elapsed_time']:.2f}s")

    # Orders
    orders = metrics["orders"]
    table.add_row("Total Submitted", str(orders["total_submitted"]))
    table.add_row("Orders Filled", str(orders["orders_filled"]))

    # Performance
    perf = metrics["performance"]
    table.add_row("Orders/Second", f"{perf['orders_per_second']:.2f}")

    console.print(table)
    console.print()
```

#### 2. Update Main CLI (`src/cow_performance/cli/main.py`)

**File**: `src/cow_performance/cli/main.py`
**Changes**: Replace baselines command

```python
from .commands.baselines import save_baseline, load_baseline, list_baselines, display_baseline

@app.command()
def baselines(
    action: str = typer.Argument("list", help="Action: list, show, save"),
    name: Optional[str] = typer.Argument(None, help="Baseline name"),
    results_file: Optional[str] = typer.Option(
        None, "--results", "-r", help="Results file to save as baseline"
    ),
) -> None:
    """Manage performance baselines.

    Actions:
        list - List saved baselines
        show <name> - Display baseline details
        save <name> - Save results as baseline (requires --results)
    """
    if action == "list":
        baselines_list = list_baselines()

        if not baselines_list:
            console.print("[yellow]No baselines found[/yellow]")
            console.print(f"\n[dim]Baselines are stored in: {BASELINES_DIR}[/dim]")
            return

        console.print("[bold green]Saved Baselines:[/bold green]\n")
        for baseline in baselines_list:
            console.print(f"  [cyan]{baseline['name']}[/cyan]")
            console.print(f"    Saved: {baseline['timestamp']}\n")

    elif action == "show":
        if not name:
            console.print("[red]Error:[/red] baseline name required")
            raise typer.Exit(1)

        baseline_data = load_baseline(name)
        if not baseline_data:
            console.print(f"[red]Error:[/red] Baseline not found: {name}")
            raise typer.Exit(2)

        display_baseline(baseline_data)

    elif action == "save":
        if not name:
            console.print("[red]Error:[/red] baseline name required")
            raise typer.Exit(1)

        if not results_file:
            console.print("[red]Error:[/red] --results required for save")
            console.print("\n[dim]Usage: cow-perf baselines save my-baseline --results results.json[/dim]")
            raise typer.Exit(1)

        results_path = Path(results_file)
        if not results_path.exists():
            console.print(f"[red]Error:[/red] Results file not found: {results_file}")
            raise typer.Exit(2)

        try:
            with open(results_path) as f:
                metrics = json.load(f)

            baseline_path = save_baseline(name, metrics)
            console.print(f"[green]✓[/green] Baseline saved: {baseline_path}")
        except Exception as e:
            console.print(f"[red]Error saving baseline:[/red] {e}")
            raise typer.Exit(1)

    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Valid actions: list, show, save")
        raise typer.Exit(1)
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_cli_baselines.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/commands/baselines.py`
- [ ] Baseline save creates JSON file
- [ ] Baseline load returns correct data
- [ ] List baselines returns empty list when none exist

#### Manual Verification:
- [ ] Run `cow-perf baselines save test --results results.json` creates baseline
- [ ] Run `cow-perf baselines list` shows saved baseline
- [ ] Run `cow-perf baselines show test` displays baseline metrics
- [ ] Baselines stored in `~/.cow-perf/baselines/`
- [ ] Invalid baseline name shows clear error

---

## Phase 5: Output Formatting

### Overview

Implement structured output formatting with JSON as primary format (for automation/Prometheus) and Rich tables as secondary format (for human readability).

### Changes Required:

#### 1. Output Formatters (`src/cow_performance/cli/output.py` - NEW FILE)

**File**: `src/cow_performance/cli/output.py`
**Changes**: Create output formatting module

```python
"""Output formatting utilities."""

import csv
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def format_metrics_for_prometheus(metrics: dict[str, Any]) -> dict[str, float]:
    """
    Format metrics for Prometheus/Grafana consumption.

    Returns flat dictionary with metric names and values.
    """
    flat_metrics = {}

    # Orchestration metrics
    orch = metrics["orchestration"]
    flat_metrics["cow_perf_traders_total"] = float(orch["num_traders"])
    flat_metrics["cow_perf_duration_seconds"] = float(orch["elapsed_time"])
    flat_metrics["cow_perf_restarts_total"] = float(orch["total_restarts"])

    # Order metrics
    orders = metrics["orders"]
    flat_metrics["cow_perf_orders_submitted_total"] = float(orders["total_submitted"])
    flat_metrics["cow_perf_orders_filled_total"] = float(orders["orders_filled"])
    flat_metrics["cow_perf_orders_failed_total"] = float(orders["orders_failed"])
    flat_metrics["cow_perf_orders_expired_total"] = float(orders["orders_expired"])

    # Performance metrics
    perf = metrics["performance"]
    flat_metrics["cow_perf_orders_per_second"] = float(perf["orders_per_second"])

    if perf.get("avg_time_to_fill"):
        flat_metrics["cow_perf_avg_time_to_fill_seconds"] = float(perf["avg_time_to_fill"])

    return flat_metrics


def output_json(metrics: dict[str, Any], file_path: Path | None = None) -> None:
    """
    Output metrics as JSON.

    Args:
        metrics: Test metrics
        file_path: Optional file path. If None, prints to stdout.
    """
    if file_path:
        with open(file_path, "w") as f:
            json.dump(metrics, f, indent=2)
        console.print(f"[green]✓[/green] JSON output saved: {file_path}")
    else:
        print(json.dumps(metrics, indent=2))


def output_prometheus_format(metrics: dict[str, Any], file_path: Path | None = None) -> None:
    """
    Output metrics in Prometheus exposition format.

    Args:
        metrics: Test metrics
        file_path: Optional file path. If None, prints to stdout.
    """
    flat_metrics = format_metrics_for_prometheus(metrics)

    lines = []
    for metric_name, value in flat_metrics.items():
        lines.append(f"{metric_name} {value}")

    output_text = "\n".join(lines)

    if file_path:
        with open(file_path, "w") as f:
            f.write(output_text)
        console.print(f"[green]✓[/green] Prometheus format saved: {file_path}")
    else:
        print(output_text)


def output_csv(metrics: dict[str, Any], file_path: Path) -> None:
    """
    Output metrics as CSV.

    Args:
        metrics: Test metrics
        file_path: File path for CSV
    """
    flat_metrics = format_metrics_for_prometheus(metrics)

    with open(file_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for metric_name, value in flat_metrics.items():
            writer.writerow([metric_name, value])

    console.print(f"[green]✓[/green] CSV output saved: {file_path}")


def output_table(metrics: dict[str, Any]) -> None:
    """
    Output metrics as formatted table.

    Args:
        metrics: Test metrics
    """
    table = Table(title="Performance Test Results", show_header=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Orchestration
    orch = metrics["orchestration"]
    table.add_row("Traders", str(orch["num_traders"]))
    table.add_row("Duration", f"{orch['elapsed_time']:.2f}s")
    table.add_row("Restarts", str(orch["total_restarts"]))

    # Orders
    orders = metrics["orders"]
    table.add_row("", "")  # Separator
    table.add_row("Total Submitted", str(orders["total_submitted"]))
    table.add_row("Orders Filled", str(orders["orders_filled"]))
    table.add_row("Orders Failed", str(orders["orders_failed"]))
    table.add_row("Orders Expired", str(orders["orders_expired"]))

    # Performance
    perf = metrics["performance"]
    table.add_row("", "")  # Separator
    table.add_row("Orders/Second", f"{perf['orders_per_second']:.2f}")

    if perf.get("avg_time_to_fill"):
        table.add_row("Avg Time to Fill", f"{perf['avg_time_to_fill']:.2f}s")

    console.print()
    console.print(table)
    console.print()
```

#### 2. Update Run Command (`src/cow_performance/cli/commands/run.py`)

**File**: `src/cow_performance/cli/commands/run.py`
**Changes**: Add output format options

```python
# Add to imports
from ..output import output_json, output_prometheus_format, output_csv, output_table

# Update run command in main.py to include format option
@app.command()
def run(
    # ... existing parameters ...
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, prometheus, csv"
    ),
) -> None:
    """Run a performance test scenario."""
    # ... existing code ...

    # Display results based on format
    if not dry_run:
        if output_format == "json":
            output_json(metrics, Path(output) if output else None)
        elif output_format == "prometheus":
            output_prometheus_format(metrics, Path(output) if output else None)
        elif output_format == "csv":
            if not output:
                console.print("[red]Error:[/red] --output required for CSV format")
                raise typer.Exit(1)
            output_csv(metrics, Path(output))
        else:  # table (default)
            output_table(metrics)
            if output:
                # Also save JSON when using table format
                output_json(metrics, Path(output))
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_cli_output.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/output.py`
- [ ] JSON output can be parsed by `json.load()`
- [ ] Prometheus format follows exposition format spec
- [ ] CSV output has proper headers

#### Manual Verification:
- [ ] Run `cow-perf run scenario.yml --format json` outputs valid JSON
- [ ] Run `cow-perf run scenario.yml --format prometheus` outputs flat metrics
- [ ] Run `cow-perf run scenario.yml --format csv -o results.csv` creates CSV
- [ ] Run `cow-perf run scenario.yml --format table` shows Rich table
- [ ] JSON output can be piped to `jq`
- [ ] Prometheus format compatible with `curl -X POST` to Pushgateway

---

## Phase 6: Error Handling & Polish

### Overview

Add comprehensive error handling, input validation, verbose logging, and dry-run support to make the CLI production-ready.

### Changes Required:

#### 1. Error Handler Utilities (`src/cow_performance/cli/errors.py` - NEW FILE)

**File**: `src/cow_performance/cli/errors.py`
**Changes**: Create error handling utilities

```python
"""Error handling utilities for CLI."""

from typing import Any, Callable

import typer
from rich.console import Console

console = Console()


class CLIError(Exception):
    """Base exception for CLI errors."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ConfigurationError(CLIError):
    """Configuration-related error."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)


class ValidationError(CLIError):
    """Validation error."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)


def handle_cli_errors(func: Callable) -> Callable:
    """
    Decorator to handle CLI errors consistently.

    Usage:
        @handle_cli_errors
        def my_command(...) -> None:
            ...
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except CLIError as e:
            console.print(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(e.exit_code)
        except FileNotFoundError as e:
            console.print(f"[red]File Not Found:[/red] {e}")
            raise typer.Exit(2)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            raise typer.Exit(130)
        except Exception as e:
            console.print(f"[red]Unexpected Error:[/red] {e}")
            if kwargs.get("verbose"):
                import traceback
                console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
            raise typer.Exit(1)

    return wrapper
```

#### 2. Verbose Logging Setup (`src/cow_performance/cli/logging_config.py` - NEW FILE)

**File**: `src/cow_performance/cli/logging_config.py`
**Changes**: Create logging configuration

```python
"""Logging configuration for CLI."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(verbose: bool = False, log_file: Path | None = None) -> None:
    """
    Setup logging configuration.

    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional log file path
    """
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = []

    # Console handler with Rich
    console_handler = RichHandler(
        console=console,
        show_time=False,
        show_path=verbose,
    )
    console_handler.setLevel(level)
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=handlers,
    )

    # Silence noisy libraries
    logging.getLogger("web3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
```

#### 3. Global Options (`src/cow_performance/cli/main.py`)

**File**: `src/cow_performance/cli/main.py`
**Changes**: Add global options to app callback

```python
from .logging_config import setup_logging
from .errors import handle_cli_errors

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
    log_file: Optional[str] = typer.Option(
        None, "--log-file", help="Write logs to file"
    ),
) -> None:
    """
    CoW Protocol Performance Testing Suite.

    A comprehensive tool for load testing and benchmarking CoW Protocol.
    """
    # Setup logging
    setup_logging(
        verbose=verbose,
        log_file=Path(log_file) if log_file else None
    )

    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
```

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `pytest tests/unit/test_cli_errors.py -v`
- [ ] Type checking passes: `mypy src/cow_performance/cli/`
- [ ] All linting passes: `ruff check src/cow_performance/cli/`
- [ ] Error decorator catches and formats exceptions
- [ ] Exit codes are correct for different error types

#### Manual Verification:
- [ ] Run `cow-perf --verbose run scenario.yml` shows debug logs
- [ ] Run `cow-perf --log-file test.log run scenario.yml` creates log file
- [ ] Invalid config shows clear error message with fix suggestion
- [ ] Missing file shows "File not found" with path
- [ ] Ctrl+C shows "Operation cancelled" message
- [ ] `--verbose` flag shows full traceback on errors
- [ ] `--dry-run` validates all inputs without executing

---

## Testing Strategy

### Unit Tests

Create test files for each module:

**`tests/unit/test_config.py`**:
- Test config loading from YAML
- Test environment variable overrides
- Test config validation errors
- Test config file discovery
- Test default config creation

**`tests/unit/test_cli_run.py`**:
- Test run command with valid scenario
- Test run command with missing file
- Test run command with invalid config
- Test duration and traders overrides
- Test dry-run mode
- Test output file creation

**`tests/unit/test_cli_scenarios.py`**:
- Test scenario validation (valid/invalid)
- Test list scenarios (empty/populated)
- Test order ratio validation

**`tests/unit/test_cli_baselines.py`**:
- Test baseline save
- Test baseline load
- Test baseline list
- Test baseline show

**`tests/unit/test_cli_output.py`**:
- Test JSON output formatting
- Test Prometheus format
- Test CSV output
- Test table rendering

### Integration Tests

**`tests/integration/test_cli_end_to_end.py`**:
- Test complete workflow: init config → validate scenario → run test → save baseline
- Test real TraderOrchestrator integration
- Test progress display updates
- Test graceful shutdown

### Manual Testing Steps

1. **Installation Verification**:
   - Run `pip install -e .`
   - Run `cow-perf --version`
   - Verify CLI is in PATH

2. **Configuration Workflow**:
   - Run `cow-perf config init`
   - Edit `.cow-perf.yml`
   - Run `cow-perf config show`
   - Run `cow-perf config validate .cow-perf.yml`

3. **Scenario Testing**:
   - Create `scenarios/test.yml`
   - Run `cow-perf scenarios validate scenarios/test.yml`
   - Run `cow-perf scenarios list`

4. **Run Test**:
   - Run `cow-perf run scenarios/test.yml`
   - Observe progress bar
   - Press Ctrl+C to test graceful shutdown
   - Check exit code: `echo $?`

5. **Output Formats**:
   - Run `cow-perf run scenarios/test.yml -o results.json`
   - Run `cat results.json | jq .`
   - Run `cow-perf run scenarios/test.yml --format prometheus`

6. **Baseline Workflow**:
   - Run `cow-perf baselines save test1 --results results.json`
   - Run `cow-perf baselines list`
   - Run `cow-perf baselines show test1`

7. **Error Handling**:
   - Run `cow-perf run nonexistent.yml` (expect error)
   - Run `cow-perf scenarios validate invalid.yml` (expect validation error)
   - Run `cow-perf baselines show nonexistent` (expect not found)

## Performance Considerations

**Configuration Loading**:
- Config file discovery happens once per command execution
- YAML parsing is fast for small config files (<1KB)
- Pydantic validation adds ~10ms overhead (acceptable)

**Progress Display**:
- Updates every 0.5 seconds (not every trader action)
- Minimal performance impact on test execution
- Async progress updates don't block test

**Output Formatting**:
- JSON serialization is fast (< 1ms for typical metrics)
- Table rendering happens after test completion
- File I/O is non-blocking

**Memory Usage**:
- CLI itself uses < 50MB
- TraderOrchestrator memory scales with trader count
- Metrics collection uses < 10MB per 1000 orders

## Migration Notes

**Not applicable** - This is new functionality, no migration needed.

**Backwards Compatibility**:
- Existing placeholder commands will be replaced
- CLI entry point remains `cow-perf`
- No breaking changes to `pyproject.toml`

**Configuration Location**:
- Baselines stored in `~/.cow-perf/baselines/`
- Config files searched in `./.cow-perf.yml` then `~/.cow-perf.yml`
- Results output to `./results/` by default

## References

- Original ticket: `issues/description/m1-issue-05-cli-tool-interface.md`
- TraderOrchestrator implementation: `src/cow_performance/load_generation/trader_orchestrator.py:45-382`
- Existing CLI skeleton: `src/cow_performance/cli/main.py:1-75`
- Configuration patterns: `src/cow_performance/load_generation/trader_simulator.py:31-86`
- Testing patterns: `tests/unit/test_cli.py:1-47`
- Dependencies: `pyproject.toml:10-36` (typer, rich, pydantic-settings, pyyaml)
