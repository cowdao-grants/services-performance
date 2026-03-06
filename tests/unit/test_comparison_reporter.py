"""Unit tests for RegressionReporter."""

import json
from datetime import datetime

import pytest

from cow_performance.comparison.models import (
    ComparisonResult,
    MetricComparison,
    MetricType,
    RegressionSeverity,
)
from cow_performance.comparison.reporter import RegressionReporter


class TestRegressionReporter:
    """Tests for RegressionReporter."""

    @pytest.fixture
    def sample_result(self) -> ComparisonResult:
        """Create a sample comparison result."""
        result = ComparisonResult(
            baseline_id="baseline-123456789012",
            baseline_name="release-v1.0",
            current_id="current-456789012345",
            current_name="pr-feature-x",
            compared_at=datetime(2025, 1, 15, 10, 30, 0),
        )

        # Add a critical regression
        result.add_comparison(
            MetricComparison(
                metric_name="time_to_fill_p95",
                metric_type=MetricType.LATENCY,
                baseline_value=0.10,
                current_value=0.15,
                absolute_diff=0.05,
                percent_change=0.50,
                p_value=0.001,
                effect_size=1.5,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
                context="50% latency increase",
            )
        )

        # Add an improvement
        result.add_comparison(
            MetricComparison(
                metric_name="orders_per_second",
                metric_type=MetricType.THROUGHPUT,
                baseline_value=5.0,
                current_value=6.0,
                absolute_diff=1.0,
                percent_change=0.20,
                is_significant=True,
                regression_severity=RegressionSeverity.NONE,
                context="20% throughput improvement",
            )
        )

        result.calculate_verdict()
        return result

    @pytest.fixture
    def neutral_result(self) -> ComparisonResult:
        """Create a neutral comparison result."""
        result = ComparisonResult(
            baseline_id="baseline-111111111111",
            baseline_name="baseline",
            current_id="current-222222222222",
            current_name="current",
            compared_at=datetime(2025, 1, 15, 10, 30, 0),
        )

        # Add non-significant change
        result.add_comparison(
            MetricComparison(
                metric_name="latency",
                metric_type=MetricType.LATENCY,
                baseline_value=0.10,
                current_value=0.101,
                absolute_diff=0.001,
                percent_change=0.01,
                is_significant=False,
                regression_severity=RegressionSeverity.NONE,
            )
        )

        result.calculate_verdict()
        return result

    def test_text_report_generation(self, sample_result: ComparisonResult) -> None:
        """Test text report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_text_report(sample_result)

        assert "PERFORMANCE COMPARISON REPORT" in report
        assert "release-v1.0" in report
        assert "pr-feature-x" in report
        assert "CRITICAL REGRESSIONS" in report
        assert "time_to_fill_p95" in report
        assert "VERDICT:" in report

    def test_text_report_contains_summary(self, sample_result: ComparisonResult) -> None:
        """Test text report contains summary statistics."""
        reporter = RegressionReporter()
        report = reporter.generate_text_report(sample_result)

        assert "Total metrics compared:" in report
        assert "Significant changes:" in report
        assert "Regressions:" in report
        assert "Improvements:" in report

    def test_text_report_improvements_section(self, sample_result: ComparisonResult) -> None:
        """Test text report includes improvements section."""
        reporter = RegressionReporter()
        report = reporter.generate_text_report(sample_result)

        assert "IMPROVEMENTS" in report
        assert "orders_per_second" in report

    def test_text_report_neutral_verdict(self, neutral_result: ComparisonResult) -> None:
        """Test text report with neutral verdict."""
        reporter = RegressionReporter()
        report = reporter.generate_text_report(neutral_result)

        assert "NEUTRAL" in report
        # Should not have critical/major/minor sections if counts are 0
        assert "CRITICAL REGRESSIONS" not in report

    def test_markdown_report_generation(self, sample_result: ComparisonResult) -> None:
        """Test Markdown report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "## " in report  # Has headers
        assert "| Property | Value |" in report  # Has tables
        assert "`release-v1.0`" in report
        assert "**Verdict**" in report

    def test_markdown_report_has_summary_section(self, sample_result: ComparisonResult) -> None:
        """Test Markdown report has summary section."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "### Summary" in report
        assert "**Total metrics compared:**" in report
        assert "**Regressions:**" in report

    def test_markdown_report_has_regressions_table(self, sample_result: ComparisonResult) -> None:
        """Test Markdown report has regressions table."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "### Regressions" in report
        assert "| Severity | Metric | Baseline | Current | Change |" in report

    def test_markdown_report_has_improvements_table(self, sample_result: ComparisonResult) -> None:
        """Test Markdown report has improvements table."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "### Improvements" in report

    def test_markdown_report_has_collapsible_details(self, sample_result: ComparisonResult) -> None:
        """Test Markdown report has collapsible all metrics section."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "<details>" in report
        assert "<summary>All Metric Comparisons</summary>" in report
        assert "</details>" in report

    def test_json_report_generation(self, sample_result: ComparisonResult) -> None:
        """Test JSON report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        # Should be valid JSON
        data = json.loads(report)

        assert data["baseline_name"] == "release-v1.0"
        assert data["current_name"] == "pr-feature-x"
        assert data["verdict"] == "regression"
        assert len(data["regressions"]) == 1
        assert len(data["improvements"]) == 1

    def test_json_report_summary_section(self, sample_result: ComparisonResult) -> None:
        """Test JSON report has summary section."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        data = json.loads(report)

        assert "summary" in data
        assert data["summary"]["total_metrics_compared"] == 2
        assert data["summary"]["significant_changes"] == 2
        assert data["summary"]["regressions"] == 1
        assert data["summary"]["improvements"] == 1

    def test_json_report_regression_details(self, sample_result: ComparisonResult) -> None:
        """Test JSON report regression details."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        data = json.loads(report)

        regression = data["regressions"][0]
        assert regression["metric_name"] == "time_to_fill_p95"
        assert regression["metric_type"] == "latency"
        assert regression["baseline_value"] == 0.10
        assert regression["current_value"] == 0.15
        assert regression["percent_change"] == 0.50
        assert regression["is_significant"] is True
        assert regression["regression_severity"] == "critical"
        assert regression["is_regression"] is True

    def test_json_report_all_comparisons(self, sample_result: ComparisonResult) -> None:
        """Test JSON report includes all comparisons."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        data = json.loads(report)

        assert "all_comparisons" in data
        assert "time_to_fill_p95" in data["all_comparisons"]
        assert "orders_per_second" in data["all_comparisons"]

    def test_json_report_dates_serialized(self, sample_result: ComparisonResult) -> None:
        """Test JSON report dates are serialized properly."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        data = json.loads(report)

        assert "compared_at" in data
        assert "2025-01-15" in data["compared_at"]

    def test_report_with_all_severity_levels(self) -> None:
        """Test report with all severity levels."""
        result = ComparisonResult(
            baseline_id="baseline-123",
            baseline_name="baseline",
            current_id="current-456",
            current_name="current",
        )

        # Add critical
        result.add_comparison(
            MetricComparison(
                metric_name="critical_metric",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.2,
                absolute_diff=0.1,
                percent_change=1.0,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
            )
        )

        # Add major
        result.add_comparison(
            MetricComparison(
                metric_name="major_metric",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.15,
                absolute_diff=0.05,
                percent_change=0.5,
                is_significant=True,
                regression_severity=RegressionSeverity.MAJOR,
            )
        )

        # Add minor
        result.add_comparison(
            MetricComparison(
                metric_name="minor_metric",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.12,
                absolute_diff=0.02,
                percent_change=0.2,
                is_significant=True,
                regression_severity=RegressionSeverity.MINOR,
            )
        )

        result.calculate_verdict()

        reporter = RegressionReporter()
        text_report = reporter.generate_text_report(result)

        assert "CRITICAL REGRESSIONS" in text_report
        assert "MAJOR REGRESSIONS" in text_report
        assert "MINOR REGRESSIONS" in text_report
        assert "critical_metric" in text_report
        assert "major_metric" in text_report
        assert "minor_metric" in text_report

    def test_report_empty_result(self) -> None:
        """Test report with empty result."""
        result = ComparisonResult(
            baseline_id="baseline-123",
            baseline_name="baseline",
            current_id="current-456",
            current_name="current",
        )
        result.calculate_verdict()

        reporter = RegressionReporter()

        text_report = reporter.generate_text_report(result)
        assert "PERFORMANCE COMPARISON REPORT" in text_report
        assert "Total metrics compared: 0" in text_report

        md_report = reporter.generate_markdown_report(result)
        assert "## " in md_report

        json_report = reporter.generate_json_report(result)
        data = json.loads(json_report)
        assert data["verdict"] == "neutral"
