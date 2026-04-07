"""Scale command: run a doubling-sequence scaling experiment and classify complexity."""

import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from web3 import Web3

from cow_performance.benchmarking import (
    ComplexityAnalyzer,
    ComplexityEntry,
    DockerMemorySampler,
    ScalingPhaseResult,
    ScalingReport,
)
from cow_performance.prometheus import PrometheusExporter

from ..config import PerformanceTestConfig
from ..wallet_funding import create_trader_pool_from_config, fund_trader_pool
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
    funded_private_keys: list[str] | None = None,
) -> PerformanceTestConfig:
    """Return a config copy with base_rate and duration overridden for one step.

    base_rate (orders/min per trader) = total_target / duration_seconds * 60 / num_traders
    If funded_private_keys is provided, the step config disables wallet funding and
    injects the pre-funded keys so wallets aren't re-funded on every step.
    """
    num_traders = base.default_trader_count
    if base.num_traders is not None:
        num_traders = base.num_traders

    # Avoid division by zero
    effective_traders = max(1, num_traders)
    rate_per_trader = (order_count / duration_per_step * 60.0) / effective_traders

    update: dict = {
        "base_rate": max(1.0, rate_per_trader),
        "default_duration": duration_per_step,
        "trading_pattern": "constant_rate",
    }

    if funded_private_keys is not None:
        # Reuse pre-funded wallets; disable funding so run_performance_test skips it
        wallet_update = base.wallet.model_copy(
            update={"funding_enabled": False, "private_keys": funded_private_keys}
        )
        update["wallet"] = wallet_update

    return base.model_copy(update=update)


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
    prometheus_port: int | None = None,
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
        prometheus_port: Optional port to expose Prometheus metrics during the experiment.
    """
    console = Console()
    sampler = DockerMemorySampler()
    analyzer = ComplexityAnalyzer()

    scenario_name = config.name or "scaling-complexity"

    # Start a single shared exporter for the entire experiment to avoid port conflicts
    shared_exporter: PrometheusExporter | None = None
    if prometheus_port is not None:
        shared_exporter = PrometheusExporter(
            port=prometheus_port,
            scenario=config.trading_pattern,
        )
        shared_exporter.start()
        console.print(
            f"[cyan]Prometheus Exporter:[/cyan] http://localhost:{prometheus_port}/metrics"
        )

    secs_per_step = duration_per_step * 2  # trading + settlement wait (equal by design)
    total_est_secs = len(order_counts) * secs_per_step

    def _fmt_secs(s: float) -> str:
        m, sec = divmod(int(s), 60)
        return f"{m}m {sec:02d}s" if m else f"{sec}s"

    console.print(f"[bold cyan]Scaling Experiment:[/bold cyan] {scenario_name}")
    console.print(f"  Steps        : {order_counts}")
    console.print(
        f"  Step duration: {duration_per_step}s trading + {duration_per_step}s settlement wait"
    )
    console.print(f"  Traders      : {config.num_traders or config.default_trader_count}")
    if not skip_memory:
        console.print(f"  Memory containers: {monitor_containers}")
    console.print(
        f"\n  [bold yellow]Estimated total time: {_fmt_secs(total_est_secs)} "
        f"({len(order_counts)} steps × ~{_fmt_secs(secs_per_step)}/step)[/bold yellow]"
    )
    console.print()

    # Fund wallets once before the loop so each step reuses the same accounts.
    # Without this, run_performance_test generates fresh wallets every step
    # and funds them, resulting in num_steps × num_traders × num_tokens transactions.
    funded_private_keys: list[str] | None = None
    if config.wallet.funding_enabled:
        num_traders = config.num_traders or config.default_trader_count
        console.print(f"Connecting to RPC at {config.network.rpc_url}...")
        _web3 = Web3(Web3.HTTPProvider(config.network.rpc_url, request_kwargs={"timeout": 120}))
        if not _web3.is_connected():
            console.print(
                f"[bold red]Error:[/bold red] Cannot connect to RPC at {config.network.rpc_url}"
            )
            sys.exit(1)
        console.print(
            f"[green]✓[/green] Connected (chain {_web3.eth.chain_id}). "
            f"Funding {num_traders} wallets (once for all steps)..."
        )

        # Lower the base fee to 1 wei so CoW Protocol quote fees are negligible.
        # Forked mainnet gas prices cause fees of 100+ WETH per order. Even 1 gwei
        # is too high for USDC sell orders (6 decimals: 240M units = 240 USDC fee).
        # 1 wei makes fees effectively zero for all token types.
        _web3.provider.make_request(  # type: ignore[union-attr]
            "anvil_setNextBlockBaseFeePerGas", [hex(1)]
        )
        console.print("[green]✓[/green] Base fee set to 1 wei (fees negligible for all tokens)")

        _pool = create_trader_pool_from_config(config.wallet, num_traders)
        fund_trader_pool(
            web3=_web3,
            trader_pool=_pool,
            eth_balance=config.wallet.eth_balance,
            token_balances=config.wallet.token_balances,
            vault_relayer=config.network.vault_relayer,
        )
        funded_private_keys = [t.private_key for t in _pool.get_all_traders()]
        console.print(f"[green]✓[/green] Funded {len(funded_private_keys)} wallets\n")

    phases: list[ScalingPhaseResult] = []
    experiment_start = time.monotonic()

    for step_idx, order_count in enumerate(order_counts):
        steps_done = step_idx
        elapsed = time.monotonic() - experiment_start
        if steps_done > 0:
            avg_step = elapsed / steps_done
            remaining = avg_step * (len(order_counts) - steps_done)
            eta_str = f"  ETA: ~{_fmt_secs(remaining)} remaining"
        else:
            eta_str = f"  ETA: ~{_fmt_secs(total_est_secs - elapsed)} remaining"

        console.rule(
            f"[bold]Step {step_idx + 1}/{len(order_counts)}: {order_count} orders[/bold]"
        )
        console.print(eta_str)

        step_config = _build_step_config(
            config, order_count, duration_per_step, funded_private_keys
        )

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
                    settlement_wait=duration_per_step,
                    verbose=verbose,
                    prometheus_exporter=shared_exporter,
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

        step_elapsed = time.monotonic() - experiment_start - elapsed
        console.print(
            f"  [green]✓[/green] submitted={phase.orders_submitted} "
            f"filled={phase.orders_filled} "
            f"p99_submit={phase.p99_submission_latency_ms:.0f}ms "
            f"p99_lifecycle={phase.p99_lifecycle_latency_ms:.0f}ms "
            f"[dim](step took {_fmt_secs(step_elapsed)})[/dim]"
        )

    # Stop the shared exporter now that all steps are done
    if shared_exporter is not None:
        shared_exporter.stop()

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

