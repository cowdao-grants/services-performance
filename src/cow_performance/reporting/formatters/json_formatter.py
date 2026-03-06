"""JSON report formatter for machine-readable output."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
)

if TYPE_CHECKING:
    from cow_performance.baselines.models import PerformanceBaseline
    from cow_performance.comparison.models import ComparisonResult


class JSONReportFormatter:
    """
    Formats performance reports as JSON.

    Designed for programmatic consumption and data pipelines.
    """

    def __init__(self, indent: int = 2):
        """
        Initialize the formatter.

        Args:
            indent: JSON indentation level (0 for compact)
        """
        self._indent = indent if indent > 0 else None

    def format(self, report: PerformanceReport) -> str:
        """
        Format a complete performance report as JSON.

        Args:
            report: The report to format

        Returns:
            JSON formatted string
        """
        data = self._report_to_dict(report)
        return json.dumps(data, indent=self._indent, default=self._json_serializer)

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "value"):  # Enum
            return obj.value
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _report_to_dict(self, report: PerformanceReport) -> dict[str, Any]:
        """Convert report to dictionary."""
        data: dict[str, Any] = {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "report_version": report.report_version,
            "test_name": report.test_name,
            "scenario_name": report.scenario_name,
            "git_commit": report.git_commit,
            "git_branch": report.git_branch,
        }

        if report.summary:
            data["summary"] = self._summary_to_dict(report.summary)

        if report.baseline:
            data["baseline"] = self._baseline_to_dict(report.baseline)

        if report.comparison:
            data["comparison"] = self._comparison_to_dict(report.comparison)

        if report.recommendations:
            data["recommendations"] = [
                self._recommendation_to_dict(r) for r in report.recommendations
            ]

        data["data_files"] = report.data_files

        return data

    def _summary_to_dict(self, summary: ExecutiveSummary) -> dict[str, Any]:
        """Convert executive summary to dictionary."""
        return {
            "test_name": summary.test_name,
            "test_duration_seconds": summary.test_duration_seconds,
            "test_start_time": summary.test_start_time.isoformat(),
            "test_end_time": summary.test_end_time.isoformat(),
            "total_orders_submitted": summary.total_orders_submitted,
            "total_orders_filled": summary.total_orders_filled,
            "total_orders_failed": summary.total_orders_failed,
            "success_rate": summary.success_rate,
            "average_throughput": summary.average_throughput,
            "peak_throughput": summary.peak_throughput,
            "submission_latency_p95_ms": summary.submission_latency_p95_ms,
            "fill_latency_p95_ms": summary.fill_latency_p95_ms,
            "total_lifecycle_p95_ms": summary.total_lifecycle_p95_ms,
            "total_api_requests": summary.total_api_requests,
            "api_success_rate": summary.api_success_rate,
            "api_response_time_p95_ms": summary.api_response_time_p95_ms,
            "verdict": summary.verdict.value,
            "verdict_reason": summary.verdict_reason,
            "key_findings": summary.key_findings,
        }

    def _baseline_to_dict(self, baseline: PerformanceBaseline) -> dict[str, Any]:
        """Convert baseline to dictionary (reuse existing serialization)."""
        from cow_performance.baselines.models import baseline_to_dict

        return baseline_to_dict(baseline)

    def _comparison_to_dict(self, comparison: ComparisonResult) -> dict[str, Any]:
        """Convert comparison result to dictionary."""
        return {
            "baseline_id": comparison.baseline_id,
            "baseline_name": comparison.baseline_name,
            "current_id": comparison.current_id,
            "current_name": comparison.current_name,
            "compared_at": comparison.compared_at.isoformat(),
            "verdict": comparison.verdict.value,
            "total_metrics_compared": comparison.total_metrics_compared,
            "significant_changes": comparison.significant_changes,
            "regressions_count": len(comparison.regressions),
            "improvements_count": len(comparison.improvements),
            "critical_count": comparison.critical_count,
            "major_count": comparison.major_count,
            "minor_count": comparison.minor_count,
        }

    def _recommendation_to_dict(self, rec: Recommendation) -> dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "severity": rec.severity.value,
            "category": rec.category.value,
            "title": rec.title,
            "description": rec.description,
            "action": rec.action,
            "metric_name": rec.metric_name,
            "metric_value": rec.metric_value,
            "threshold": rec.threshold,
        }
