"""Scenario management commands for performance testing.

This module provides the foundation for scenario management, with full
implementation coming in M1-06.
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.table import Table


class ResourceRequirements(BaseModel):
    """Resource requirements for a scenario."""

    min_memory_gb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Minimum memory required in GB",
    )
    min_cpu_cores: Optional[int] = Field(
        default=None,
        ge=1,
        description="Minimum CPU cores required",
    )
    recommended_memory_gb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Recommended memory in GB",
    )
    recommended_cpu_cores: Optional[int] = Field(
        default=None,
        ge=1,
        description="Recommended CPU cores",
    )


class ScenarioMetadata(BaseModel):
    """Metadata about a scenario including expected outcomes and resource requirements."""

    expected_orders: Optional[int] = Field(
        default=None,
        ge=0,
        description="Expected number of orders for this scenario",
    )
    expected_duration_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        description="Expected test duration in seconds",
    )
    resources: Optional[ResourceRequirements] = Field(
        default=None,
        description="Resource requirements for this scenario",
    )


class SuccessCriteria(BaseModel):
    """Success criteria for validating test results."""

    min_success_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum order success rate (0.0-1.0)",
    )
    max_p95_latency_seconds: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Maximum P95 latency in seconds",
    )
    max_error_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Maximum error rate (0.0-1.0)",
    )
    min_throughput_per_second: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Minimum throughput in orders per second",
    )


class ScenarioConfig(BaseModel):
    """Configuration for a performance test scenario.

    This defines the parameters for a complete performance test scenario,
    including trader behavior and order type distribution.
    """

    name: str = Field(description="Scenario name")
    description: str = Field(default="", description="Scenario description")
    version: str = Field(default="1.0", description="Scenario version")
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorizing the scenario (e.g., 'stress', 'baseline', 'short')",
    )

    # Metadata about expected outcomes and resource requirements
    metadata: Optional[ScenarioMetadata] = Field(
        default=None,
        description="Scenario metadata including expected orders and resource requirements",
    )

    # Success criteria for automated validation
    success_criteria: Optional[SuccessCriteria] = Field(
        default=None,
        description="Success criteria for validating test results",
    )

    # Trader configuration
    num_traders: int = Field(default=10, ge=1, description="Number of concurrent traders")
    duration: int = Field(default=60, ge=1, description="Test duration in seconds")
    startup_interval: float = Field(
        default=0.1,
        ge=0.0,
        description="Interval between trader startups",
    )

    # Order type ratios (must sum to 1.0)
    market_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    limit_order_ratio: float = Field(default=0.4, ge=0.0, le=1.0)
    twap_order_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    stop_loss_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    good_after_time_order_ratio: float = Field(default=0.05, ge=0.0, le=1.0)

    # Trading pattern
    trading_pattern: str = Field(
        default="constant_rate",
        description="Trading pattern (constant_rate, burst, random_interval)",
    )
    base_rate: float = Field(
        default=60.0,
        gt=0.0,
        description="Base trading rate (orders per minute) for constant_rate pattern",
    )

    # Burst pattern parameters (optional)
    burst_size: int | None = Field(
        default=None,
        ge=1,
        description="Number of orders per burst (for burst pattern)",
    )
    burst_interval: float | None = Field(
        default=None,
        gt=0.0,
        description="Interval between orders in burst (for burst pattern)",
    )
    quiet_period: float | None = Field(
        default=None,
        gt=0.0,
        description="Quiet period between bursts (for burst pattern)",
    )

    # Random interval parameters (optional)
    min_interval: float | None = Field(
        default=None,
        ge=0.0,
        description="Minimum interval between orders (for random_interval pattern)",
    )
    max_interval: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum interval between orders (for random_interval pattern)",
    )

    @field_validator("trading_pattern")
    @classmethod
    def validate_trading_pattern(cls, v: str) -> str:
        """Validate trading pattern."""
        allowed = ["constant_rate", "burst", "random_interval"]
        if v not in allowed:
            raise ValueError(f"Trading pattern must be one of: {', '.join(allowed)}, got: {v}")
        return v

    def validate_ratios(self) -> None:
        """Validate that order type ratios sum to 1.0."""
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
                f"Current ratios: market={self.market_order_ratio}, "
                f"limit={self.limit_order_ratio}, twap={self.twap_order_ratio}, "
                f"stop_loss={self.stop_loss_order_ratio}, "
                f"good_after_time={self.good_after_time_order_ratio}"
            )

    def validate_pattern_parameters(self) -> None:
        """Validate that required parameters for trading pattern are present."""
        if self.trading_pattern == "burst":
            if self.burst_size is None:
                raise ValueError("burst_size is required for burst pattern")
            if self.burst_interval is None:
                raise ValueError("burst_interval is required for burst pattern")
            if self.quiet_period is None:
                raise ValueError("quiet_period is required for burst pattern")

        if self.trading_pattern == "random_interval":
            if self.min_interval is None:
                raise ValueError("min_interval is required for random_interval pattern")
            if self.max_interval is None:
                raise ValueError("max_interval is required for random_interval pattern")
            if self.min_interval >= self.max_interval:
                raise ValueError("min_interval must be less than max_interval")


def load_scenario_from_yaml(
    scenario_path: Path,
    show_warnings: bool = True,
    resolve_inheritance: bool = True,
    apply_defaults: bool = True,
    project_root: Optional[Path] = None,
    profile: Optional[str] = None,
) -> ScenarioConfig:
    """Load scenario configuration from YAML file with enhanced validation.

    Configuration precedence (lowest to highest priority):
    1. Built-in defaults (ScenarioConfig field defaults)
    2. Project defaults (.cow-perf-defaults.yml)
    3. Scenario file
    4. Profile overrides (via --profile flag)
    5. CLI arguments (applied separately)

    Args:
        scenario_path: Path to scenario YAML file
        show_warnings: Whether to display validation warnings (default: True)
        resolve_inheritance: Whether to resolve inheritance (extends) (default: True)
        apply_defaults: Whether to apply project defaults (default: True)
        project_root: Root directory for project defaults (default: scenario file's parent)
        profile: Optional profile name to apply (default: None)

    Returns:
        Parsed and validated ScenarioConfig

    Raises:
        FileNotFoundError: If scenario file doesn't exist
        ValueError: If scenario configuration is invalid
        yaml.YAMLError: If YAML is malformed
    """
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")

    with open(scenario_path, "r") as f:
        scenario_data = yaml.safe_load(f)

    if scenario_data is None:
        raise ValueError(f"Scenario file is empty: {scenario_path}")

    # Expand template if present (happens before defaults and inheritance)
    if "template" in scenario_data:
        from cow_performance.scenarios.templates import TemplateExpander

        try:
            template_name = scenario_data.get("template")
            template_params = scenario_data.get("parameters", {})

            # Expand template
            expander = TemplateExpander()
            expanded = expander.expand_template(template_name, template_params)

            # Merge expanded template with any additional fields in scenario file
            # (fields in scenario_data override template, except 'template' and 'parameters')
            for key, value in scenario_data.items():
                if key not in ("template", "parameters"):
                    expanded[key] = value

            scenario_data = expanded
        except Exception as e:
            raise ValueError(f"Template expansion failed: {e}") from e

    # Apply project defaults if requested
    if apply_defaults:
        from cow_performance.scenarios.defaults import load_with_defaults

        try:
            # Use scenario's parent directory as project root if not specified
            root = project_root or scenario_path.parent
            scenario_data = load_with_defaults(scenario_data, project_root=root)
        except Exception as e:
            raise ValueError(f"Failed to apply project defaults: {e}") from e

    # Resolve inheritance if requested
    if resolve_inheritance and "extends" in scenario_data:
        from cow_performance.scenarios.inheritance import resolve_inheritance as resolve_inh

        try:
            scenario_data = resolve_inh(
                scenario_data,
                config_path=scenario_path,
                base_dir=scenario_path.parent,
            )
        except Exception as e:
            raise ValueError(f"Inheritance resolution failed: {e}") from e

    # Apply profile overrides if requested
    from cow_performance.scenarios.profiles import apply_profile_if_requested

    try:
        scenario_data = apply_profile_if_requested(scenario_data, profile)
    except Exception as e:
        raise ValueError(f"Profile application failed: {e}") from e

    # Parse and validate with Pydantic
    scenario = ScenarioConfig(**scenario_data)
    scenario.validate_ratios()
    scenario.validate_pattern_parameters()

    # Run enhanced validation
    from cow_performance.scenarios.config_validation import ConfigValidator

    validator = ConfigValidator()
    result = validator.validate(scenario)

    # Display or raise errors
    if not result.valid:
        # Display errors with rich formatting
        if show_warnings:
            console = Console()
            result.display(console)
        raise ValueError("Scenario configuration validation failed")

    # Display warnings if requested
    if show_warnings and result.has_warnings:
        console = Console()
        result.display(console)

    return scenario


def save_scenario_to_yaml(scenario: ScenarioConfig, output_path: Path) -> None:
    """Save scenario configuration to YAML file.

    Args:
        scenario: Scenario configuration to save
        output_path: Path where to save the scenario
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dictionary
    scenario_data = scenario.model_dump(exclude_none=True)

    with open(output_path, "w") as f:
        yaml.dump(scenario_data, f, default_flow_style=False, sort_keys=False)


def create_scenario_template() -> str:
    """Create a scenario template string.

    Returns:
        YAML string with scenario template
    """
    template = """# Performance Test Scenario Configuration

# Scenario metadata
name: "example-scenario"
description: "Example performance test scenario"

# Trader configuration
num_traders: 10
duration: 60  # seconds
startup_interval: 0.1

# Order type distribution (must sum to 1.0)
market_order_ratio: 0.4
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.05
good_after_time_order_ratio: 0.05

# Trading pattern
trading_pattern: "constant_rate"  # constant_rate, burst, or random_interval
base_rate: 60.0  # orders per minute (for constant_rate)

# Burst pattern parameters (uncomment if using burst pattern)
# burst_size: 5
# burst_interval: 0.1
# quiet_period: 5.0

# Random interval parameters (uncomment if using random_interval)
# min_interval: 0.5
# max_interval: 3.0
"""
    return template


def list_scenarios_command(
    scenarios_dir: Path | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
    show_metadata: bool = True,
) -> None:
    """List available scenarios with optional filtering.

    Args:
        scenarios_dir: Optional directory to search for scenarios
        tags: Optional list of tags to filter by (scenarios must match ALL tags)
        search: Optional search term to filter by name or description
        show_metadata: Whether to show metadata columns (default True)
    """
    console = Console()

    if scenarios_dir is None:
        scenarios_dir = Path(".cow-perf") / "scenarios"

    # Build title with filters
    title = "Available Scenarios"
    if tags:
        title += f" [dim](tags: {', '.join(tags)})[/dim]"
    if search:
        title += f" [dim](search: {search})[/dim]"

    console.print(f"[bold cyan]Scenarios Directory:[/bold cyan] {scenarios_dir}\n")

    if not scenarios_dir.exists():
        console.print("[yellow]No scenarios directory found. " "Create scenarios with:[/yellow]")
        console.print("  cow-perf scenarios --create-template my-scenario.yml")
        return

    # Find all YAML files recursively
    scenario_files = list(scenarios_dir.rglob("*.yml")) + list(scenarios_dir.rglob("*.yaml"))

    if not scenario_files:
        console.print("[yellow]No scenario files found.[/yellow]")
        return

    # Load scenarios and apply filters
    scenarios_to_display = []
    errors = []

    for scenario_file in sorted(scenario_files):
        try:
            scenario = load_scenario_from_yaml(scenario_file)

            # Apply tag filter (must match ALL tags)
            if tags:
                scenario_tags = set(scenario.tags)
                if not all(tag in scenario_tags for tag in tags):
                    continue

            # Apply search filter (match name or description)
            if search:
                search_lower = search.lower()
                if (
                    search_lower not in scenario.name.lower()
                    and search_lower not in scenario.description.lower()
                ):
                    continue

            scenarios_to_display.append((scenario, scenario_file))

        except Exception as e:
            # Collect errors to show at the end
            errors.append((scenario_file, str(e)))

    # Show results
    if not scenarios_to_display and not errors:
        console.print("[yellow]No scenarios match the specified filters.[/yellow]")
        return

    # Build table based on metadata display preference
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")

    if show_metadata:
        table.add_column("Tags", style="blue")
        table.add_column("Orders", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Memory", justify="right")
    else:
        table.add_column("Traders", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Pattern", style="cyan")

    table.add_column("File", style="dim")

    for scenario, scenario_file in scenarios_to_display:
        # Get relative path for cleaner display
        try:
            rel_path = scenario_file.relative_to(scenarios_dir)
        except ValueError:
            rel_path = scenario_file

        if show_metadata:
            # Enhanced view with metadata
            tags_display = ", ".join(scenario.tags[:3]) if scenario.tags else "-"
            if len(scenario.tags) > 3:
                tags_display += f" +{len(scenario.tags) - 3}"

            orders_display = (
                str(scenario.metadata.expected_orders)
                if scenario.metadata and scenario.metadata.expected_orders
                else "-"
            )

            duration_display = (
                f"{scenario.metadata.expected_duration_seconds}s"
                if scenario.metadata and scenario.metadata.expected_duration_seconds
                else f"{scenario.duration}s"
            )

            memory_display = "-"
            if scenario.metadata and scenario.metadata.resources:
                if scenario.metadata.resources.min_memory_gb:
                    memory_display = f"{scenario.metadata.resources.min_memory_gb}GB"

            table.add_row(
                scenario.name,
                tags_display,
                orders_display,
                duration_display,
                memory_display,
                str(rel_path),
            )
        else:
            # Simple view
            table.add_row(
                scenario.name,
                str(scenario.num_traders),
                f"{scenario.duration}s",
                scenario.trading_pattern,
                str(rel_path),
            )

    console.print(table)

    # Show errors if any
    if errors:
        console.print()
        error_table = Table(title="Errors", show_header=True, header_style="bold red")
        error_table.add_column("File", style="dim")
        error_table.add_column("Error", style="red")

        for scenario_file, error in errors:
            try:
                rel_path = scenario_file.relative_to(scenarios_dir)
            except ValueError:
                rel_path = scenario_file
            error_table.add_row(
                str(rel_path), str(error)[:60] + "..." if len(str(error)) > 60 else str(error)
            )

        console.print(error_table)


def list_templates_command() -> None:
    """List available scenario templates with descriptions.

    Templates provide quick ways to create common test patterns like
    ramp-up, spike, and sustained load tests.
    """
    from cow_performance.scenarios.templates import TemplateExpander

    console = Console()

    expander = TemplateExpander()

    # Build table
    table = Table(title="Available Scenario Templates", show_header=True, header_style="bold cyan")
    table.add_column("Template", style="green", width=20)
    table.add_column("Description", style="white", width=60)
    table.add_column("Location", style="dim", width=30)

    templates_found: list[tuple[str, str, str]] = []

    # Search for templates in all directories
    for template_dir in expander.template_dirs:
        if not template_dir.exists():
            continue

        # Find all .template.yml and .yml files
        for pattern in ["*.template.yml", "*.yml"]:
            for template_file in template_dir.glob(pattern):
                # Extract template name (remove .template.yml or .yml)
                template_name = template_file.stem
                if template_name.endswith(".template"):
                    template_name = template_name[: -len(".template")]

                # Skip if already found (prefer first occurrence)
                if template_name in [t[0] for t in templates_found]:
                    continue

                # Load template to get metadata
                try:
                    template_data = expander.load_template(template_name)
                    metadata = template_data.get("template_metadata", {})
                    description = metadata.get("description", "No description available")

                    # Get relative path from current directory
                    try:
                        rel_path = template_file.relative_to(Path.cwd())
                    except ValueError:
                        rel_path = template_file

                    templates_found.append((template_name, description, str(rel_path)))
                except Exception as e:
                    # If we can't load it, still show it but with error
                    templates_found.append(
                        (
                            template_name,
                            f"[red]Error loading: {str(e)[:40]}[/red]",
                            str(template_file),
                        )
                    )

    if not templates_found:
        console.print("[yellow]No templates found.[/yellow]")
        console.print("\nDefault template locations:")
        for template_dir in expander.template_dirs:
            console.print(f"  • {template_dir}")
        return

    # Sort by template name
    templates_found.sort(key=lambda x: x[0])

    for template_name, description, location in templates_found:
        table.add_row(template_name, description, location)

    console.print(table)

    # Show usage example
    console.print("\n[bold cyan]Usage:[/bold cyan]")
    console.print("Create a scenario from a template:")
    console.print("  1. Create a file with template reference:")
    console.print("     [dim]cat > my-test.yml <<EOF[/dim]")
    console.print("     [dim]template: ramp-up[/dim]")
    console.print("     [dim]parameters:[/dim]")
    console.print("     [dim]  num_traders: 10[/dim]")
    console.print("     [dim]  duration: 300[/dim]")
    console.print("     [dim]  start_rate: 6.0[/dim]")
    console.print("     [dim]  target_rate: 60.0[/dim]")
    console.print("     [dim]EOF[/dim]")
    console.print()
    console.print("  2. Run the test:")
    console.print("     [dim]cow-perf run --config my-test.yml[/dim]")


def validate_scenario_command(scenario_path: Path) -> None:
    """Validate a scenario configuration file.

    Args:
        scenario_path: Path to scenario file to validate
    """
    console = Console()

    try:
        scenario = load_scenario_from_yaml(scenario_path)

        console.print("[bold green]✓[/bold green] Scenario is valid!")
        console.print()

        # Display scenario details
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", scenario.name)
        table.add_row("Description", scenario.description or "-")
        table.add_row("Version", scenario.version)
        if scenario.tags:
            table.add_row("Tags", ", ".join(scenario.tags))
        table.add_row("Traders", str(scenario.num_traders))
        table.add_row("Duration", f"{scenario.duration}s")
        table.add_row("Trading Pattern", scenario.trading_pattern)

        console.print(table)
        console.print()

        # Metadata (if present)
        if scenario.metadata:
            metadata_table = Table(
                title="Scenario Metadata", show_header=True, header_style="bold cyan"
            )
            metadata_table.add_column("Property", style="cyan")
            metadata_table.add_column("Value", style="green")

            if scenario.metadata.expected_orders is not None:
                metadata_table.add_row("Expected Orders", str(scenario.metadata.expected_orders))
            if scenario.metadata.expected_duration_seconds is not None:
                metadata_table.add_row(
                    "Expected Duration", f"{scenario.metadata.expected_duration_seconds}s"
                )

            if scenario.metadata.resources:
                res = scenario.metadata.resources
                if res.min_memory_gb is not None:
                    metadata_table.add_row("Min Memory", f"{res.min_memory_gb}GB")
                if res.min_cpu_cores is not None:
                    metadata_table.add_row("Min CPU Cores", str(res.min_cpu_cores))
                if res.recommended_memory_gb is not None:
                    metadata_table.add_row("Recommended Memory", f"{res.recommended_memory_gb}GB")
                if res.recommended_cpu_cores is not None:
                    metadata_table.add_row("Recommended CPU Cores", str(res.recommended_cpu_cores))

            console.print(metadata_table)
            console.print()

        # Success criteria (if present)
        if scenario.success_criteria:
            criteria_table = Table(
                title="Success Criteria", show_header=True, header_style="bold cyan"
            )
            criteria_table.add_column("Criterion", style="cyan")
            criteria_table.add_column("Value", style="green")

            crit = scenario.success_criteria
            if crit.min_success_rate is not None:
                criteria_table.add_row("Min Success Rate", f"{crit.min_success_rate:.1%}")
            if crit.max_p95_latency_seconds is not None:
                criteria_table.add_row("Max P95 Latency", f"{crit.max_p95_latency_seconds}s")
            if crit.max_error_rate is not None:
                criteria_table.add_row("Max Error Rate", f"{crit.max_error_rate:.1%}")
            if crit.min_throughput_per_second is not None:
                criteria_table.add_row(
                    "Min Throughput", f"{crit.min_throughput_per_second} orders/s"
                )

            console.print(criteria_table)
            console.print()

        # Order type distribution
        table = Table(title="Order Type Distribution", show_header=True, header_style="bold cyan")
        table.add_column("Order Type", style="cyan")
        table.add_column("Ratio", style="green", justify="right")

        table.add_row("Market", f"{scenario.market_order_ratio:.1%}")
        table.add_row("Limit", f"{scenario.limit_order_ratio:.1%}")
        table.add_row("TWAP", f"{scenario.twap_order_ratio:.1%}")
        table.add_row("Stop-Loss", f"{scenario.stop_loss_order_ratio:.1%}")
        table.add_row("Good-After-Time", f"{scenario.good_after_time_order_ratio:.1%}")

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(2) from None
    except ValueError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {e}")
        raise SystemExit(3) from None
    except yaml.YAMLError as e:
        console.print(f"[bold red]YAML Error:[/bold red] {e}")
        raise SystemExit(3) from None
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from None
