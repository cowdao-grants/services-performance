"""Scale command: run a doubling-sequence scaling experiment and classify complexity."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from cow_performance.benchmarking import (
    ComplexityAnalyzer,
    ComplexityEntry,
    DockerMemorySampler,
    ScalingPhaseResult,
    ScalingReport,
)

from ..config import PerformanceTestConfig
from .run import run_performance_test

logger = logging.getLogger(__name__)

_DEFAULT_ORDER_COUNTS = [50, 100, 200, 400, 800, 1600, 3200, 6400, 12800]
_DEFAULT_MONITOR_CONTAINERS = ["autopilot", "driver", "orderbook"]
_METRICS_TO_ANALYZE = [
    "p99_submission_latency_ms",
    "p99_lifecycle_latency_ms",
    "total_memory_delta_bytes",
]


def _build_step_config(
    base: PerformanceTestConfig,
    order_count: int,
    duration_per_step: int,
) -> PerformanceTestConfig:
    """Return a config copy with base_rate and duration overridden for one step.

    base_rate (orders/min per trader) = total_target / duration_seconds * 60 / num_traders
    """
    num_traders = base.default_trader_count
    if base.num_traders is not None:
        num_traders = base.num_traders

    # Avoid division by zero
    effective_traders = max(1, num_traders)
    rate_per_trader = (order_count / duration_per_step * 60.0) / effective_traders

    return base.model_copy(
        update={
            "base_rate": max(1.0, rate_per_trader),
            "default_duration": duration_per_step,
            "trading_pattern": "constant_rate",
        }
    )


def _extract_phase_metrics(results: dict[str, Any]) -> dict[str, float]:
    """Pull the metrics we need from the run_performance_test result dict."""
    perf = results.get("performance", {})
    orders = results.get("orders", {})
    timing = results.get("timing", {})
    return {
        "orders_submitted": float(orders.get("total_submitted", 0)),
        "orders_filled": float(orders.get("orders_filled", 0)),
        "duration_seconds": float(timing.get("duration_seconds", 0)),
        "p99_submission_latency_ms": float(perf.get("submission_latency_p99_ms", 0.0)),
        "p99_lifecycle_latency_ms": float(perf.get("order_lifecycle_p99_ms", 0.0)),
        "orders_per_second": float(perf.get("orders_per_second", 0.0)),
    }


def _print_report(report: ScalingReport, console: Console) -> None:
    """Render the ScalingReport to the console using Rich tables."""
    console.print()
    console.print(
        f"[bold green]Scaling Report:[/bold green] {report.scenario_name}",
        justify="center",
    )
    console.print()

    # Phase table
    phase_table = Table(
        title="Phase Results",
        show_header=True,
        header_style="bold cyan",
    )
    phase_table.add_column("Orders (target)", justify="right")
    phase_table.add_column("Submitted", justify="right")
    phase_table.add_column("Filled", justify="right")
    phase_table.add_column("p99 Submit (ms)", justify="right")
    phase_table.add_column("p99 Lifecycle (ms)", justify="right")
    phase_table.add_column("Mem Δ (MB)", justify="right")

    for p in report.phases:
        mem_mb = p.total_memory_delta_bytes / (1024 * 1024) if p.total_memory_delta_bytes else 0.0
        phase_table.add_row(
            str(p.order_count_target),
            str(p.orders_submitted),
            str(p.orders_filled),
            f"{p.p99_submission_latency_ms:.0f}",
            f"{p.p99_lifecycle_latency_ms:.0f}",
            f"{mem_mb:+.1f}",
        )

    console.print(phase_table)
    console.print()

    if report.complexity_results:
        # Complexity table
        cx_table = Table(
            title="Complexity Classification",
            show_header=True,
            header_style="bold magenta",
        )
        cx_table.add_column("Metric")
        cx_table.add_column("Slope (k)")
        cx_table.add_column("R²")
        cx_table.add_column("Class")
        cx_table.add_column("Label")

        for c in report.complexity_results:
            fit_color = "green" if c.r_squared >= 0.90 else "yellow"
            cx_table.add_row(
                c.metric,
                f"{c.slope:.3f}",
                f"[{fit_color}]{c.r_squared:.3f}[/{fit_color}]",
                c.complexity_class,
                c.label,
            )

        console.print(cx_table)
        console.print()


def scale_command(
    config: PerformanceTestConfig,
    order_counts: list[int],
    duration_per_step: int,
    monitor_containers: list[str],
    output_file: Path | None,
    skip_memory: bool,
    verbose: bool,
) -> None:
    """Execute a scaling experiment across doubling order counts.

    For each order count in *order_counts*:
    1. Capture container RSS before the test.
    2. Run a full performance test with the appropriate rate.
    3. Capture container RSS after the test.
    4. Record phase metrics.

    After all phases, run log-log regression on latency and memory metrics
    to classify algorithmic complexity.

    Args:
        config: Base PerformanceTestConfig (base_rate and duration will be overridden).
        order_counts: Ordered list of target order counts (e.g. [50, 100, 200, ...]).
        duration_per_step: Duration in seconds for each test phase.
        monitor_containers: Docker container names to sample for RSS memory.
        output_file: Optional path to write the JSON report.
        skip_memory: Skip Docker memory sampling (useful when Docker is unavailable).
        verbose: Enable verbose output.
    """
    console = Console()
    sampler = DockerMemorySampler()
    analyzer = ComplexityAnalyzer()

    scenario_name = config.name or "scaling-complexity"

    console.print(f"[bold cyan]Scaling Experiment:[/bold cyan] {scenario_name}")
    console.print(f"  Steps : {order_counts}")
    console.print(
        f"  Step duration: {duration_per_step}s | "
        f"Traders: {config.num_traders or config.default_trader_count}"
    )
    if not skip_memory:
        console.print(f"  Memory containers: {monitor_containers}")
    console.print()

    phases: list[ScalingPhaseResult] = []

    for step_idx, order_count in enumerate(order_counts):
        console.rule(
            f"[bold]Step {step_idx + 1}/{len(order_counts)}: " f"{order_count} orders[/bold]"
        )

        step_config = _build_step_config(config, order_count, duration_per_step)

        if verbose:
            console.print(
                f"  base_rate={step_config.base_rate:.1f} orders/min/trader, "
                f"duration={step_config.default_duration}s"
            )

        # Memory snapshot before
        mem_before = sampler.capture(monitor_containers) if not skip_memory else {}

        try:
            results = asyncio.run(
                run_performance_test(
                    config=step_config,
                    duration=duration_per_step,
                    verbose=verbose,
                )
            )
        except Exception as exc:
            console.print(f"[bold red]Step failed:[/bold red] {exc}")
            if verbose:
                import traceback

                traceback.print_exc()
            console.print("[yellow]Skipping step and continuing...[/yellow]")
            continue

        # Memory snapshot after
        mem_after = sampler.capture(monitor_containers) if not skip_memory else {}
        mem_delta = sampler.delta_bytes(mem_before, mem_after)

        metrics = _extract_phase_metrics(results)

        phase = ScalingPhaseResult(
            order_count_target=order_count,
            orders_submitted=int(metrics["orders_submitted"]),
            orders_filled=int(metrics["orders_filled"]),
            duration_seconds=metrics["duration_seconds"],
            p99_submission_latency_ms=metrics["p99_submission_latency_ms"],
            p99_lifecycle_latency_ms=metrics["p99_lifecycle_latency_ms"],
            orders_per_second=metrics["orders_per_second"],
            memory_delta_bytes=mem_delta,
            total_memory_delta_bytes=sum(mem_delta.values()),
        )
        phases.append(phase)

        console.print(
            f"  [green]✓[/green] submitted={phase.orders_submitted} "
            f"filled={phase.orders_filled} "
            f"p99_submit={phase.p99_submission_latency_ms:.0f}ms "
            f"p99_lifecycle={phase.p99_lifecycle_latency_ms:.0f}ms"
        )

    if not phases:
        console.print("[bold red]No phases completed — cannot produce report.[/bold red]")
        sys.exit(1)

    # Complexity analysis
    xs = [float(p.order_count_target) for p in phases]
    complexity_results: list[ComplexityEntry] = []

    metrics_vectors: dict[str, list[float]] = {
        "p99_submission_latency_ms": [p.p99_submission_latency_ms for p in phases],
        "p99_lifecycle_latency_ms": [p.p99_lifecycle_latency_ms for p in phases],
        "total_memory_delta_bytes": [float(p.total_memory_delta_bytes) for p in phases],
    }

    for metric_name, ys in metrics_vectors.items():
        try:
            fit = analyzer.fit(xs, ys)
            complexity_results.append(
                ComplexityEntry(
                    metric=metric_name,
                    slope=fit.slope,
                    r_squared=fit.r_squared,
                    complexity_class=fit.complexity_class.value,
                    label=fit.label,
                )
            )
        except ValueError as exc:
            logger.debug("Complexity fit skipped for %s: %s", metric_name, exc)

    report = ScalingReport(
        scenario_name=scenario_name,
        phases=phases,
        complexity_results=complexity_results,
    )

    _print_report(report, console)

    if output_file is not None:
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(report.to_json())
            console.print(f"[bold green]✓[/bold green] Report saved to [cyan]{output_file}[/cyan]")
        except Exception as exc:
            console.print(f"[bold red]Error saving report:[/bold red] {exc}")
            sys.exit(1)
