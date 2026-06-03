"""
Live metrics display for CLI during test execution.

Provides real-time metrics visualization using Rich Live display.
"""

import asyncio
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cow_performance.metrics import (
    MetricsAggregator,
    MetricsEventStream,
    MetricsStore,
    RollingMetricsSummary,
)


class LiveMetricsDisplay:
    """
    Real-time metrics display for CLI.

    Shows live updating metrics during performance test execution
    using Rich Live display.
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        console: Console | None = None,
        refresh_rate: float = 1.0,
    ):
        """
        Initialize the live display.

        Args:
            metrics_store: The metrics store to display
            console: Optional Rich Console instance
            refresh_rate: Display refresh rate in seconds
        """
        self._store = metrics_store
        self._console = console or Console()
        self._refresh_rate = refresh_rate
        self._stream: MetricsEventStream | None = None
        self._rolling_summary = RollingMetricsSummary(window_size=100)
        self._running = False
        self._start_time: datetime | None = None
        self._live: Live | None = None
        self._task: asyncio.Task[None] | None = None

    def _build_header(self) -> Panel:
        """Build the header panel."""
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            elapsed_str = f"{elapsed:.1f}s"
        else:
            elapsed_str = "0.0s"

        header_text = Text()
        header_text.append("CoW Protocol Performance Test", style="bold cyan")
        header_text.append(f"  |  Elapsed: {elapsed_str}", style="green")

        return Panel(header_text, style="blue")

    def _build_order_stats_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the order statistics table."""
        metrics = aggregator.aggregate_orders()

        table = Table(title="Order Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Orders", str(metrics.total_orders))
        table.add_row("Filled", str(metrics.orders_filled))
        table.add_row("Failed", str(metrics.orders_failed))
        table.add_row("Expired", str(metrics.orders_expired))

        if metrics.total_orders > 0:
            table.add_row("Success Rate", f"{metrics.success_rate * 100:.1f}%")

        return table

    def _build_latency_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the latency statistics table."""
        metrics = aggregator.aggregate_orders()

        table = Table(title="Latency (seconds)", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("P50", style="green", justify="right")
        table.add_column("P95", style="yellow", justify="right")
        table.add_column("P99", style="red", justify="right")

        if metrics.time_to_fill.count > 0:
            table.add_row(
                "Time to Fill",
                f"{metrics.time_to_fill.p50:.3f}",
                f"{metrics.time_to_fill.p95:.3f}",
                f"{metrics.time_to_fill.p99:.3f}",
            )

        if metrics.total_lifecycle.count > 0:
            table.add_row(
                "Total Lifecycle",
                f"{metrics.total_lifecycle.p50:.3f}",
                f"{metrics.total_lifecycle.p95:.3f}",
                f"{metrics.total_lifecycle.p99:.3f}",
            )

        return table

    def _build_api_stats_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the API statistics table."""
        metrics = aggregator.aggregate_api_metrics()

        table = Table(title="API Metrics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Requests", str(metrics.total_requests))
        table.add_row("Success Rate", f"{metrics.success_rate * 100:.1f}%")

        if metrics.response_time.count > 0:
            table.add_row("Avg Response", f"{metrics.response_time.mean:.1f}ms")
            table.add_row("P95 Response", f"{metrics.response_time.p95:.1f}ms")

        if metrics.requests_per_second > 0:
            table.add_row("Requests/sec", f"{metrics.requests_per_second:.2f}")

        return table

    def _build_throughput_table(self, aggregator: MetricsAggregator) -> Table:
        """Build the throughput table."""
        throughput = aggregator.calculate_throughput()

        table = Table(title="Throughput", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Orders/sec", f"{throughput['orders_per_second']:.2f}")
        table.add_row("API Requests/sec", f"{throughput['api_requests_per_second']:.2f}")

        return table

    def _build_display(self) -> Layout:
        """Build the complete display layout."""
        aggregator = MetricsAggregator(self._store)

        layout = Layout()

        # Header
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        layout["header"].update(self._build_header())

        # Body with stats
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        # Left column: Orders and Latency
        layout["left"].split(
            Layout(self._build_order_stats_table(aggregator)),
            Layout(self._build_latency_table(aggregator)),
        )

        # Right column: API and Throughput
        layout["right"].split(
            Layout(self._build_api_stats_table(aggregator)),
            Layout(self._build_throughput_table(aggregator)),
        )

        return layout

    async def _update_loop(self) -> None:
        """Background loop to process events and update rolling summary."""
        if self._stream is None:
            return

        while self._running:
            event = await self._stream.get_event(timeout=0.1)
            if event is not None:
                self._rolling_summary.add_event(event)

    async def start(self) -> None:
        """Start the live display."""
        if self._running:
            return

        self._running = True
        self._start_time = datetime.now()

        # Start event stream
        self._stream = MetricsEventStream(self._store)
        await self._stream.start()

        # Start background event processing
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        """Stop the live display."""
        if not self._running:
            return

        self._running = False

        # Stop event stream
        if self._stream:
            await self._stream.stop()

        # Cancel background task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_live_context(self) -> Live:
        """
        Get Rich Live context manager for display.

        Returns:
            Rich Live instance configured for metrics display
        """
        return Live(
            self._build_display(),
            console=self._console,
            refresh_per_second=1.0 / self._refresh_rate,
            transient=True,
        )

    def update(self) -> Layout:
        """
        Get updated display layout.

        Returns:
            Updated Rich Layout
        """
        return self._build_display()


def create_performance_metrics_dict(
    metrics_store: MetricsStore,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """
    Create performance metrics dict for CLI output.

    Includes percentile latencies expected by output.py.

    Args:
        metrics_store: The metrics store
        elapsed_seconds: Test duration in seconds

    Returns:
        Dict with performance metrics including percentiles
    """
    aggregator = MetricsAggregator(metrics_store)

    order_metrics = aggregator.aggregate_orders()
    api_metrics = aggregator.aggregate_api_metrics()
    throughput = aggregator.calculate_throughput()

    # Build performance dict with fields expected by output.py
    performance: dict[str, Any] = {
        "orders_per_second": throughput["orders_per_second"],
        "avg_order_latency_ms": order_metrics.total_lifecycle.mean * 1000,
    }

    # Add percentile latencies (in milliseconds)
    if order_metrics.total_lifecycle.count > 0:
        performance["p50_latency_ms"] = order_metrics.total_lifecycle.p50 * 1000
        performance["p95_latency_ms"] = order_metrics.total_lifecycle.p95 * 1000
        performance["p99_latency_ms"] = order_metrics.total_lifecycle.p99 * 1000

    # Add API metrics
    performance["api_success_rate"] = api_metrics.success_rate
    if api_metrics.response_time.count > 0:
        performance["avg_api_response_ms"] = api_metrics.response_time.mean
        performance["p95_api_response_ms"] = api_metrics.response_time.p95

    return performance
