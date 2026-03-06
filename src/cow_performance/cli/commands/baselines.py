"""Baseline management commands for performance testing.

This module provides CLI commands for managing performance baselines
using the BaselineManager class.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from cow_performance.baselines import BaselineManager, BaselineValidationError


def save_baseline_command(
    name: str,
    results_file: Path,
    description: str = "",
    tags: list[str] | None = None,
    baselines_dir: Path | None = None,
) -> None:
    """
    Save a baseline from a results file.

    Note: This command is for backward compatibility. The preferred
    method is to use BaselineManager.save() directly with a MetricsStore.

    Args:
        name: Baseline name
        results_file: Path to results JSON file
        description: Optional description
        tags: Optional list of tags
        baselines_dir: Optional directory for baselines
    """
    console = Console()

    console.print("[bold red]Error:[/bold red] This command is no longer supported.")
    console.print(
        "\nBaselines should be saved programmatically using [cyan]BaselineManager.save()[/cyan]."
    )
    console.print("\nExample:")
    console.print("  [dim]from cow_performance.baselines import BaselineManager[/dim]")
    console.print("  [dim]manager = BaselineManager()[/dim]")
    console.print("  [dim]baseline = manager.save('my-baseline', metrics_store)[/dim]")
    console.print("\nSee [cyan]docs/architecture.md[/cyan] for the full programmatic workflow.")
    raise SystemExit(1)


def show_baseline_command(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """
    Show details of a saved baseline.

    Args:
        name: Baseline name, ID, or git commit
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    try:
        baseline = manager.load(name)

        # Header
        console.print(f"[bold cyan]Baseline:[/bold cyan] {baseline.name}")
        console.print(f"[dim]ID: {baseline.id}[/dim]")
        console.print(f"[dim]Schema: v{baseline.schema_version}[/dim]")

        # Format timestamp
        created_dt = datetime.fromtimestamp(baseline.created_at)
        console.print(f"[dim]Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

        if baseline.description:
            console.print(f"\n[italic]{baseline.description}[/italic]")

        if baseline.tags:
            console.print(f"[dim]Tags: {', '.join(baseline.tags)}[/dim]")

        console.print()

        # Git info table
        if baseline.git_commit:
            table = Table(title="Git Information", show_header=True, header_style="bold cyan")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Commit", baseline.git_commit[:12] if baseline.git_commit else "N/A")
            table.add_row("Branch", baseline.git_branch or "N/A")
            table.add_row("Repository", baseline.git_repo or "N/A")
            table.add_row(
                "Dirty",
                "[yellow]Yes[/yellow]" if baseline.has_uncommitted_changes else "[green]No[/green]",
            )

            console.print(table)
            console.print()

        # Test config table
        table = Table(title="Test Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Scenario", baseline.scenario_name or "N/A")
        table.add_row("Duration", f"{baseline.duration_seconds:.1f}s")
        table.add_row("Traders", str(baseline.num_traders))

        console.print(table)
        console.print()

        # Environment table
        table = Table(title="Environment", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Python", baseline.python_version)
        table.add_row("Platform", baseline.platform)

        console.print(table)
        console.print()

        # Order metrics table
        if baseline.order_metrics:
            om = baseline.order_metrics
            table = Table(title="Order Metrics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")

            table.add_row("Total Orders", str(om.total_orders))
            table.add_row("Filled", str(om.orders_filled))
            table.add_row("Failed", str(om.orders_failed))
            table.add_row("Success Rate", f"{om.success_rate * 100:.1f}%")
            table.add_row("Time to Submit (p50)", f"{om.time_to_submit.p50 * 1000:.1f}ms")
            table.add_row("Time to Submit (p95)", f"{om.time_to_submit.p95 * 1000:.1f}ms")
            table.add_row("Time to Fill (p50)", f"{om.time_to_fill.p50 * 1000:.1f}ms")
            table.add_row("Time to Fill (p95)", f"{om.time_to_fill.p95 * 1000:.1f}ms")

            console.print(table)
            console.print()

        # API metrics table
        if baseline.api_metrics:
            am = baseline.api_metrics
            table = Table(title="API Metrics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")

            table.add_row("Total Requests", str(am.total_requests))
            table.add_row("Success Rate", f"{am.success_rate * 100:.1f}%")
            table.add_row("Response Time (p50)", f"{am.response_time.p50:.1f}ms")
            table.add_row("Response Time (p95)", f"{am.response_time.p95:.1f}ms")
            table.add_row("Requests/sec", f"{am.requests_per_second:.2f}")

            console.print(table)
            console.print()

        # Throughput summary
        table = Table(title="Throughput", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Orders/sec", f"{baseline.orders_per_second:.2f}")
        table.add_row("Peak Orders/sec", f"{baseline.peak_orders_per_second:.2f}")

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(2) from None
    except BaselineValidationError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {e}")
        raise SystemExit(3) from None
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from None


def list_baselines_command(
    tags: list[str] | None = None,
    branch: str | None = None,
    baselines_dir: Path | None = None,
) -> None:
    """
    List all saved baselines.

    Args:
        tags: Optional tags to filter by
        branch: Optional git branch to filter by
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    baselines = manager.list(tags=tags, branch=branch)

    if not baselines:
        console.print("[yellow]No baselines found.[/yellow]")
        if tags or branch:
            console.print("[dim]Try removing filters to see all baselines.[/dim]")
        else:
            console.print(
                "\n[dim]Save baselines programmatically with BaselineManager.save()[/dim]"
            )
            console.print("[dim]See docs/architecture.md for usage examples.[/dim]")
        return

    # Display baselines table
    table = Table(title="Saved Baselines", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Created", style="dim")
    table.add_column("Branch", style="cyan")
    table.add_column("Commit", style="dim")
    table.add_column("Orders/sec", justify="right")
    table.add_column("Tags", style="dim")

    for metadata in baselines:
        # Format timestamp
        try:
            timestamp = datetime.fromtimestamp(metadata.created_at)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")
        except Exception:
            timestamp_str = "unknown"

        # Format commit (truncate)
        commit_str = metadata.git_commit[:8] if metadata.git_commit else "N/A"

        # Format tags
        tags_str = ", ".join(metadata.tags) if metadata.tags else ""

        table.add_row(
            metadata.name,
            timestamp_str,
            metadata.git_branch or "N/A",
            commit_str,
            f"{metadata.orders_per_second:.2f}",
            tags_str,
        )

    console.print(table)


def delete_baseline_command(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """
    Delete a saved baseline.

    Args:
        name: Baseline name or ID
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    try:
        manager.delete(name)
        console.print(f"[bold green]\u2713[/bold green] Baseline deleted: {name}")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(2) from None
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from None


# Keep these functions for backward compatibility during transition
# They will be removed in a future version


def save_baseline(
    name: str,
    metrics: dict[str, Any],
    baselines_dir: Path | None = None,
) -> Path:
    """Deprecated: Use BaselineManager.save() instead."""
    raise NotImplementedError("save_baseline() is deprecated. Use BaselineManager.save() instead.")


def load_baseline(
    name: str,
    baselines_dir: Path | None = None,
) -> dict[str, Any]:
    """Deprecated: Use BaselineManager.load() instead."""
    raise NotImplementedError("load_baseline() is deprecated. Use BaselineManager.load() instead.")


def list_baselines(baselines_dir: Path | None = None) -> list[dict[str, Any]]:
    """Deprecated: Use BaselineManager.list() instead."""
    raise NotImplementedError("list_baselines() is deprecated. Use BaselineManager.list() instead.")


def delete_baseline(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """Deprecated: Use BaselineManager.delete() instead."""
    raise NotImplementedError(
        "delete_baseline() is deprecated. Use BaselineManager.delete() instead."
    )
