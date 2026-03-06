"""Integration tests for full reporting workflow."""

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
from cow_performance.reporting import ReportGenerator
from cow_performance.reporting.models import ReportVerdict


class TestReportingIntegration:
    """Integration tests for complete reporting workflow."""

    @pytest.fixture
    def sample_baseline(self):
        """Create a realistic sample baseline."""
        return PerformanceBaseline(
            id="integration-test-baseline",
            name="Integration Test",
            scenario_name="test-scenario",
            duration_seconds=300,
            created_at=datetime.now().timestamp(),
            git_commit="abc123def456",
            git_branch="main",
            order_metrics=OrderAggregateMetrics(
                total_orders=500,
                orders_submitted=500,
                orders_accepted=495,
                orders_filled=480,
                orders_failed=20,
                success_rate=0.96,
                failure_rate=0.04,
                time_to_submit=PercentileStats(
                    count=500, mean=0.05, p50=0.04, p90=0.08, p95=0.1, p99=0.15
                ),
                time_to_accept=PercentileStats(
                    count=495, mean=0.3, p50=0.25, p90=0.5, p95=0.6, p99=0.8
                ),
                time_to_fill=PercentileStats(
                    count=480, mean=1.5, p50=1.2, p90=2.5, p95=3.0, p99=4.5
                ),
                total_lifecycle=PercentileStats(
                    count=480, mean=2.0, p50=1.5, p90=3.0, p95=4.0, p99=6.0
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=2000,
                successful_requests=1980,
                failed_requests=20,
                success_rate=0.99,
                response_time=PercentileStats(count=2000, mean=50, p50=45, p95=120),
                requests_per_second=6.67,
            ),
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=25, p50=23, p95=45),
                    memory_percent=PercentileStats(count=60, mean=40, p50=38, p95=55),
                ),
                "solver": ResourceAggregateMetrics(
                    container_name="solver",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=35, p50=33, p95=55),
                    memory_percent=PercentileStats(count=60, mean=30, p50=28, p95=42),
                ),
            },
            orders_per_second=1.6,
            peak_orders_per_second=2.5,
        )

    def test_full_report_generation(self, sample_baseline):
        """Test generating a complete report."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)

        assert report.report_id is not None
        assert report.summary is not None
        assert report.summary.verdict == ReportVerdict.SUCCESS
        assert report.baseline == sample_baseline
        assert len(report.recommendations) >= 0  # May or may not have recs

    def test_report_with_test_name_override(self, sample_baseline):
        """Test report with custom test name."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline, test_name="Custom Test Name")

        assert report.test_name == "Custom Test Name"
        assert report.summary.test_name == "Custom Test Name"

    def test_text_format_output(self, sample_baseline):
        """Test text format output."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        text_output = generator.format(report, "text", use_colors=False)

        assert "PERFORMANCE REPORT" in text_output
        assert "Integration Test" in text_output
        assert "EXECUTIVE SUMMARY" in text_output
        assert "SUCCESS" in text_output
        assert "DETAILED METRICS" in text_output

    def test_text_format_with_colors(self, sample_baseline):
        """Test text format with colors."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        text_output = generator.format(report, "text", use_colors=True)

        # Should contain ANSI color codes
        assert "\033[" in text_output

    def test_markdown_format_output(self, sample_baseline):
        """Test markdown format output."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        md_output = generator.format(report, "markdown")

        assert "# " in md_output  # Has headers
        assert "| " in md_output  # Has tables
        assert "Integration Test" in md_output
        assert "Executive Summary" in md_output
        assert "Detailed Metrics" in md_output
        assert "Generated by CoW Performance Testing Suite" in md_output

    def test_json_format_output(self, sample_baseline):
        """Test JSON format output."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        json_output = generator.format(report, "json")

        # Should be valid JSON
        data = json.loads(json_output)
        assert data["test_name"] == "Integration Test"
        assert "summary" in data
        assert "baseline" in data
        assert data["summary"]["verdict"] == "success"

    def test_csv_export(self, sample_baseline, tmp_path):
        """Test CSV export functionality."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        exported = generator.export_csv(report, tmp_path)

        assert "summary" in exported
        assert "latencies" in exported
        assert "resources" in exported

        # Verify files exist and are non-empty
        for _file_type, path in exported.items():
            assert path.exists()
            assert path.stat().st_size > 0

    def test_save_report(self, sample_baseline, tmp_path):
        """Test saving report to file."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)

        output_path = tmp_path / "report.md"
        generator.save_report(report, output_path, format="markdown")

        assert output_path.exists()
        content = output_path.read_text()
        assert "Integration Test" in content
        assert "Performance Report" in content

    def test_warning_verdict_for_issues(self):
        """Test report with warning-level issues."""
        baseline = PerformanceBaseline(
            id="warning-test",
            name="Warning Test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=90,
                orders_failed=10,
                success_rate=0.90,  # Below 95% threshold
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=200,
                successful_requests=200,
                success_rate=1.0,
            ),
            orders_per_second=1.0,
        )

        generator = ReportGenerator()
        report = generator.generate(baseline)

        assert report.summary.verdict == ReportVerdict.WARNING

    def test_failure_verdict_for_critical_issues(self):
        """Test report with critical issues."""
        baseline = PerformanceBaseline(
            id="failure-test",
            name="Failure Test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=50,
                orders_failed=50,
                success_rate=0.50,  # Below 80% threshold
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=200,
                successful_requests=200,
                success_rate=1.0,
            ),
            orders_per_second=1.0,
        )

        generator = ReportGenerator()
        report = generator.generate(baseline)

        assert report.summary.verdict == ReportVerdict.FAILURE

    def test_recommendations_generated(self):
        """Test that recommendations are generated for issues."""
        baseline = PerformanceBaseline(
            id="recs-test",
            name="Recommendations Test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=70,
                orders_failed=30,
                success_rate=0.70,  # Will trigger reliability recommendation
                time_to_fill=PercentileStats(count=70, p95=20.0),  # 20s > 15s threshold
            ),
            orders_per_second=0.1,  # Will trigger throughput recommendation
        )

        generator = ReportGenerator()
        report = generator.generate(baseline)

        # Should have recommendations for reliability and throughput
        assert len(report.recommendations) > 0

        categories = {r.category.value for r in report.recommendations}
        assert "reliability" in categories
        assert "throughput" in categories


