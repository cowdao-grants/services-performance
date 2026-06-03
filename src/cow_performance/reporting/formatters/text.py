"""Plain text report formatter with optional color support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationSeverity,
    ReportVerdict,
)
from cow_performance.reporting.summary import (
    format_duration,
    format_latency,
    format_rate,
)

if TYPE_CHECKING:
    from cow_performance.baselines.models import PerformanceBaseline
    from cow_performance.comparison.models import ComparisonResult


class TextReportFormatter:
    """
    Formats performance reports as plain text.

    Supports optional ANSI color codes for terminal output.
    """

    def __init__(self, use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            use_colors: Whether to use ANSI color codes
        """
        self._use_colors = use_colors

    def format(self, report: PerformanceReport) -> str:
        """
        Format a complete performance report.

        Args:
            report: The report to format

        Returns:
            Formatted text string
        """
        lines: list[str] = []

        # Header
        lines.append(self._header("PERFORMANCE REPORT"))
        lines.append("")
        lines.append(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Report ID: {report.report_id}")
        if report.git_commit:
            lines.append(f"Git: {report.git_branch or 'detached'}@{report.git_commit[:8]}")
        lines.append("")

        # Executive Summary
        if report.summary:
            lines.extend(self._format_summary(report.summary))
            lines.append("")

        # Detailed Metrics
        if report.baseline:
            lines.extend(self._format_metrics(report.baseline))
            lines.append("")

        # Comparison Results
        if report.comparison:
            lines.extend(self._format_comparison(report.comparison))
            lines.append("")

        # Recommendations
        if report.recommendations:
            lines.extend(self._format_recommendations(report.recommendations))
            lines.append("")

        # Footer
        lines.append(self._divider())

        return "\n".join(lines)

    def _header(self, text: str) -> str:
        """Format a major header."""
        divider = "=" * 70
        return f"{divider}\n{text:^70}\n{divider}"

    def _subheader(self, text: str) -> str:
        """Format a section header."""
        return f"\n{'-' * 70}\n{text}\n{'-' * 70}"

    def _divider(self) -> str:
        """Return a divider line."""
        return "=" * 70

    def _color(self, text: str, color: str) -> str:
        """Apply ANSI color if colors are enabled."""
        if not self._use_colors:
            return text

        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def _verdict_str(self, verdict: ReportVerdict) -> str:
        """Format verdict with appropriate color."""
        if verdict == ReportVerdict.SUCCESS:
            return self._color("[SUCCESS]", "green")
        elif verdict == ReportVerdict.WARNING:
            return self._color("[WARNING]", "yellow")
        else:
            return self._color("[FAILURE]", "red")

    def _format_summary(self, summary: ExecutiveSummary) -> list[str]:
        """Format the executive summary section."""
        lines = [self._subheader("EXECUTIVE SUMMARY")]

        # Verdict
        lines.append(f"\nVerdict: {self._verdict_str(summary.verdict)}")
        lines.append(f"Reason:  {summary.verdict_reason}")
        lines.append("")

        # Test info
        lines.append(f"Test:     {summary.test_name}")
        lines.append(f"Duration: {format_duration(summary.test_duration_seconds)}")
        lines.append(
            f"Period:   {summary.test_start_time.strftime('%H:%M:%S')} - "
            f"{summary.test_end_time.strftime('%H:%M:%S')}"
        )
        lines.append("")

        # Order metrics table
        lines.append("Order Metrics:")
        lines.append(f"  Submitted:     {summary.total_orders_submitted:,}")
        lines.append(f"  Filled:        {summary.total_orders_filled:,}")
        lines.append(f"  Failed:        {summary.total_orders_failed:,}")
        lines.append(f"  Success Rate:  {format_rate(summary.success_rate)}")
        lines.append("")

        # Throughput
        lines.append("Throughput:")
        lines.append(f"  Average: {summary.average_throughput:.2f} orders/sec")
        lines.append(f"  Peak:    {summary.peak_throughput:.2f} orders/sec")
        lines.append("")

        # Latency
        lines.append("Latency (P95):")
        lines.append(f"  Submission:  {format_latency(summary.submission_latency_p95_ms)}")
        lines.append(f"  Fill:        {format_latency(summary.fill_latency_p95_ms)}")
        lines.append(f"  Lifecycle:   {format_latency(summary.total_lifecycle_p95_ms)}")
        lines.append("")

        # API metrics
        lines.append("API Performance:")
        lines.append(f"  Requests:      {summary.total_api_requests:,}")
        lines.append(f"  Success Rate:  {format_rate(summary.api_success_rate)}")
        lines.append(f"  Response P95:  {format_latency(summary.api_response_time_p95_ms)}")

        # Key findings
        if summary.key_findings:
            lines.append("")
            lines.append("Key Findings:")
            for finding in summary.key_findings:
                lines.append(f"  * {finding}")

        return lines

    def _format_metrics(self, baseline: PerformanceBaseline) -> list[str]:
        """Format detailed metrics."""
        lines = [self._subheader("DETAILED METRICS")]

        # Order metrics percentiles
        if baseline.order_metrics:
            om = baseline.order_metrics
            lines.append("\nOrder Lifecycle Latencies:")
            lines.append("  Metric            P50       P90       P95       P99")
            lines.append("  " + "-" * 56)

            for name, stats in [
                ("Time to Submit", om.time_to_submit),
                ("Time to Accept", om.time_to_accept),
                ("Time to Fill", om.time_to_fill),
                ("Total Lifecycle", om.total_lifecycle),
            ]:
                if stats.count > 0:
                    lines.append(
                        f"  {name:16} "
                        f"{format_latency(stats.p50 * 1000):>8}  "
                        f"{format_latency(stats.p90 * 1000):>8}  "
                        f"{format_latency(stats.p95 * 1000):>8}  "
                        f"{format_latency(stats.p99 * 1000):>8}"
                    )

        # Resource metrics
        if baseline.resource_metrics:
            lines.append("\nResource Utilization:")
            lines.append("  Container         CPU(P95)  Memory(P95)")
            lines.append("  " + "-" * 42)

            for name, metrics in baseline.resource_metrics.items():
                lines.append(
                    f"  {name:16} "
                    f"{metrics.cpu_percent.p95:>7.1f}%  "
                    f"{metrics.memory_percent.p95:>9.1f}%"
                )

        return lines

    def _format_comparison(self, comparison: ComparisonResult) -> list[str]:
        """Format comparison results."""
        lines = [self._subheader("COMPARISON RESULTS")]

        lines.append(f"\nBaseline: {comparison.baseline_name}")
        lines.append(f"Current:  {comparison.current_name}")
        lines.append(f"Verdict:  {comparison.verdict.value.upper()}")
        lines.append("")

        # Regressions
        if comparison.regressions:
            lines.append(f"Regressions ({len(comparison.regressions)}):")
            for reg in comparison.regressions:
                severity = f"[{reg.regression_severity.value.upper()}]"
                lines.append(f"  {severity:10} {reg.metric_name}: {reg.context}")

        # Improvements
        if comparison.improvements:
            lines.append(f"\nImprovements ({len(comparison.improvements)}):")
            for imp in comparison.improvements:
                lines.append(f"  {imp.metric_name}: {imp.context}")

        return lines

    def _format_recommendations(self, recommendations: list[Recommendation]) -> list[str]:
        """Format recommendations section."""
        lines = [self._subheader("RECOMMENDATIONS")]

        for rec in recommendations:
            if rec.severity == RecommendationSeverity.CRITICAL:
                severity_str = self._color("[CRITICAL]", "red")
            elif rec.severity == RecommendationSeverity.WARNING:
                severity_str = self._color("[WARNING]", "yellow")
            else:
                severity_str = "[INFO]"

            lines.append(f"\n{severity_str} {rec.title}")
            lines.append(f"  Category: {rec.category.value}")
            lines.append(f"  {rec.description}")
            lines.append(f"  Action: {rec.action}")

        return lines
