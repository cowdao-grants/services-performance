"""Unit tests for recommendations engine."""

from datetime import datetime

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)
from cow_performance.reporting.models import (
    RecommendationCategory,
    RecommendationSeverity,
)
from cow_performance.reporting.recommendations import RecommendationsEngine


class TestRecommendationsEngine:
    """Tests for RecommendationsEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a recommendations engine."""
        return RecommendationsEngine()

    @pytest.fixture
    def healthy_baseline(self):
        """Create a baseline with healthy metrics."""
        return PerformanceBaseline(
            id="healthy",
            name="healthy-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=98,
                orders_failed=2,
                success_rate=0.98,
                time_to_submit=PercentileStats(count=100, p95=0.1),  # 100ms
                time_to_fill=PercentileStats(count=98, p95=2.0),  # 2s
                total_lifecycle=PercentileStats(count=98, p95=2.5),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                successful_requests=500,
                failed_requests=0,
                success_rate=1.0,
                response_time=PercentileStats(count=500, p95=50.0),
            ),
            orders_per_second=2.0,
            peak_orders_per_second=4.0,
        )

    def test_no_recommendations_for_healthy_baseline(self, engine, healthy_baseline):
        """Test that healthy baseline generates no recommendations."""
        recommendations = engine.analyze(healthy_baseline)
        assert len(recommendations) == 0

    def test_critical_submission_latency(self, engine):
        """Test critical submission latency recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="high-latency",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
                time_to_submit=PercentileStats(count=10, p95=3.0),  # 3000ms > 2000ms
                time_to_fill=PercentileStats(count=10, p95=2.0),
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        latency_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.LATENCY
            and r.severity == RecommendationSeverity.CRITICAL
        ]
        assert len(latency_recs) == 1
        assert "submission" in latency_recs[0].title.lower()
        assert latency_recs[0].metric_value == 3000.0

    def test_warning_submission_latency(self, engine):
        """Test warning submission latency recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="elevated-latency",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
                time_to_submit=PercentileStats(count=10, p95=0.8),  # 800ms > 500ms
                time_to_fill=PercentileStats(count=10, p95=2.0),
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        latency_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.LATENCY
            and r.severity == RecommendationSeverity.WARNING
        ]
        assert len(latency_recs) == 1
        assert "submission" in latency_recs[0].title.lower()

    def test_critical_fill_latency(self, engine):
        """Test critical fill latency recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="slow-fill",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
                time_to_submit=PercentileStats(count=10, p95=0.1),
                time_to_fill=PercentileStats(count=10, p95=20.0),  # 20000ms > 15000ms
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        latency_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.LATENCY and "fill" in r.title.lower()
        ]
        assert len(latency_recs) == 1
        assert latency_recs[0].severity == RecommendationSeverity.CRITICAL

    def test_critical_success_rate(self, engine):
        """Test critical success rate recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="low-success",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=70,
                orders_failed=30,
                success_rate=0.70,  # Below 80%
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        reliability_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.RELIABILITY
            and r.severity == RecommendationSeverity.CRITICAL
        ]
        assert len(reliability_recs) == 1
        assert "failure rate" in reliability_recs[0].title.lower()

    def test_warning_success_rate(self, engine):
        """Test warning success rate recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="moderate-success",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=90,
                orders_failed=10,
                success_rate=0.90,  # Between 80% and 95%
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        reliability_recs = [
            r for r in recommendations if r.category == RecommendationCategory.RELIABILITY
        ]
        assert len(reliability_recs) == 1
        assert reliability_recs[0].severity == RecommendationSeverity.WARNING

    def test_api_failure_recommendation(self, engine):
        """Test API failure recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="api-issues",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=100,
                successful_requests=95,
                failed_requests=5,
                success_rate=0.95,  # Below 99%
            ),
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        api_recs = [r for r in recommendations if "API" in r.title]
        assert len(api_recs) == 1
        assert api_recs[0].severity == RecommendationSeverity.WARNING

    def test_low_throughput_recommendation(self, engine):
        """Test low throughput recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="low-throughput",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            orders_per_second=0.1,  # Below 0.5
        )

        recommendations = engine.analyze(baseline)

        throughput_recs = [
            r for r in recommendations if r.category == RecommendationCategory.THROUGHPUT
        ]
        assert len(throughput_recs) == 1
        assert throughput_recs[0].severity == RecommendationSeverity.WARNING

    def test_resource_critical_cpu(self, engine):
        """Test critical CPU usage recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="high-cpu",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, p95=95.0),  # > 90%
                    memory_percent=PercentileStats(count=60, p95=50.0),
                ),
            },
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        resource_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.RESOURCE and "CPU" in r.title
        ]
        assert len(resource_recs) == 1
        assert resource_recs[0].severity == RecommendationSeverity.CRITICAL

    def test_resource_warning_memory(self, engine):
        """Test warning memory usage recommendation."""
        baseline = PerformanceBaseline(
            id="test",
            name="high-memory",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            resource_metrics={
                "solver": ResourceAggregateMetrics(
                    container_name="solver",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, p95=50.0),
                    memory_percent=PercentileStats(count=60, p95=75.0),  # > 70%
                ),
            },
            orders_per_second=1.0,
        )

        recommendations = engine.analyze(baseline)

        memory_recs = [
            r
            for r in recommendations
            if r.category == RecommendationCategory.RESOURCE and "memory" in r.title.lower()
        ]
        assert len(memory_recs) == 1
        assert memory_recs[0].severity == RecommendationSeverity.WARNING

    def test_recommendations_sorted_by_severity(self, engine):
        """Test that recommendations are sorted by severity."""
        baseline = PerformanceBaseline(
            id="test",
            name="multi-issue",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=70,
                orders_failed=30,
                success_rate=0.70,  # Critical reliability
                time_to_submit=PercentileStats(count=100, p95=0.8),  # Warning latency
            ),
            orders_per_second=0.1,  # Warning throughput
        )

        recommendations = engine.analyze(baseline)

        # Critical should come first
        assert len(recommendations) > 0
        assert recommendations[0].severity == RecommendationSeverity.CRITICAL

    def test_custom_thresholds(self):
        """Test using custom thresholds."""
        custom_engine = RecommendationsEngine(
            latency_thresholds={
                "submission_p95_warning_ms": 100,  # Stricter than default 500
                "submission_p95_critical_ms": 500,
                "fill_p95_warning_ms": 1000,
                "fill_p95_critical_ms": 3000,
            }
        )

        baseline = PerformanceBaseline(
            id="test",
            name="test",
            created_at=datetime.now().timestamp(),
            duration_seconds=60,
            order_metrics=OrderAggregateMetrics(
                total_orders=10,
                orders_submitted=10,
                orders_filled=10,
                success_rate=1.0,
                time_to_submit=PercentileStats(count=10, p95=0.2),  # 200ms > 100ms
            ),
            orders_per_second=1.0,
        )

        recommendations = custom_engine.analyze(baseline)

        # Should trigger warning with stricter threshold
        latency_recs = [r for r in recommendations if r.category == RecommendationCategory.LATENCY]
        assert len(latency_recs) == 1


