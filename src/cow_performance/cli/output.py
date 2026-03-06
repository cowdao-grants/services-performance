"""Output formatting utilities for performance test results."""

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


def format_metrics_json(metrics: dict[str, Any]) -> str:
    """Format metrics as JSON string.

    Args:
        metrics: The metrics dictionary

    Returns:
        JSON formatted string
    """
    return json.dumps(metrics, indent=2)


def format_metrics_for_prometheus(metrics: dict[str, Any]) -> dict[str, float]:
    """Format metrics as flat dictionary suitable for Prometheus.

    Converts nested metrics dictionary into flat key-value pairs with
    Prometheus-style metric names.

    Args:
        metrics: The metrics dictionary with nested structure

    Returns:
        Flat dictionary with Prometheus-compatible metric names
    """
    flat_metrics: dict[str, float] = {}

    # Orchestration metrics
    if "orchestration" in metrics:
        orch = metrics["orchestration"]
        flat_metrics["cow_perf_traders_total"] = float(orch.get("num_traders", 0))
        flat_metrics["cow_perf_duration_seconds"] = float(orch.get("duration", 0))

    # Order metrics
    if "orders" in metrics:
        orders = metrics["orders"]
        flat_metrics["cow_perf_orders_total"] = float(orders.get("total_submitted", 0))
        flat_metrics["cow_perf_orders_market"] = float(orders.get("market_orders", 0))
        flat_metrics["cow_perf_orders_limit"] = float(orders.get("limit_orders", 0))
        flat_metrics["cow_perf_orders_twap"] = float(orders.get("twap_orders", 0))
        flat_metrics["cow_perf_orders_stop_loss"] = float(orders.get("stop_loss_orders", 0))
        flat_metrics["cow_perf_orders_good_after_time"] = float(
            orders.get("good_after_time_orders", 0)
        )

    # Performance metrics
    if "performance" in metrics:
        perf = metrics["performance"]
        flat_metrics["cow_perf_orders_per_second"] = float(perf.get("orders_per_second", 0.0))
        flat_metrics["cow_perf_avg_order_latency_ms"] = float(perf.get("avg_order_latency_ms", 0.0))

    # Trader metrics
    if "traders" in metrics:
        traders = metrics["traders"]
        flat_metrics["cow_perf_traders_active"] = float(traders.get("active_traders", 0))

    return flat_metrics


def format_metrics_prometheus_text(metrics: dict[str, Any]) -> str:
    """Format metrics in Prometheus text exposition format.

    Args:
        metrics: The metrics dictionary

    Returns:
        String in Prometheus text format
    """
    flat_metrics = format_metrics_for_prometheus(metrics)

    lines = []
    for key, value in sorted(flat_metrics.items()):
        # Add HELP and TYPE comments for each metric
        lines.append(f"# HELP {key} CoW Protocol performance test metric")
        lines.append(f"# TYPE {key} gauge")
        lines.append(f"{key} {value}")
        lines.append("")

    return "\n".join(lines)


def format_metrics_csv(metrics: dict[str, Any]) -> str:
    """Format metrics as CSV string.

    Args:
        metrics: The metrics dictionary

    Returns:
        CSV formatted string
    """
    flat_metrics = format_metrics_for_prometheus(metrics)

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["metric", "value"])

    # Write data
    for key, value in sorted(flat_metrics.items()):
        writer.writerow([key, value])

    return output.getvalue()


def format_metrics_table(metrics: dict[str, Any], console: Console | None = None) -> None:
    """Format and print metrics as Rich tables.

    Args:
        metrics: The metrics dictionary
        console: Optional Rich Console instance (creates new one if None)
    """
    if console is None:
        console = Console()

    # Orchestration summary
    if "orchestration" in metrics:
        orch = metrics["orchestration"]
        table = Table(title="Orchestration Summary", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Traders", str(orch.get("num_traders", 0)))
        table.add_row("Duration", f"{orch.get('duration', 0)}s")
        table.add_row("Startup Interval", f"{orch.get('startup_interval', 0)}s")

        console.print(table)
        console.print()

    # Order statistics
    if "orders" in metrics:
        orders = metrics["orders"]
        table = Table(title="Order Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Order Type", style="cyan")
        table.add_column("Count", style="green", justify="right")

        table.add_row("Total Orders", str(orders.get("total_submitted", 0)))
        table.add_row("Market Orders", str(orders.get("market_orders", 0)))
        table.add_row("Limit Orders", str(orders.get("limit_orders", 0)))
        table.add_row("TWAP Orders", str(orders.get("twap_orders", 0)))
        table.add_row("Stop-Loss Orders", str(orders.get("stop_loss_orders", 0)))
        table.add_row("Good-After-Time Orders", str(orders.get("good_after_time_orders", 0)))

        console.print(table)
        console.print()

    # Performance metrics
    if "performance" in metrics:
        perf = metrics["performance"]
        table = Table(title="Performance Metrics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Orders per Second", f"{perf.get('orders_per_second', 0.0):.2f}")
        table.add_row("Avg Order Latency", f"{perf.get('avg_order_latency_ms', 0.0):.2f}ms")

        if "p50_latency_ms" in perf:
            table.add_row("P50 Latency", f"{perf['p50_latency_ms']:.2f}ms")
        if "p95_latency_ms" in perf:
            table.add_row("P95 Latency", f"{perf['p95_latency_ms']:.2f}ms")
        if "p99_latency_ms" in perf:
            table.add_row("P99 Latency", f"{perf['p99_latency_ms']:.2f}ms")

        console.print(table)
        console.print()

    # Trader statistics
    if "traders" in metrics:
        traders = metrics["traders"]
        table = Table(title="Trader Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Active Traders", str(traders.get("active_traders", 0)))
        table.add_row("Total Traders", str(traders.get("total_traders", 0)))

        console.print(table)


def save_metrics_to_file(
    metrics: dict[str, Any],
    output_format: str,
    output_path: Path,
) -> None:
    """Save metrics to file in specified format.

    Args:
        metrics: The metrics dictionary
        output_format: Format to use (json, csv, prometheus)
        output_path: Path where to save the file

    Raises:
        ValueError: If output format is not supported
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "json":
        content = format_metrics_json(metrics)
    elif output_format == "csv":
        content = format_metrics_csv(metrics)
    elif output_format == "prometheus":
        content = format_metrics_prometheus_text(metrics)
    else:
        raise ValueError(
            f"Unsupported output format: {output_format}. "
            f"Supported formats: json, csv, prometheus"
        )

    with open(output_path, "w") as f:
        f.write(content)


def create_result_filename(
    prefix: str = "results",
    output_format: str = "json",
    timestamp: datetime | None = None,
) -> str:
    """Create a timestamped filename for results.

    Args:
        prefix: Prefix for the filename
        output_format: File format (determines extension)
        timestamp: Optional timestamp (uses current time if None)

    Returns:
        Filename string
    """
    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")

    extensions = {
        "json": "json",
        "csv": "csv",
        "prometheus": "txt",
        "table": "txt",
    }

    ext = extensions.get(output_format, "txt")

    return f"{prefix}-{timestamp_str}.{ext}"
