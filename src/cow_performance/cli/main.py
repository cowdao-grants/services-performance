"""Main CLI entry point for the CoW Performance Testing Suite."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .commands.baselines import (
    delete_baseline_command,
    list_baselines_command,
    save_baseline_command,
    show_baseline_command,
)
from .commands.report import app as report_app
from .commands.run import run_command
from .commands.scenarios import (
    create_scenario_template,
    list_scenarios_command,
    validate_scenario_command,
)
from .config import load_config, save_config_template

app = typer.Typer(
    name="cow-perf",
    help="CoW Protocol Performance Testing Suite",
    add_completion=False,
)

# Register sub-commands
app.add_typer(report_app, name="report")

console = Console()


@app.callback()
def main() -> None:
    """
    CoW Protocol Performance Testing Suite.

    A comprehensive tool for load testing and benchmarking the CoW Protocol Playground.
    """
    pass


@app.command(name="version")
def show_version() -> None:
    """Show version and exit."""
    console.print("[bold green]CoW Performance Testing Suite[/bold green] v0.1.0")


@app.command()
def run(
    traders: Optional[int] = typer.Option(
        None, "--traders", "-t", help="Number of concurrent traders"
    ),
    duration: Optional[int] = typer.Option(
        None, "--duration", "-d", help="Test duration in seconds"
    ),
    settlement_wait: Optional[int] = typer.Option(
        None,
        "--settlement-wait",
        "-w",
        help="Seconds to wait after test for settlements (default 300)",
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--format", "-f", help="Output format (json, table, csv, prometheus)"
    ),
    save_results: bool = typer.Option(False, "--save", "-s", help="Save results to file"),
    output_file: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Perform dry run without submitting orders"
    ),
    prometheus_port: Optional[int] = typer.Option(
        None,
        "--prometheus-port",
        help="Port for Prometheus metrics exporter (default: 9091 from config, use 0 to disable)",
    ),
    save_baseline: Optional[str] = typer.Option(
        None,
        "--save-baseline",
        "-b",
        help="Save test results as a baseline with the given name",
    ),
    baseline_description: Optional[str] = typer.Option(
        None,
        "--baseline-description",
        help="Description for the saved baseline",
    ),
    baseline_tags: Optional[str] = typer.Option(
        None,
        "--baseline-tags",
        help="Comma-separated tags for the baseline (e.g., 'production,v1.0')",
    ),
) -> None:
    """Run a performance test.

    This command runs a performance test with the specified configuration.
    Traders will submit orders concurrently for the specified duration.

    Examples:
        # Run with default settings
        cow-perf run

        # Run with custom traders and duration
        cow-perf run --traders 20 --duration 120

        # Run with custom config file
        cow-perf run --config my-config.yml

        # Save results to file
        cow-perf run --save

        # Save as baseline for later comparison
        cow-perf run --save-baseline "v1.0" --baseline-description "Initial baseline"

        # Dry run (no actual order submission)
        cow-perf run --dry-run
    """
    try:
        # Load configuration
        cfg = load_config(Path(config_file) if config_file else None)

        # Use CLI prometheus_port override, or config value (default 9091)
        # A value of 0 disables the exporter
        effective_prometheus_port = (
            prometheus_port if prometheus_port is not None else cfg.prometheus_port
        )
        if effective_prometheus_port == 0:
            effective_prometheus_port = None

        # Parse baseline tags from comma-separated string
        parsed_tags = None
        if baseline_tags:
            parsed_tags = [tag.strip() for tag in baseline_tags.split(",") if tag.strip()]

        # Run the test
        run_command(
            config=cfg,
            traders=traders,
            duration=duration,
            settlement_wait=settlement_wait,
            output_format=output_format,
            save_results=save_results,
            output_file=output_file,
            verbose=verbose,
            dry_run=dry_run,
            prometheus_port=effective_prometheus_port,
            save_baseline=save_baseline,
            baseline_description=baseline_description or "",
            baseline_tags=parsed_tags,
        )

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("\n[yellow]Tip:[/yellow] Generate a config template with:")
        console.print("  cow-perf config --save-template .cow-perf.yml")
        sys.exit(2)
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(3)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@app.command()
def scenarios(
    list_all: bool = typer.Option(True, "--list", "-l", help="List available scenarios"),
    validate: Optional[str] = typer.Option(
        None, "--validate", "-v", help="Validate a scenario file"
    ),
    create_template: Optional[str] = typer.Option(
        None, "--create-template", help="Create a scenario template file"
    ),
    scenarios_dir: Optional[str] = typer.Option(None, "--dir", "-d", help="Scenarios directory"),
) -> None:
    """Manage performance test scenarios.

    Examples:
        # List available scenarios
        cow-perf scenarios

        # Validate a scenario file
        cow-perf scenarios --validate my-scenario.yml

        # Create a template scenario file
        cow-perf scenarios --create-template my-scenario.yml

        # List scenarios from custom directory
        cow-perf scenarios --dir ./scenarios
    """
    if create_template:
        # Create template file
        output_path = Path(create_template)
        template = create_scenario_template()

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(template)

            console.print(f"[bold green]✓[/bold green] Scenario template created: {output_path}")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Failed to create template: {e}")
            sys.exit(1)
        return

    if validate:
        # Validate scenario file
        scenario_path = Path(validate)
        validate_scenario_command(scenario_path)
        return

    # List scenarios (default)
    dir_path = Path(scenarios_dir) if scenarios_dir else None
    list_scenarios_command(dir_path)


@app.command()
def baselines(
    list_all: bool = typer.Option(True, "--list", "-l", help="List all baselines"),
    save: Optional[str] = typer.Option(
        None, "--save", "-s", help="Save baseline from results file (format: NAME:FILE)"
    ),
    show: Optional[str] = typer.Option(None, "--show", help="Show baseline details"),
    delete: Optional[str] = typer.Option(None, "--delete", help="Delete a baseline"),
    baselines_dir: Optional[str] = typer.Option(None, "--dir", "-d", help="Baselines directory"),
) -> None:
    """Manage performance baselines.

    Baselines allow you to save performance test results for later comparison.
    Full comparison and regression detection coming in M2-08.

    Examples:
        # List all baselines
        cow-perf baselines

        # Save a baseline from results file
        cow-perf baselines --save "v1.0:results-20240115.json"

        # Show baseline details
        cow-perf baselines --show v1.0

        # Delete a baseline
        cow-perf baselines --delete v1.0

        # Use custom baselines directory
        cow-perf baselines --dir ./baselines
    """
    dir_path = Path(baselines_dir) if baselines_dir else None

    if save:
        # Parse save argument (format: NAME:FILE)
        if ":" not in save:
            console.print("[bold red]Error:[/bold red] Save format should be NAME:FILE")
            console.print('Example: cow-perf baselines --save "v1.0:results.json"')
            sys.exit(1)

        name, file_path = save.split(":", 1)
        save_baseline_command(name.strip(), Path(file_path.strip()), baselines_dir=dir_path)
        return

    if show:
        show_baseline_command(show, baselines_dir=dir_path)
        return

    if delete:
        delete_baseline_command(delete, baselines_dir=dir_path)
        return

    # List baselines (default)
    list_baselines_command(baselines_dir=dir_path)


@app.command()
def config(
    show_template: bool = typer.Option(False, "--template", help="Show configuration template"),
    save_template: Optional[str] = typer.Option(
        None, "--save-template", help="Save configuration template to file"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
) -> None:
    """Show current configuration or generate template."""
    # Handle template generation
    if save_template:
        output_path = Path(save_template)
        try:
            save_config_template(output_path)
            console.print(
                f"[bold green]✓[/bold green] Configuration template saved to: {output_path}"
            )
            return
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] Failed to save template: {e}")
            sys.exit(1)

    if show_template:
        console.print("[bold green]Configuration Template:[/bold green]\n")
        template_path = Path("/tmp/cow-perf-template.yml")
        save_config_template(template_path)
        with open(template_path, "r") as f:
            console.print(f.read())
        template_path.unlink()
        return

    # Load and display current configuration
    try:
        cfg = load_config(Path(config_file) if config_file else None)

        console.print("[bold green]Current Configuration:[/bold green]\n")

        # Network settings
        table = Table(title="Network Settings", show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Chain ID", str(cfg.network.chain_id))
        table.add_row("RPC URL", cfg.network.rpc_url)
        table.add_row("Settlement Contract", cfg.network.settlement_contract)
        table.add_row("ComposableCow Contract", cfg.network.composable_cow_contract)
        console.print(table)
        console.print()

        # API settings
        table = Table(title="API Settings", show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Base URL", cfg.api.base_url)
        table.add_row("Timeout", f"{cfg.api.timeout}s")
        table.add_row("Max Retries", str(cfg.api.max_retries))
        console.print(table)
        console.print()

        # Output settings
        table = Table(title="Output Settings", show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Format", cfg.output.format)
        table.add_row("Verbose", str(cfg.output.verbose))
        table.add_row("Save Results", str(cfg.output.save_results))
        table.add_row("Results Directory", str(cfg.output.results_dir))
        console.print(table)
        console.print()

        # Test defaults
        table = Table(title="Test Defaults", show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Trader Count", str(cfg.default_trader_count))
        table.add_row("Duration", f"{cfg.default_duration}s")
        table.add_row("Startup Interval", f"{cfg.default_startup_interval}s")
        console.print(table)
        console.print()

        # Order type ratios
        table = Table(title="Order Type Ratios", show_header=True, header_style="bold")
        table.add_column("Order Type", style="cyan")
        table.add_column("Ratio", style="green")
        table.add_row("Market Orders", f"{cfg.market_order_ratio:.2%}")
        table.add_row("Limit Orders", f"{cfg.limit_order_ratio:.2%}")
        table.add_row("TWAP Orders", f"{cfg.twap_order_ratio:.2%}")
        table.add_row("Stop-Loss Orders", f"{cfg.stop_loss_order_ratio:.2%}")
        table.add_row("Good-After-Time Orders", f"{cfg.good_after_time_order_ratio:.2%}")
        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("\n[yellow]Tip:[/yellow] Generate a config template with:")
        console.print("  cow-perf config --save-template .cow-perf.yml")
        sys.exit(2)
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(3)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