class TestAnalyzeComparison:
    """Tests for analyze_comparison method."""

    @pytest.fixture
    def engine(self):
        """Create a recommendations engine."""
        return RecommendationsEngine()

    def test_analyze_comparison_with_regressions(self, engine):
        """Test generating recommendations from comparison with regressions."""
        from cow_performance.comparison.models import (
            ComparisonResult,
            ComparisonVerdict,
            MetricComparison,
            MetricType,
            RegressionSeverity,
        )

        comparison = ComparisonResult(
            baseline_id="baseline",
            baseline_name="v1.0",
            current_id="current",
            current_name="v2.0",
            verdict=ComparisonVerdict.REGRESSION,
        )

        # Add a critical regression
        regression = MetricComparison(
            metric_name="time_to_fill_p95",
            metric_type=MetricType.LATENCY,
            baseline_value=2000,
            current_value=4000,
            absolute_diff=2000,
            percent_change=1.0,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
            context="Fill latency increased by 100%",
        )
        comparison.add_comparison(regression)

        recommendations = engine.analyze_comparison(comparison)

        assert len(recommendations) == 1
        assert recommendations[0].severity == RecommendationSeverity.CRITICAL
        assert recommendations[0].category == RecommendationCategory.REGRESSION
        assert "time_to_fill_p95" in recommendations[0].title

    def test_analyze_comparison_maps_severity_correctly(self, engine):
        """Test that regression severity is mapped correctly."""
        from cow_performance.comparison.models import (
            ComparisonResult,
            ComparisonVerdict,
            MetricComparison,
            MetricType,
            RegressionSeverity,
        )

        comparison = ComparisonResult(
            baseline_id="baseline",
            baseline_name="v1.0",
            current_id="current",
            current_name="v2.0",
            verdict=ComparisonVerdict.REGRESSION,
        )

        # Add regressions of different severities
        for severity in [
            RegressionSeverity.CRITICAL,
            RegressionSeverity.MAJOR,
            RegressionSeverity.MINOR,
        ]:
            regression = MetricComparison(
                metric_name=f"metric_{severity.value}",
                metric_type=MetricType.LATENCY,
                baseline_value=100,
                current_value=150,
                absolute_diff=50,
                percent_change=0.5,
                is_significant=True,
                regression_severity=severity,
                context=f"Regression: {severity.value}",
            )
            comparison.add_comparison(regression)

        recommendations = engine.analyze_comparison(comparison)

        assert len(recommendations) == 3

        # Check severity mapping
        severities = {r.metric_name: r.severity for r in recommendations}
        assert severities["metric_critical"] == RecommendationSeverity.CRITICAL
        assert severities["metric_major"] == RecommendationSeverity.WARNING
        assert severities["metric_minor"] == RecommendationSeverity.INFO
