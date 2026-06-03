"""Unit tests for ComparisonEngine."""

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison.engine import ComparisonEngine
from cow_performance.comparison.models import ComparisonVerdict
from cow_performance.comparison.thresholds import RELAXED_THRESHOLDS, RegressionThresholds
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)


class TestComparisonEngine:
    """Tests for ComparisonEngine."""

    @pytest.fixture
    def baseline(self) -> PerformanceBaseline:
        """Create a sample baseline."""
        return PerformanceBaseline(
            id="baseline-1234567890",
            name="test-baseline",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.90,
                failure_rate=0.10,
                time_to_submit=PercentileStats(
                    count=90,
                    mean=0.1,
                    std_dev=0.02,
                    p50=0.095,
                    p90=0.12,
                    p95=0.13,
                    p99=0.15,
                ),
                time_to_accept=PercentileStats(
                    count=90,
                    mean=0.05,
                    std_dev=0.01,
                    p50=0.048,
                    p90=0.06,
                    p95=0.065,
                    p99=0.07,
                ),
                time_to_fill=PercentileStats(
                    count=90,
                    mean=0.2,
                    std_dev=0.04,
                    p50=0.19,
                    p90=0.24,
                    p95=0.26,
                    p99=0.30,
                ),
                total_lifecycle=PercentileStats(
                    count=90,
                    mean=0.35,
                    std_dev=0.06,
                    p50=0.33,
                    p90=0.42,
                    p95=0.455,
                    p99=0.52,
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                successful_requests=475,
                failed_requests=25,
                success_rate=0.95,
                response_time=PercentileStats(
                    count=500,
                    mean=50,
                    std_dev=10,
                    p50=48,
                    p90=60,
                    p95=65,
                    p99=80,
                ),
                requests_per_second=10.0,
            ),
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(
                        count=60, mean=25.0, std_dev=5.0, p50=24, p90=30, p95=32, p99=35
                    ),
                    memory_percent=PercentileStats(
                        count=60, mean=40.0, std_dev=5.0, p50=39, p90=45, p95=47, p99=50
                    ),
                    memory_bytes=PercentileStats(count=60, mean=1e9, std_dev=1e8),
                ),
            },
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

    @pytest.fixture
    def current_regression(self) -> PerformanceBaseline:
        """Create a current run with regressions."""
        return PerformanceBaseline(
            id="current-1234567890",
            name="test-current",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=80,
                success_rate=0.80,  # 10pp drop
                failure_rate=0.20,
                time_to_submit=PercentileStats(
                    count=80,
                    mean=0.15,
                    std_dev=0.03,
                    p50=0.14,
                    p90=0.18,
                    p95=0.20,  # 54% increase
                    p99=0.25,
                ),
                time_to_accept=PercentileStats(
                    count=80,
                    mean=0.08,
                    std_dev=0.02,
                    p50=0.075,
                    p90=0.10,
                    p95=0.11,  # 69% increase
                    p99=0.12,
                ),
                time_to_fill=PercentileStats(
                    count=80,
                    mean=0.30,
                    std_dev=0.06,
                    p50=0.28,
                    p90=0.36,
                    p95=0.40,  # 54% increase
                    p99=0.50,
                ),
                total_lifecycle=PercentileStats(
                    count=80,
                    mean=0.53,
                    std_dev=0.10,
                    p50=0.50,
                    p90=0.64,
                    p95=0.71,  # 56% increase
                    p99=0.87,
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=400,
                successful_requests=360,
                failed_requests=40,
                success_rate=0.90,  # 5pp drop
                response_time=PercentileStats(
                    count=400,
                    mean=75,
                    std_dev=15,
                    p50=72,
                    p90=90,
                    p95=100,  # 54% increase
                    p99=120,
                ),
                requests_per_second=8.0,  # 20% drop
            ),
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(
                        count=60,
                        mean=40.0,
                        std_dev=8.0,
                        p50=38,
                        p90=48,
                        p95=52,  # 62.5% increase
                        p99=58,
                    ),
                    memory_percent=PercentileStats(
                        count=60,
                        mean=55.0,
                        std_dev=8.0,
                        p50=53,
                        p90=63,
                        p95=67,  # 42.5% increase
                        p99=72,
                    ),
                    memory_bytes=PercentileStats(count=60, mean=1.4e9, std_dev=1.5e8),
                ),
            },
            orders_per_second=3.0,  # 40% drop
            peak_orders_per_second=5.0,  # 37.5% drop
        )

    @pytest.fixture
    def current_improvement(self) -> PerformanceBaseline:
        """Create a current run with improvements."""
        return PerformanceBaseline(
            id="current-improved",
            name="test-improved",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=95,
                success_rate=0.95,  # 5pp increase
                failure_rate=0.05,
                time_to_submit=PercentileStats(
                    count=95,
                    mean=0.08,
                    std_dev=0.015,
                    p50=0.075,
                    p90=0.095,
                    p95=0.10,  # 23% decrease
                    p99=0.12,
                ),
                time_to_accept=PercentileStats(
                    count=95,
                    mean=0.04,
                    std_dev=0.008,
                    p50=0.038,
                    p90=0.048,
                    p95=0.05,  # 23% decrease
                    p99=0.055,
                ),
                time_to_fill=PercentileStats(
                    count=95,
                    mean=0.16,
                    std_dev=0.03,
                    p50=0.15,
                    p90=0.19,
                    p95=0.20,  # 23% decrease
                    p99=0.24,
                ),
                total_lifecycle=PercentileStats(
                    count=95,
                    mean=0.28,
                    std_dev=0.05,
                    p50=0.26,
                    p90=0.33,
                    p95=0.35,  # 23% decrease
                    p99=0.41,
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=600,
                successful_requests=582,
                failed_requests=18,
                success_rate=0.97,  # 2pp increase
                response_time=PercentileStats(
                    count=600,
                    mean=40,
                    std_dev=8,
                    p50=38,
                    p90=48,
                    p95=50,  # 23% decrease
                    p99=60,
                ),
                requests_per_second=12.0,  # 20% increase
            ),
            orders_per_second=6.0,  # 20% increase
            peak_orders_per_second=10.0,  # 25% increase
        )

    def test_compare_detects_regressions(
        self, baseline: PerformanceBaseline, current_regression: PerformanceBaseline
    ) -> None:
        """Test that comparison detects regressions."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_regression)

        assert result.verdict == ComparisonVerdict.REGRESSION
        assert result.critical_count > 0 or result.major_count > 0
        assert len(result.regressions) > 0

    def test_compare_detects_improvements(
        self, baseline: PerformanceBaseline, current_improvement: PerformanceBaseline
    ) -> None:
        """Test that comparison detects improvements."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_improvement)

        assert result.verdict == ComparisonVerdict.IMPROVEMENT
        assert len(result.improvements) > 0

    def test_compare_with_identical_baselines(self, baseline: PerformanceBaseline) -> None:
        """Test comparison of identical baselines."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, baseline)

        assert result.verdict == ComparisonVerdict.NEUTRAL
        assert result.critical_count == 0
        assert result.major_count == 0
        assert result.minor_count == 0

    def test_compare_with_custom_thresholds(
        self, baseline: PerformanceBaseline, current_regression: PerformanceBaseline
    ) -> None:
        """Test comparison with custom thresholds."""
        engine = ComparisonEngine(thresholds=RELAXED_THRESHOLDS)
        result = engine.compare(baseline, current_regression)

        # With relaxed thresholds, some regressions may be classified as less severe
        assert result is not None

    def test_compare_result_contains_baseline_info(
        self, baseline: PerformanceBaseline, current_regression: PerformanceBaseline
    ) -> None:
        """Test that comparison result contains baseline info."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_regression)

        assert result.baseline_id == baseline.id
        assert result.baseline_name == baseline.name
        assert result.current_id == current_regression.id
        assert result.current_name == current_regression.name

    def test_compare_result_has_metrics(
        self, baseline: PerformanceBaseline, current_regression: PerformanceBaseline
    ) -> None:
        """Test that comparison result has metric comparisons."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_regression)

        # Should have order metrics
        assert "order_success_rate" in result.metric_comparisons
        assert "order_time_to_fill" in result.metric_comparisons

        # Should have API metrics
        assert "api_success_rate" in result.metric_comparisons
        assert "api_response_time" in result.metric_comparisons

        # Should have throughput metrics
        assert "orders_per_second" in result.metric_comparisons
        assert "peak_orders_per_second" in result.metric_comparisons

    def test_compare_resource_metrics(
        self, baseline: PerformanceBaseline, current_regression: PerformanceBaseline
    ) -> None:
        """Test comparison of resource metrics."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_regression)

        # Should have resource metrics for common container
        assert "resource_orderbook_cpu" in result.metric_comparisons
        assert "resource_orderbook_memory" in result.metric_comparisons

    def test_compare_handles_missing_order_metrics(self) -> None:
        """Test comparison handles missing order metrics."""
        baseline = PerformanceBaseline(
            id="baseline",
            name="baseline",
            order_metrics=None,
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )
        current = PerformanceBaseline(
            id="current",
            name="current",
            order_metrics=None,
            orders_per_second=6.0,
            peak_orders_per_second=9.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Should still have throughput metrics
        assert "orders_per_second" in result.metric_comparisons
        # Should not have order metrics
        assert "order_success_rate" not in result.metric_comparisons

    def test_compare_handles_missing_api_metrics(self) -> None:
        """Test comparison handles missing API metrics."""
        baseline = PerformanceBaseline(
            id="baseline",
            name="baseline",
            api_metrics=None,
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )
        current = PerformanceBaseline(
            id="current",
            name="current",
            api_metrics=None,
            orders_per_second=6.0,
            peak_orders_per_second=9.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Should not have API metrics
        assert "api_success_rate" not in result.metric_comparisons

    def test_compare_handles_different_resource_containers(self) -> None:
        """Test comparison handles different resource containers."""
        baseline = PerformanceBaseline(
            id="baseline",
            name="baseline",
            resource_metrics={
                "container-a": ResourceAggregateMetrics(
                    container_name="container-a",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=25.0, std_dev=5.0),
                ),
            },
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )
        current = PerformanceBaseline(
            id="current",
            name="current",
            resource_metrics={
                "container-b": ResourceAggregateMetrics(
                    container_name="container-b",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=30.0, std_dev=6.0),
                ),
            },
            orders_per_second=6.0,
            peak_orders_per_second=9.0,
        )

        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Should not have resource metrics for non-common containers
        assert "resource_container-a_cpu" not in result.metric_comparisons
        assert "resource_container-b_cpu" not in result.metric_comparisons

    def test_engine_thresholds_property(self) -> None:
        """Test that thresholds property returns correct value."""
        default_engine = ComparisonEngine()
        assert default_engine.thresholds.significance_level == 0.05

        custom_thresholds = RegressionThresholds(significance_level=0.01)
        custom_engine = ComparisonEngine(thresholds=custom_thresholds)
        assert custom_engine.thresholds.significance_level == 0.01
