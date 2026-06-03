"""Integration tests for comparison engine."""


from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison import (
    ComparisonEngine,
    ComparisonVerdict,
    RegressionReporter,
)
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
)


class TestComparisonIntegration:
    """Integration tests for full comparison workflow."""

    def test_full_comparison_workflow(self) -> None:
        """Test complete comparison from baselines to report."""
        # Create baselines
        baseline = PerformanceBaseline(
            id="baseline-integration-test",
            name="baseline",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=95,
                success_rate=0.95,
                failure_rate=0.05,
                time_to_submit=PercentileStats(
                    count=95, mean=0.1, std_dev=0.02, p50=0.09, p90=0.12, p95=0.13, p99=0.15
                ),
                time_to_accept=PercentileStats(
                    count=95, mean=0.05, std_dev=0.01, p50=0.048, p90=0.06, p95=0.065, p99=0.07
                ),
                time_to_fill=PercentileStats(
                    count=95, mean=0.2, std_dev=0.04, p50=0.19, p90=0.24, p95=0.26, p99=0.30
                ),
                total_lifecycle=PercentileStats(
                    count=95, mean=0.35, std_dev=0.06, p50=0.33, p90=0.42, p95=0.45, p99=0.52
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                successful_requests=475,
                failed_requests=25,
                success_rate=0.95,
                response_time=PercentileStats(
                    count=500, mean=50, std_dev=10, p50=48, p90=60, p95=65, p99=80
                ),
                requests_per_second=10.0,
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

        current = PerformanceBaseline(
            id="current-integration-test",
            name="current",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.90,
                failure_rate=0.10,
                time_to_submit=PercentileStats(
                    count=90, mean=0.12, std_dev=0.03, p50=0.11, p90=0.15, p95=0.16, p99=0.18
                ),
                time_to_accept=PercentileStats(
                    count=90, mean=0.06, std_dev=0.012, p50=0.058, p90=0.072, p95=0.078, p99=0.084
                ),
                time_to_fill=PercentileStats(
                    count=90, mean=0.24, std_dev=0.05, p50=0.23, p90=0.29, p95=0.31, p99=0.36
                ),
                total_lifecycle=PercentileStats(
                    count=90, mean=0.42, std_dev=0.08, p50=0.40, p90=0.50, p95=0.54, p99=0.62
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=450,
                successful_requests=414,
                failed_requests=36,
                success_rate=0.92,
                response_time=PercentileStats(
                    count=450, mean=60, std_dev=12, p50=58, p90=72, p95=78, p99=96
                ),
                requests_per_second=9.0,
            ),
            orders_per_second=4.5,
            peak_orders_per_second=7.0,
        )

        # Compare
        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Generate reports
        reporter = RegressionReporter()
        text_report = reporter.generate_text_report(result)
        md_report = reporter.generate_markdown_report(result)
        json_report = reporter.generate_json_report(result)

        # Verify comparison detected the regressions
        assert result.total_metrics_compared > 0
        # Most metrics should show degradation
        assert len(result.regressions) > 0 or result.verdict == ComparisonVerdict.REGRESSION

        # Verify reports contain expected content
        assert "baseline" in text_report.lower()
        assert "current" in md_report.lower()
        assert '"verdict"' in json_report

    def test_comparison_with_improvement(self) -> None:
        """Test comparison detecting improvements."""
        baseline = PerformanceBaseline(
            id="baseline-slow",
            name="slow-baseline",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=80,
                success_rate=0.80,
                time_to_fill=PercentileStats(
                    count=80, mean=0.3, std_dev=0.06, p50=0.29, p90=0.36, p95=0.40, p99=0.48
                ),
            ),
            orders_per_second=4.0,
            peak_orders_per_second=6.0,
        )

        current = PerformanceBaseline(
            id="current-fast",
            name="fast-current",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=95,
                success_rate=0.95,
                time_to_fill=PercentileStats(
                    count=95, mean=0.2, std_dev=0.04, p50=0.19, p90=0.24, p95=0.26, p99=0.30
                ),
            ),
            orders_per_second=6.0,
            peak_orders_per_second=9.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Should detect improvements
        assert result.verdict == ComparisonVerdict.IMPROVEMENT
        assert len(result.improvements) > 0

    def test_comparison_with_no_change(self) -> None:
        """Test comparison with identical baselines shows neutral."""
        baseline = PerformanceBaseline(
            id="baseline-stable",
            name="stable",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.90,
                time_to_fill=PercentileStats(count=90, mean=0.2, std_dev=0.04, p95=0.26),
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, baseline)

        assert result.verdict == ComparisonVerdict.NEUTRAL
        assert result.critical_count == 0
        assert result.major_count == 0
        assert result.minor_count == 0

    def test_report_roundtrip(self) -> None:
        """Test that JSON report can be loaded and contains all data."""
        import json

        baseline = PerformanceBaseline(
            id="baseline-roundtrip",
            name="roundtrip-test",
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )
        current = PerformanceBaseline(
            id="current-roundtrip",
            name="roundtrip-current",
            orders_per_second=6.0,
            peak_orders_per_second=9.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        reporter = RegressionReporter()
        json_str = reporter.generate_json_report(result)

        # Parse and verify
        data = json.loads(json_str)

        assert data["baseline_id"] == "baseline-roundtrip"
        assert data["baseline_name"] == "roundtrip-test"
        assert data["current_id"] == "current-roundtrip"
        assert data["current_name"] == "roundtrip-current"
        assert "verdict" in data
        assert "summary" in data
        assert "all_comparisons" in data
