"""Report generator for performance testing."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.csv_export import CSVExporter
from cow_performance.reporting.formatters import (
    JSONReportFormatter,
    MarkdownReportFormatter,
    TextReportFormatter,
)
from cow_performance.reporting.models import PerformanceReport
from cow_performance.reporting.recommendations import RecommendationsEngine
from cow_performance.reporting.summary import generate_executive_summary

if TYPE_CHECKING:
    from cow_performance.comparison.models import ComparisonResult

logger = logging.getLogger(__name__)

ReportFormat = Literal["text", "markdown", "json"]


class ReportGenerator:
    """
    Main class for generating performance reports.

    Orchestrates summary generation, recommendations, and formatting.

    Example:
        generator = ReportGenerator()
        report = generator.generate(baseline)
        print(generator.format(report, "text"))
    """

    def __init__(
        self,
        recommendations_engine: RecommendationsEngine | None = None,
    ):
        """
        Initialize the report generator.

        Args:
            recommendations_engine: Custom recommendations engine
        """
        self._recommendations_engine = recommendations_engine or RecommendationsEngine()
        self._markdown_formatter = MarkdownReportFormatter()
        self._json_formatter = JSONReportFormatter()
        self._csv_exporter = CSVExporter()

    def generate(
        self,
        baseline: PerformanceBaseline,
        comparison: ComparisonResult | None = None,
        test_name: str | None = None,
    ) -> PerformanceReport:
        """
        Generate a complete performance report.

        Args:
            baseline: The performance baseline (aggregated metrics)
            comparison: Optional comparison result from COW-589
            test_name: Optional test name override

        Returns:
            Complete PerformanceReport
        """
        report_id = str(uuid.uuid4())

        # Generate executive summary
        summary = generate_executive_summary(baseline, test_name)

        # Generate recommendations
        recommendations = self._recommendations_engine.analyze(baseline)

        # Add comparison-based recommendations
        if comparison:
            recommendations.extend(self._recommendations_engine.analyze_comparison(comparison))

        # Create report
        report = PerformanceReport(
            report_id=report_id,
            generated_at=datetime.now(),
            test_name=test_name or baseline.name,
            scenario_name=baseline.scenario_name,
            git_commit=baseline.git_commit,
            git_branch=baseline.git_branch,
            summary=summary,
            baseline=baseline,
            comparison=comparison,
            recommendations=recommendations,
        )

        logger.info(
            "Generated report %s with verdict %s and %d recommendations",
            report_id,
            summary.verdict.value,
            len(recommendations),
        )

        return report

    def format(
        self,
        report: PerformanceReport,
        format: ReportFormat = "text",
        use_colors: bool = True,
    ) -> str:
        """
        Format a report in the specified format.

        Args:
            report: The report to format
            format: Output format ("text", "markdown", or "json")
            use_colors: Whether to use ANSI colors (text format only)

        Returns:
            Formatted report string
        """
        if format == "text":
            formatter = TextReportFormatter(use_colors=use_colors)
            return formatter.format(report)
        elif format == "markdown":
            return self._markdown_formatter.format(report)
        elif format == "json":
            return self._json_formatter.format(report)
        else:
            raise ValueError(f"Unknown format: {format}")

    def export_csv(
        self,
        report: PerformanceReport,
        output_dir: Path,
    ) -> dict[str, Path]:
        """
        Export report data as CSV files.

        Args:
            report: The report to export
            output_dir: Directory for CSV files

        Returns:
            Dictionary mapping file type to file path
        """
        return self._csv_exporter.export_to_directory(report, output_dir)

    def save_report(
        self,
        report: PerformanceReport,
        output_path: Path,
        format: ReportFormat = "markdown",
    ) -> None:
        """
        Save a formatted report to a file.

        Args:
            report: The report to save
            output_path: Output file path
            format: Output format
        """
        content = self.format(report, format, use_colors=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        logger.info("Saved report to %s", output_path)
