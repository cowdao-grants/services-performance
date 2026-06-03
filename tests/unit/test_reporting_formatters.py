"""Unit tests for report formatters."""

import json
from datetime import datetime

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)
from cow_performance.reporting.formatters import (
    JSONReportFormatter,
    MarkdownReportFormatter,
    TextReportFormatter,
)
from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    ReportVerdict,
)


@pytest.fixture
def sample_summary():
    """Create a sample executive summary."""
    now = datetime.now()
    return ExecutiveSummary(
        test_name="test-run",
        test_duration_seconds=300.0,
        test_start_time=now,
        test_end_time=now,
        total_orders_submitted=100,
        total_orders_filled=95,
        total_orders_failed=5,
        success_rate=0.95,
        average_throughput=1.5,
        peak_throughput=3.0,
        submission_latency_p95_ms=100.0,
        fill_latency_p95_ms=2500.0,
        total_lifecycle_p95_ms=3000.0,
        total_api_requests=500,
        api_success_rate=0.99,
        api_response_time_p95_ms=120.0,
        verdict=ReportVerdict.SUCCESS,
        verdict_reason="All metrics within acceptable thresholds",
        key_findings=["Success rate is 95%", "5 orders failed"],
    )


@pytest.fixture
def sample_baseline():
    """Create a sample baseline."""
    return PerformanceBaseline(
        id="test-baseline",
        name="test-run",
        created_at=datetime.now().timestamp(),
        duration_seconds=300,
        git_commit="abc123def456",
        git_branch="main",
        order_metrics=OrderAggregateMetrics(
            total_orders=100,
            orders_submitted=100,
            orders_filled=95,
            orders_failed=5,
            success_rate=0.95,
            time_to_submit=PercentileStats(count=100, p50=0.05, p90=0.08, p95=0.1, p99=0.15),
            time_to_fill=PercentileStats(count=95, p50=1.5, p90=2.0, p95=2.5, p99=3.5),
            time_to_accept=PercentileStats(count=98, p50=0.2, p90=0.3, p95=0.4, p99=0.5),
            total_lifecycle=PercentileStats(count=95, p50=2.0, p90=2.5, p95=3.0, p99=4.0),
        ),
        api_metrics=APIAggregateMetrics(
            total_requests=500,
            successful_requests=495,
            failed_requests=5,
            success_rate=0.99,
            response_time=PercentileStats(count=500, p50=50.0, p95=120.0),
        ),
        resource_metrics={
            "orderbook": ResourceAggregateMetrics(
                container_name="orderbook",
                sample_count=60,
                cpu_percent=PercentileStats(count=60, p95=45.0),
                memory_percent=PercentileStats(count=60, p95=55.0),
            ),
        },
        orders_per_second=1.5,
        peak_orders_per_second=3.0,
    )


@pytest.fixture
def sample_recommendations():
    """Create sample recommendations."""
    return [
        Recommendation(
            severity=RecommendationSeverity.WARNING,
            category=RecommendationCategory.LATENCY,
            title="Elevated fill latency",
            description="Fill latency P95 is above warning threshold.",
            action="Review solver configuration.",
            metric_name="fill_latency_p95",
            metric_value=2500.0,
            threshold=2000.0,
        ),
        Recommendation(
            severity=RecommendationSeverity.INFO,
            category=RecommendationCategory.RELIABILITY,
            title="Order failures detected",
            description="5 orders failed during the test.",
            action="Review error logs.",
        ),
    ]


@pytest.fixture
def sample_report(sample_summary, sample_baseline, sample_recommendations):
    """Create a sample report."""
    return PerformanceReport(
        report_id="test-report-123",
        test_name="test-run",
        scenario_name="basic-load",
        git_commit="abc123def456",
        git_branch="main",
        summary=sample_summary,
        baseline=sample_baseline,
        recommendations=sample_recommendations,
    )


class TestTextReportFormatter:
    """Tests for TextReportFormatter."""

    def test_format_basic_report(self, sample_report):
        """Test formatting a basic report."""
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(sample_report)

        assert "PERFORMANCE REPORT" in output
        assert "test-report-123" in output
        assert "abc123de" in output  # First 8 chars of commit

    def test_format_summary_section(self, sample_report):
        """Test that summary section is formatted."""
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(sample_report)

        assert "EXECUTIVE SUMMARY" in output
        assert "[SUCCESS]" in output
        assert "test-run" in output
        assert "95" in output  # Orders filled

    def test_format_metrics_section(self, sample_report):
        """Test that metrics section is formatted."""
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(sample_report)

        assert "DETAILED METRICS" in output
        assert "Order Lifecycle Latencies" in output
        assert "Resource Utilization" in output
        assert "orderbook" in output

    def test_format_recommendations_section(self, sample_report):
        """Test that recommendations section is formatted."""
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(sample_report)

        assert "RECOMMENDATIONS" in output
        assert "Elevated fill latency" in output
        assert "[WARNING]" in output

    def test_color_disabled(self, sample_report):
        """Test that colors are disabled when specified."""
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(sample_report)

        # ANSI escape codes should not be present
        assert "\033[" not in output

    def test_color_enabled(self, sample_report):
        """Test that colors are enabled when specified."""
        formatter = TextReportFormatter(use_colors=True)
        output = formatter.format(sample_report)

        # ANSI escape codes should be present (green for SUCCESS)
        assert "\033[" in output

    def test_format_empty_report(self):
        """Test formatting a minimal report."""
        report = PerformanceReport(report_id="empty-report")
        formatter = TextReportFormatter(use_colors=False)
        output = formatter.format(report)

        assert "PERFORMANCE REPORT" in output
        assert "empty-report" in output