class TestReportingWithComparison:
    """Tests for reporting with comparison results."""

    @pytest.fixture
    def baseline_baseline(self):
        """Create a baseline for comparison."""
        return PerformanceBaseline(
            id="baseline",
            name="Baseline v1.0",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=500,
                orders_submitted=500,
                orders_filled=490,
                orders_failed=10,
                success_rate=0.98,
                time_to_fill=PercentileStats(count=490, p95=2.0),
            ),
            orders_per_second=1.5,
        )

    @pytest.fixture
    def current_baseline(self):
        """Create a current baseline with regression."""
        return PerformanceBaseline(
            id="current",
            name="Current v2.0",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=500,
                orders_submitted=500,
                orders_filled=480,
                orders_failed=20,
                success_rate=0.96,
                time_to_fill=PercentileStats(count=480, p95=4.0),  # 2x latency
            ),
            orders_per_second=1.4,
        )

    def test_report_with_comparison(self, baseline_baseline, current_baseline):
        """Test generating report with comparison."""
        from cow_performance.comparison import ComparisonEngine

        # Create comparison
        engine = ComparisonEngine()
        comparison = engine.compare(baseline_baseline, current_baseline)

        # Generate report with comparison
        generator = ReportGenerator()
        report = generator.generate(current_baseline, comparison=comparison)

        assert report.comparison is not None
        assert report.comparison.baseline_name == "Baseline v1.0"
        assert report.comparison.current_name == "Current v2.0"

    def test_comparison_in_text_output(self, baseline_baseline, current_baseline):
        """Test comparison appears in text output."""
        from cow_performance.comparison import ComparisonEngine

        engine = ComparisonEngine()
        comparison = engine.compare(baseline_baseline, current_baseline)

        generator = ReportGenerator()
        report = generator.generate(current_baseline, comparison=comparison)
        text_output = generator.format(report, "text", use_colors=False)

        assert "COMPARISON RESULTS" in text_output
        assert "Baseline v1.0" in text_output
        assert "Current v2.0" in text_output

    def test_comparison_in_markdown_output(self, baseline_baseline, current_baseline):
        """Test comparison appears in markdown output."""
        from cow_performance.comparison import ComparisonEngine

        engine = ComparisonEngine()
        comparison = engine.compare(baseline_baseline, current_baseline)

        generator = ReportGenerator()
        report = generator.generate(current_baseline, comparison=comparison)
        md_output = generator.format(report, "markdown")

        assert "## Comparison Results" in md_output
        assert "`Baseline v1.0`" in md_output
        assert "`Current v2.0`" in md_output
