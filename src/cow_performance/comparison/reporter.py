"""Report generation for comparison results."""

import json
from typing import Any

from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    RegressionSeverity,
)
from cow_performance.comparison.statistics import format_percent_change


class RegressionReporter:
    """
    Generates reports from comparison results.

    Supports multiple output formats: text, markdown, JSON.

    Example:
        reporter = RegressionReporter()
        text_report = reporter.generate_text_report(comparison_result)
        md_report = reporter.generate_markdown_report(comparison_result)
    """

    def __init__(self) -> None:
        """Initialize the reporter."""
        pass

    def generate_text_report(self, result: ComparisonResult) -> str:
        """
        Generate a plain text report.

        Args:
            result: The comparison result to report

        Returns:
            Formatted text report
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 70)
        lines.append("PERFORMANCE COMPARISON REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Summary
        lines.append(f"Baseline:  {result.baseline_name} ({result.baseline_id[:8]})")
        lines.append(f"Current:   {result.current_name} ({result.current_id[:8]})")
        lines.append(f"Compared:  {result.compared_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Verdict
        verdict_symbol = self._get_verdict_symbol(result.verdict)
        lines.append(f"VERDICT: {verdict_symbol} {result.verdict.value.upper()}")
        lines.append("")

        # Summary counts
        lines.append(f"Total metrics compared: {result.total_metrics_compared}")
        lines.append(f"Significant changes:    {result.significant_changes}")
        lines.append(f"Regressions:            {len(result.regressions)}")
        lines.append(f"  - Critical: {result.critical_count}")
        lines.append(f"  - Major:    {result.major_count}")
        lines.append(f"  - Minor:    {result.minor_count}")
        lines.append(f"Improvements:           {len(result.improvements)}")
        lines.append("")

        # Critical regressions (if any)
        if result.critical_count > 0:
            lines.append("-" * 70)
            lines.append("CRITICAL REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.CRITICAL:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Major regressions (if any)
        if result.major_count > 0:
            lines.append("-" * 70)
            lines.append("MAJOR REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.MAJOR:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Minor regressions (if any)
        if result.minor_count > 0:
            lines.append("-" * 70)
            lines.append("MINOR REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.MINOR:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Improvements (if any)
        if result.improvements:
            lines.append("-" * 70)
            lines.append("IMPROVEMENTS")
            lines.append("-" * 70)
            for comparison in result.improvements:
                lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Footer
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_markdown_report(self, result: ComparisonResult) -> str:
        """
        Generate a Markdown report suitable for GitHub PRs.

        Args:
            result: The comparison result to report

        Returns:
            Formatted Markdown report
        """
        lines: list[str] = []

        # Header with verdict badge
        verdict_emoji = self._get_verdict_emoji(result.verdict)
        lines.append(f"## {verdict_emoji} Performance Comparison Report")
        lines.append("")

        # Summary table
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Baseline | `{result.baseline_name}` ({result.baseline_id[:8]}) |")
        lines.append(f"| Current | `{result.current_name}` ({result.current_id[:8]}) |")
        lines.append(f"| Compared | {result.compared_at.strftime('%Y-%m-%d %H:%M:%S')} |")
        lines.append(f"| **Verdict** | **{result.verdict.value.upper()}** |")
        lines.append("")

        # Summary stats
        lines.append("### Summary")
        lines.append("")
        lines.append(f"- **Total metrics compared:** {result.total_metrics_compared}")
        lines.append(f"- **Significant changes:** {result.significant_changes}")
        lines.append(
            f"- **Regressions:** {len(result.regressions)} "
            f"({result.critical_count} critical, "
            f"{result.major_count} major, "
            f"{result.minor_count} minor)"
        )
        lines.append(f"- **Improvements:** {len(result.improvements)}")
        lines.append("")

        # Regressions section
        if result.regressions:
            lines.append("### Regressions")
            lines.append("")
            lines.append(self._generate_comparison_table_md(result.regressions))
            lines.append("")

        # Improvements section
        if result.improvements:
            lines.append("### Improvements")
            lines.append("")
            lines.append(self._generate_comparison_table_md(result.improvements))
            lines.append("")

        # Detailed metrics (collapsible)
        lines.append("<details>")
        lines.append("<summary>All Metric Comparisons</summary>")
        lines.append("")
        lines.append(self._generate_all_metrics_table_md(result))
        lines.append("")
        lines.append("</details>")
        lines.append("")

        return "\n".join(lines)

    def generate_json_report(self, result: ComparisonResult) -> str:
        """
        Generate a JSON report.

        Args:
            result: The comparison result to report

        Returns:
            JSON string
        """
        data = self._result_to_dict(result)
        return json.dumps(data, indent=2, default=str)

    def _get_verdict_symbol(self, verdict: ComparisonVerdict) -> str:
        """Get ASCII symbol for verdict."""
        mapping = {
            ComparisonVerdict.IMPROVEMENT: "[+]",
            ComparisonVerdict.REGRESSION: "[!]",
            ComparisonVerdict.NEUTRAL: "[=]",
        }
        return mapping[verdict]

    def _get_verdict_emoji(self, verdict: ComparisonVerdict) -> str:
        """Get emoji for verdict."""
        mapping = {
            ComparisonVerdict.IMPROVEMENT: "pass",
            ComparisonVerdict.REGRESSION: "warning",
            ComparisonVerdict.NEUTRAL: "neutral",
        }
        return mapping[verdict]

    def _get_severity_emoji(self, severity: RegressionSeverity) -> str:
        """Get emoji for severity level."""
        mapping = {
            RegressionSeverity.CRITICAL: "critical",
            RegressionSeverity.MAJOR: "major",
            RegressionSeverity.MINOR: "minor",
            RegressionSeverity.NONE: "none",
        }
        return mapping[severity]

    def _format_comparison_text(self, comparison: MetricComparison) -> str:
        """Format a single comparison for text output."""
        change_str = format_percent_change(comparison.percent_change)
        return (
            f"  {comparison.metric_name}:\n"
            f"    Baseline: {comparison.baseline_value:.4f}\n"
            f"    Current:  {comparison.current_value:.4f}\n"
            f"    Change:   {change_str}\n"
            f"    {comparison.context}"
        )

    def _generate_comparison_table_md(
        self,
        comparisons: list[MetricComparison],
    ) -> str:
        """Generate a Markdown table for comparisons."""
        lines = [
            "| Severity | Metric | Baseline | Current | Change |",
            "|----------|--------|----------|---------|--------|",
        ]

        for c in comparisons:
            severity_label = self._get_severity_emoji(c.regression_severity)
            change_str = format_percent_change(c.percent_change)
            lines.append(
                f"| {severity_label} | "
                f"`{c.metric_name}` | "
                f"{c.baseline_value:.4f} | "
                f"{c.current_value:.4f} | "
                f"{change_str} |"
            )

        return "\n".join(lines)

    def _generate_all_metrics_table_md(self, result: ComparisonResult) -> str:
        """Generate table with all metrics."""
        lines = [
            "| Metric | Type | Baseline | Current | Change | Significant |",
            "|--------|------|----------|---------|--------|-------------|",
        ]

        for name, c in sorted(result.metric_comparisons.items()):
            change_str = format_percent_change(c.percent_change)
            sig_str = "yes" if c.is_significant else "-"
            lines.append(
                f"| `{name}` | {c.metric_type.value} | "
                f"{c.baseline_value:.4f} | {c.current_value:.4f} | "
                f"{change_str} | {sig_str} |"
            )

        return "\n".join(lines)

    def _result_to_dict(self, result: ComparisonResult) -> dict[str, Any]:
        """Convert ComparisonResult to dict for JSON serialization."""
        return {
            "baseline_id": result.baseline_id,
            "baseline_name": result.baseline_name,
            "current_id": result.current_id,
            "current_name": result.current_name,
            "compared_at": result.compared_at.isoformat(),
            "verdict": result.verdict.value,
            "summary": {
                "total_metrics_compared": result.total_metrics_compared,
                "significant_changes": result.significant_changes,
                "regressions": len(result.regressions),
                "critical_count": result.critical_count,
                "major_count": result.major_count,
                "minor_count": result.minor_count,
                "improvements": len(result.improvements),
            },
            "regressions": [self._comparison_to_dict(c) for c in result.regressions],
            "improvements": [self._comparison_to_dict(c) for c in result.improvements],
            "all_comparisons": {
                name: self._comparison_to_dict(c) for name, c in result.metric_comparisons.items()
            },
        }

    def _comparison_to_dict(self, c: MetricComparison) -> dict[str, Any]:
        """Convert MetricComparison to dict."""
        return {
            "metric_name": c.metric_name,
            "metric_type": c.metric_type.value,
            "baseline_value": c.baseline_value,
            "current_value": c.current_value,
            "absolute_diff": c.absolute_diff,
            "percent_change": c.percent_change,
            "p_value": c.p_value,
            "effect_size": c.effect_size,
            "is_significant": c.is_significant,
            "regression_severity": c.regression_severity.value,
            "is_regression": c.is_regression,
            "is_improvement": c.is_improvement,
            "context": c.context,
        }
