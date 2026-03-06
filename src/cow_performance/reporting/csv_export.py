"""CSV export for performance metrics."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import PerformanceReport

if TYPE_CHECKING:
    from cow_performance.reporting.models import ExecutiveSummary, Recommendation


class CSVExporter:
    """
    Exports performance metrics to CSV files.

    Generates multiple CSV files for different data types:
    - summary.csv: Executive summary metrics
    - latencies.csv: Latency percentiles by stage
    - resources.csv: Resource utilization by container
    - recommendations.csv: All recommendations
    """

    def export_to_directory(
        self,
        report: PerformanceReport,
        output_dir: Path,
    ) -> dict[str, Path]:
        """
        Export all CSV files to a directory.

        Args:
            report: The performance report to export
            output_dir: Directory to write CSV files

        Returns:
            Dictionary mapping file type to file path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: dict[str, Path] = {}

        # Export summary
        if report.summary:
            summary_path = output_dir / "summary.csv"
            self._export_summary(report.summary, summary_path)
            exported_files["summary"] = summary_path

        # Export latencies
        if report.baseline and report.baseline.order_metrics:
            latencies_path = output_dir / "latencies.csv"
            self._export_latencies(report.baseline, latencies_path)
            exported_files["latencies"] = latencies_path

        # Export resources
        if report.baseline and report.baseline.resource_metrics:
            resources_path = output_dir / "resources.csv"
            self._export_resources(report.baseline, resources_path)
            exported_files["resources"] = resources_path

        # Export recommendations
        if report.recommendations:
            recs_path = output_dir / "recommendations.csv"
            self._export_recommendations(report.recommendations, recs_path)
            exported_files["recommendations"] = recs_path

        return exported_files

    def export_summary_to_string(self, report: PerformanceReport) -> str:
        """Export summary as CSV string."""
        if not report.summary:
            return ""

        output = io.StringIO()
        self._export_summary(report.summary, output)
        return output.getvalue()

    def _export_summary(
        self,
        summary: ExecutiveSummary,
        output: Path | io.StringIO,
    ) -> None:
        """Export executive summary to CSV."""
        rows = [
            ("metric", "value"),
            ("test_name", summary.test_name),
            ("test_duration_seconds", summary.test_duration_seconds),
            ("total_orders_submitted", summary.total_orders_submitted),
            ("total_orders_filled", summary.total_orders_filled),
            ("total_orders_failed", summary.total_orders_failed),
            ("success_rate", summary.success_rate),
            ("average_throughput", summary.average_throughput),
            ("peak_throughput", summary.peak_throughput),
            ("submission_latency_p95_ms", summary.submission_latency_p95_ms),
            ("fill_latency_p95_ms", summary.fill_latency_p95_ms),
            ("total_lifecycle_p95_ms", summary.total_lifecycle_p95_ms),
            ("total_api_requests", summary.total_api_requests),
            ("api_success_rate", summary.api_success_rate),
            ("api_response_time_p95_ms", summary.api_response_time_p95_ms),
            ("verdict", summary.verdict.value),
        ]

        self._write_rows(output, rows)

    def _export_latencies(
        self,
        baseline: PerformanceBaseline,
        output: Path | io.StringIO,
    ) -> None:
        """Export latency percentiles to CSV."""
        om = baseline.order_metrics
        if not om:
            return

        header = (
            "stage",
            "count",
            "min",
            "max",
            "mean",
            "p50",
            "p90",
            "p95",
            "p99",
            "std_dev",
        )
        rows: list[tuple] = [header]

        for name, stats in [
            ("time_to_submit", om.time_to_submit),
            ("time_to_accept", om.time_to_accept),
            ("time_to_fill", om.time_to_fill),
            ("total_lifecycle", om.total_lifecycle),
        ]:
            if stats.count > 0:
                rows.append(
                    (
                        name,
                        stats.count,
                        stats.min * 1000,  # Convert to ms
                        stats.max * 1000,
                        stats.mean * 1000,
                        stats.p50 * 1000,
                        stats.p90 * 1000,
                        stats.p95 * 1000,
                        stats.p99 * 1000,
                        stats.std_dev * 1000,
                    )
                )

        self._write_rows(output, rows)

    def _export_resources(
        self,
        baseline: PerformanceBaseline,
        output: Path | io.StringIO,
    ) -> None:
        """Export resource utilization to CSV."""
        header = (
            "container",
            "sample_count",
            "cpu_mean",
            "cpu_p50",
            "cpu_p95",
            "cpu_max",
            "memory_mean",
            "memory_p50",
            "memory_p95",
            "memory_max",
        )
        rows: list[tuple] = [header]

        for name, metrics in baseline.resource_metrics.items():
            rows.append(
                (
                    name,
                    metrics.sample_count,
                    metrics.cpu_percent.mean,
                    metrics.cpu_percent.p50,
                    metrics.cpu_percent.p95,
                    metrics.cpu_percent.max,
                    metrics.memory_percent.mean,
                    metrics.memory_percent.p50,
                    metrics.memory_percent.p95,
                    metrics.memory_percent.max,
                )
            )

        self._write_rows(output, rows)

    def _export_recommendations(
        self,
        recommendations: list[Recommendation],
        output: Path | io.StringIO,
    ) -> None:
        """Export recommendations to CSV."""
        header = (
            "severity",
            "category",
            "title",
            "description",
            "action",
            "metric_name",
        )
        rows: list[tuple] = [header]

        for rec in recommendations:
            rows.append(
                (
                    rec.severity.value,
                    rec.category.value,
                    rec.title,
                    rec.description,
                    rec.action,
                    rec.metric_name or "",
                )
            )

        self._write_rows(output, rows)

    def _write_rows(
        self,
        output: Path | io.StringIO,
        rows: list[tuple],
    ) -> None:
        """Write rows to CSV output."""
        if isinstance(output, Path):
            with open(output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
        else:
            writer = csv.writer(output)
            writer.writerows(rows)
