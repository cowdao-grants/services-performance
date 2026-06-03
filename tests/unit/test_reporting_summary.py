"""Unit tests for summary generation."""

from datetime import datetime

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
)
from cow_performance.reporting.models import ReportVerdict
from cow_performance.reporting.summary import (
    format_duration,
    format_latency,
    format_rate,
    generate_executive_summary,
)


class TestGenerateExecutiveSummary:
    """Tests for generate_executive_summary function."""

    @pytest.fixture
    def good_baseline(self):
        """Create a baseline with good metrics."""
        return PerformanceBaseline(
            id="test",
            name="good-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=98,
                orders_failed=2,
                success_rate=0.98,
                time_to_submit=PercentileStats(count=100, p95=0.1),
                time_to_fill=PercentileStats(count=98, p95=2.0),
                total_lifecycle=PercentileStats(count=98, p95=2.5),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                successful_requests=500,
                failed_requests=0,
                success_rate=1.0,  # Perfect API success rate
                response_time=PercentileStats(count=500, p95=50.0),
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

    @pytest.fixture
    def poor_baseline(self):
        """Create a baseline with poor metrics."""
        return PerformanceBaseline(
            id="test-poor",
            name="poor-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=60,
                orders_failed=40,
                success_rate=0.60,  # Below critical threshold
                time_to_submit=PercentileStats(count=100, p95=0.5),
                time_to_fill=PercentileStats(count=60, p95=30.0),  # Very high latency
                total_lifecycle=PercentileStats(count=60, p95=35.0),
            ),
            orders_per_second=1.0,
            peak_orders_per_second=2.0,
        )

    @pytest.fixture
    def warning_baseline(self):
        """Create a baseline with warning-level metrics."""
        return PerformanceBaseline(
            id="test-warning",
            name="warning-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=90,
                orders_failed=10,
                success_rate=0.90,  # Between warning and critical thresholds
                time_to_submit=PercentileStats(count=100, p95=0.2),
                time_to_fill=PercentileStats(count=90, p95=5.0),
                total_lifecycle=PercentileStats(count=90, p95=6.0),
            ),
            orders_per_second=3.0,
            peak_orders_per_second=5.0,
        )

    def test_generates_summary_from_baseline(self, good_baseline):
        """Test that summary is generated correctly."""
        summary = generate_executive_summary(good_baseline)

        assert summary.test_name == "good-test"
        assert summary.total_orders_submitted == 100
        assert summary.total_orders_filled == 98
        assert summary.total_orders_failed == 2
        assert summary.success_rate == 0.98
        assert summary.verdict == ReportVerdict.SUCCESS

    def test_verdict_failure_for_critical_issues(self, poor_baseline):
        """Test failure verdict for critical issues."""
        summary = generate_executive_summary(poor_baseline)
        assert summary.verdict == ReportVerdict.FAILURE
        assert "Critical" in summary.verdict_reason or "low" in summary.verdict_reason

    def test_verdict_warning_for_moderate_issues(self, warning_baseline):
        """Test warning verdict for moderate issues."""
        summary = generate_executive_summary(warning_baseline)
        assert summary.verdict == ReportVerdict.WARNING

    def test_test_name_override(self, good_baseline):
        """Test that test_name parameter overrides baseline name."""
        summary = generate_executive_summary(good_baseline, test_name="custom-name")
        assert summary.test_name == "custom-name"

    def test_extracts_latency_metrics(self, good_baseline):
        """Test that latency metrics are correctly extracted."""
        summary = generate_executive_summary(good_baseline)

        # P95 values should be converted to milliseconds
        assert summary.submission_latency_p95_ms == 100.0  # 0.1s -> 100ms
        assert summary.fill_latency_p95_ms == 2000.0  # 2.0s -> 2000ms
        assert summary.total_lifecycle_p95_ms == 2500.0  # 2.5s -> 2500ms

    def test_extracts_throughput_metrics(self, good_baseline):
        """Test that throughput metrics are extracted."""
        summary = generate_executive_summary(good_baseline)

        assert summary.average_throughput == 5.0
        assert summary.peak_throughput == 8.0

    def test_handles_missing_order_metrics(self):
        """Test handling of baseline with no order metrics."""
        baseline = PerformanceBaseline(
            id="test",
            name="empty-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=None,
        )

        summary = generate_executive_summary(baseline)

        assert summary.total_orders_submitted == 0
        assert summary.total_orders_filled == 0
        assert summary.success_rate == 0.0

    def test_handles_missing_api_metrics(self):
        """Test handling of baseline with no API metrics."""
        baseline = PerformanceBaseline(
            id="test",
            name="no-api-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
            ),
            api_metrics=None,
        )

        summary = generate_executive_summary(baseline)

        assert summary.total_api_requests == 0
        assert summary.api_success_rate == 0.0
        assert summary.api_response_time_p95_ms == 0.0

    def test_key_findings_populated(self, good_baseline):
        """Test that key findings are populated."""
        summary = generate_executive_summary(good_baseline)

        assert len(summary.key_findings) > 0
        # Should have finding about success rate
        assert any("success rate" in f.lower() for f in summary.key_findings)

    def test_api_metrics_extraction(self):
        """Test that API metrics are correctly extracted."""
        baseline = PerformanceBaseline(
            id="test",
            name="api-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                successful_requests=495,
                failed_requests=5,
                success_rate=0.99,
                response_time=PercentileStats(count=500, p95=120.0),
            ),
        )

        summary = generate_executive_summary(baseline)

        assert summary.total_api_requests == 500
        assert summary.api_success_rate == 0.99
        assert summary.api_response_time_p95_ms == 120.0


class TestFormatFunctions:
    """Tests for formatting utility functions."""

    def test_format_duration_seconds(self):
        """Test duration formatting in seconds."""
        assert format_duration(30) == "30.0s"
        assert format_duration(45.5) == "45.5s"

    def test_format_duration_minutes(self):
        """Test duration formatting in minutes."""
        assert format_duration(60) == "1.0m"
        assert format_duration(150) == "2.5m"
        assert format_duration(3599) == "60.0m"

    def test_format_duration_hours(self):
        """Test duration formatting in hours."""
        assert format_duration(3600) == "1.0h"
        assert format_duration(7200) == "2.0h"

    def test_format_latency_microseconds(self):
        """Test latency formatting in microseconds."""
        assert format_latency(0.5) == "500μs"
        assert format_latency(0.001) == "1μs"

    def test_format_latency_ms(self):
        """Test latency formatting in milliseconds."""
        assert format_latency(100) == "100.0ms"
        assert format_latency(500.5) == "500.5ms"

    def test_format_latency_seconds(self):
        """Test latency formatting in seconds."""
        assert format_latency(1000) == "1.00s"
        assert format_latency(2500) == "2.50s"
        assert format_latency(5000) == "5.00s"

    def test_format_rate(self):
        """Test rate formatting as percentage."""
        assert format_rate(0.95) == "95.0%"
        assert format_rate(0.998) == "99.8%"
        assert format_rate(1.0) == "100.0%"
        assert format_rate(0.0) == "0.0%"