class TestMarkdownReportFormatter:
    """Tests for MarkdownReportFormatter."""

    def test_format_basic_report(self, sample_report):
        """Test formatting a basic report."""
        formatter = MarkdownReportFormatter()
        output = formatter.format(sample_report)

        assert "# ✅ Performance Report" in output
        assert "| Property | Value |" in output
        assert "test-report-123" in output

    def test_format_summary_section(self, sample_report):
        """Test that summary section is formatted as Markdown."""
        formatter = MarkdownReportFormatter()
        output = formatter.format(sample_report)

        assert "## Executive Summary" in output
        assert "**Verdict:**" in output
        assert "**SUCCESS**" in output

    def test_format_metrics_tables(self, sample_report):
        """Test that metrics are formatted as Markdown tables."""
        formatter = MarkdownReportFormatter()
        output = formatter.format(sample_report)

        assert "## Detailed Metrics" in output
        assert "| Stage | P50 | P90 | P95 | P99 |" in output
        assert "| Container | CPU (P95) | Memory (P95) |" in output

    def test_format_recommendations_with_emoji(self, sample_report):
        """Test that recommendations have appropriate emoji."""
        formatter = MarkdownReportFormatter()
        output = formatter.format(sample_report)

        assert "## Recommendations" in output
        assert "🟠" in output  # Warning emoji
        assert "🔵" in output  # Info emoji

    def test_footer_present(self, sample_report):
        """Test that footer is present."""
        formatter = MarkdownReportFormatter()
        output = formatter.format(sample_report)

        assert "---" in output
        assert "Generated by CoW Performance Testing Suite" in output

    def test_verdict_emojis(self):
        """Test different verdict emojis."""
        formatter = MarkdownReportFormatter()

        assert formatter._verdict_emoji(ReportVerdict.SUCCESS) == "✅"
        assert formatter._verdict_emoji(ReportVerdict.WARNING) == "⚠️"
        assert formatter._verdict_emoji(ReportVerdict.FAILURE) == "❌"
        assert formatter._verdict_emoji(None) == "📊"


class TestJSONReportFormatter:
    """Tests for JSONReportFormatter."""

    def test_format_produces_valid_json(self, sample_report):
        """Test that output is valid JSON."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)

        # Should not raise
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_format_includes_report_id(self, sample_report):
        """Test that report ID is included."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)
        data = json.loads(output)

        assert data["report_id"] == "test-report-123"

    def test_format_includes_summary(self, sample_report):
        """Test that summary is included."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)
        data = json.loads(output)

        assert "summary" in data
        assert data["summary"]["test_name"] == "test-run"
        assert data["summary"]["verdict"] == "success"

    def test_format_includes_recommendations(self, sample_report):
        """Test that recommendations are included."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)
        data = json.loads(output)

        assert "recommendations" in data
        assert len(data["recommendations"]) == 2
        assert data["recommendations"][0]["severity"] == "warning"

    def test_format_compact_mode(self, sample_report):
        """Test compact JSON output."""
        formatter = JSONReportFormatter(indent=0)
        output = formatter.format(sample_report)

        # Compact JSON should have no indentation newlines
        assert "\n" not in output.strip()

    def test_format_includes_baseline(self, sample_report):
        """Test that baseline is included."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)
        data = json.loads(output)

        assert "baseline" in data
        assert data["baseline"]["id"] == "test-baseline"

    def test_datetime_serialization(self, sample_report):
        """Test that datetime values are serialized correctly."""
        formatter = JSONReportFormatter()
        output = formatter.format(sample_report)
        data = json.loads(output)

        # generated_at should be ISO format string
        assert isinstance(data["generated_at"], str)
        # Should be parseable as datetime
        datetime.fromisoformat(data["generated_at"])

    def test_format_empty_report(self):
        """Test formatting a minimal report."""
        report = PerformanceReport(report_id="empty-report")
        formatter = JSONReportFormatter()
        output = formatter.format(report)
        data = json.loads(output)

        assert data["report_id"] == "empty-report"
        assert "summary" not in data
        assert "baseline" not in data
